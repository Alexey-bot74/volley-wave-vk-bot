import os
import sqlite3
from datetime import datetime, timedelta

import requests
from flask import Flask, request


# ============================================================
# НАСТРОЙКИ
# ============================================================

VK_TOKEN = os.getenv("VK_TOKEN")
VK_SECRET_KEY = os.getenv("VK_SECRET_KEY")
VK_CONFIRMATION_TOKEN = os.getenv("VK_CONFIRMATION_TOKEN")

VK_API_VERSION = "5.199"

ADMIN_IDS = {
    87984447,
    172892670,
    148372158,
}

DB_FILE = "volley_wave.db"

app = Flask(__name__)


# ============================================================
# БАЗА ДАННЫХ
# ============================================================

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS trainings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day_of_week INTEGER NOT NULL,
            start_time TEXT NOT NULL,
            duration INTEGER NOT NULL DEFAULT 90,
            category TEXT NOT NULL,
            format TEXT NOT NULL DEFAULT '',
            level TEXT NOT NULL DEFAULT '',
            trainer TEXT NOT NULL DEFAULT '',
            capacity INTEGER NOT NULL DEFAULT 10,
            price INTEGER NOT NULL DEFAULT 1200,
            active INTEGER NOT NULL DEFAULT 1
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            training_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL DEFAULT '',
            phone TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY(training_id) REFERENCES trainings(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL DEFAULT '',
            phone TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL
        )
    """)

    conn.commit()

    # --------------------------------------------------------
    # Миграция старой базы
    # --------------------------------------------------------

    columns = {
        row["name"]
        for row in cur.execute("PRAGMA table_info(trainings)").fetchall()
    }

    migrations = {
        "category": "ALTER TABLE trainings ADD COLUMN category TEXT NOT NULL DEFAULT 'Взрослые'",
        "format": "ALTER TABLE trainings ADD COLUMN format TEXT NOT NULL DEFAULT ''",
        "level": "ALTER TABLE trainings ADD COLUMN level TEXT NOT NULL DEFAULT ''",
        "trainer": "ALTER TABLE trainings ADD COLUMN trainer TEXT NOT NULL DEFAULT ''",
        "capacity": "ALTER TABLE trainings ADD COLUMN capacity INTEGER NOT NULL DEFAULT 10",
        "price": "ALTER TABLE trainings ADD COLUMN price INTEGER NOT NULL DEFAULT 1200",
        "active": "ALTER TABLE trainings ADD COLUMN active INTEGER NOT NULL DEFAULT 1",
    }

    for column, sql in migrations.items():
        if column not in columns:
            try:
                cur.execute(sql)
            except sqlite3.OperationalError:
                pass

    conn.commit()

    # --------------------------------------------------------
    # Если расписание пустое — создаём базовое
    # --------------------------------------------------------

    count = cur.execute(
        "SELECT COUNT(*) FROM trainings WHERE active = 1"
    ).fetchone()[0]

    if count == 0:
        create_default_schedule(conn)

    conn.commit()
    conn.close()


def create_default_schedule(conn):
    trainings = [
        # day, time, duration, category, format, level, trainer, capacity, price

        # ПОНЕДЕЛЬНИК
        (0, "09:00", 120, "Дети", "Групповая тренировка", "9–13 лет", "—", 10, 600),
        (0, "17:00", 120, "Дети", "Групповая тренировка", "11–14 лет", "—", 10, 600),
        (0, "19:00", 90, "Взрослые", "Техничка", "Любой уровень", "—", 10, 1200),

        # ВТОРНИК
        (1, "09:00", 120, "Взрослые", "Групповая тренировка", "Любой уровень", "—", 8, 1200),
        (1, "17:00", 90, "Дети", "Групповая тренировка", "11–14 лет", "—", 10, 600),
        (1, "19:30", 90, "Взрослые", "Групповая тренировка", "Женщины, средний+", "—", 8, 1200),

        # СРЕДА
        (2, "09:00", 120, "Дети", "Групповая тренировка", "9–14 лет", "—", 10, 600),
        (2, "17:00", 60, "Дети", "Групповая тренировка", "5–9 лет", "—", 10, 600),
        (2, "18:00", 90, "Взрослые", "Групповая тренировка", "Продвинутый", "—", 8, 1200),
        (2, "19:30", 90, "Взрослые", "MIXED", "Средний+", "—", 8, 1200),

        # ЧЕТВЕРГ
        (3, "09:00", 120, "Взрослые", "Групповая тренировка", "Любой уровень", "—", 8, 1200),
        (3, "17:00", 120, "Дети", "Групповая тренировка", "11–14 лет", "—", 10, 600),
        (3, "19:00", 90, "Взрослые", "Групповая тренировка", "Средний", "—", 8, 1200),

        # ПЯТНИЦА
        (4, "09:00", 120, "Дети", "Групповая тренировка", "9–14 лет", "—", 10, 600),
        (4, "17:00", 60, "Дети", "Групповая тренировка", "5–10 лет", "—", 10, 600),
        (4, "17:00", 120, "Дети", "Групповая тренировка", "11–14 лет", "—", 10, 600),
        (4, "19:00", 90, "Взрослые", "Техничка", "Любой уровень", "—", 10, 1200),
    ]

    conn.executemany("""
        INSERT INTO trainings
        (day_of_week, start_time, duration, category, format, level, trainer, capacity, price)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, trainings)


init_db()


# ============================================================
# VK API
# ============================================================

def vk_api(method, params=None):
    if params is None:
        params = {}

    params["access_token"] = VK_TOKEN
    params["v"] = VK_API_VERSION

    try:
        response = requests.post(
            f"https://api.vk.com/method/{method}",
            data=params,
            timeout=15
        )

        data = response.json()

        if "error" in data:
            print("VK API ERROR:", data["error"])

        return data

    except Exception as e:
        print("VK REQUEST ERROR:", e)
        return None


def send_message(user_id, message, keyboard=None):
    params = {
        "user_id": user_id,
        "random_id": int(datetime.now().timestamp() * 1000) % 2147483647,
        "message": message,
    }

    if keyboard is not None:
        params["keyboard"] = keyboard

    return vk_api("messages.send", params)


