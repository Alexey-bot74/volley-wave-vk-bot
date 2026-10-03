import os
import json
import sqlite3
import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from flask import Flask, request


# ============================================================
# НАСТРОЙКИ
# ============================================================

VK_TOKEN = os.getenv("VK_TOKEN", "")
VK_SECRET_KEY = os.getenv("VK_SECRET_KEY", "")
VK_CONFIRMATION_TOKEN = os.getenv("VK_CONFIRMATION_TOKEN", "")

VK_API_VERSION = "5.199"
GROUP_ID = 221776135

DB_NAME = "volley_wave.db"

ADMIN_IDS = {
    87984447,
    172892670,
    148372158,
}

LOCAL_TZ = ZoneInfo("Asia/Yekaterinburg")

app = Flask(__name__)

# Состояния пользователей в памяти.
# Для текущей версии этого достаточно.
user_states = {}


# ============================================================
# ВРЕМЯ
# ============================================================

def now_local():
    return datetime.now(LOCAL_TZ)


def today_local():
    return now_local().date()


# ============================================================
# БАЗА ДАННЫХ
# ============================================================

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS trainings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            time_start TEXT NOT NULL,
            time_end TEXT NOT NULL,
            category TEXT NOT NULL,
            age TEXT NOT NULL,
            format TEXT NOT NULL,
            level TEXT NOT NULL,
            coach TEXT NOT NULL,
            capacity INTEGER NOT NULL,
            price INTEGER NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            training_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(user_id, training_id)
        )
    """)

    conn.commit()
    conn.close()


# ============================================================
# РАСПИСАНИЕ
# ============================================================

WEEKDAYS = {
    0: "Понедельник",
    1: "Вторник",
    2: "Среда",
    3: "Четверг",
    4: "Пятница",
    5: "Суббота",
    6: "Воскресенье",
}


INITIAL_SCHEDULE = [
    # weekday, start, end, category, age, format, level, coach, capacity, price
    (0, "09:00", "11:00", "Дети", "9–13 лет", "Группа", "Начальный / средний", "Алексей", 10, 600),
    (0, "17:00", "19:00", "Дети", "11–14 лет", "Группа", "Средний", "Алексей", 10, 600),
    (0, "19:00", "20:30", "Взрослые", "18+", "Группа", "Техничка", "Алексей", 10, 1200),

    (1, "09:00", "11:00", "Взрослые", "18+", "Группа", "Общий уровень", "Алексей", 8, 1200),
    (1, "17:00", "18:30", "Дети", "11–14 лет", "Группа", "Средний", "Алексей", 10, 600),
    (1, "19:30", "21:00", "Взрослые", "18+", "Группа", "Женская, средний+", "Алексей", 8, 1200),

    (2, "09:00", "11:00", "Дети", "9–14 лет", "Группа", "Начальный / средний", "Алексей", 10, 600),
    (2, "17:00", "18:00", "Дети", "5–9 лет", "Группа", "Начальный", "Ксения", 10, 600),
    (2, "18:00", "19:30", "Взрослые", "18+", "Группа", "Продвинутый", "Алексей", 8, 1200),
    (2, "19:30", "21:00", "Взрослые", "18+", "MIXED", "Средний+", "Алексей", 8, 1200),

    (3, "09:00", "11:00", "Взрослые", "18+", "Группа", "Общий уровень", "Алексей", 8, 1200),
    (3, "17:00", "19:00", "Дети", "11–14 лет", "Группа", "Средний", "Алексей", 10, 600),
    (3, "19:00", "20:30", "Взрослые", "18+", "Группа", "Средний", "Алексей", 8, 1200),

    (4, "09:00", "11:00", "Дети", "9–14 лет", "Группа", "Начальный / средний", "Алексей", 10, 600),
    (4, "17:00", "18:00", "Дети", "5–10 лет", "Группа", "Начальный", "Ксения", 10, 600),
    (4, "17:00", "19:00", "Дети", "11–14 лет", "Группа", "Средний", "Алексей", 10, 600),
    (4, "19:00", "20:30", "Взрослые", "18+", "Группа", "Техничка", "Алексей", 10, 1200),
]


def seed_schedule():
    """
    Создаёт расписание на ближайшие 7 дней.
    Дубликаты не создаются.
    """

    conn = get_db()
    cur = conn.cursor()

    start_date = today_local()

    for day_offset in range(7):
        current_date = start_date + timedelta(days=day_offset)
        weekday = current_date.weekday()

        for item in INITIAL_SCHEDULE:
            (
                item_weekday,
                time_start,
                time_end,
                category,
                age,
                training_format,
                level,
                coach,
                capacity,
                price,
            ) = item

            if item_weekday != weekday:
                continue

            date_str = current_date.strftime("%Y-%m-%d")

            cur.execute("""
                SELECT id
                FROM trainings
                WHERE date = ?
                  AND time_start = ?
                  AND category = ?
            """, (
                date_str,
                time_start,
                category,
            ))

            exists = cur.fetchone()

            if not exists:
                cur.execute("""
                    INSERT INTO trainings (
                        date,
                        time_start,
                        time_end,
                        category,
                        age,
                        format,
                        level,
                        coach,
                        capacity,
                        price
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    date_str,
                    time_start,
                    time_end,
                    category,
                    age,
                    training_format,
                    level,
                    coach,
                    capacity,
                    price,
                ))

    conn.commit()
    conn.close()


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
            timeout=15,
        )

        result = response.json()

        if "error" in result:
            print("❌ VK API ERROR:", result["error"], flush=True)

        return result

    except Exception as e:
        print("❌ VK API REQUEST ERROR:", repr(e), flush=True)
        return None


