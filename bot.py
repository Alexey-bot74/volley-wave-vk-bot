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
GROUP_ID = 221776135

ADMIN_IDS = {
    87984447,
    172892670,
    148372158,
}

DB_FILE = "volley_wave.db"

app = Flask(__name__)

# Для переключения админов между режимами:
# True  = админский режим
# False = обычный пользовательский режим
admin_modes = {}


# ============================================================
# VK API
# ============================================================

def vk_api(method, params=None):
    if params is None:
        params = {}

    params["access_token"] = VK_TOKEN
    params["v"] = VK_API_VERSION

    response = requests.post(
        f"https://api.vk.com/method/{method}",
        data=params,
        timeout=20,
    )

    return response.json()


def send_message(user_id, text, keyboard=None):
    params = {
        "user_id": user_id,
        "message": text,
        "random_id": 0,
    }

    if keyboard is not None:
        params["keyboard"] = keyboard

    result = vk_api("messages.send", params)

    if "error" in result:
        print("VK ERROR:", result)

    return result


def get_user_name(user_id):
    result = vk_api(
        "users.get",
        {
            "user_ids": user_id,
            "fields": "first_name,last_name",
        },
    )

    try:
        user = result["response"][0]
        return f'{user.get("first_name", "")} {user.get("last_name", "")}'.strip()
    except Exception:
        return "Пользователь VK"


# ============================================================
# DATABASE
# ============================================================

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def column_exists(conn, table_name, column_name):
    rows = conn.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    return any(row["name"] == column_name for row in rows)


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            vk_id INTEGER PRIMARY KEY,
            name TEXT,
            phone TEXT,
            created_at TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS trainings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            category TEXT NOT NULL,
            age_group TEXT,
            format TEXT,
            level TEXT,
            trainer TEXT,
            capacity INTEGER DEFAULT 10,
            price INTEGER DEFAULT 600,
            active INTEGER DEFAULT 1
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            training_id INTEGER NOT NULL,
            vk_id INTEGER NOT NULL,
            name TEXT,
            phone TEXT,
            created_at TEXT,
            UNIQUE(training_id, vk_id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vk_id INTEGER NOT NULL,
            name TEXT,
            question TEXT,
            created_at TEXT
        )
        """
    )

    # --------------------------------------------------------
    # Миграция старой БД
    # --------------------------------------------------------

    needed_columns = {
        "age_group": "TEXT",
        "format": "TEXT",
        "level": "TEXT",
        "trainer": "TEXT",
        "capacity": "INTEGER DEFAULT 10",
        "price": "INTEGER DEFAULT 600",
        "active": "INTEGER DEFAULT 1",
    }

    for column_name, column_type in needed_columns.items():
        if not column_exists(conn, "trainings", column_name):
            cur.execute(
                f"ALTER TABLE trainings ADD COLUMN {column_name} {column_type}"
            )

    conn.commit()

    # --------------------------------------------------------
    # Заполняем расписание только если его нет
    # --------------------------------------------------------

    count = cur.execute(
        "SELECT COUNT(*) AS count FROM trainings"
    ).fetchone()["count"]

    if count == 0:
        insert_default_schedule(conn)

    conn.commit()
    conn.close()


def insert_default_schedule(conn):
    schedule = [
        # day, start, end, category, age, format, level, trainer, capacity, price
        ("Пн", "09:00", "11:00", "Дети", "9–13 лет", "Групповая", "Начальный / средний", "Алексей", 10, 600),
        ("Пн", "17:00", "19:00", "Дети", "11–14 лет", "Групповая", "Средний", "Алексей", 10, 600),
        ("Пн", "19:00", "20:30", "Взрослые", "18+", "Групповая", "Техническая", "Алексей", 10, 1200),

        ("Вт", "09:00", "11:00", "Взрослые", "18+", "Групповая", "Общий уровень", "Алексей", 8, 1200),
        ("Вт", "17:00", "18:30", "Дети", "11–14 лет", "Групповая", "Средний", "Алексей", 10, 600),
        ("Вт", "19:30", "21:00", "Взрослые", "18+", "Групповая", "Женская, средний+", "Алексей", 8, 1200),

        ("Ср", "09:00", "11:00", "Дети", "9–14 лет", "Групповая", "Начальный / средний", "Алексей", 10, 600),
        ("Ср", "17:00", "18:00", "Дети", "5–9 лет", "Групповая", "Начальный", "Ксения", 10, 600),
        ("Ср", "18:00", "19:30", "Взрослые", "18+", "Групповая", "Продвинутый", "Алексей", 8, 1200),
        ("Ср", "19:30", "21:00", "Взрослые", "18+", "MIXED", "Средний+", "Алексей", 8, 1200),

        ("Чт", "09:00", "11:00", "Взрослые", "18+", "Групповая", "Общий уровень", "Алексей", 8, 1200),
        ("Чт", "17:00", "19:00", "Дети", "11–14 лет", "Групповая", "Средний", "Алексей", 10, 600),
        ("Чт", "19:00", "20:30", "Взрослые", "18+", "Групповая", "Средний", "Алексей", 8, 1200),

        ("Пт", "09:00", "11:00", "Дети", "9–14 лет", "Групповая", "Начальный / средний", "Алексей", 10, 600),
        ("Пт", "17:00", "18:00", "Дети", "5–10 лет", "Групповая", "Начальный", "Ксения", 10, 600),
        ("Пт", "17:00", "19:00", "Дети", "11–14 лет", "Групповая", "Средний", "Алексей", 10, 600),
        ("Пт", "19:00", "20:30", "Взрослые", "18+", "Групповая", "Техническая", "Алексей", 10, 1200),
    ]

    conn.executemany(
        """
        INSERT INTO trainings
        (
            day,
            start_time,
            end_time,
            category,
            age_group,
            format,
            level,
            trainer,
            capacity,
            price,
            active
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """,
        schedule,
    )


# ============================================================
# СОСТОЯНИЕ ПОЛЬЗОВАТЕЛЕЙ
# ============================================================

user_states = {}


def set_state(user_id, state, data=None):
    user_states[user_id] = {
        "state": state,
        "data": data or {},
    }


def get_state(user_id):
    return user_states.get(user_id)


def clear_state(user_id):
    user_states.pop(user_id, None)


# ============================================================
# АДМИН
# ============================================================

def is_admin(user_id):
    return user_id in ADMIN_IDS


def is_admin_mode(user_id):
    if not is_admin(user_id):
        return False

    return admin_modes.get(user_id, True)


def set_admin_mode(user_id, enabled):
    admin_modes[user_id] = enabled


# ============================================================
# KEYBOARDS
# ============================================================

def make_keyboard(buttons, columns=1):
    rows = []

    for i in range(0, len(buttons), columns):
        row = []

        for item in buttons[i:i + columns]:
            if isinstance(item, tuple):
                label, color = item
            else:
                label, color = item, "secondary"

            row.append({
                "action": {
                    "type": "text",
                    "label": label,
                },
                "color": color,
            })

        rows.append(row)

    return {
        "one_time": False,
        "buttons": rows,
    }


def main_keyboard(user_id):
    buttons = [
        ("🏐 Записаться", "primary"),
        ("📅 Расписание", "secondary"),
        ("👤 Мои тренировки", "secondary"),
        ("💰 Цены", "secondary"),
        ("📍 Где тренируемся", "secondary"),
        ("🎯 Индивидуальная тренировка", "secondary"),
        ("❓ Задать вопрос", "secondary"),
    ]

    if is_admin(user_id):
        buttons.append(("⚙️ Админ-панель", "negative"))

    return make_keyboard(buttons)


def admin_keyboard():
    buttons = [
        ("📅 Управление расписанием", "primary"),
        ("📋 Записи на тренировку", "primary"),
        ("📊 Статистика", "secondary"),
        ("👤 Режим пользователя", "secondary"),
        ("⬅️ Главное меню", "secondary"),
    ]

    return make_keyboard(buttons)


def back_keyboard():
    return make_keyboard([
        ("⬅️ Назад", "secondary"),
    ])


def admin_back_keyboard():
    return make_keyboard([
        ("⬅️ Назад", "secondary"),
        ("🏠 Админ-панель", "secondary"),
    ])


# ============================================================
# ТЕКСТЫ
# ============================================================

def prices_text():
    return (
        "💰 ЦЕНЫ\n\n"
        "👶 Дети\n"
        "600 ₽ за тренировку.\n\n"
        "🏐 Взрослые\n"
        "1–6 человек — 1200 ₽ с человека.\n"
        "7 и более человек — 1000 ₽ с человека.\n\n"
        "Минимальный размер взрослой группы — 4 человека.\n"
        "Это информационное условие, при записи оно автоматически не блокирует тренировку."
    )


def location_text():
    return (
        "📍 ГДЕ ТРЕНИРУЕМСЯ\n\n"
        "☀️ Летом\n"
        "Парк Гагарина.\n\n"
        "❄️ Зимой\n"
        "СК «Арена»\n"
        "ул. Молодогвардейцев, 7."
    )


# ============================================================
# ФОРМАТ ТРЕНИРОВКИ
# ============================================================

def training_label(training):
    return (
        f'{training["start_time"]}–{training["end_time"]} | '
        f'{training["format"] or "Групповая"} | '
        f'{training["level"] or "Общий уровень"} | '
        f'{training["age_group"] or ""}'
    )


def training_short_label(training):
    return (
        f'{training["start_time"]}–{training["end_time"]} '
        f'| {training["format"] or "Групповая"} '
        f'| {training["level"] or "Общий уровень"}'
    )


def training_price(training, participant_count=None):
    if training["category"] == "Дети":
        return 600

    if participant_count is None:
        participant_count = get_registration_count(training["id"])

    if participant_count >= 7:
        return 1000

    return 1200


# ============================================================
# РАСПИСАНИЕ
# ============================================================

DAY_ORDER = {
    "Пн": 1,
    "Вт": 2,
    "Ср": 3,
    "Чт": 4,
    "Пт": 5,
    "Сб": 6,
    "Вс": 7,
}


def get_trainings(category=None):
    conn = get_db()

    if category:
        rows = conn.execute(
            """
            SELECT *
            FROM trainings
            WHERE active = 1 AND category = ?
            ORDER BY
                CASE day
                    WHEN 'Пн' THEN 1
                    WHEN 'Вт' THEN 2
                    WHEN 'Ср' THEN 3
                    WHEN 'Чт' THEN 4
                    WHEN 'Пт' THEN 5
                    WHEN 'Сб' THEN 6
                    WHEN 'Вс' THEN 7
                    ELSE 8
                END,
                start_time
            """,
            (category,),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT *
            FROM trainings
            WHERE active = 1
            ORDER BY
                CASE day
                    WHEN 'Пн' THEN 1
                    WHEN 'Вт' THEN 2
                    WHEN 'Ср' THEN 3
                    WHEN 'Чт' THEN 4
                    WHEN 'Пт' THEN 5
                    WHEN 'Сб' THEN 6
                    WHEN 'Вс' THEN 7
                    ELSE 8
                END,
                start_time
            """
        ).fetchall()

    conn.close()
    return rows