def get_user_name(user_id):
    result = vk_api("users.get", {
        "user_ids": user_id,
        "fields": "first_name,last_name"
    })

    try:
        user = result["response"][0]
        return f'{user.get("first_name", "")} {user.get("last_name", "")}'.strip()
    except Exception:
        return ""


# ============================================================
# КЛАВИАТУРЫ
# ============================================================

def button(label, color="secondary"):
    return {
        "action": {
            "type": "text",
            "label": label
        },
        "color": color
    }


def keyboard(rows):
    return {
        "one_time": False,
        "inline": False,
        "buttons": rows
    }


def main_keyboard(user_id=None):
    rows = [
        [
            button("🏐 Записаться", "primary"),
            button("📅 Расписание", "primary"),
        ],
        [
            button("👤 Мои тренировки", "secondary"),
            button("💰 Цены", "secondary"),
        ],
        [
            button("📍 Где тренируемся", "secondary"),
            button("🎯 Индивидуальная тренировка", "secondary"),
        ],
        [
            button("❓ Задать вопрос", "secondary"),
    ]

    if user_id in ADMIN_IDS:
        rows.append([
            button("⚙️ Админ-панель", "positive")
        ])

    return keyboard(rows)


def admin_keyboard():
    return keyboard([
        [
            button("📅 Управление расписанием", "primary"),
            button("📝 Записи", "primary"),
        ],
        [
            button("➕ Добавить тренировку", "positive"),
            button("📊 Статистика", "secondary"),
        ],
        [
            button("👤 Режим пользователя", "secondary"),
        ],
        [
            button("⬅️ Главное меню", "secondary"),
        ]
    ])


def user_mode_keyboard():
    return main_keyboard()


def back_keyboard():
    return keyboard([
        [
            button("⬅️ Назад", "secondary")
        ]
    ])


def category_keyboard():
    return keyboard([
        [
            button("👨 Взрослые", "primary"),
            button("👶 Дети", "primary"),
        ],
        [
            button("⬅️ Назад", "secondary")
        ]
    ])


def admin_category_keyboard():
    return keyboard([
        [
            button("👨 Взрослые", "primary"),
            button("👶 Дети", "primary"),
        ],
        [
            button("⬅️ Назад", "secondary")
        ]
    ])


# ============================================================
# ДНИ НЕДЕЛИ
# ============================================================

DAYS = {
    0: "Понедельник",
    1: "Вторник",
    2: "Среда",
    3: "Четверг",
    4: "Пятница",
    5: "Суббота",
    6: "Воскресенье",
}


def day_name(day):
    return DAYS.get(day, "")


# ============================================================
# СОСТОЯНИЯ
# ============================================================

user_states = {}


def set_state(user_id, state, data=None):
    user_states[user_id] = {
        "state": state,
        "data": data or {}
    }


def get_state(user_id):
    return user_states.get(user_id)


def clear_state(user_id):
    user_states.pop(user_id, None)


# ============================================================
# РЕЖИМ АДМИНИСТРАТОРА
# ============================================================

admin_modes = {}


def is_admin(user_id):
    return user_id in ADMIN_IDS


def is_admin_mode(user_id):
    return is_admin(user_id) and admin_modes.get(user_id, True)


# ============================================================
# РАСПИСАНИЕ
# ============================================================

def get_trainings(category=None, day=None):
    conn = get_db()

    query = """
        SELECT *
        FROM trainings
        WHERE active = 1
    """

    params = []

    if category:
        query += " AND category = ?"
        params.append(category)

    if day is not None:
        query += " AND day_of_week = ?"
        params.append(day)

    query += " ORDER BY day_of_week, start_time"

    rows = conn.execute(query, params).fetchall()
    conn.close()

    return rows


def get_training(training_id):
    conn = get_db()

    row = conn.execute(
        "SELECT * FROM trainings WHERE id = ? AND active = 1",
        (training_id,)
    ).fetchone()

    conn.close()

    return row


def get_registration_count(training_id):
    conn = get_db()

    count = conn.execute(
        "SELECT COUNT(*) FROM registrations WHERE training_id = ?",
        (training_id,)
    ).fetchone()[0]

    conn.close()

    return count


def is_registered(training_id, user_id):
    conn = get_db()

    row = conn.execute("""
        SELECT id
        FROM registrations
        WHERE training_id = ? AND user_id = ?
    """, (training_id, user_id)).fetchone()

    conn.close()

    return row is not None


def adult_price(count):
    if count >= 7:
        return 1000

    return 1200


def current_training_price(training, count):
    if training["category"] == "Дети":
        return 600

    return adult_price(count)


# ============================================================
# ФОРМАТ ТРЕНИРОВКИ
# ============================================================

def training_short_text(training):
    count = get_registration_count(training["id"])
    price = current_training_price(training, count)

    free = max(training["capacity"] - count, 0)

    return (
        f'{training["start_time"]} — {training["format"]}\n'
        f'Уровень: {training["level"]}\n'
        f'Мест: {free}/{training["capacity"]}\n'
        f'Цена: {price} ₽'
    )


def training_full_text(training):
    count = get_registration_count(training["id"])
    price = current_training_price(training, count)

    free = max(training["capacity"] - count, 0)

    text = (
        f'🏐 {day_name(training["day_of_week"])}\n'
        f'⏰ {training["start_time"]}\n\n'
        f'Формат: {training["format"]}\n'
        f'Уровень: {training["level"]}\n'
        f'Тренер: {training["trainer"] or "—"}\n\n'
        f'👥 Записано: {count}/{training["capacity"]}\n'
        f'Свободно: {free}\n'
        f'💰 Стоимость: {price} ₽'
    )

    if training["category"] == "Взрослые":
        text += (
            "\n\n"
            "Стоимость зависит от количества участников:\n"
            "1–6 человек — 1200 ₽\n"
            "7 и более — 1000 ₽"
        )

    return text


# ============================================================
# КНОПКИ ТРЕНИРОВОК
# ============================================================

def training_buttons(trainings, include_back=True):
    rows = []

    for training in trainings:
        count = get_registration_count(training["id"])
        price = current_training_price(training, count)

        label = (
            f'{day_name(training["day_of_week"])[:2]} '
            f'{training["start_time"]} '
            f'{training["format"][:18]}'
        )

        rows.append([
            button(label, "primary")
        ])

    if include_back:
        rows.append([
            button("⬅️ Назад", "secondary")
        ])

    return keyboard(rows)


# ============================================================
# РАСПИСАНИЕ НА НЕДЕЛЮ
# ============================================================

def weekly_schedule_text(category):
    trainings = get_trainings(category)

    if not trainings:
        return f"📅 Расписание: {category}\n\nПока тренировок нет."

    text = f"📅 Расписание — {category}\n\n"

    current_day = None

    for training in trainings:
        if training["day_of_week"] != current_day:
            current_day = training["day_of_week"]
            text += f'━━ {day_name(current_day)} ━━\n'

        count = get_registration_count(training["id"])
        price = current_training_price(training, count)

        text += (
            f'⏰ {training["start_time"]}\n'
            f'Формат: {training["format"]}\n'
            f'Уровень: {training["level"]}\n'
            f'Тренер: {training["trainer"] or "—"}\n'
            f'👥 {count}/{training["capacity"]}\n'
            f'💰 {price} ₽\n\n'
        )

    return text


def weekly_schedule_keyboard(category):
    trainings = get_trainings(category)

    rows = []

    for training in trainings:
        rows.append([
            button(
                f'{day_name(training["day_of_week"])[:2]} '
                f'{training["start_time"]} — '
                f'{training["format"][:15]}',
                "primary"
            )
        ])

    rows.append([
        button("⬅️ Назад", "secondary")
    ])

    return keyboard(rows)


# ============================================================
# МИНИМАЛЬНАЯ ДАТА ТРЕНИРОВКИ
# ============================================================

def next_training_datetime(training):
    now = datetime.now()

    target_day = training["day_of_week"]

    days_ahead = (target_day - now.weekday()) % 7

    if days_ahead == 0:
        candidate = datetime.strptime(
            now.strftime("%Y-%m-%d") + " " + training["start_time"],
            "%Y-%m-%d %H:%M"
        )

        if candidate <= now:
            days_ahead = 7

    date = now + timedelta(days=days_ahead)

    return datetime.strptime(
        date.strftime("%Y-%m-%d") + " " + training["start_time"],
        "%Y-%m-%d %H:%M"
    )


# ============================================================
# ОТМЕНА
# ============================================================

def can_cancel(training):
    start = next_training_datetime(training)
    return datetime.now() <= start - timedelta(hours=24)


def cancel_registration(training_id, user_id):
    conn = get_db()

    conn.execute("""
        DELETE FROM registrations
        WHERE training_id = ? AND user_id = ?
    """, (training_id, user_id))

    conn.commit()
    conn.close()


# ============================================================
# ДОБАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯ
# ============================================================

def save_user(user_id, name="", phone=""):
    conn = get_db()

    existing = conn.execute(
        "SELECT user_id FROM users WHERE user_id = ?",
        (user_id,)
    ).fetchone()

    now = datetime.now().isoformat()

    if existing:
        conn.execute("""
            UPDATE users
            SET name = ?, phone = ?, updated_at = ?
            WHERE user_id = ?
        """, (name, phone, now, user_id))
    else:
        conn.execute("""
            INSERT INTO users
            (user_id, name, phone, updated_at)
            VALUES (?, ?, ?, ?)
        """, (user_id, name, phone, now))

    conn.commit()
    conn.close()


# ============================================================
# ЗАПИСЬ
# ============================================================

def register_user(user_id, training_id, name, phone):
    conn = get_db()

    existing = conn.execute("""
        SELECT id
        FROM registrations
        WHERE training_id = ? AND user_id = ?
    """, (training_id, user_id)).fetchone()

    if existing:
        conn.close()
        return False, "Вы уже записаны на эту тренировку."

    training = conn.execute("""
        SELECT *
        FROM trainings
        WHERE id = ? AND active = 1
    """, (training_id,)).fetchone()

    if not training:
        conn.close()
        return False, "Тренировка не найдена."

    count = conn.execute("""
        SELECT COUNT(*)
        FROM registrations
        WHERE training_id = ?
    """, (training_id,)).fetchone()[0]

    if count >= training["capacity"]:
        conn.close()
        return False, "На тренировке больше нет свободных мест."

    conn.execute("""
        INSERT INTO registrations
        (training_id, user_id, name, phone, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (
        training_id,
        user_id,
        name,
        phone,
        datetime.now().isoformat()
    ))

    conn.commit()
    conn.close()

    save_user(user_id, name, phone)

    return True, "Вы успешно записаны."


# ============================================================
# МОИ ТРЕНИРОВКИ
# ============================================================

def my_trainings(user_id):
    conn = get_db()

    rows = conn.execute("""
        SELECT
            r.id AS registration_id,
            t.*
        FROM registrations r
        JOIN trainings t ON t.id = r.training_id
        WHERE r.user_id = ?
        ORDER BY t.day_of_week, t.start_time
    """, (user_id,)).fetchall()

    conn.close()

    return rows


# ============================================================
# ЦЕНЫ
# ============================================================

def prices_text():
    return (
        "💰 Цены\n\n"
        "👶 Детские тренировки — 600 ₽\n\n"
        "🏐 Взрослые тренировки:\n"
        "• 1–6 человек — 1200 ₽/чел.\n"
        "• 7 и более человек — 1000 ₽/чел.\n\n"
        "👥 Минимальный набор на взрослую тренировку — 4 человека.\n\n"
        "Цена для взрослых зависит от количества участников "
        "в конкретной тренировке."
    )


# ============================================================
# ГДЕ ТРЕНИРУЕМСЯ
# ============================================================

def location_text():
    return (
        "📍 Где тренируемся\n\n"
        "☀️ Летом:\n"
        "Парк Гагарина\n\n"
        "❄️ Зимой:\n"
        "СК «Арена»\n"
        "Молодогвардейцев, 7"
    )


# ============================================================
# АДМИНЫ
# ============================================================

def notify_admins(message):
    for admin_id in ADMIN_IDS:
        send_message(admin_id, message)


# ============================================================
# АДМИН — СПИСОК ТРЕНИРОВОК
# ============================================================

def admin_schedule_text():
    trainings = get_trainings()

    if not trainings:
        return "📅 Расписание пустое."

    text = "📅 Управление расписанием\n\n"

    current_day = None

    for training in trainings:
        if training["day_of_week"] != current_day:
            current_day = training["day_of_week"]
            text += f"\n━━ {day_name(current_day)} ━━\n"

        count = get_registration_count(training["id"])

        text += (
            f'ID {training["id"]}\n'
            f'⏰ {training["start_time"]}\n'
            f'Категория: {training["category"]}\n'
            f'Формат: {training["format"]}\n'
            f'Уровень: {training["level"]}\n'
            f'Тренер: {training["trainer"] or "—"}\n'
            f'👥 {count}/{training["capacity"]}\n'
            f'💰 {current_training_price(training, count)} ₽\n\n'
        )

    return text


def admin_training_buttons():
    trainings = get_trainings()

    rows = []

    for training in trainings:
        rows.append([
            button(
                f'✏️ {training["id"]} | '
                f'{day_name(training["day_of_week"])[:2]} '
                f'{training["start_time"]}',
                "primary"
            )
        ])

    rows.append([
        button("➕ Добавить тренировку", "positive")
    ])

    rows.append([
        button("⬅️ Админ-панель", "secondary")
    ])

    return keyboard(rows)


# ============================================================
# АДМИН — ЗАПИСИ
# ============================================================

def admin_registrations_text():
    trainings = get_trainings()

    text = "📝 Записи на тренировки\n\n"

    has_any = False

    for training in trainings:
        count = get_registration_count(training["id"])

        if count == 0:
            continue

        has_any = True

        text += (
            f'🏐 {day_name(training["day_of_week"])} '
            f'{training["start_time"]}\n'
            f'{training["format"]} | {training["level"]}\n'
        )

        conn = get_db()

        users = conn.execute("""
            SELECT name, phone, user_id
            FROM registrations
            WHERE training_id = ?
            ORDER BY id
        """, (training["id"],)).fetchall()

        conn.close()

        for index, user in enumerate(users, 1):
            name = user["name"] or "Без имени"
            phone = user["phone"] or "Телефон не указан"

            text += (
                f'{index}. {name}\n'
                f'   📱 {phone}\n'
            )

        text += "\n"

    if not has_any:
        text += "Пока ни на одну тренировку никто не записан."

    return text


# ============================================================
# АДМИН — СТАТИСТИКА
# ============================================================

def statistics_text():
    conn = get_db()

    users = conn.execute(
        "SELECT COUNT(*) FROM users"
    ).fetchone()[0]

    registrations = conn.execute(
        "SELECT COUNT(*) FROM registrations"
    ).fetchone()[0]

    trainings = conn.execute(
        "SELECT COUNT(*) FROM trainings WHERE active = 1"
    ).fetchone()[0]

    questions = conn.execute(
        "SELECT COUNT(*) FROM questions"
    ).fetchone()[0]

    conn.close()

    return (
        "📊 Статистика\n\n"
        f"👤 Пользователей: {users}\n"
        f"🏐 Активных тренировок: {trainings}\n"
        f"📝 Записей: {registrations}\n"
        f"❓ Вопросов: {questions}"
    )


# ============================================================
# АДМИН — ДОБАВЛЕНИЕ
# ============================================================

def start_add_training(user_id):
    set_state(user_id, "admin_add_category")

    send_message(
        user_id,
        "➕ Добавление тренировки\n\n"
        "Выберите категорию:",
        admin_category_keyboard()
    )


def admin_add_next(user_id, field, prompt, next_state, data_update=None):
    state = get_state(user_id)

    if state is None:
        return

    if data_update:
        state["data"].update(data_update)

    state["state"] = next_state
    user_states[user_id] = state

    send_message(user_id, prompt, back_keyboard())


def start_admin_add_day(user_id, category):
    set_state(
        user_id,
        "admin_add_day",
        {
            "category": category
        }
    )

    rows = []

    for number, name in DAYS.items():
        rows.append([
            button(name, "primary")
        ])

    rows.append([
        button("⬅️ Назад", "secondary")
    ])

    send_message(
        user_id,
        "Выберите день недели:",
        keyboard(rows)
    )


def start_admin_add_format(user_id):
    set_state(
        user_id,
        "admin_add_format",
        get_state(user_id)["data"]
    )

    send_message(
        user_id,
        "Введите формат тренировки.\n\n"
        "Например:\n"
        "• Групповая тренировка\n"
        "• Техничка\n"
        "• MIXED\n"
        "• Индивидуальная",
        back_keyboard()
    )


def start_admin_add_level(user_id):
    set_state(
        user_id,
        "admin_add_level",
        get_state(user_id)["data"]
    )

    send_message(
        user_id,
        "Введите уровень / группу.\n\n"
        "Например:\n"
        "• Любой уровень\n"
        "• Средний+\n"
        "• Продвинутый\n"
        "• 11–14 лет",
        back_keyboard()
    )


def start_admin_add_trainer(user_id):
    set_state(
        user_id,
        "admin_add_trainer",
        get_state(user_id)["data"]
    )

    send_message(
        user_id,
        "Введите имя тренера:",
        back_keyboard()
    )


def start_admin_add_capacity(user_id):
    set_state(
        user_id,
        "admin_add_capacity",
        get_state(user_id)["data"]
    )

    send_message(
        user_id,
        "Введите количество мест:",
        back_keyboard()
    )


def save_new_training(user_id):
    state = get_state(user_id)

    if not state:
        return

    data = state["data"]

    category = data["category"]

    price = 600 if category == "Дети" else 1200

    conn = get_db()

    conn.execute("""
        INSERT INTO trainings
        (
            day_of_week,
            start_time,
            duration,
            category,
            format,
            level,
            trainer,
            capacity,
            price
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data["day"],
        data["time"],
        data["duration"],
        category,
        data["format"],
        data["level"],
        data["trainer"],
        data["capacity"],
        price
    ))

    conn.commit()
    conn.close()

    clear_state(user_id)

    send_message(
        user_id,
        "✅ Тренировка успешно добавлена.",
        admin_keyboard()
    )


# ============================================================
# АДМИН — РЕДАКТИРОВАНИЕ
# ============================================================

def start_edit_training(user_id, training_id):
    training = get_training(training_id)

    if not training:
        send_message(
            user_id,
            "Тренировка не найдена.",
            admin_schedule_buttons()
        )
        return

    set_state(
        user_id,
        "admin_edit_menu",
        {
            "training_id": training_id
        }
    )

    send_message(
        user_id,
        training_full_text(training) +
        "\n\nЧто изменить?",
        keyboard([
            [button("⏰ Время", "primary")],
            [button("📅 День", "primary")],
            [button("📋 Формат", "primary")],
            [button("🎯 Уровень", "primary")],
            [button("👨‍🏫 Тренер", "primary")],
            [button("👥 Количество мест", "primary")],
            [button("🗑 Удалить", "negative")],
            [button("⬅️ Назад", "secondary")]
        ])
    )


def admin_schedule_buttons():
    return admin_training_buttons()


def delete_training(user_id, training_id):
    conn = get_db()

    conn.execute("""
        UPDATE trainings
        SET active = 0
        WHERE id = ?
    """, (training_id,))

    conn.commit()
    conn.close()

    clear_state(user_id)

    send_message(
        user_id,
        "🗑 Тренировка удалена.",
        admin_keyboard()
    )


# ============================================================
# ИНДИВИДУАЛЬНАЯ ТРЕНИРОВКА
# ============================================================

def start_individual(user_id):
    set_state(user_id, "individual_question")

    send_message(
        user_id,
        "🎯 Индивидуальная тренировка\n\n"
        "Напишите, пожалуйста, что вам нужно:\n"
        "• желаемый день и время;\n"
        "• ваш уровень;\n"
        "• сколько человек будет тренироваться;\n"
        "• другие пожелания.\n\n"
        "Администратор свяжется с вами для подбора времени.",
        back_keyboard()
    )


def save_question(user_id, text):
    conn = get_db()

    conn.execute("""
        INSERT INTO questions
        (user_id, text, created_at)
        VALUES (?, ?, ?)
    """, (
        user_id,
        text,
        datetime.now().isoformat()
    ))

    conn.commit()
    conn.close()

    name = get_user_name(user_id)

    notify_admins(
        "🎯 Новая заявка на индивидуальную тренировку\n\n"
        f"👤 {name or 'Имя не определено'}\n"
        f"VK ID: {user_id}\n\n"
        f"{text}"
    )


# ============================================================
# ВОПРОС
# ============================================================

def start_question(user_id):
    set_state(user_id, "question")

    send_message(
        user_id,
        "❓ Напишите ваш вопрос.\n\n"
        "Сообщение будет передано администратору.",
        back_keyboard()
    )


# ============================================================
# РЕГИСТРАЦИЯ — ВЫБОР ДНЯ
# ============================================================

def start_booking(user_id):
    clear_state(user_id)

    send_message(
        user_id,
        "🏐 На какую категорию хотите записаться?",
        category_keyboard()
    )


def show_booking_days(user_id, category):
    set_state(
        user_id,
        "booking_day",
        {
            "category": category
        }
    )

    trainings = get_trainings(category)

    if not trainings:
        send_message(
            user_id,
            "Для этой категории сейчас нет тренировок.",
            back_keyboard()
        )
        return

    days = sorted(set(t["day_of_week"] for t in trainings))

    rows = []

    for day in days:
        rows.append([
            button(day_name(day), "primary")
        ])

    rows.append([
        button("⬅️ Назад", "secondary")
    ])

    send_message(
        user_id,
        f"🏐 {category}\n\nВыберите день:",
        keyboard(rows)
    )


def show_booking_trainings(user_id, category, day):
    trainings = get_trainings(category, day)

    if not trainings:
        send_message(
            user_id,
            "В этот день тренировок нет.",
            back_keyboard()
        )
        return

    set_state(
        user_id,
        "booking_training",
        {
            "category": category,
            "day": day
        }
    )

    rows = []

    for training in trainings:
        count = get_registration_count(training["id"])
        price = current_training_price(training, count)

        label = (
            f'{training["start_time"]} | '
            f'{training["format"][:15]} | '
            f'{training["level"][:15]}'
        )

        rows.append([
            button(label, "primary")
        ])

    rows.append([
        button("⬅️ Назад", "secondary")
    ])

    send_message(
        user_id,
        f"🏐 {day_name(day)}\n\n"
        "Выберите тренировку:",
        keyboard(rows)
    )


# ============================================================
# РЕГИСТРАЦИЯ — ВЫБОР КОНКРЕТНОЙ ТРЕНИРОВКИ
# ============================================================

def training_from_state_selection(user_id, text):
    state = get_state(user_id)

    if not state:
        return None

    category = state["data"].get("category")
    day = state["data"].get("day")

    trainings = get_trainings(category, day)

    # Сопоставляем по времени / тексту кнопки
    for training in trainings:
        if training["start_time"] in text:
            return training

    return None


def show_training_for_booking(user_id, training):
    set_state(
        user_id,
        "training_info",
        {
            "training_id": training["id"]
        }
    )

    count = get_registration_count(training["id"])

    rows = []

    if is_registered(training["id"], user_id):
        rows.append([
            button("❌ Отменить запись", "negative")
        ])
    else:
        if count < training["capacity"]:
            rows.append([
                button("✅ Записаться", "positive")
            ])
        else:
            rows.append([
                button("Мест нет", "secondary")
            ])

    # --------------------------------------------------------
    # Список участников
    # --------------------------------------------------------

    conn = get_db()

    participants = conn.execute("""
        SELECT name
        FROM registrations
        WHERE training_id = ?
        ORDER BY id
    """, (training["id"],)).fetchall()

    conn.close()

    if participants:
        participant_text = "\n\n👥 Уже записаны:\n"

        for index, participant in enumerate(participants, 1):
            name = participant["name"] or "Участник"
            participant_text += f"{index}. {name}"
    else:
        participant_text = "\n\n👥 Пока никто не записан."

    send_message(
        user_id,
        training_full_text(training) + participant_text,
        keyboard(
            rows + [
                [button("⬅️ Назад", "secondary")]
            ]
        )
    )


# ============================================================
# ЗАПРОС ИМЕНИ
# ============================================================

def start_registration_name(user_id, training_id):
    set_state(
        user_id,
        "registration_name",
        {
            "training_id": training_id
        }
    )

    send_message(
        user_id,
        "Введите ваше имя и фамилию:",
        back_keyboard()
    )


def start_registration_phone(user_id, name, training_id):
    set_state(
        user_id,
        "registration_phone",
        {
            "training_id": training_id,
            "name": name
        }
    )

    send_message(
        user_id,
        "Введите номер телефона:",
        back_keyboard()
    )


# ============================================================
# ГЛАВНОЕ МЕНЮ
# ============================================================

def show_main_menu(user_id):
    clear_state(user_id)

    if is_admin(user_id):
        mode_text = (
            "\n\n⚙️ Вы находитесь в режиме "
            + ("администратора." if is_admin_mode(user_id)
               else "пользователя.")
        )
    else:
        mode_text = ""

    send_message(
        user_id,
        "🏐 VOLLEY WAVE\n\n"
        "Добро пожаловать!\n"
        "Выберите нужный раздел:" +
        mode_text,
        admin_keyboard() if is_admin_mode(user_id)
        else main_keyboard(user_id)
    )


# ============================================================
# ОБРАБОТКА АДМИНСКИХ СОСТОЯНИЙ
# ============================================================

def handle_admin_state(user_id, text, state):
    state_name = state["state"]
    data = state["data"]

    # --------------------------------------------------------
    # Добавление
    # --------------------------------------------------------

    if state_name == "admin_add_category":
        if text == "👨 Взрослые":
            start_admin_add_day(user_id, "Взрослые")
            return True

        if text == "👶 Дети":
            start_admin_add_day(user_id, "Дети")
            return True

    if state_name == "admin_add_day":
        for number, name in DAYS.items():
            if text == name:
                data["day"] = number

                set_state(
                    user_id,
                    "admin_add_time",
                    data
                )

                send_message(
                    user_id,
                    "Введите время начала.\n\n"
                    "Например: 19:00",
                    back_keyboard()
                )

                return True

    if state_name == "admin_add_time":
        try:
            datetime.strptime(text, "%H:%M")

            data["time"] = text

            set_state(
                user_id,
                "admin_add_duration",
                data
            )

            send_message(
                user_id,
                "Введите продолжительность в минутах.\n\n"
                "Например: 90 или 120",
                back_keyboard()
            )

        except ValueError:
            send_message(
                user_id,
                "Неверный формат времени.\n"
                "Введите, например: 19:00",
                back_keyboard()
            )

        return True

    if state_name == "admin_add_duration":
        try:
            duration = int(text)

            if duration <= 0:
                raise ValueError

            data["duration"] = duration

            set_state(
                user_id,
                "admin_add_format",
                data
            )

            send_message(
                user_id,
                "Введите формат тренировки.",
                back_keyboard()
            )

        except ValueError:
            send_message(
                user_id,
                "Введите продолжительность числом.\n"
                "Например: 90",
                back_keyboard()
            )

        return True

    if state_name == "admin_add_format":
        if not text.strip():
            return True

        data["format"] = text.strip()

        set_state(
            user_id,
            "admin_add_level",
            data
        )

        send_message(
            user_id,
            "Введите уровень / возрастную группу.",
            back_keyboard()
        )

        return True

    if state_name == "admin_add_level":
        if not text.strip():
            return True

        data["level"] = text.strip()

        set_state(
            user_id,
            "admin_add_trainer",
            data
        )

        send_message(
            user_id,
            "Введите имя тренера.",
            back_keyboard()
        )

        return True

    if state_name == "admin_add_trainer":
        data["trainer"] = text.strip()

        set_state(
            user_id,
            "admin_add_capacity",
            data
        )

        send_message(
            user_id,
            "Введите количество мест:",
            back_keyboard()
        )

        return True

    if state_name == "admin_add_capacity":
        try:
            capacity = int(text)

            if capacity <= 0:
                raise ValueError

            data["capacity"] = capacity

            save_new_training(user_id)

        except ValueError:
            send_message(
                user_id,
                "Введите количество мест числом.",
                back_keyboard()
            )

        return True

    # --------------------------------------------------------
    # Редактирование
    # --------------------------------------------------------

    if state_name == "admin_edit_menu":

        if text == "⏰ Время":
            set_state(
                user_id,
                "admin_edit_time",
                data
            )

            send_message(
                user_id,
                "Введите новое время:",
                back_keyboard()
            )

            return True

        if text == "📅 День":
            set_state(
                user_id,
                "admin_edit_day",
                data
            )

            rows = []

            for number, name in DAYS.items():
                rows.append([
                    button(name, "primary")
                ])

            rows.append([
                button("⬅️ Назад", "secondary")
            ])

            send_message(
                user_id,
                "Выберите новый день:",
                keyboard(rows)
            )

            return True

        if text == "📋 Формат":
            set_state(
                user_id,
                "admin_edit_format",
                data
            )

            send_message(
                user_id,
                "Введите новый формат:",
                back_keyboard()
            )

            return True

        if text == "🎯 Уровень":
            set_state(
                user_id,
                "admin_edit_level",
                data
            )

            send_message(
                user_id,
                "Введите новый уровень:",
                back_keyboard()
            )

            return True

        if text == "👨‍🏫 Тренер":
            set_state(
                user_id,
                "admin_edit_trainer",
                data
            )

            send_message(
                user_id,
                "Введите имя тренера:",
                back_keyboard()
            )

            return True

        if text == "👥 Количество мест":
            set_state(
                user_id,
                "admin_edit_capacity",
                data
            )

            send_message(
                user_id,
                "Введите новое количество мест:",
                back_keyboard()
            )

            return True

        if text == "🗑 Удалить":
            delete_training(
                user_id,
                data["training_id"]
            )

            return True

    if state_name == "admin_edit_time":
        try:
            datetime.strptime(text, "%H:%M")

            conn = get_db()

            conn.execute("""
                UPDATE trainings
                SET start_time = ?
                WHERE id = ?
            """, (text, data["training_id"]))

            conn.commit()
            conn.close()

            clear_state(user_id)

            send_message(
                user_id,
                "✅ Время изменено.",
                admin_keyboard()
            )

        except ValueError:
            send_message(
                user_id,
                "Введите время в формате 19:00.",
                back_keyboard()
            )

        return True

    if state_name == "admin_edit_day":
        for number, name in DAYS.items():
            if text == name:
                conn = get_db()

                conn.execute("""
                    UPDATE trainings
                    SET day_of_week = ?
                    WHERE id = ?
                """, (number, data["training_id"]))

                conn.commit()
                conn.close()

                clear_state(user_id)

                send_message(
                    user_id,
                    "✅ День изменён.",
                    admin_keyboard()
                )

                return True

    if state_name == "admin_edit_format":
        conn = get_db()

        conn.execute("""
            UPDATE trainings
            SET format = ?
            WHERE id = ?
        """, (text, data["training_id"]))

        conn.commit()
        conn.close()

        clear_state(user_id)

        send_message(
            user_id,
            "✅ Формат изменён.",
            admin_keyboard()
        )

        return True

    if state_name == "admin_edit_level":
        conn = get_db()

        conn.execute("""
            UPDATE trainings
            SET level = ?
            WHERE id = ?
        """, (text, data["training_id"]))

        conn.commit()
        conn.close()

        clear_state(user_id)

        send_message(
            user_id,
            "✅ Уровень изменён.",
            admin_keyboard()
        )

        return True

    if state_name == "admin_edit_trainer":
        conn = get_db()

        conn.execute("""
            UPDATE trainings
            SET trainer = ?
            WHERE id = ?
        """, (text, data["training_id"]))

        conn.commit()
        conn.close()

        clear_state(user_id)

        send_message(
            user_id,
            "✅ Тренер изменён.",
            admin_keyboard()
        )

        return True

    if state_name == "admin_edit_capacity":
        try:
            capacity = int(text)

            if capacity <= 0:
                raise ValueError

            conn = get_db()

            conn.execute("""
                UPDATE trainings
                SET capacity = ?
                WHERE id = ?
            """, (capacity, data["training_id"]))

            conn.commit()
            conn.close()

            clear_state(user_id)

            send_message(
                user_id,
                "✅ Количество мест изменено.",
                admin_keyboard()
            )

        except ValueError:
            send_message(
                user_id,
                "Введите количество мест числом.",
                back_keyboard()
            )

        return True

    return False


# ============================================================
# ОСНОВНАЯ ОБРАБОТКА СООБЩЕНИЙ
# ============================================================

def handle_message(user_id, text):

    text = text.strip()

    # --------------------------------------------------------
    # Назад
    # --------------------------------------------------------

    if text == "⬅️ Назад":

        state = get_state(user_id)

        if state:
            state_name = state["state"]

            # Добавление тренировки
            if state_name.startswith("admin_add_"):
                clear_state(user_id)
                send_message(
                    user_id,
                    "Возврат в админ-панель.",
                    admin_keyboard()
                )
                return

            # Редактирование
            if state_name.startswith("admin_edit_"):
                training_id = state["data"].get("training_id")

                if training_id:
                    start_edit_training(user_id, training_id)
                else:
                    clear_state(user_id)
                    send_message(
                        user_id,
                        "Возврат в админ-панель.",
                        admin_keyboard()
                    )

                return

            # Запись
            if state_name in {
                "booking_day",
                "booking_training",
                "training_info",
                "registration_name",
                "registration_phone"
            }:
                clear_state(user_id)
                start_booking(user_id)
                return

            # Индивидуальная
            if state_name == "individual_question":
                show_main_menu(user_id)
                return

            # Вопрос
            if state_name == "question":
                show_main_menu(user_id)
                return

        show_main_menu(user_id)
        return

    # --------------------------------------------------------
    # Приветствие
    # --------------------------------------------------------

    if text.lower() in {
        "привет",
        "начать",
        "старт",
        "/start"
    }:
        show_main_menu(user_id)
        return

    # --------------------------------------------------------
    # Режим пользователя
    # --------------------------------------------------------

    if is_admin(user_id) and text == "👤 Режим пользователя":
        admin_modes[user_id] = False
        clear_state(user_id)

        send_message(
            user_id,
            "👤 Включён режим обычного пользователя.\n\n"
            "Теперь ты видишь бота так, как его видит клиент.",
            main_keyboard(user_id)
        )

        return

    # --------------------------------------------------------
    # Админ-панель
    # --------------------------------------------------------

    if is_admin(user_id) and text == "⚙️ Админ-панель":
        admin_modes[user_id] = True
        clear_state(user_id)

        send_message(
            user_id,
            "⚙️ Админ-панель",
            admin_keyboard()
        )

        return

    # --------------------------------------------------------
    # Если админ в админском режиме
    # --------------------------------------------------------

    if is_admin_mode(user_id):

        state = get_state(user_id)

        if state and state["state"].startswith("admin_"):
            if handle_admin_state(user_id, text, state):
                return

        if text == "📅 Управление расписанием":
            clear_state(user_id)

            send_message(
                user_id,
                admin_schedule_text(),
                admin_schedule_buttons()
            )
            return

        if text == "📝 Записи":
            clear_state(user_id)

            send_message(
                user_id,
                admin_registrations_text(),
                admin_keyboard()
            )
            return

        if text == "➕ Добавить тренировку":
            start_add_training(user_id)
            return

        if text == "📊 Статистика":
            send_message(
                user_id,
                statistics_text(),
                admin_keyboard()
            )
            return

        # Редактирование по кнопке
        if text.startswith("✏️ "):
            try:
                training_id = int(
                    text.split("|")[0]
                    .replace("✏️", "")
                    .strip()
                )

                start_edit_training(
                    user_id,
                    training_id
                )

            except Exception:
                send_message(
                    user_id,
                    "Не удалось определить тренировку.",
                    admin_schedule_buttons()
                )

            return

        if text == "⬅️ Главное меню":
            show_main_menu(user_id)
            return

    # --------------------------------------------------------
    # Состояние записи
    # --------------------------------------------------------

    state = get_state(user_id)

    if state:

        if state["state"] == "booking_day":

            category = state["data"]["category"]

            for day, name in DAYS.items():
                if text == name:
                    show_booking_trainings(
                        user_id,
                        category,
                        day
                    )
                    return

        if state["state"] == "booking_training":

            training = training_from_state_selection(
                user_id,
                text
            )

            if training:
                show_training_for_booking(
                    user_id,
                    training
                )

                return

        if state["state"] == "training_info":

            training_id = state["data"]["training_id"]

            training = get_training(training_id)

            if not training:
                send_message(
                    user_id,
                    "Тренировка больше недоступна.",
                    main_keyboard(user_id)
                )
                clear_state(user_id)
                return

            if text == "✅ Записаться":

                count = get_registration_count(training_id)

                if count >= training["capacity"]:
                    send_message(
                        user_id,
                        "На этой тренировке больше нет свободных мест.",
                        back_keyboard()
                    )
                    return

                start_registration_name(
                    user_id,
                    training_id
                )
                return

            if text == "❌ Отменить запись":

                if not can_cancel(training):
                    send_message(
                        user_id,
                        "❌ Отмена невозможна.\n\n"
                        "Отменить запись можно не позднее чем "
                        "за 24 часа до начала тренировки.",
                        back_keyboard()
                    )
                    return

                cancel_registration(
                    training_id,
                    user_id
                )

                clear_state(user_id)

                send_message(
                    user_id,
                    "✅ Запись отменена.",
                    main_keyboard(user_id)
                )

                return

        if state["state"] == "registration_name":

            name = text.strip()

            if len(name) < 2:
                send_message(
                    user_id,
                    "Пожалуйста, напишите имя и фамилию.",
                    back_keyboard()
                )
                return

            start_registration_phone(
                user_id,
                name,
                state["data"]["training_id"]
            )

            return

        if state["state"] == "registration_phone":

            phone = text.strip()

            if len(phone) < 5:
                send_message(
                    user_id,
                    "Пожалуйста, укажите номер телефона.",
                    back_keyboard()
                )
                return

            training_id = state["data"]["training_id"]
            name = state["data"]["name"]

            success, message = register_user(
                user_id,
                training_id,
                name,
                phone
            )

            if not success:
                send_message(
                    user_id,
                    message,
                    main_keyboard(user_id)
                )
                clear_state(user_id)
                return

            training = get_training(training_id)

            clear_state(user_id)

            send_message(
                user_id,
                "✅ Вы записаны на тренировку!\n\n" +
                training_full_text(training),
                main_keyboard(user_id)
            )

            notify_admins(
                "🏐 Новая запись на тренировку\n\n"
                f"Тренировка: "
                f"{day_name(training['day_of_week'])} "
                f"{training['start_time']}\n"
                f"Формат: {training['format']}\n"
                f"Уровень: {training['level']}\n\n"
                f"👤 {name}\n"
                f"📱 {phone}\n"
                f"VK ID: {user_id}"
            )

            return

        # Индивидуальная тренировка

        if state["state"] == "individual_question":

            save_question(
                user_id,
                text
            )

            clear_state(user_id)

            send_message(
                user_id,
                "✅ Сообщение отправлено администратору.\n\n"
                "Мы свяжемся с вами для подбора времени "
                "и формата тренировки.",
                main_keyboard(user_id)
            )

            return

        # Обычный вопрос

        if state["state"] == "question":

            save_question(
                user_id,
                text
            )

            clear_state(user_id)

            send_message(
                user_id,
                "✅ Вопрос отправлен администратору.",
                main_keyboard(user_id)
            )

            return

    # --------------------------------------------------------
    # ГЛАВНОЕ МЕНЮ — ПОЛЬЗОВАТЕЛЬ
    # --------------------------------------------------------

    if text == "🏐 Записаться":

        start_booking(user_id)
        return

    if text == "📅 Расписание":

        send_message(
            user_id,
            "📅 Выберите категорию:",
            category_keyboard()
        )

        set_state(
            user_id,
            "schedule_category"
        )

        return

    if text == "👤 Мои тренировки":

        rows = my_trainings(user_id)

        if not rows:
            send_message(
                user_id,
                "👤 У вас пока нет активных записей.",
                main_keyboard(user_id)
            )
            return

        text_message = "👤 Мои тренировки\n\n"

        for training in rows:
            text_message += (
                f'🏐 {day_name(training["day_of_week"])} '
                f'{training["start_time"]}\n'
                f'{training["format"]}\n'
                f'Уровень: {training["level"]}\n\n'
            )

        send_message(
            user_id,
            text_message,
            main_keyboard(user_id)
        )

        return

    if text == "💰 Цены":

        send_message(
            user_id,
            prices_text(),
            main_keyboard(user_id)
        )

        return

    if text == "📍 Где тренируемся":

        send_message(
            user_id,
            location_text(),
            main_keyboard(user_id)
        )

        return

    if text == "🎯 Индивидуальная тренировка":

        start_individual(user_id)
        return

    if text == "❓ Задать вопрос":

        start_question(user_id)
        return

    # --------------------------------------------------------
    # РАСПИСАНИЕ — КАТЕГОРИЯ
    # --------------------------------------------------------

    if state and state["state"] == "schedule_category":

        if text in ["👨 Взрослые", "👶 Дети"]:

            category = "Взрослые" if text == "👨 Взрослые" else "Дети"

            clear_state(user_id)

            send_message(
                user_id,
                weekly_schedule_text(category),
                weekly_schedule_keyboard(category)
            )

            return

    # --------------------------------------------------------
    # Неизвестная команда
    # --------------------------------------------------------

    send_message(
        user_id,
        "Выберите действие из меню:",
        admin_keyboard()
        if is_admin_mode(user_id)
        else main_keyboard(user_id)
    )


# ============================================================
# CALLBACK VK
# ============================================================

@app.route("/callback", methods=["POST"])
def callback():

    data = request.json

    if not data:
        return "ok"

    # --------------------------------------------------------
    # Подтверждение сервера VK
    # --------------------------------------------------------

    if data.get("type") == "confirmation":

        return VK_CONFIRMATION_TOKEN

    # --------------------------------------------------------
    # Проверка секретного ключа
    # --------------------------------------------------------

    if data.get("secret") != VK_SECRET_KEY:

        return "invalid secret", 403

    # --------------------------------------------------------
    # Новое сообщение
    # --------------------------------------------------------

    if data.get("type") == "message_new":

        obj = data.get("object", {})

        user_id = obj.get("message", {}).get("from_id")

        if not user_id:
            user_id = obj.get("from_id")

        text = obj.get("message", {}).get("text", "")

        if not text:
            text = obj.get("text", "")

        if user_id:
            handle_message(
                int(user_id),
                text
            )

    return "ok"


# ============================================================
# ПРОВЕРКА СЕРВЕРА
# ============================================================

@app.route("/", methods=["GET"])
def index():
    return "VOLLEY WAVE VK BOT is running"


# ============================================================
# ЗАПУСК
# ============================================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port
    )