def send_message(user_id, text, keyboard=None):
    params = {
        "peer_id": user_id,
        "message": text,
        "random_id": random.randint(1, 2147483647),
    }

    if keyboard is not None:
        params["keyboard"] = json.dumps(
            keyboard,
            ensure_ascii=False
        )

    result = vk_api("messages.send", params)

    return result


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


def main_menu(user_id):
    rows = [
        [
            button("🏐 Записаться", "positive"),
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
            button("⚙️ Админ-панель", "primary")
        ])

    return keyboard(rows)


def category_keyboard():
    return keyboard([
        [
            button("👦 Дети", "positive"),
            button("👨 Взрослые", "positive"),
        ],
        [
            button("◀️ Назад", "secondary")
        ]
    ])


def booking_days_keyboard():
    return keyboard([
        [
            button("Пн", "primary"),
            button("Вт", "primary"),
            button("Ср", "primary"),
        ],
        [
            button("Чт", "primary"),
            button("Пт", "primary"),
        ],
        [
            button("◀️ Назад", "secondary")
        ]
    ])


def admin_menu_keyboard():
    return keyboard([
        [
            button("📋 Расписание", "primary"),
            button("👥 Записи", "primary"),
        ],
        [
            button("➕ Добавить тренировку", "positive"),
            button("📊 Общая информация", "secondary"),
        ],
        [
            button("👤 Режим пользователя", "secondary"),
        ],
        [
            button("🏠 Главное меню", "secondary"),
        ]
    ])


def back_keyboard():
    return keyboard([
        [
            button("◀️ Назад", "secondary")
        ]
    ])


# ============================================================
# ПОЛЬЗОВАТЕЛИ
# ============================================================

def save_user(user_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT OR IGNORE INTO users (user_id, created_at)
        VALUES (?, ?)
    """, (
        user_id,
        now_local().isoformat()
    ))

    conn.commit()
    conn.close()


# ============================================================
# СОСТОЯНИЯ
# ============================================================

def set_state(user_id, state=None, **kwargs):
    if state is None and not kwargs:
        user_states.pop(user_id, None)
        return

    current = user_states.get(user_id, {})

    if state is not None:
        current["state"] = state

    current.update(kwargs)

    user_states[user_id] = current


def get_state(user_id):
    return user_states.get(user_id, {})


def clear_state(user_id):
    user_states.pop(user_id, None)


def is_admin_mode(user_id):
    return (
        user_id in ADMIN_IDS
        and user_states.get(user_id, {}).get("admin_mode", False)
    )


def enter_admin_mode(user_id):
    user_states[user_id] = {
        "admin_mode": True,
        "state": None
    }


def enter_user_mode(user_id):
    user_states[user_id] = {
        "admin_mode": False,
        "state": None
    }


# ============================================================
# РАСПИСАНИЕ / ТРЕНИРОВКИ
# ============================================================

def training_datetime(training):
    dt = datetime.strptime(
        f"{training['date']} {training['time_start']}",
        "%Y-%m-%d %H:%M"
    )

    return dt.replace(tzinfo=LOCAL_TZ)


def get_training_by_id(training_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM trainings
        WHERE id = ?
    """, (training_id,))

    row = cur.fetchone()
    conn.close()

    return row


def get_participants(training_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT user_id
        FROM registrations
        WHERE training_id = ?
        ORDER BY id
    """, (training_id,))

    rows = cur.fetchall()
    conn.close()

    return [row["user_id"] for row in rows]


def participant_count(training_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*) AS count
        FROM registrations
        WHERE training_id = ?
    """, (training_id,))

    result = cur.fetchone()
    conn.close()

    return result["count"]