def get_training(training_id):
    conn = get_db()

    row = conn.execute(
        "SELECT * FROM trainings WHERE id = ?",
        (training_id,),
    ).fetchone()

    conn.close()
    return row


def get_registration_count(training_id):
    conn = get_db()

    count = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM registrations
        WHERE training_id = ?
        """,
        (training_id,),
    ).fetchone()["count"]

    conn.close()
    return count


def get_training_registrations(training_id):
    conn = get_db()

    rows = conn.execute(
        """
        SELECT *
        FROM registrations
        WHERE training_id = ?
        ORDER BY created_at
        """,
        (training_id,),
    ).fetchall()

    conn.close()
    return rows


def weekly_schedule_text(category):
    trainings = get_trainings(category)

    if category == "Дети":
        title = "👶 РАСПИСАНИЕ ДЕТСКИХ ТРЕНИРОВОК"
    else:
        title = "🏐 РАСПИСАНИЕ ВЗРОСЛЫХ ТРЕНИРОВОК"

    if not trainings:
        return f"{title}\n\nРасписание пока не заполнено."

    grouped = {}

    for training in trainings:
        grouped.setdefault(training["day"], []).append(training)

    lines = [title, ""]

    for day in ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]:
        if day not in grouped:
            continue

        lines.append(f"━━ {day} ━━")

        for training in grouped[day]:
            count = get_registration_count(training["id"])
            capacity = training["capacity"] or 10
            price = training_price(training, count)

            lines.append(
                f'{training["start_time"]}–{training["end_time"]} '
                f'• {training["format"] or "Групповая"}'
            )
            lines.append(
                f'Уровень: {training["level"] or "—"}'
            )
            lines.append(
                f'Возраст: {training["age_group"] or "—"}'
            )
            lines.append(
                f'Тренер: {training["trainer"] or "—"}'
            )
            lines.append(
                f'Мест: {max(capacity - count, 0)}/{capacity} '
                f'• {price} ₽'
            )
            lines.append("")

    return "\n".join(lines)


# ============================================================
# ЗАПИСЬ
# ============================================================

def booking_category_keyboard():
    return make_keyboard([
        ("👨 Взрослые", "primary"),
        ("👶 Дети", "primary"),
        ("⬅️ Назад", "secondary"),
    ])


def booking_days_keyboard(category):
    trainings = get_trainings(category)

    days = []
    seen = set()

    for training in trainings:
        if training["day"] not in seen:
            seen.add(training["day"])
            days.append(training["day"])

    buttons = []

    for day in days:
        buttons.append((day, "primary"))

    buttons.append(("⬅️ Назад", "secondary"))

    return make_keyboard(buttons, columns=3)


def booking_trainings_keyboard(category, day):
    conn = get_db()

    rows = conn.execute(
        """
        SELECT *
        FROM trainings
        WHERE active = 1
          AND category = ?
          AND day = ?
        ORDER BY start_time
        """,
        (category, day),
    ).fetchall()

    conn.close()

    buttons = []

    # Каждая кнопка уникальна за счёт формата/уровня/возраста.
    for training in rows:
        count = get_registration_count(training["id"])
        capacity = training["capacity"] or 10

        if count >= capacity:
            label = (
                f'❌ {training["start_time"]}–{training["end_time"]} | '
                f'{training["format"] or "Групповая"} | '
                f'{training["level"] or "Общий"} | '
                f'{training["age_group"] or ""} | МЕСТ НЕТ'
            )
        else:
            label = (
                f'🏐 {training["start_time"]}–{training["end_time"]} | '
                f'{training["format"] or "Групповая"} | '
                f'{training["level"] or "Общий"} | '
                f'{training["age_group"] or ""}'
            )

        buttons.append((label, "primary"))

    buttons.append(("⬅️ Назад", "secondary"))

    return make_keyboard(buttons)


def training_details(training):
    count = get_registration_count(training["id"])
    capacity = training["capacity"] or 10
    free = max(capacity - count, 0)
    price = training_price(training, count)

    text = (
        f'🏐 ТРЕНИРОВКА\n\n'
        f'📅 {training["day"]}\n'
        f'⏰ {training["start_time"]}–{training["end_time"]}\n'
        f'👥 Формат: {training["format"] or "Групповая"}\n'
        f'🎯 Уровень: {training["level"] or "—"}\n'
        f'👶 Возраст: {training["age_group"] or "—"}\n'
        f'🏆 Тренер: {training["trainer"] or "—"}\n'
        f'💰 Цена: {price} ₽\n'
        f'🪑 Свободных мест: {free} из {capacity}\n\n'
        f'Участники: {count}/{capacity}'
    )

    return text


def user_registered(training_id, user_id):
    conn = get_db()

    row = conn.execute(
        """
        SELECT id
        FROM registrations
        WHERE training_id = ? AND vk_id = ?
        """,
        (training_id, user_id),
    ).fetchone()

    conn.close()

    return row is not None


def save_user(user_id, name, phone=None):
    conn = get_db()

    conn.execute(
        """
        INSERT INTO users(vk_id, name, phone, created_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(vk_id)
        DO UPDATE SET
            name = excluded.name,
            phone = COALESCE(excluded.phone, users.phone)
        """,
        (
            user_id,
            name,
            phone,
            datetime.now().isoformat(),
        ),
    )

    conn.commit()
    conn.close()


def create_registration(training_id, user_id, name, phone=None):
    conn = get_db()

    try:
        conn.execute(
            """
            INSERT INTO registrations
            (
                training_id,
                vk_id,
                name,
                phone,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                training_id,
                user_id,
                name,
                phone,
                datetime.now().isoformat(),
            ),
        )

        conn.commit()
        success = True

    except sqlite3.IntegrityError:
        success = False

    conn.close()

    return success


def delete_registration(training_id, user_id):
    conn = get_db()

    conn.execute(
        """
        DELETE FROM registrations
        WHERE training_id = ? AND vk_id = ?
        """,
        (training_id, user_id),
    )

    conn.commit()
    conn.close()


def can_cancel_training(training):
    # У расписания нет конкретной даты.
    # Используем следующий ближайший день недели.
    now = datetime.now()

    target_day_number = {
        "Пн": 0,
        "Вт": 1,
        "Ср": 2,
        "Чт": 3,
        "Пт": 4,
        "Сб": 5,
        "Вс": 6,
    }[training["day"]]

    days_ahead = (target_day_number - now.weekday()) % 7

    target_date = now.date() + timedelta(days=days_ahead)

    training_datetime = datetime.strptime(
        f"{target_date} {training['start_time']}",
        "%Y-%m-%d %H:%M",
    )

    # Если тренировка сегодняшняя, но время уже прошло,
    # берём следующую неделю.
    if training_datetime <= now:
        target_date += timedelta(days=7)

        training_datetime = datetime.strptime(
            f"{target_date} {training['start_time']}",
            "%Y-%m-%d %H:%M",
        )

    return now <= training_datetime - timedelta(hours=24)


# ============================================================
# МОИ ТРЕНИРОВКИ
# ============================================================

def my_trainings(user_id):
    conn = get_db()

    rows = conn.execute(
        """
        SELECT
            registrations.*,
            trainings.day,
            trainings.start_time,
            trainings.end_time,
            trainings.category,
            trainings.age_group,
            trainings.format,
            trainings.level,
            trainings.trainer,
            trainings.capacity,
            trainings.price,
            trainings.active
        FROM registrations
        JOIN trainings
            ON trainings.id = registrations.training_id
        WHERE registrations.vk_id = ?
          AND trainings.active = 1
        ORDER BY
            CASE trainings.day
                WHEN 'Пн' THEN 1
                WHEN 'Вт' THEN 2
                WHEN 'Ср' THEN 3
                WHEN 'Чт' THEN 4
                WHEN 'Пт' THEN 5
                WHEN 'Сб' THEN 6
                WHEN 'Вс' THEN 7
                ELSE 8
            END,
            trainings.start_time
        """,
        (user_id,),
    ).fetchall()

    conn.close()
    return rows


def my_trainings_keyboard(rows):
    buttons = []

    for row in rows:
        label = (
            f'❌ {row["day"]} {row["start_time"]} '
            f'| {row["format"] or "Групповая"}'
        )

        buttons.append((label, "negative"))

    buttons.append(("⬅️ Назад", "secondary"))

    return make_keyboard(buttons)


# ============================================================
# АДМИН: РАСПИСАНИЕ
# ============================================================