def is_registered(user_id, training_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id
        FROM registrations
        WHERE user_id = ?
          AND training_id = ?
    """, (
        user_id,
        training_id
    ))

    result = cur.fetchone()
    conn.close()

    return result is not None


def get_trainings_for_period(start_date, end_date, category=None):
    conn = get_db()
    cur = conn.cursor()

    if category:
        cur.execute("""
            SELECT *
            FROM trainings
            WHERE date >= ?
              AND date <= ?
              AND category = ?
            ORDER BY date, time_start
        """, (
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d"),
            category
        ))
    else:
        cur.execute("""
            SELECT *
            FROM trainings
            WHERE date >= ?
              AND date <= ?
            ORDER BY date, time_start
        """, (
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d")
        ))

    rows = cur.fetchall()
    conn.close()

    result = []

    current_time = now_local()

    for row in rows:
        dt = training_datetime(row)

        # Не показываем уже начавшиеся/прошедшие тренировки.
        if dt <= current_time:
            continue

        result.append(row)

    return result


def get_trainings_for_week(category=None):
    start_date = today_local()
    end_date = start_date + timedelta(days=6)

    return get_trainings_for_period(
        start_date,
        end_date,
        category
    )


def get_trainings_for_day(category, weekday):
    start_date = today_local()
    end_date = start_date + timedelta(days=6)

    trainings = get_trainings_for_period(
        start_date,
        end_date,
        category
    )

    result = []

    for training in trainings:
        dt = datetime.strptime(
            training["date"],
            "%Y-%m-%d"
        )

        if dt.weekday() == weekday:
            result.append(training)

    return result


# ============================================================
# КНОПКИ ТРЕНИРОВОК
# ============================================================

def short_training_label(training):
    """
    Формируем ОДИНАКОВУЮ строку для кнопки и словаря.
    Поэтому нажатие никогда не потеряется из-за разного текста.
    """

    date = datetime.strptime(
        training["date"],
        "%Y-%m-%d"
    ).strftime("%d.%m")

    label = (
        f"{date} {training['time_start']} "
        f"{training['level']}"
    )

    # VK ограничивает длину текста кнопки.
    if len(label) > 40:
        label = label[:40]

    return label


def short_my_training_label(training):
    date = datetime.strptime(
        training["date"],
        "%Y-%m-%d"
    ).strftime("%d.%m")

    label = (
        f"{date} {training['time_start']} "
        f"{training['category']}"
    )

    if len(label) > 40:
        label = label[:40]

    return label


# ============================================================
# ФОРМАТ ТРЕНИРОВКИ
# ============================================================

def training_text(training, user_id=None):
    date_obj = datetime.strptime(
        training["date"],
        "%Y-%m-%d"
    )

    date_text = date_obj.strftime("%d.%m.%Y")
    weekday = WEEKDAYS[date_obj.weekday()]

    count = participant_count(training["id"])
    places = max(training["capacity"] - count, 0)

    text = (
        f"🏐 {weekday}, {date_text}\n"
        f"⏰ {training['time_start']}–{training['time_end']}\n\n"
        f"Формат: {training['format']}\n"
        f"Возраст: {training['age']}\n"
        f"Уровень: {training['level']}\n"
        f"Тренер: {training['coach']}\n"
        f"💰 Стоимость: {training['price']} ₽\n"
        f"👥 Мест свободно: {places} из {training['capacity']}\n"
    )

    if user_id is not None:
        if is_registered(user_id, training["id"]):
            text += "\n✅ Вы уже записаны на эту тренировку."

    return text


# ============================================================
# ПОКАЗ РАСПИСАНИЯ
# ============================================================

def show_week_schedule(user_id, category=None):
    trainings = get_trainings_for_week(category)

    if not trainings:
        send_message(
            user_id,
            "📅 На ближайшие 7 дней подходящих тренировок нет.",
            main_menu(user_id)
        )
        return

    title = "📅 Расписание на ближайшие 7 дней"

    if category == "Дети":
        title += "\n👦 Детские группы"
    elif category == "Взрослые":
        title += "\n👨 Взрослые группы"

    lines = [title, ""]

    current_date = None

    for training in trainings:
        if training["date"] != current_date:
            current_date = training["date"]

            date_obj = datetime.strptime(
                current_date,
                "%Y-%m-%d"
            )

            lines.append(
                f"📌 {WEEKDAYS[date_obj.weekday()]} "
                f"{date_obj.strftime('%d.%m')}"
            )

        count = participant_count(training["id"])
        places = max(training["capacity"] - count, 0)

        lines.append(
            f"• {training['time_start']}–{training['time_end']} — "
            f"{training['format']}, {training['level']}\n"
            f"  {training['age']} · {training['coach']} · "
            f"{training['price']} ₽ · мест: {places}"
        )

    send_message(
        user_id,
        "\n".join(lines),
        main_menu(user_id)
    )


# ============================================================
# ЗАПИСЬ
# ============================================================

def show_booking_category(user_id):
    set_state(
        user_id,
        "booking_category",
        admin_mode=False
    )

    send_message(
        user_id,
        "🏐 На какую тренировку хотите записаться?",
        category_keyboard()
    )


def show_booking_days(user_id, category):
    set_state(
        user_id,
        "booking_day",
        category=category,
        admin_mode=False
    )

    send_message(
        user_id,
        f"Выбрано: {category}\n\n"
        f"Выберите день:",
        booking_days_keyboard()
    )


def show_booking_trainings(user_id, category, weekday):
    trainings = get_trainings_for_day(
        category,
        weekday
    )

    if not trainings:
        send_message(
            user_id,
            "На выбранный день подходящих тренировок нет.",
            booking_days_keyboard()
        )
        return

    rows = []
    mapping = {}

    for training in trainings:
        label = short_training_label(training)

        rows.append([
            button(label, "primary")
        ])

        mapping[label] = training["id"]

    rows.append([
        button("◀️ Назад", "secondary")
    ])

    set_state(
        user_id,
        "booking_training",
        category=category,
        weekday=weekday,
        training_map=mapping,
        admin_mode=False
    )

    send_message(
        user_id,
        f"🏐 {WEEKDAYS[weekday]}\n\n"
        f"Выберите тренировку:",
        keyboard(rows)
    )


def show_training_for_booking(user_id, training_id):
    training = get_training_by_id(training_id)

    if not training:
        send_message(
            user_id,
            "❌ Тренировка не найдена.",
            main_menu(user_id)
        )
        return

    text = training_text(training, user_id)

    count = participant_count(training_id)

    if is_registered(user_id, training_id):
        send_message(
            user_id,
            text + "\n\nВы уже записаны.",
            keyboard([
                [button("◀️ Главное меню", "secondary")]
            ])
        )
        return

    if count >= training["capacity"]:
        send_message(
            user_id,
            text + "\n\n❌ Свободных мест нет.",
            keyboard([
                [button("◀️ К тренировкам", "secondary")],
                [button("🏠 Главное меню", "secondary")]
            ])
        )
        return

    send_message(
        user_id,
        text + "\n\n"
        "Записаться на эту тренировку?",
        keyboard([
            [
                button("✅ Записаться", "positive")
            ],
            [
                button("◀️ Назад", "secondary")
            ]
        ])
    )

    set_state(
        user_id,
        "confirm_booking",
        training_id=training_id,
        admin_mode=False
    )


def register_user(user_id, training_id):
    training = get_training_by_id(training_id)

    if not training:
        return False, "Тренировка не найдена."

    if is_registered(user_id, training_id):
        return False, "Вы уже записаны на эту тренировку."

    count = participant_count(training_id)

    if count >= training["capacity"]:
        return False, "К сожалению, свободных мест больше нет."

    if training_datetime(training) <= now_local():
        return False, "Эта тренировка уже началась или прошла."

    conn = get_db()
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO registrations (
                user_id,
                training_id,
                created_at
            )
            VALUES (?, ?, ?)
        """, (
            user_id,
            training_id,
            now_local().isoformat()
        ))

        conn.commit()

    except sqlite3.IntegrityError:
        conn.rollback()
        conn.close()
        return False, "Вы уже записаны на эту тренировку."

    conn.close()

    notify_admins_about_registration(
        user_id,
        training
    )

    return True, "Запись успешно создана."


# ============================================================
# МОИ ТРЕНИРОВКИ
# ============================================================

def get_user_trainings(user_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT t.*
        FROM trainings t
        JOIN registrations r
          ON r.training_id = t.id
        WHERE r.user_id = ?
        ORDER BY t.date, t.time_start
    """, (user_id,))

    rows = cur.fetchall()
    conn.close()

    current_time = now_local()

    result = []

    for row in rows:
        if training_datetime(row) > current_time:
            result.append(row)

    return result


def show_my_trainings(user_id):
    trainings = get_user_trainings(user_id)

    if not trainings:
        send_message(
            user_id,
            "👤 У вас пока нет предстоящих тренировок.",
            main_menu(user_id)
        )
        return

    rows = []
    mapping = {}

    for training in trainings:
        label = short_my_training_label(training)

        rows.append([
            button(label, "primary")
        ])

        mapping[label] = training["id"]

    rows.append([
        button("🏠 Главное меню", "secondary")
    ])

    set_state(
        user_id,
        "my_training",
        training_map=mapping,
        admin_mode=False
    )

    send_message(
        user_id,
        "👤 Ваши предстоящие тренировки:\n\n"
        "Выберите тренировку:",
        keyboard(rows)
    )


def show_my_training_details(user_id, training_id):
    training = get_training_by_id(training_id)

    if not training or not is_registered(user_id, training_id):
        send_message(
            user_id,
            "❌ Запись не найдена.",
            main_menu(user_id)
        )
        return

    send_message(
        user_id,
        training_text(training, user_id) +
        "\n\nВы можете отменить запись.",
        keyboard([
            [
                button("❌ Отменить запись", "negative")
            ],
            [
                button("◀️ Назад", "secondary")
            ]
        ])
    )

    set_state(
        user_id,
        "my_training_details",
        training_id=training_id,
        admin_mode=False
    )


# ============================================================
# ОТМЕНА
# ============================================================

def can_cancel(training):
    start = training_datetime(training)
    difference = start - now_local()

    return difference.total_seconds() >= 24 * 60 * 60


def cancel_registration(user_id, training_id):
    training = get_training_by_id(training_id)

    if not training:
        return False, "Тренировка не найдена."

    if not is_registered(user_id, training_id):
        return False, "Вы не записаны на эту тренировку."

    if not can_cancel(training):
        return (
            False,
            "❌ Отменить запись уже нельзя.\n\n"
            "До начала тренировки осталось меньше 24 часов."
        )

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM registrations
        WHERE user_id = ?
          AND training_id = ?
    """, (
        user_id,
        training_id
    ))

    conn.commit()
    conn.close()

    notify_admins_about_cancellation(
        user_id,
        training
    )

    return True, "Запись отменена."


# ============================================================
# УВЕДОМЛЕНИЯ АДМИНАМ
# ============================================================

def notify_admins_about_registration(user_id, training):
    count = participant_count(training["id"])

    text = (
        "🏐 Новая запись\n\n"
        f"ID пользователя: {user_id}\n"
        f"Дата: {training['date']}\n"
        f"Время: {training['time_start']}–{training['time_end']}\n"
        f"Категория: {training['category']}\n"
        f"Формат: {training['format']}\n"
        f"Уровень: {training['level']}\n"
        f"Тренер: {training['coach']}\n"
        f"Участников: {count}/{training['capacity']}"
    )

    for admin_id in ADMIN_IDS:
        send_message(admin_id, text)


def notify_admins_about_cancellation(user_id, training):
    text = (
        "❌ Отмена записи\n\n"
        f"ID пользователя: {user_id}\n"
        f"Дата: {training['date']}\n"
        f"Время: {training['time_start']}–{training['time_end']}\n"
        f"Категория: {training['category']}"
    )

    for admin_id in ADMIN_IDS:
        send_message(admin_id, text)


def forward_to_admins(title, user_id, message):
    text = (
        f"{title}\n\n"
        f"ID пользователя: {user_id}\n\n"
        f"{message}"
    )

    for admin_id in ADMIN_IDS:
        send_message(admin_id, text)


# ============================================================
# ЦЕНЫ / ЛОКАЦИЯ
# ============================================================

def show_prices(user_id):
    text = (
        "💰 ЦЕНЫ\n\n"
        "👦 Дети\n"
        "600 ₽ за тренировку.\n\n"
        "👨 Взрослые\n"
        "1–6 человек — 1200 ₽ с человека.\n"
        "7 и более человек — 1000 ₽ с человека.\n\n"
        "Минимальный размер взрослой группы — "
        "4 человека."
    )

    send_message(
        user_id,
        text,
        main_menu(user_id)
    )