def admin_training_buttons():
    trainings = get_trainings()

    buttons = []

    for training in trainings:
        label = (
            f'✏️ #{training["id"]} '
            f'{training["day"]} '
            f'{training["start_time"]} '
            f'| {training["category"]} '
            f'| {training["level"] or "—"}'
        )

        buttons.append((label, "secondary"))

    buttons.append(("➕ Добавить тренировку", "positive"))
    buttons.append(("⬅️ Админ-панель", "secondary"))

    return make_keyboard(buttons)


def admin_training_details(training):
    count = get_registration_count(training["id"])

    return (
        f'⚙️ ТРЕНИРОВКА #{training["id"]}\n\n'
        f'День: {training["day"]}\n'
        f'Время: {training["start_time"]}–{training["end_time"]}\n'
        f'Категория: {training["category"]}\n'
        f'Возраст: {training["age_group"] or "—"}\n'
        f'Формат: {training["format"] or "—"}\n'
        f'Уровень: {training["level"] or "—"}\n'
        f'Тренер: {training["trainer"] or "—"}\n'
        f'Вместимость: {training["capacity"]}\n'
        f'Цена: {training["price"]} ₽\n'
        f'Записано: {count}\n'
    )


def admin_training_actions(training_id):
    return make_keyboard([
        (f"📋 Записи", "primary"),
        (f"✏️ Изменить", "secondary"),
        (f"🗑 Удалить", "negative"),
        ("⬅️ Назад", "secondary"),
    ])


# ============================================================
# АДМИН: УВЕДОМЛЕНИЯ
# ============================================================

def notify_admins(text):
    for admin_id in ADMIN_IDS:
        send_message(admin_id, text)


# ============================================================
# ГЛАВНОЕ МЕНЮ
# ============================================================

def show_main_menu(user_id, text="Главное меню"):
    clear_state(user_id)

    if is_admin(user_id) and is_admin_mode(user_id):
        send_message(
            user_id,
            "⚙️ Режим администратора\n\nВыберите действие:",
            admin_keyboard(),
        )
    else:
        send_message(
            user_id,
            text,
            main_keyboard(user_id),
        )


def show_admin_menu(user_id):
    clear_state(user_id)

    send_message(
        user_id,
        "⚙️ АДМИН-ПАНЕЛЬ\n\nВыберите действие:",
        admin_keyboard(),
    )


# ============================================================
# ОБРАБОТКА СООБЩЕНИЙ
# ============================================================