def show_location(user_id):
    text = (
        "📍 ГДЕ ТРЕНИРУЕМСЯ\n\n"
        "☀️ Летом\n"
        "Парк Гагарина.\n\n"
        "❄️ Зимой\n"
        "СК «Арена»\n"
        "ул. Молодогвардейцев, 7\n\n"
        "Тренировки проходят на песке."
    )

    send_message(
        user_id,
        text,
        main_menu(user_id)
    )


# ============================================================
# ИНДИВИДУАЛЬНАЯ ТРЕНИРОВКА
# ============================================================

def start_individual(user_id):
    set_state(
        user_id,
        "individual_request",
        admin_mode=False
    )

    send_message(
        user_id,
        "🎯 Индивидуальная тренировка\n\n"
        "Напишите удобный день, примерное время "
        "и любую дополнительную информацию.\n\n"
        "Например:\n"
        "«Хочу индивидуальную тренировку во вторник "
        "после 18:00, хочу поработать над атакой».",
        back_keyboard()
    )


# ============================================================
# ВОПРОС
# ============================================================

def start_question(user_id):
    set_state(
        user_id,
        "question",
        admin_mode=False
    )

    send_message(
        user_id,
        "❓ Напишите ваш вопрос одним сообщением.\n\n"
        "Мы передадим его тренеру.",
        back_keyboard()
    )


# ============================================================
# АДМИНКА
# ============================================================

def show_admin_panel(user_id):
    if user_id not in ADMIN_IDS:
        send_message(
            user_id,
            "Доступ запрещён.",
            main_menu(user_id)
        )
        return

    enter_admin_mode(user_id)

    send_message(
        user_id,
        "⚙️ АДМИН-ПАНЕЛЬ\n\n"
        "Выберите действие:",
        admin_menu_keyboard()
    )


def admin_schedule(user_id):
    if user_id not in ADMIN_IDS:
        return

    trainings = get_trainings_for_week()

    if not trainings:
        send_message(
            user_id,
            "📋 На ближайшие 7 дней тренировок нет.",
            admin_menu_keyboard()
        )
        return

    lines = ["📋 РАСПИСАНИЕ", ""]

    current_date = None

    for training in trainings:
        if training["date"] != current_date:
            current_date = training["date"]

            date_obj = datetime.strptime(
                current_date,
                "%Y-%m-%d"
            )

            lines.append(
                f"📌 {WEEKDAYS[date_obj.weekday()]} "
                f"{date_obj.strftime('%d.%m')}"
            )

        count = participant_count(training["id"])

        lines.append(
            f"• {training['time_start']}–{training['time_end']} | "
            f"{training['category']} | "
            f"{training['format']} | "
            f"{training['level']} | "
            f"{count}/{training['capacity']}"
        )

    send_message(
        user_id,
        "\n".join(lines),
        admin_menu_keyboard()
    )


def admin_registrations(user_id):
    if user_id not in ADMIN_IDS:
        return

    trainings = get_trainings_for_week()

    if not trainings:
        send_message(
            user_id,
            "👥 На ближайшие 7 дней записей нет.",
            admin_menu_keyboard()
        )
        return

    lines = ["👥 ЗАПИСИ НА ТРЕНИРОВКИ", ""]

    has_registrations = False

    for training in trainings:
        participants = get_participants(training["id"])

        if not participants:
            continue

        has_registrations = True

        date_obj = datetime.strptime(
            training["date"],
            "%Y-%m-%d"
        )

        lines.append(
            f"📌 {date_obj.strftime('%d.%m')} "
            f"{training['time_start']}–{training['time_end']}"
        )

        lines.append(
            f"{training['category']} · "
            f"{training['format']} · "
            f"{training['level']}"
        )

        for number, participant_id in enumerate(
            participants,
            start=1
        ):
            lines.append(
                f"{number}. ID {participant_id}"
            )

        lines.append("")

    if not has_registrations:
        lines.append("Пока никто не записан.")

    send_message(
        user_id,
        "\n".join(lines),
        admin_menu_keyboard()
    )


def admin_info(user_id):
    if user_id not in ADMIN_IDS:
        return

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) AS count FROM users")
    users_count = cur.fetchone()["count"]

    cur.execute("""
        SELECT COUNT(*) AS count
        FROM registrations r
        JOIN trainings t ON t.id = r.training_id
        WHERE t.date >= ?
    """, (
        today_local().strftime("%Y-%m-%d"),
    ))

    registrations_count = cur.fetchone()["count"]

    cur.execute("""
        SELECT COUNT(*) AS count
        FROM trainings
        WHERE date >= ?
          AND date <= ?
    """, (
        today_local().strftime("%Y-%m-%d"),
        (today_local() + timedelta(days=6)).strftime("%Y-%m-%d")
    ))

    trainings_count = cur.fetchone()["count"]

    conn.close()

    text = (
        "📊 ОБЩАЯ ИНФОРМАЦИЯ\n\n"
        f"👤 Пользователей в базе: {users_count}\n"
        f"🏐 Тренировок на 7 дней: {trainings_count}\n"
        f"📝 Предстоящих записей: {registrations_count}"
    )

    send_message(
        user_id,
        text,
        admin_menu_keyboard()
    )


# ============================================================
# ДОБАВЛЕНИЕ ТРЕНИРОВКИ АДМИНОМ
# ============================================================

def start_add_training(user_id):
    set_state(
        user_id,
        "admin_add_date",
        admin_mode=True
    )

    send_message(
        user_id,
        "➕ ДОБАВЛЕНИЕ ТРЕНИРОВКИ\n\n"
        "Шаг 1/7\n"
        "Введите дату в формате:\n"
        "ДД.ММ.ГГГГ\n\n"
        "Например: 15.10.2026",
        back_keyboard()
    )


def process_add_training(user_id, text):
    state = get_state(user_id)
    current_state = state.get("state")

    if text == "◀️ Назад":
        show_admin_panel(user_id)
        return

    if current_state == "admin_add_date":
        try:
            date_obj = datetime.strptime(
                text.strip(),
                "%d.%m.%Y"
            )

            if date_obj.date() < today_local():
                send_message(
                    user_id,
                    "❌ Дата уже прошла.\n\n"
                    "Введите будущую дату.",
                    back_keyboard()
                )
                return

            set_state(
                user_id,
                "admin_add_start",
                admin_mode=True,
                add_date=date_obj.strftime("%Y-%m-%d")
            )

            send_message(
                user_id,
                "Шаг 2/7\n"
                "Введите время начала.\n\n"
                "Например: 19:00",
                back_keyboard()
            )

        except ValueError:
            send_message(
                user_id,
                "❌ Неверный формат.\n\n"
                "Введите дату так:\n"
                "15.10.2026",
                back_keyboard()
            )

        return

    if current_state == "admin_add_start":
        try:
            datetime.strptime(
                text.strip(),
                "%H:%M"
            )

            set_state(
                user_id,
                "admin_add_end",
                admin_mode=True,
                add_start=text.strip()
            )

            send_message(
                user_id,
                "Шаг 3/7\n"
                "Введите время окончания.\n\n"
                "Например: 20:30",
                back_keyboard()
            )

        except ValueError:
            send_message(
                user_id,
                "❌ Неверное время.\n\n"
                "Например: 19:00",
                back_keyboard()
            )

        return

    if current_state == "admin_add_end":
        try:
            datetime.strptime(
                text.strip(),
                "%H:%M"
            )

            set_state(
                user_id,
                "admin_add_category",
                admin_mode=True,
                add_end=text.strip()
            )

            send_message(
                user_id,
                "Шаг 4/7\n"
                "Введите категорию:\n\n"
                "Дети\n"
                "или\n"
                "Взрослые",
                back_keyboard()
            )

        except ValueError:
            send_message(
                user_id,
                "❌ Неверное время.",
                back_keyboard()
            )

        return

    if current_state == "admin_add_category":
        if text not in ("Дети", "Взрослые"):
            send_message(
                user_id,
                "Введите только:\n"
                "Дети\n"
                "или\n"
                "Взрослые",
                back_keyboard()
            )
            return

        set_state(
            user_id,
            "admin_add_age",
            admin_mode=True,
            add_category=text
        )

        send_message(
            user_id,
            "Шаг 5/7\n"
            "Введите возраст.\n\n"
            "Например:\n"
            "11–14 лет\n"
            "18+",
            back_keyboard()
        )

        return

    if current_state == "admin_add_age":
        set_state(
            user_id,
            "admin_add_format",
            admin_mode=True,
            add_age=text.strip()
        )

        send_message(
            user_id,
            "Шаг 6/7\n"
            "Введите формат и уровень через |.\n\n"
            "Например:\n"
            "Группа | Средний\n\n"
            "Или:\n"
            "MIXED | Средний+",
            back_keyboard()
        )

        return

    if current_state == "admin_add_format":
        parts = [
            part.strip()
            for part in text.split("|")
        ]

        if len(parts) != 2:
            send_message(
                user_id,
                "❌ Нужно два значения через |.\n\n"
                "Например:\n"
                "Группа | Средний",
                back_keyboard()
            )
            return

        training_format = parts[0]
        level = parts[1]

        set_state(
            user_id,
            "admin_add_details",
            admin_mode=True,
            add_format=training_format,
            add_level=level
        )

        send_message(
            user_id,
            "Шаг 7/7\n"
            "Введите тренера, количество мест и цену через |.\n\n"
            "Например:\n"
            "Алексей | 10 | 600",
            back_keyboard()
        )

        return

    if current_state == "admin_add_details":
        parts = [
            part.strip()
            for part in text.split("|")
        ]

        if len(parts) != 3:
            send_message(
                user_id,
                "❌ Нужно три значения через |.\n\n"
                "Например:\n"
                "Алексей | 10 | 600",
                back_keyboard()
            )
            return

        coach = parts[0]

        try:
            capacity = int(parts[1])
            price = int(parts[2])

            if capacity <= 0 or price < 0:
                raise ValueError

        except ValueError:
            send_message(
                user_id,
                "❌ Количество мест и цена должны быть числами.",
                back_keyboard()
            )
            return

        state = get_state(user_id)

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO trainings (
                date,
                time_start,
                time_end,
                category,
                age,
                format,
                level,
                coach,
                capacity,
                price
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            state["add_date"],
            state["add_start"],
            state["add_end"],
            state["add_category"],
            state["add_age"],
            state["add_format"],
            state["add_level"],
            coach,
            capacity,
            price
        ))

        conn.commit()
        conn.close()

        clear_state(user_id)
        enter_admin_mode(user_id)

        send_message(
            user_id,
            "✅ Тренировка добавлена в расписание.",
            admin_menu_keyboard()
        )


# ============================================================
# ОБРАБОТКА ТЕКСТА
# ============================================================