def handle_message(user_id, text):
    text = text.strip()
    state = get_state(user_id)

    # --------------------------------------------------------
    # Назад
    # --------------------------------------------------------

    if text in ("🏠 Главное меню", "⬅️ Главное меню"):
        show_main_menu(user_id)
        return

    if text == "🏠 Админ-панель":
        show_admin_menu(user_id)
        return

    if text == "⬅️ Назад":
        clear_state(user_id)

        if is_admin(user_id) and is_admin_mode(user_id):
            show_admin_menu(user_id)
        else:
            show_main_menu(user_id)

        return

    # --------------------------------------------------------
    # Админский режим
    # --------------------------------------------------------

    if is_admin(user_id):

        if text == "⚙️ Админ-панель":
            show_admin_menu(user_id)
            return

        if text == "👤 Режим пользователя":
            set_admin_mode(user_id, False)
            show_main_menu(
                user_id,
                "👤 Включён режим пользователя.\n\n"
                "Теперь вы видите бота так, как его видит обычный клиент.",
            )
            return

        if text == "📅 Управление расписанием":
            set_state(user_id, "admin_schedule")
            send_message(
                user_id,
                "📅 УПРАВЛЕНИЕ РАСПИСАНИЕМ\n\n"
                "Выберите тренировку для изменения "
                "или добавьте новую.",
                admin_training_buttons(),
            )
            return

        if text == "📋 Записи на тренировку":
            trainings = get_trainings()

            if not trainings:
                send_message(
                    user_id,
                    "Активных тренировок нет.",
                    admin_back_keyboard(),
                )
                return

            set_state(user_id, "admin_registrations_select")

            buttons = []

            for training in trainings:
                count = get_registration_count(training["id"])

                buttons.append(
                    (
                        f'📋 #{training["id"]} {training["day"]} '
                        f'{training["start_time"]} '
                        f'| {training["category"]} '
                        f'({count}/{training["capacity"]})',
                        "primary",
                    )
                )

            buttons.append(("⬅️ Админ-панель", "secondary"))

            send_message(
                user_id,
                "📋 ВЫБЕРИТЕ ТРЕНИРОВКУ:",
                make_keyboard(buttons),
            )
            return

        if text == "📊 Статистика":
            conn = get_db()

            total_users = conn.execute(
                "SELECT COUNT(*) AS count FROM users"
            ).fetchone()["count"]

            total_registrations = conn.execute(
                "SELECT COUNT(*) AS count FROM registrations"
            ).fetchone()["count"]

            total_trainings = conn.execute(
                "SELECT COUNT(*) AS count FROM trainings WHERE active = 1"
            ).fetchone()["count"]

            conn.close()

            send_message(
                user_id,
                (
                    "📊 СТАТИСТИКА\n\n"
                    f"Пользователей: {total_users}\n"
                    f"Записей: {total_registrations}\n"
                    f"Активных тренировок: {total_trainings}"
                ),
                admin_back_keyboard(),
            )
            return

    # --------------------------------------------------------
    # Состояние админов
    # --------------------------------------------------------

    if is_admin(user_id) and state:

        current_state = state["state"]
        data = state["data"]

        # --------------------------------------------
        # Выбор тренировки для редактирования
        # --------------------------------------------

        if current_state == "admin_schedule":

            if text == "➕ Добавить тренировку":
                set_state(
                    user_id,
                    "admin_add_day",
                    {},
                )

                send_message(
                    user_id,
                    "➕ ДОБАВЛЕНИЕ ТРЕНИРОВКИ\n\n"
                    "Введите день:\n"
                    "Пн, Вт, Ср, Чт или Пт",
                    back_keyboard(),
                )
                return

            if text.startswith("✏️ #"):
                try:
                    training_id = int(
                        text.split("#")[1].split()[0]
                    )
                except Exception:
                    send_message(
                        user_id,
                        "Не удалось определить тренировку.",
                        admin_back_keyboard(),
                    )
                    return

                training = get_training(training_id)

                if not training:
                    send_message(
                        user_id,
                        "Тренировка не найдена.",
                        admin_back_keyboard(),
                    )
                    return

                set_state(
                    user_id,
                    "admin_training_actions",
                    {
                        "training_id": training_id,
                    },
                )

                send_message(
                    user_id,
                    admin_training_details(training),
                    admin_training_actions(training_id),
                )
                return

        # --------------------------------------------
        # Действия с тренировкой
        # --------------------------------------------

        if current_state == "admin_training_actions":
            training_id = data["training_id"]

            training = get_training(training_id)

            if not training:
                show_admin_menu(user_id)
                return

            if text == "📋 Записи":
                registrations = get_training_registrations(training_id)

                if not registrations:
                    text_result = (
                        admin_training_details(training)
                        + "\n\n"
                        + "Пока никто не записан."
                    )
                else:
                    lines = [
                        admin_training_details(training),
                        "",
                        "👥 УЧАСТНИКИ:",
                    ]

                    for index, reg in enumerate(registrations, start=1):
                        name = reg["name"] or "Без имени"
                        phone = reg["phone"] or "телефон не указан"

                        lines.append(
                            f'{index}. {name} — {phone}'
                        )

                    text_result = "\n".join(lines)

                send_message(
                    user_id,
                    text_result,
                    admin_back_keyboard(),
                )
                return

            if text == "✏️ Изменить":
                set_state(
                    user_id,
                    "admin_edit_field",
                    {
                        "training_id": training_id,
                    },
                )

                send_message(
                    user_id,
                    "Что изменить?",
                    make_keyboard([
                        ("📅 День", "secondary"),
                        ("⏰ Время", "secondary"),
                        ("👥 Категорию", "secondary"),
                        ("👶 Возраст", "secondary"),
                        ("🏐 Формат", "secondary"),
                        ("🎯 Уровень", "secondary"),
                        ("🏆 Тренера", "secondary"),
                        ("🪑 Вместимость", "secondary"),
                        ("💰 Цену", "secondary"),
                        ("⬅️ Назад", "secondary"),
                    ]),
                )
                return

            if text == "🗑 Удалить":
                conn = get_db()

                conn.execute(
                    "UPDATE trainings SET active = 0 WHERE id = ?",
                    (training_id,),
                )

                conn.commit()
                conn.close()

                send_message(
                    user_id,
                    "🗑 Тренировка убрана из активного расписания.",
                    admin_back_keyboard(),
                )
                return

        # --------------------------------------------
        # Поле для редактирования
        # --------------------------------------------

        if current_state == "admin_edit_field":
            training_id = data["training_id"]

            field_map = {
                "📅 День": "day",
                "⏰ Время": "time",
                "👥 Категорию": "category",
                "👶 Возраст": "age_group",
                "🏐 Формат": "format",
                "🎯 Уровень": "level",
                "🏆 Тренера": "trainer",
                "🪑 Вместимость": "capacity",
                "💰 Цену": "price",
            }

            if text not in field_map:
                send_message(
                    user_id,
                    "Выберите поле кнопкой.",
                    back_keyboard(),
                )
                return

            field = field_map[text]

            set_state(
                user_id,
                "admin_edit_value",
                {
                    "training_id": training_id,
                    "field": field,
                },
            )

            instructions = {
                "day": "Введите день: Пн, Вт, Ср, Чт или Пт.",
                "time": "Введите время в формате:\n09:00-11:00",
                "category": "Введите: Взрослые или Дети.",
                "age_group": "Введите возрастную группу.",
                "format": "Введите формат, например:\nГрупповая или MIXED.",
                "level": "Введите уровень.",
                "trainer": "Введите имя тренера.",
                "capacity": "Введите количество мест числом.",
                "price": "Введите цену числом.",
            }

            send_message(
                user_id,
                instructions[field],
                back_keyboard(),
            )
            return

        # --------------------------------------------
        # Значение поля
        # --------------------------------------------

        if current_state == "admin_edit_value":
            training_id = data["training_id"]
            field = data["field"]

            conn = get_db()

            try:
                if field == "time":
                    parts = text.replace(" ", "").split("-")

                    if len(parts) != 2:
                        raise ValueError

                    start_time = parts[0]
                    end_time = parts[1]

                    conn.execute(
                        """
                        UPDATE trainings
                        SET start_time = ?, end_time = ?
                        WHERE id = ?
                        """,
                        (
                            start_time,
                            end_time,
                            training_id,
                        ),
                    )

                elif field == "capacity":
                    value = int(text)

                    conn.execute(
                        """
                        UPDATE trainings
                        SET capacity = ?
                        WHERE id = ?
                        """,
                        (value, training_id),
                    )

                elif field == "price":
                    value = int(text)

                    conn.execute(
                        """
                        UPDATE trainings
                        SET price = ?
                        WHERE id = ?
                        """,
                        (value, training_id),
                    )

                elif field == "category":
                    if text not in ("Взрослые", "Дети"):
                        raise ValueError

                    conn.execute(
                        """
                        UPDATE trainings
                        SET category = ?
                        WHERE id = ?
                        """,
                        (text, training_id),
                    )

                elif field == "day":
                    if text not in ("Пн", "Вт", "Ср", "Чт", "Пт"):
                        raise ValueError

                    conn.execute(
                        """
                        UPDATE trainings
                        SET day = ?
                        WHERE id = ?
                        """,
                        (text, training_id),
                    )

                else:
                    conn.execute(
                        f"""
                        UPDATE trainings
                        SET {field} = ?
                        WHERE id = ?
                        """,
                        (text, training_id),
                    )

                conn.commit()
                success = True

            except Exception:
                success = False

            conn.close()

            if not success:
                send_message(
                    user_id,
                    "❌ Не удалось сохранить значение.\n"
                    "Проверьте формат введённых данных.",
                    back_keyboard(),
                )
                return

            training = get_training(training_id)

            send_message(
                user_id,
                "✅ Тренировка обновлена.\n\n"
                + admin_training_details(training),
                admin_training_actions(training_id),
            )

            set_state(
                user_id,
                "admin_training_actions",
                {
                    "training_id": training_id,
                },
            )

            return

        # --------------------------------------------
        # Добавление тренировки
        # --------------------------------------------

        if current_state == "admin_add_day":
            if text not in ("Пн", "Вт", "Ср", "Чт", "Пт"):
                send_message(
                    user_id,
                    "Введите один из вариантов: Пн, Вт, Ср, Чт или Пт.",
                    back_keyboard(),
                )
                return

            data["day"] = text

            set_state(
                user_id,
                "admin_add_time",
                data,
            )

            send_message(
                user_id,
                "Введите время в формате:\n09:00-11:00",
                back_keyboard(),
            )
            return

        if current_state == "admin_add_time":
            parts = text.replace(" ", "").split("-")

            if len(parts) != 2:
                send_message(
                    user_id,
                    "Неверный формат.\nПример: 19:00-20:30",
                    back_keyboard(),
                )
                return

            data["start_time"] = parts[0]
            data["end_time"] = parts[1]

            set_state(
                user_id,
                "admin_add_category",
                data,
            )

            send_message(
                user_id,
                "Выберите категорию:",
                make_keyboard([
                    ("👨 Взрослые", "primary"),
                    ("👶 Дети", "primary"),
                    ("⬅️ Назад", "secondary"),
                ]),
            )
            return

        if current_state == "admin_add_category":
            if text == "👨 Взрослые":
                data["category"] = "Взрослые"
            elif text == "👶 Дети":
                data["category"] = "Дети"
            else:
                send_message(
                    user_id,
                    "Выберите категорию кнопкой.",
                    back_keyboard(),
                )
                return

            set_state(
                user_id,
                "admin_add_age",
                data,
            )

            send_message(
                user_id,
                "Введите возрастную группу.\n"
                "Например: 11–14 лет или 18+",
                back_keyboard(),
            )
            return

        if current_state == "admin_add_age":
            data["age_group"] = text

            set_state(
                user_id,
                "admin_add_format",
                data,
            )

            send_message(
                user_id,
                "Введите формат.\n"
                "Например: Групповая или MIXED.",
                back_keyboard(),
            )
            return

        if current_state == "admin_add_format":
            data["format"] = text

            set_state(
                user_id,
                "admin_add_level",
                data,
            )

            send_message(
                user_id,
                "Введите уровень.",
                back_keyboard(),
            )
            return

        if current_state == "admin_add_level":
            data["level"] = text

            set_state(
                user_id,
                "admin_add_trainer",
                data,
            )

            send_message(
                user_id,
                "Введите имя тренера.",
                back_keyboard(),
            )
            return

        if current_state == "admin_add_trainer":
            data["trainer"] = text

            set_state(
                user_id,
                "admin_add_capacity",
                data,
            )

            send_message(
                user_id,
                "Введите количество мест.",
                back_keyboard(),
            )
            return

        if current_state == "admin_add_capacity":
            try:
                capacity = int(text)
            except ValueError:
                send_message(
                    user_id,
                    "Введите количество мест числом.",
                    back_keyboard(),
                )
                return

            data["capacity"] = capacity

            set_state(
                user_id,
                "admin_add_price",
                data,
            )

            default_price = 600 if data["category"] == "Дети" else 1200

            send_message(
                user_id,
                f"Введите цену.\n"
                f"Для этой категории стандартная цена: {default_price} ₽",
                back_keyboard(),
            )
            return

        if current_state == "admin_add_price":
            try:
                price = int(text)
            except ValueError:
                send_message(
                    user_id,
                    "Введите цену числом.",
                    back_keyboard(),
                )
                return

            data["price"] = price

            conn = get_db()

            conn.execute(
                """
                INSERT INTO trainings
                (
                    day,
                    start_time,
                    end_time,
                    category,
                    age_group,
                    format,
                    level,
                    trainer,
                    capacity,
                    price,
                    active
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    data["day"],
                    data["start_time"],
                    data["end_time"],
                    data["category"],
                    data["age_group"],
                    data["format"],
                    data["level"],
                    data["trainer"],
                    data["capacity"],
                    data["price"],
                ),
            )

            conn.commit()
            new_id = conn.execute(
                "SELECT last_insert_rowid() AS id"
            ).fetchone()["id"]

            conn.close()

            clear_state(user_id)

            send_message(
                user_id,
                f"✅ Тренировка #{new_id} добавлена.",
                admin_training_buttons(),
            )
            return

        # --------------------------------------------
        # Записи на тренировку
        # --------------------------------------------

        if current_state == "admin_registrations_select":
            if not text.startswith("📋 #"):
                return

            try:
                training_id = int(
                    text.split("#")[1].split()[0]
                )
            except Exception:
                return

            training = get_training(training_id)

            if not training:
                send_message(
                    user_id,
                    "Тренировка не найдена.",
                    admin_back_keyboard(),
                )
                return

            registrations = get_training_registrations(training_id)

            lines = [
                admin_training_details(training),
                "",
                "👥 УЧАСТНИКИ:",
            ]

            if not registrations:
                lines.append("Пока никто не записан.")
            else:
                for index, reg in enumerate(registrations, start=1):
                    lines.append(
                        f'{index}. {reg["name"] or "Без имени"}'
                    )

            send_message(
                user_id,
                "\n".join(lines),
                admin_back_keyboard(),
            )
            return

    # --------------------------------------------------------
    # ПОЛЬЗОВАТЕЛЬСКОЕ МЕНЮ
    # --------------------------------------------------------

    if text == "⚙️ Админ-панель" and is_admin(user_id):
        set_admin_mode(user_id, True)
        show_admin_menu(user_id)
        return

    if text == "🏐 Записаться":
        set_state(
            user_id,
            "booking_category",
            {},
        )

        send_message(
            user_id,
            "🏐 ВЫБЕРИТЕ КАТЕГОРИЮ:",
            booking_category_keyboard(),
        )
        return

    if text == "📅 Расписание":
        set_state(
            user_id,
            "schedule_category",
            {},
        )

        send_message(
            user_id,
            "📅 ВЫБЕРИТЕ РАСПИСАНИЕ:",
            booking_category_keyboard(),
        )
        return

    if text == "💰 Цены":
        send_message(
            user_id,
            prices_text(),
            main_keyboard(user_id),
        )
        return

    if text == "📍 Где тренируемся":
        send_message(
            user_id,
            location_text(),
            main_keyboard(user_id),
        )
        return

    if text == "🎯 Индивидуальная тренировка":
        set_state(
            user_id,
            "individual_question",
            {},
        )

        send_message(
            user_id,
            "🎯 ИНДИВИДУАЛЬНАЯ ТРЕНИРОВКА\n\n"
            "Напишите, пожалуйста, что вас интересует:\n"
            "желаемая дата, время и ваш уровень.\n\n"
            "Я передам информацию администратору.",
            back_keyboard(),
        )
        return

    if text == "❓ Задать вопрос":
        set_state(
            user_id,
            "question",
            {},
        )

        send_message(
            user_id,
            "❓ Напишите ваш вопрос одним сообщением.\n\n"
            "Он будет передан администратору.",
            back_keyboard(),
        )
        return

    if text == "👤 Мои тренировки":
        rows = my_trainings(user_id)

        if not rows:
            send_message(
                user_id,
                "👤 У вас пока нет активных записей.",
                main_keyboard(user_id),
            )
            return

        lines = ["👤 МОИ ТРЕНИРОВКИ\n"]

        for row in rows:
            lines.append(
                f'🏐 {row["day"]} '
                f'{row["start_time"]}–{row["end_time"]}\n'
                f'{row["format"] or "Групповая"} • '
                f'{row["level"] or "Общий уровень"}\n'
                f'Возраст: {row["age_group"] or "—"}\n'
                f'Тренер: {row["trainer"] or "—"}\n'
            )

        send_message(
            user_id,
            "\n".join(lines),
            my_trainings_keyboard(rows),
        )
        return

    # --------------------------------------------------------
    # ПОЛЬЗОВАТЕЛЬСКИЕ СОСТОЯНИЯ
    # --------------------------------------------------------

    if state:

        current_state = state["state"]
        data = state["data"]

        # --------------------------------------------
        # Выбор категории для расписания
        # --------------------------------------------

        if current_state == "schedule_category":

            if text == "👨 Взрослые":
                send_message(
                    user_id,
                    weekly_schedule_text("Взрослые"),
                    main_keyboard(user_id),
                )
                clear_state(user_id)
                return

            if text == "👶 Дети":
                send_message(
                    user_id,
                    weekly_schedule_text("Дети"),
                    main_keyboard(user_id),
                )
                clear_state(user_id)
                return

        # --------------------------------------------
        # Выбор категории для записи
        # --------------------------------------------

        if current_state == "booking_category":

            if text == "👨 Взрослые":
                data["category"] = "Взрослые"

                set_state(
                    user_id,
                    "booking_day",
                    data,
                )

                send_message(
                    user_id,
                    "📅 Выберите день:",
                    booking_days_keyboard("Взрослые"),
                )
                return

            if text == "👶 Дети":
                data["category"] = "Дети"

                set_state(
                    user_id,
                    "booking_day",
                    data,
                )

                send_message(
                    user_id,
                    "📅 Выберите день:",
                    booking_days_keyboard("Дети"),
                )
                return

        # --------------------------------------------
        # Выбор дня
        # --------------------------------------------

        if current_state == "booking_day":
            category = data["category"]

            valid_days = {
                training["day"]
                for training in get_trainings(category)
            }

            if text not in valid_days:
                return

            data["day"] = text

            set_state(
                user_id,
                "booking_training",
                data,
            )

            send_message(
                user_id,
                f'🏐 {category} — {text}\n\n'
                f'Выберите тренировку:',
                booking_trainings_keyboard(
                    category,
                    text,
                ),
            )
            return

        # --------------------------------------------
        # Выбор тренировки
        # --------------------------------------------

        if current_state == "booking_training":
            category = data["category"]
            day = data["day"]

            trainings = get_trainings(category)

            selected_training = None

            for training in trainings:
                if training["day"] != day:
                    continue

                expected = (
                    f'🏐 {training["start_time"]}–{training["end_time"]} | '
                    f'{training["format"] or "Групповая"} | '
                    f'{training["level"] or "Общий"} | '
                    f'{training["age_group"] or ""}'
                )

                full_expected = expected

                if text == full_expected:
                    selected_training = training
                    break

                # Обработка случая, когда мест уже нет.
                no_places = (
                    f'❌ {training["start_time"]}–{training["end_time"]} | '
                    f'{training["format"] or "Групповая"} | '
                    f'{training["level"] or "Общий"} | '
                    f'{training["age_group"] or ""} | МЕСТ НЕТ'
                )

                if text == no_places:
                    selected_training = training
                    break

            if not selected_training:
                send_message(
                    user_id,
                    "Не удалось определить тренировку. "
                    "Выберите её кнопкой ещё раз.",
                    booking_trainings_keyboard(
                        category,
                        day,
                    ),
                )
                return

            training_id = selected_training["id"]

            count = get_registration_count(training_id)
            capacity = selected_training["capacity"] or 10

            if count >= capacity:
                send_message(
                    user_id,
                    "❌ На эту тренировку уже нет свободных мест.",
                    booking_trainings_keyboard(
                        category,
                        day,
                    ),
                )
                return

            data["training_id"] = training_id

            set_state(
                user_id,
                "booking_confirm",
                data,
            )

            if user_registered(training_id, user_id):
                send_message(
                    user_id,
                    "Вы уже записаны на эту тренировку.",
                    main_keyboard(user_id),
                )
                clear_state(user_id)
                return

            send_message(
                user_id,
                training_details(selected_training)
                + "\n\nЗаписаться?",
                make_keyboard([
                    ("✅ Записаться", "positive"),
                    ("⬅️ Назад", "secondary"),
                ]),
            )
            return

        # --------------------------------------------
        # Подтверждение записи
        # --------------------------------------------

        if current_state == "booking_confirm":

            if text != "✅ Записаться":
                return

            training_id = data["training_id"]
            training = get_training(training_id)

            if not training:
                send_message(
                    user_id,
                    "Тренировка больше недоступна.",
                    main_keyboard(user_id),
                )
                clear_state(user_id)
                return

            count = get_registration_count(training_id)
            capacity = training["capacity"] or 10

            if count >= capacity:
                send_message(
                    user_id,
                    "❌ Пока вы подтверждали запись, "
                    "свободные места закончились.",
                    main_keyboard(user_id),
                )
                clear_state(user_id)
                return

            name = get_user_name(user_id)

            save_user(user_id, name)

            success = create_registration(
                training_id,
                user_id,
                name,
            )

            if not success:
                send_message(
                    user_id,
                    "Вы уже записаны на эту тренировку.",
                    main_keyboard(user_id),
                )
                clear_state(user_id)
                return

            new_count = get_registration_count(training_id)

            send_message(
                user_id,
                "✅ Вы записаны!\n\n"
                + training_details(training),
                main_keyboard(user_id),
            )

            notify_admins(
                "🏐 НОВАЯ ЗАПИСЬ\n\n"
                f"Тренировка: {training['day']} "
                f"{training['start_time']}–{training['end_time']}\n"
                f"Категория: {training['category']}\n"
                f"Формат: {training['format']}\n"
                f"Уровень: {training['level']}\n"
                f"Участник: {name}\n"
                f"Всего участников: {new_count}/{training['capacity']}"
            )

            clear_state(user_id)
            return

        # --------------------------------------------
        # Вопрос
        # --------------------------------------------

        if current_state == "question":

            name = get_user_name(user_id)

            conn = get_db()

            conn.execute(
                """
                INSERT INTO questions
                (
                    vk_id,
                    name,
                    question,
                    created_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    user_id,
                    name,
                    text,
                    datetime.now().isoformat(),
                ),
            )

            conn.commit()
            conn.close()

            notify_admins(
                "❓ НОВЫЙ ВОПРОС\n\n"
                f"От: {name}\n"
                f"VK ID: {user_id}\n\n"
                f"{text}"
            )

            send_message(
                user_id,
                "✅ Вопрос передан администратору.\n"
                "С вами свяжутся в VK.",
                main_keyboard(user_id),
            )

            clear_state(user_id)
            return

        # --------------------------------------------
        # Индивидуальная тренировка
        # --------------------------------------------

        if current_state == "individual_question":

            name = get_user_name(user_id)

            conn = get_db()

            conn.execute(
                """
                INSERT INTO questions
                (
                    vk_id,
                    name,
                    question,
                    created_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    user_id,
                    name,
                    "Индивидуальная тренировка: " + text,
                    datetime.now().isoformat(),
                ),
            )

            conn.commit()
            conn.close()

            notify_admins(
                "🎯 ЗАПРОС НА ИНДИВИДУАЛЬНУЮ ТРЕНИРОВКУ\n\n"
                f"От: {name}\n"
                f"VK ID: {user_id}\n\n"
                f"{text}"
            )

            send_message(
                user_id,
                "✅ Запрос передан администратору.\n"
                "Мы свяжемся с вами для согласования времени.",
                main_keyboard(user_id),
            )

            clear_state(user_id)
            return

        # --------------------------------------------
        # Мои тренировки — отмена
        # --------------------------------------------

        if current_state == "my_cancel":
            training_id = data.get("training_id")

            training = get_training(training_id)

            if not training:
                send_message(
                    user_id,
                    "Тренировка не найдена.",
                    main_keyboard(user_id),
                )
                clear_state(user_id)
                return

            if not user_registered(training_id, user_id):
                send_message(
                    user_id,
                    "Вы уже не записаны на эту тренировку.",
                    main_keyboard(user_id),
                )
                clear_state(user_id)
                return

            if not can_cancel_training(training):
                send_message(
                    user_id,
                    "❌ Отменить запись уже нельзя.\n\n"
                    "Отмена доступна не позднее чем за 24 часа "
                    "до начала тренировки.",
                    main_keyboard(user_id),
                )
                clear_state(user_id)
                return

            delete_registration(training_id, user_id)

            send_message(
                user_id,
                "✅ Запись отменена.",
                main_keyboard(user_id),
            )

            notify_admins(
                "❌ ОТМЕНА ЗАПИСИ\n\n"
                f"Участник: {get_user_name(user_id)}\n"
                f"Тренировка: {training['day']} "
                f"{training['start_time']}–{training['end_time']}"
            )

            clear_state(user_id)
            return

    # --------------------------------------------------------
    # Обработка кнопок "Мои тренировки" для отмены
    # --------------------------------------------------------

    if text.startswith("❌ "):
        rows = my_trainings(user_id)

        selected = None

        for row in rows:
            expected = (
                f'❌ {row["day"]} {row["start_time"]} '
                f'| {row["format"] or "Групповая"}'
            )

            if text == expected:
                selected = row
                break

        if selected:
            set_state(
                user_id,
                "my_cancel",
                {
                    "training_id": selected["training_id"],
                },
            )

            send_message(
                user_id,
                training_details(selected)
                + "\n\n"
                + "Отменить запись?",
                make_keyboard([
                    ("❌ Отменить запись", "negative"),
                    ("⬅️ Назад", "secondary"),
                ]),
            )

            return

    if text == "❌ Отменить запись":
        state = get_state(user_id)

        if state and state["state"] == "my_cancel":
            training_id = state["data"]["training_id"]
            training = get_training(training_id)

            if not training:
                show_main_menu(user_id)
                return

            if not can_cancel_training(training):
                send_message(
                    user_id,
                    "❌ Отмена невозможна.\n\n"
                    "До тренировки осталось менее 24 часов.",
                    main_keyboard(user_id),
                )
                clear_state(user_id)
                return

            delete_registration(training_id, user_id)

            send_message(
                user_id,
                "✅ Запись отменена.",
                main_keyboard(user_id),
            )

            notify_admins(
                "❌ ОТМЕНА ЗАПИСИ\n\n"
                f"Участник: {get_user_name(user_id)}\n"
                f"Тренировка: {training['day']} "
                f"{training['start_time']}–{training['end_time']}"
            )

            clear_state(user_id)
            return

    # --------------------------------------------------------
    # Неизвестная команда
    # --------------------------------------------------------

    send_message(
        user_id,
        "Не совсем понял команду.\n"
        "Выберите действие из меню:",
        main_keyboard(user_id),
    )


# ============================================================
# CALLBACK API
# ============================================================

@app.route("/", methods=["GET"])
def index():
    return "VOLLEY WAVE VK BOT OK", 200


@app.route("/callback", methods=["POST"])
def callback():

    data = request.get_json(silent=True) or {}

    # --------------------------------------------------------
    # Подтверждение Callback API
    # --------------------------------------------------------

    if data.get("type") == "confirmation":
        return VK_CONFIRMATION_TOKEN, 200

    # --------------------------------------------------------
    # Проверка секрета
    # --------------------------------------------------------

    if VK_SECRET_KEY:
        if data.get("secret") != VK_SECRET_KEY:
            return "invalid secret", 403

    # --------------------------------------------------------
    # Новое сообщение
    # --------------------------------------------------------

    if data.get("type") == "message_new":

        obj = data.get("object", {})

        user_id = obj.get("from_id")
        text = obj.get("text", "")

        if user_id:
            try:
                handle_message(
                    int(user_id),
                    text,
                )
            except Exception as error:
                print("BOT ERROR:", repr(error))

                try:
                    send_message(
                        int(user_id),
                        "Произошла техническая ошибка.\n"
                        "Попробуйте ещё раз через несколько секунд.",
                        main_keyboard(int(user_id)),
                    )
                except Exception as send_error:
                    print(
                        "SEND ERROR:",
                        repr(send_error),
                    )

        return "ok", 200

    return "ok", 200


# ============================================================
# ЗАПУСК
# ============================================================

if __name__ == "__main__":
    init_db()

    port = int(os.getenv("PORT", "10000"))

    print("======================================")
    print("VOLLEY WAVE VK BOT")
    print("Bot started")
    print(f"Group ID: {GROUP_ID}")
    print(f"Admins: {ADMIN_IDS}")
    print(f"Port: {port}")
    print("======================================")

    app.run(
        host="0.0.0.0",
        port=port,
    )