def handle_message(user_id, text):
    save_user(user_id)

    text = (text or "").strip()

    state = get_state(user_id)
    current_state = state.get("state")

    # --------------------------------------------------------
    # АДМИНКА: добавление тренировки
    # --------------------------------------------------------

    if user_id in ADMIN_IDS and current_state in {
        "admin_add_date",
        "admin_add_start",
        "admin_add_end",
        "admin_add_category",
        "admin_add_age",
        "admin_add_format",
        "admin_add_details",
    }:
        process_add_training(user_id, text)
        return

    # --------------------------------------------------------
    # Индивидуальная тренировка
    # --------------------------------------------------------

    if current_state == "individual_request":
        if text == "◀️ Назад":
            clear_state(user_id)
            send_message(
                user_id,
                "Главное меню:",
                main_menu(user_id)
            )
            return

        forward_to_admins(
            "🎯 ЗАПРОС НА ИНДИВИДУАЛЬНУЮ ТРЕНИРОВКУ",
            user_id,
            text
        )

        clear_state(user_id)

        send_message(
            user_id,
            "✅ Запрос отправлен тренеру.\n\n"
            "Мы свяжемся с вами.",
            main_menu(user_id)
        )
        return

    # --------------------------------------------------------
    # Вопрос
    # --------------------------------------------------------

    if current_state == "question":
        if text == "◀️ Назад":
            clear_state(user_id)
            send_message(
                user_id,
                "Главное меню:",
                main_menu(user_id)
            )
            return

        forward_to_admins(
            "❓ ВОПРОС ОТ ПОЛЬЗОВАТЕЛЯ",
            user_id,
            text
        )

        clear_state(user_id)

        send_message(
            user_id,
            "✅ Вопрос отправлен.\n\n"
            "Мы постараемся ответить как можно скорее.",
            main_menu(user_id)
        )
        return

    # --------------------------------------------------------
    # АДМИН-РЕЖИМ
    # --------------------------------------------------------

    if user_id in ADMIN_IDS and is_admin_mode(user_id):

        if text == "📋 Расписание":
            admin_schedule(user_id)
            return

        if text == "👥 Записи":
            admin_registrations(user_id)
            return

        if text == "📊 Общая информация":
            admin_info(user_id)
            return

        if text == "➕ Добавить тренировку":
            start_add_training(user_id)
            return

        if text == "👤 Режим пользователя":
            enter_user_mode(user_id)

            send_message(
                user_id,
                "👤 Вы перешли в режим пользователя.\n\n"
                "Теперь бот работает как для обычного клиента.",
                main_menu(user_id)
            )
            return

        if text == "🏠 Главное меню":
            enter_user_mode(user_id)

            send_message(
                user_id,
                "Главное меню:",
                main_menu(user_id)
            )
            return

    # --------------------------------------------------------
    # ВОЗВРАТ В АДМИНКУ
    # --------------------------------------------------------

    if (
        text == "⚙️ Админ-панель"
        and user_id in ADMIN_IDS
    ):
        show_admin_panel(user_id)
        return

    # --------------------------------------------------------
    # ОБЩИЕ КНОПКИ
    # --------------------------------------------------------

    if text in ("Привет", "Начать", "/start"):
        clear_state(user_id)

        if user_id in ADMIN_IDS:
            enter_user_mode(user_id)

        send_message(
            user_id,
            "🏐 Привет!\n\n"
            "Добро пожаловать в VOLLEY WAVE.\n"
            "Выберите действие:",
            main_menu(user_id)
        )
        return

    if text == "🏐 Записаться":
        show_booking_category(user_id)
        return

    if text == "📅 Расписание":
        set_state(
            user_id,
            "schedule_category",
            admin_mode=False
        )

        send_message(
            user_id,
            "📅 Какое расписание показать?",
            category_keyboard()
        )
        return

    if text == "👤 Мои тренировки":
        show_my_trainings(user_id)
        return

    if text == "💰 Цены":
        show_prices(user_id)
        return

    if text == "📍 Где тренируемся":
        show_location(user_id)
        return

    if text == "🎯 Индивидуальная тренировка":
        start_individual(user_id)
        return

    if text == "❓ Задать вопрос":
        start_question(user_id)
        return

    # --------------------------------------------------------
    # ВЫБОР КАТЕГОРИИ ДЛЯ РАСПИСАНИЯ
    # --------------------------------------------------------

    if current_state == "schedule_category":

        if text == "👦 Дети":
            clear_state(user_id)
            show_week_schedule(user_id, "Дети")
            return

        if text == "👨 Взрослые":
            clear_state(user_id)
            show_week_schedule(user_id, "Взрослые")
            return

        if text == "◀️ Назад":
            clear_state(user_id)

            send_message(
                user_id,
                "Главное меню:",
                main_menu(user_id)
            )
            return

    # --------------------------------------------------------
    # ВЫБОР КАТЕГОРИИ ДЛЯ ЗАПИСИ
    # --------------------------------------------------------

    if current_state == "booking_category":

        if text == "👦 Дети":
            show_booking_days(user_id, "Дети")
            return

        if text == "👨 Взрослые":
            show_booking_days(user_id, "Взрослые")
            return

        if text == "◀️ Назад":
            clear_state(user_id)

            send_message(
                user_id,
                "Главное меню:",
                main_menu(user_id)
            )
            return

    # --------------------------------------------------------
    # ВЫБОР ДНЯ
    # --------------------------------------------------------

    if current_state == "booking_day":

        weekdays = {
            "Пн": 0,
            "Вт": 1,
            "Ср": 2,
            "Чт": 3,
            "Пт": 4,
        }

        if text in weekdays:
            show_booking_trainings(
                user_id,
                state["category"],
                weekdays[text]
            )
            return

        if text == "◀️ Назад":
            show_booking_category(user_id)
            return

    # --------------------------------------------------------
    # ВЫБОР ТРЕНИРОВКИ
    # --------------------------------------------------------

    if current_state == "booking_training":

        if text == "◀️ Назад":
            show_booking_days(
                user_id,
                state["category"]
            )
            return

        training_map = state.get(
            "training_map",
            {}
        )

        training_id = training_map.get(text)

        if training_id:
            show_training_for_booking(
                user_id,
                training_id
            )
            return

    # --------------------------------------------------------
    # ПОДТВЕРЖДЕНИЕ ЗАПИСИ
    # --------------------------------------------------------

    if current_state == "confirm_booking":

        training_id = state.get("training_id")

        if text == "✅ Записаться":
            success, message = register_user(
                user_id,
                training_id
            )

            if success:
                training = get_training_by_id(
                    training_id
                )

                clear_state(user_id)

                send_message(
                    user_id,
                    "✅ Вы записаны!\n\n" +
                    training_text(
                        training,
                        user_id
                    ),
                    main_menu(user_id)
                )
            else:
                send_message(
                    user_id,
                    f"❌ {message}",
                    main_menu(user_id)
                )

            return

        if text == "◀️ Назад":
            show_booking_category(user_id)
            return

    # --------------------------------------------------------
    # МОИ ТРЕНИРОВКИ
    # --------------------------------------------------------

    if current_state == "my_training":

        if text == "🏠 Главное меню":
            clear_state(user_id)

            send_message(
                user_id,
                "Главное меню:",
                main_menu(user_id)
            )
            return

        training_map = state.get(
            "training_map",
            {}
        )

        training_id = training_map.get(text)

        if training_id:
            show_my_training_details(
                user_id,
                training_id
            )
            return

    # --------------------------------------------------------
    # ДЕТАЛИ МОЕЙ ТРЕНИРОВКИ
    # --------------------------------------------------------

    if current_state == "my_training_details":

        training_id = state.get("training_id")

        if text == "❌ Отменить запись":
            success, message = cancel_registration(
                user_id,
                training_id
            )

            if success:
                clear_state(user_id)

                send_message(
                    user_id,
                    "✅ " + message,
                    main_menu(user_id)
                )
            else:
                send_message(
                    user_id,
                    message,
                    keyboard([
                        [
                            button("◀️ Назад", "secondary")
                        ]
                    ])
                )

            return

        if text == "◀️ Назад":
            show_my_trainings(user_id)
            return

    # --------------------------------------------------------
    # ЕСЛИ НЕ НАШЛИ КОМАНДУ
    # --------------------------------------------------------

    send_message(
        user_id,
        "Я пока не понял эту команду 🙂\n\n"
        "Выберите действие из меню:",
        main_menu(user_id)
    )


# ============================================================
# CALLBACK API
# ============================================================

@app.route("/callback", methods=["POST"])
def callback():

    print("🔥 CALLBACK REACHED", flush=True)

    data = request.get_json(
        silent=True
    ) or {}

    # Не выводим секреты в лог.
    safe_data = dict(data)

    if "secret" in safe_data:
        safe_data["secret"] = "***"

    print(
        "🔥 CALLBACK TYPE:",
        safe_data.get("type"),
        flush=True
    )

    # Проверка secret, если он используется.
    if VK_SECRET_KEY:
        received_secret = data.get("secret")

        if received_secret != VK_SECRET_KEY:
            print(
                "❌ SECRET KEY MISMATCH",
                flush=True
            )
            return "ok"

    event_type = data.get("type")

    # --------------------------------------------------------
    # CONFIRMATION
    # --------------------------------------------------------

    if event_type == "confirmation":
        print(
            "🔥 CONFIRMATION REQUEST",
            flush=True
        )

        return VK_CONFIRMATION_TOKEN

    # --------------------------------------------------------
    # MESSAGE NEW
    # --------------------------------------------------------

    if event_type == "message_new":

        obj = data.get(
            "object",
            {}
        )

        if not isinstance(obj, dict):
            print(
                "❌ OBJECT IS NOT DICT",
                flush=True
            )
            return "ok"

        # VK API 5.199:
        #
        # object
        #   └── message
        #         ├── from_id
        #         └── text

        message = obj.get(
            "message",
            {}
        )

        if not isinstance(message, dict):
            message = {}

        user_id = (
            message.get("from_id")
            or obj.get("from_id")
        )

        text = (
            message.get("text")
            or obj.get("text")
            or ""
        )

        print(
            "🔥 PARSED USER ID:",
            user_id,
            flush=True
        )

        print(
            "🔥 PARSED TEXT:",
            repr(text),
            flush=True
        )

        if not user_id:
            print(
                "❌ USER ID NOT FOUND",
                flush=True
            )
            return "ok"

        try:
            handle_message(
                int(user_id),
                text
            )

        except Exception as e:
            print(
                "❌ HANDLE MESSAGE ERROR:",
                repr(e),
                flush=True
            )

            # Пользователю отправляем безопасное сообщение.
            try:
                send_message(
                    int(user_id),
                    "Произошла техническая ошибка.\n"
                    "Попробуйте ещё раз через несколько секунд.",
                    main_menu(int(user_id))
                )
            except Exception as send_error:
                print(
                    "❌ ERROR MESSAGE SEND FAILED:",
                    repr(send_error),
                    flush=True
                )

        return "ok"

    return "ok"


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/", methods=["GET"])
def index():
    return "VOLLEY WAVE VK BOT is running"


# ============================================================
# ЗАПУСК
# ============================================================

init_db()
seed_schedule()


if __name__ == "__main__":
    port = int(
        os.getenv(
            "PORT",
            "10000"
        )
    )

    print(
        "🏐 VOLLEY WAVE VK BOT STARTED",
        flush=True
    )

    print(
        f"📍 VK GROUP ID: {GROUP_ID}",
        flush=True
    )

    print(
        f"🕐 TIMEZONE: {LOCAL_TZ}",
        flush=True
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
