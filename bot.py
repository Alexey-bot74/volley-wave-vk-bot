import os
import sqlite3
import requests
import random
import threading
from datetime import datetime, timedelta

from flask import Flask, request

# ============================================================
# НАСТРОЙКИ
# ============================================================

VK_TOKEN = os.getenv("VK_TOKEN")
VK_SECRET_KEY = os.getenv("VK_SECRET_KEY")
VK_CONFIRMATION_TOKEN = os.getenv("VK_CONFIRMATION_TOKEN")

VK_API_VERSION = "5.199"

GROUP_ID = 221776135

ADMINS = {
    87984447,
    172892670,
    148372158,
}

DATABASE = "volley_wave.db"

app = Flask(__name__)

db_lock = threading.Lock()

# Состояние пользователей
user_states = {}

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

SCHEDULE_TEMPLATE = [
    {
        "weekday": 0,
        "start": "09:00",
        "end": "11:00",
        "category": "children",
        "age": "9–13 лет",
        "format": "Группа",
        "level": "Начальный / средний",
        "coach": "Алексей",
        "capacity": 10,
        "price": 600,
    },
    {
        "weekday": 0,
        "start": "17:00",
        "end": "19:00",
        "category": "children",
        "age": "11–14 лет",
        "format": "Группа",
        "level": "Средний",
        "coach": "Алексей",
        "capacity": 10,
        "price": 600,
    },
    {
        "weekday": 0,
        "start": "19:00",
        "end": "20:30",
        "category": "adults",
        "age": "18+",
        "format": "Группа",
        "level": "Техничка",
        "coach": "Алексей",
        "capacity": 10,
        "price": 1200,
    },

    {
        "weekday": 1,
        "start": "09:00",
        "end": "11:00",
        "category": "adults",
        "age": "18+",
        "format": "Группа",
        "level": "Общая",
        "coach": "Алексей",
        "capacity": 8,
        "price": 1200,
    },
    {
        "weekday": 1,
        "start": "17:00",
        "end": "18:30",
        "category": "children",
        "age": "11–14 лет",
        "format": "Группа",
        "level": "Средний",
        "coach": "Алексей",
        "capacity": 10,
        "price": 600,
    },
    {
        "weekday": 1,
        "start": "19:30",
        "end": "21:00",
        "category": "adults",
        "age": "18+",
        "format": "Группа",
        "level": "Женская, средний+",
        "coach": "Алексей",
        "capacity": 8,
        "price": 1200,
    },

    {
        "weekday": 2,
        "start": "09:00",
        "end": "11:00",
        "category": "children",
        "age": "9–14 лет",
        "format": "Группа",
        "level": "Начальный / средний",
        "coach": "Алексей",
        "capacity": 10,
        "price": 600,
    },
    {
        "weekday": 2,
        "start": "17:00",
        "end": "18:00",
        "category": "children",
        "age": "5–9 лет",
        "format": "Группа",
        "level": "Начальный",
        "coach": "Ксения",
        "capacity": 10,
        "price": 600,
    },
    {
        "weekday": 2,
        "start": "18:00",
        "end": "19:30",
        "category": "adults",
        "age": "18+",
        "format": "Группа",
        "level": "Продвинутый",
        "coach": "Алексей",
        "capacity": 8,
        "price": 1200,
    },
    {
        "weekday": 2,
        "start": "19:30",
        "end": "21:00",
        "category": "adults",
        "age": "18+",
        "format": "MIXED",
        "level": "Средний+",
        "coach": "Алексей",
        "capacity": 8,
        "price": 1200,
    },

    {
        "weekday": 3,
        "start": "09:00",
        "end": "11:00",
        "category": "adults",
        "age": "18+",
        "format": "Группа",
        "level": "Общая",
        "coach": "Алексей",
        "capacity": 8,
        "price": 1200,
    },
    {
        "weekday": 3,
        "start": "17:00",
        "end": "19:00",
        "category": "children",
        "age": "11–14 лет",
        "format": "Группа",
        "level": "Средний",
        "coach": "Алексей",
        "capacity": 10,
        "price": 600,
    },
    {
        "weekday": 3,
        "start": "19:00",
        "end": "20:30",
        "category": "adults",
        "age": "18+",
        "format": "Группа",
        "level": "Средний",
        "coach": "Алексей",
        "capacity": 8,
        "price": 1200,
    },

    {
        "weekday": 4,
        "start": "09:00",
        "end": "11:00",
        "category": "children",
        "age": "9–14 лет",
        "format": "Группа",
        "level": "Начальный / средний",
        "coach": "Алексей",
        "capacity": 10,
        "price": 600,
    },
    {
        "weekday": 4,
        "start": "17:00",
        "end": "18:00",
        "category": "children",
        "age": "5–10 лет",
        "format": "Группа",
        "level": "Начальный",
        "coach": "Ксения",
        "capacity": 10,
        "price": 600,
    },
    {
        "weekday": 4,
        "start": "17:00",
        "end": "19:00",
        "category": "children",
        "age": "11–14 лет",
        "format": "Группа",
        "level": "Средний",
        "coach": "Алексей",
        "capacity": 10,
        "price": 600,
    },
    {
        "weekday": 4,
        "start": "19:00",
        "end": "20:30",
        "category": "adults",
        "age": "18+",
        "format": "Группа",
        "level": "Техничка",
        "coach": "Алексей",
        "capacity": 10,
        "price": 1200,
    },
]


# ============================================================
# БАЗА ДАННЫХ
# ============================================================

def get_db():
    conn = sqlite3.connect(
        DATABASE,
        check_same_thread=False
    )
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db_lock:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                name TEXT,
                phone TEXT,
                created_at TEXT
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS trainings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                category TEXT NOT NULL,
                age TEXT,
                format TEXT,
                level TEXT,
                coach TEXT,
                capacity INTEGER DEFAULT 10,
                price INTEGER DEFAULT 0,
                active INTEGER DEFAULT 1
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                training_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(user_id, training_id)
            )
            """
        )

        conn.commit()
        conn.close()

    seed_schedule()


def seed_schedule():
    """
    Создаёт расписание на ближайшие 14 дней,
    если его там ещё нет.
    """

    with db_lock:
        conn = get_db()
        cursor = conn.cursor()

        today = datetime.now().date()

        for offset in range(14):
            current_date = today + timedelta(days=offset)

            for item in SCHEDULE_TEMPLATE:
                if current_date.weekday() != item["weekday"]:
                    continue

                date_string = current_date.isoformat()

                cursor.execute(
                    """
                    SELECT id
                    FROM trainings
                    WHERE date = ?
                    AND start_time = ?
                    AND category = ?
                    AND active = 1
                    """,
                    (
                        date_string,
                        item["start"],
                        item["category"],
                    )
                )

                exists = cursor.fetchone()

                if exists:
                    continue

                cursor.execute(
                    """
                    INSERT INTO trainings (
                        date,
                        start_time,
                        end_time,
                        category,
                        age,
                        format,
                        level,
                        coach,
                        capacity,
                        price,
                        active
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                    """,
                    (
                        date_string,
                        item["start"],
                        item["end"],
                        item["category"],
                        item["age"],
                        item["format"],
                        item["level"],
                        item["coach"],
                        item["capacity"],
                        item["price"],
                    )
                )

        conn.commit()
        conn.close()


# ============================================================
# VK API
# ============================================================

def vk_api(method, params):
    url = f"https://api.vk.com/method/{method}"

    params = dict(params)
    params["access_token"] = VK_TOKEN
    params["v"] = VK_API_VERSION

    try:
        response = requests.post(
            url,
            data=params,
            timeout=15
        )

        data = response.json()

        if "error" in data:
            print(
                "VK ERROR:",
                data["error"],
                flush=True
            )

        return data

    except Exception as error:
        print(
            "VK REQUEST ERROR:",
            repr(error),
            flush=True
        )

        return {}


def send_message(user_id, text, keyboard=None):
    print(
        f"SEND MESSAGE -> user_id={user_id}, text={text[:100]!r}",
        flush=True
    )

    params = {
        "user_id": user_id,
        "random_id": random.randint(
            1,
            2147483647
        ),
        "message": text,
    }

    if keyboard is not None:
        params["keyboard"] = keyboard

    return vk_api(
        "messages.send",
        params
    )


# ============================================================
# КЛАВИАТУРЫ
# ============================================================

def keyboard(buttons, inline=False):
    rows = []

    for row in buttons:
        rows.append(
            [
                {
                    "action": {
                        "type": "text",
                        "label": label
                    },
                    "color": color
                }
                for label, color in row
            ]
        )

    return {
        "one_time": False,
        "inline": inline,
        "buttons": rows
    }


def main_keyboard(user_id):
    rows = [
        [
            ("🏐 Записаться", "positive"),
            ("📅 Расписание", "primary"),
        ],
        [
            ("👤 Мои тренировки", "primary"),
            ("💰 Цены", "primary"),
        ],
        [
            ("📍 Где тренируемся", "primary"),
            ("🎯 Индивидуальная тренировка", "primary"),
        ],
        [
            ("❓ Задать вопрос", "secondary"),
        ],
    ]

    if user_id in ADMINS:
        rows.append(
            [
                ("⚙️ Админ-панель", "secondary"),
            ]
        )

    return keyboard(rows)


def back_keyboard():
    return keyboard(
        [
            [
                ("⬅️ Назад", "secondary"),
            ],
            [
                ("🏠 Главное меню", "primary"),
            ],
        ]
    )


def category_keyboard():
    return keyboard(
        [
            [
                ("👨 Взрослые", "primary"),
                ("👶 Дети", "primary"),
            ],
            [
                ("⬅️ Назад", "secondary"),
            ],
        ]
    )


def days_keyboard():
    return keyboard(
        [
            [
                ("Понедельник", "primary"),
                ("Вторник", "primary"),
            ],
            [
                ("Среда", "primary"),
                ("Четверг", "primary"),
            ],
            [
                ("Пятница", "primary"),
            ],
            [
                ("⬅️ Назад", "secondary"),
            ],
        ]
    )


def admin_keyboard():
    return keyboard(
        [
            [
                ("➕ Добавить тренировку", "positive"),
            ],
            [
                ("📋 Расписание", "primary"),
                ("👥 Записи", "primary"),
            ],
            [
                ("👤 Режим пользователя", "primary"),
            ],
            [
                ("🏠 Главное меню", "secondary"),
            ],
        ]
    )


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def save_user(user_id, name=None, phone=None):
    with db_lock:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT user_id FROM users WHERE user_id = ?",
            (user_id,)
        )

        exists = cursor.fetchone()

        if exists:
            if name is not None:
                cursor.execute(
                    """
                    UPDATE users
                    SET name = ?
                    WHERE user_id = ?
                    """,
                    (name, user_id)
                )

            if phone is not None:
                cursor.execute(
                    """
                    UPDATE users
                    SET phone = ?
                    WHERE user_id = ?
                    """,
                    (phone, user_id)
                )

        else:
            cursor.execute(
                """
                INSERT INTO users (
                    user_id,
                    name,
                    phone,
                    created_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    user_id,
                    name,
                    phone,
                    datetime.now().isoformat()
                )
            )

        conn.commit()
        conn.close()


def get_training(training_id):
    with db_lock:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT *
            FROM trainings
            WHERE id = ?
            AND active = 1
            """,
            (training_id,)
        )

        row = cursor.fetchone()

        conn.close()

        return row


def get_training_count(training_id):
    with db_lock:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT COUNT(*) AS count
            FROM registrations
            WHERE training_id = ?
            """,
            (training_id,)
        )

        count = cursor.fetchone()["count"]

        conn.close()

        return count


def get_training_participants(training_id):
    with db_lock:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                registrations.user_id,
                users.name,
                users.phone
            FROM registrations
            LEFT JOIN users
                ON users.user_id = registrations.user_id
            WHERE registrations.training_id = ?
            ORDER BY registrations.created_at
            """,
            (training_id,)
        )

        rows = cursor.fetchall()

        conn.close()

        return rows


def get_trainings(
    category=None,
    weekday=None,
    days=7
):
    today = datetime.now().date()
    end_date = today + timedelta(days=days)

    query = """
        SELECT *
        FROM trainings
        WHERE active = 1
        AND date >= ?
        AND date <= ?
    """

    params = [
        today.isoformat(),
        end_date.isoformat(),
    ]

    if category:
        query += " AND category = ?"
        params.append(category)

    if weekday is not None:
        query += " AND CAST(strftime('%w', date) AS INTEGER) = ?"

        # SQLite:
        # Sunday = 0
        # Monday = 1
        # ...
        sqlite_weekday = (weekday + 1) % 7

        params.append(sqlite_weekday)

    query += """
        ORDER BY date, start_time
    """

    with db_lock:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            query,
            params
        )

        rows = cursor.fetchall()

        conn.close()

        return rows


def already_registered(user_id, training_id):
    with db_lock:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id
            FROM registrations
            WHERE user_id = ?
            AND training_id = ?
            """,
            (
                user_id,
                training_id
            )
        )

        row = cursor.fetchone()

        conn.close()

        return row is not None


def register_user(user_id, training_id):
    with db_lock:
        conn = get_db()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO registrations (
                    user_id,
                    training_id,
                    created_at
                )
                VALUES (?, ?, ?)
                """,
                (
                    user_id,
                    training_id,
                    datetime.now().isoformat()
                )
            )

            conn.commit()

            return True, None

        except sqlite3.IntegrityError:
            return False, "already"

        finally:
            conn.close()


def cancel_registration(user_id, training_id):
    with db_lock:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            """
            DELETE FROM registrations
            WHERE user_id = ?
            AND training_id = ?
            """,
            (
                user_id,
                training_id
            )
        )

        deleted = cursor.rowcount

        conn.commit()
        conn.close()

        return deleted > 0


def can_cancel(training):
    if not training:
        return False

    date_string = training["date"]
    start_time = training["start_time"]

    try:
        training_datetime = datetime.strptime(
            f"{date_string} {start_time}",
            "%Y-%m-%d %H:%M"
        )

    except ValueError:
        return False

    return (
        training_datetime - datetime.now()
        >= timedelta(hours=24)
    )


def format_date(date_string):
    try:
        date_object = datetime.strptime(
            date_string,
            "%Y-%m-%d"
        )

        names = [
            "Понедельник",
            "Вторник",
            "Среда",
            "Четверг",
            "Пятница",
            "Суббота",
            "Воскресенье",
        ]

        return (
            f"{names[date_object.weekday()]}, "
            f"{date_object.strftime('%d.%m')}"
        )

    except Exception:
        return date_string


def training_text(training):
    count = get_training_count(
        training["id"]
    )

    free = max(
        training["capacity"] - count,
        0
    )

    category_name = (
        "Взрослые"
        if training["category"] == "adults"
        else "Дети"
    )

    return (
        f"🏐 {format_date(training['date'])}\n"
        f"⏰ {training['start_time']}–{training['end_time']}\n\n"
        f"👤 Категория: {category_name}\n"
        f"🎯 Формат: {training['format']}\n"
        f"📊 Уровень: {training['level']}\n"
        f"🎂 Возраст: {training['age']}\n"
        f"👨‍🏫 Тренер: {training['coach']}\n"
        f"💰 Стоимость: {training['price']} ₽\n"
        f"👥 Мест свободно: {free} из {training['capacity']}"
    )


# ============================================================
# РАСПИСАНИЕ
# ============================================================

def show_schedule(user_id, category):
    category_name = (
        "взрослых"
        if category == "adults"
        else "детских"
    )

    rows = get_trainings(
        category=category,
        days=7
    )

    if not rows:
        send_message(
            user_id,
            f"📅 Расписание {category_name} тренировок пока пустое.",
            back_keyboard()
        )
        return

    message_parts = [
        f"📅 РАСПИСАНИЕ — {category_name.upper()}",
        "",
    ]

    current_date = None

    for training in rows:
        if training["date"] != current_date:
            current_date = training["date"]

            message_parts.append(
                f"📌 {format_date(current_date)}"
            )

        count = get_training_count(
            training["id"]
        )

        free = max(
            training["capacity"] - count,
            0
        )

        message_parts.append(
            f"⏰ {training['start_time']}–"
            f"{training['end_time']}"
        )

        message_parts.append(
            f"🎯 {training['format']} | "
            f"{training['level']}"
        )

        message_parts.append(
            f"🎂 {training['age']} | "
            f"👨‍🏫 {training['coach']}"
        )

        message_parts.append(
            f"👥 Свободно: {free} | "
            f"💰 {training['price']} ₽"
        )

        message_parts.append("")

    send_message(
        user_id,
        "\n".join(message_parts),
        back_keyboard()
    )


# ============================================================
# ЗАПИСЬ
# ============================================================

def show_booking_days(user_id, category):
    user_states[user_id] = {
        "state": "booking_day",
        "category": category,
    }

    send_message(
        user_id,
        "Выберите день тренировки:",
        days_keyboard()
    )


def weekday_from_text(text):
    mapping = {
        "Понедельник": 0,
        "Вторник": 1,
        "Среда": 2,
        "Четверг": 3,
        "Пятница": 4,
        "Суббота": 5,
        "Воскресенье": 6,
    }

    return mapping.get(text)


def show_booking_trainings(
    user_id,
    category,
    weekday
):
    rows = get_trainings(
        category=category,
        weekday=weekday,
        days=7
    )

    if not rows:
        send_message(
            user_id,
            "В этот день тренировок нет.",
            days_keyboard()
        )
        return

    buttons = []

    for training in rows:
        count = get_training_count(
            training["id"]
        )

        free = max(
            training["capacity"] - count,
            0
        )

        label = (
            f"{training['start_time']} "
            f"{training['format']} "
            f"{training['level']} "
            f"({free} мест)"
        )

        # VK ограничивает длину текста кнопки.
        if len(label) > 40:
            label = label[:37] + "..."

        buttons.append(
            [
                (
                    label,
                    "positive"
                )
            ]
        )

        user_states.setdefault(
            user_id,
            {}
        )

        user_states[user_id][
            f"button_{label}"
        ] = training["id"]

    user_states[user_id] = {
        "state": "booking_training",
        "category": category,
        "weekday": weekday,
        "trainings": {
            (
                f"{training['start_time']} "
                f"{training['format']} "
                f"{training['level']} "
                f"({max(training['capacity'] - get_training_count(training['id']), 0)} мест)"
            )[:40] + (
                "..."
                if len(
                    f"{training['start_time']} "
                    f"{training['format']} "
                    f"{training['level']} "
                    f"({max(training['capacity'] - get_training_count(training['id']), 0)} мест)"
                ) > 40
                else ""
            ): training["id"]
            for training in rows
        }
    }

    buttons.append(
        [
            ("⬅️ Назад", "secondary")
        ]
    )

    send_message(
        user_id,
        "Выберите тренировку:",
        keyboard(buttons)
    )


def find_training_from_button(
    user_id,
    text
):
    state = user_states.get(
        user_id,
        {}
    )

    trainings = state.get(
        "trainings",
        {}
    )

    if text in trainings:
        return trainings[text]

    return None


def show_training_for_booking(
    user_id,
    training_id
):
    training = get_training(
        training_id
    )

    if not training:
        send_message(
            user_id,
            "Эта тренировка больше недоступна.",
            main_keyboard(user_id)
        )
        return

    count = get_training_count(
        training_id
    )

    if count >= training["capacity"]:
        send_message(
            user_id,
            "❌ На эту тренировку уже нет свободных мест.",
            main_keyboard(user_id)
        )
        return

    participants = get_training_participants(
        training_id
    )

    text = training_text(
        training
    )

    text += "\n\n👥 УЖЕ ЗАПИСАНЫ:"

    if participants:
        for index, participant in enumerate(
            participants,
            start=1
        ):
            name = (
                participant["name"]
                or f"Участник {index}"
            )

            text += f"\n{index}. {name}"
    else:
        text += "\nПока никто не записан."

    text += "\n\nЗаписаться на эту тренировку?"

    user_states[user_id] = {
        "state": "confirm_booking",
        "training_id": training_id,
    }

    send_message(
        user_id,
        text,
        keyboard(
            [
                [
                    ("✅ Записаться", "positive"),
                ],
                [
                    ("⬅️ Назад", "secondary"),
                ],
            ]
        )
    )


def do_booking(
    user_id,
    training_id
):
    training = get_training(
        training_id
    )

    if not training:
        send_message(
            user_id,
            "Тренировка больше недоступна.",
            main_keyboard(user_id)
        )
        return

    if already_registered(
        user_id,
        training_id
    ):
        send_message(
            user_id,
            "Вы уже записаны на эту тренировку.",
            main_keyboard(user_id)
        )
        return

    count = get_training_count(
        training_id
    )

    if count >= training["capacity"]:
        send_message(
            user_id,
            "❌ К сожалению, все места уже заняты.",
            main_keyboard(user_id)
        )
        return

    success, error = register_user(
        user_id,
        training_id
    )

    if not success:
        if error == "already":
            send_message(
                user_id,
                "Вы уже записаны на эту тренировку.",
                main_keyboard(user_id)
            )
        else:
            send_message(
                user_id,
                "Не удалось записать вас. Попробуйте ещё раз.",
                main_keyboard(user_id)
            )

        return

    send_message(
        user_id,
        "✅ Вы успешно записаны!\n\n"
        + training_text(training),
        main_keyboard(user_id)
    )

    notify_admins_about_booking(
        user_id,
        training
    )


# ============================================================
# МОИ ТРЕНИРОВКИ
# ============================================================

def show_my_trainings(user_id):
    today = datetime.now().date().isoformat()

    with db_lock:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                trainings.*,
                registrations.id AS registration_id
            FROM registrations
            JOIN trainings
                ON trainings.id = registrations.training_id
            WHERE registrations.user_id = ?
            AND trainings.active = 1
            AND trainings.date >= ?
            ORDER BY trainings.date, trainings.start_time
            """,
            (
                user_id,
                today
            )
        )

        rows = cursor.fetchall()

        conn.close()

    if not rows:
        send_message(
            user_id,
            "👤 У вас пока нет предстоящих тренировок.",
            main_keyboard(user_id)
        )
        return

    buttons = []

    for training in rows:
        label = (
            f"{training['date'][8:10]}."
            f"{training['date'][5:7]} "
            f"{training['start_time']} "
            f"{training['level']}"
        )

        if len(label) > 40:
            label = label[:37] + "..."

        buttons.append(
            [
                (
                    label,
                    "primary"
                )
            ]
        )

    user_states[user_id] = {
        "state": "my_training",
        "trainings": {
            (
                f"{training['date'][8:10]}."
                f"{training['date'][5:7]} "
                f"{training['start_time']} "
                f"{training['level']}"
            )[:40] + (
                "..."
                if len(
                    f"{training['date'][8:10]}."
                    f"{training['date'][5:7]} "
                    f"{training['start_time']} "
                    f"{training['level']}"
                ) > 40
                else ""
            ): training["id"]
            for training in rows
        }
    }

    buttons.append(
        [
            ("⬅️ Назад", "secondary")
        ]
    )

    send_message(
        user_id,
        "👤 Ваши предстоящие тренировки:",
        keyboard(buttons)
    )


def show_my_training_details(
    user_id,
    training_id
):
    training = get_training(
        training_id
    )

    if not training:
        send_message(
            user_id,
            "Тренировка не найдена.",
            main_keyboard(user_id)
        )
        return

    if not already_registered(
        user_id,
        training_id
    ):
        send_message(
            user_id,
            "Вы больше не записаны на эту тренировку.",
            main_keyboard(user_id)
        )
        return

    if can_cancel(training):
        cancel_label = "❌ Отменить запись"
    else:
        cancel_label = "🚫 Отмена недоступна (<24 ч)"

    user_states[user_id] = {
        "state": "my_training_detail",
        "training_id": training_id,
    }

    send_message(
        user_id,
        training_text(training),
        keyboard(
            [
                [
                    (
                        cancel_label,
                        "negative"
                        if can_cancel(training)
                        else "secondary"
                    )
                ],
                [
                    ("⬅️ Назад", "secondary"),
                ],
            ]
        )
    )


def cancel_my_training(
    user_id,
    training_id
):
    training = get_training(
        training_id
    )

    if not training:
        send_message(
            user_id,
            "Тренировка не найдена.",
            main_keyboard(user_id)
        )
        return

    if not can_cancel(training):
        send_message(
            user_id,
            "🚫 Отмена записи невозможна.\n\n"
            "До начала тренировки осталось меньше 24 часов.",
            main_keyboard(user_id)
        )
        return

    success = cancel_registration(
        user_id,
        training_id
    )

    if success:
        send_message(
            user_id,
            "✅ Запись отменена.",
            main_keyboard(user_id)
        )

        notify_admins_about_cancellation(
            user_id,
            training
        )

    else:
        send_message(
            user_id,
            "Вы не были записаны на эту тренировку.",
            main_keyboard(user_id)
        )


# ============================================================
# АДМИНИСТРАТОРЫ
# ============================================================

def notify_admins_about_booking(
    user_id,
    training
):
    user_name = get_user_name(
        user_id
    )

    text = (
        "📥 НОВАЯ ЗАПИСЬ\n\n"
        f"👤 {user_name}\n"
        f"ID: {user_id}\n\n"
        f"{training_text(training)}"
    )

    for admin_id in ADMINS:
        send_message(
            admin_id,
            text
        )


def notify_admins_about_cancellation(
    user_id,
    training
):
    user_name = get_user_name(
        user_id
    )

    text = (
        "❌ ОТМЕНА ЗАПИСИ\n\n"
        f"👤 {user_name}\n"
        f"ID: {user_id}\n\n"
        f"{training_text(training)}"
    )

    for admin_id in ADMINS:
        send_message(
            admin_id,
            text
        )


def get_user_name(user_id):
    with db_lock:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT name
            FROM users
            WHERE user_id = ?
            """,
            (user_id,)
        )

        row = cursor.fetchone()

        conn.close()

    if row and row["name"]:
        return row["name"]

    return f"ID {user_id}"


def show_admin_schedule(user_id):
    rows = get_trainings(
        days=7
    )

    if not rows:
        send_message(
            user_id,
            "Расписание пустое.",
            admin_keyboard()
        )
        return

    text = "📋 РАСПИСАНИЕ НА БЛИЖАЙШУЮ НЕДЕЛЮ\n\n"

    current_date = None

    for training in rows:
        if training["date"] != current_date:
            current_date = training["date"]

            text += (
                f"\n📌 {format_date(current_date)}\n"
            )

        count = get_training_count(
            training["id"]
        )

        text += (
            f"#{training['id']} "
            f"{training['start_time']}–"
            f"{training['end_time']} | "
            f"{training['category']} | "
            f"{training['level']} | "
            f"{count}/{training['capacity']}\n"
        )

    send_message(
        user_id,
        text,
        admin_keyboard()
    )


def show_admin_bookings(user_id):
    rows = get_trainings(
        days=7
    )

    if not rows:
        send_message(
            user_id,
            "Записей пока нет.",
            admin_keyboard()
        )
        return

    text = "👥 ЗАПИСИ НА БЛИЖАЙШИЕ ТРЕНИРОВКИ\n\n"

    has_bookings = False

    for training in rows:
        participants = get_training_participants(
            training["id"]
        )

        if not participants:
            continue

        has_bookings = True

        text += (
            f"📌 #{training['id']} "
            f"{format_date(training['date'])} "
            f"{training['start_time']}\n"
        )

        for index, participant in enumerate(
            participants,
            start=1
        ):
            name = (
                participant["name"]
                or f"ID {participant['user_id']}"
            )

            text += (
                f"{index}. {name}"
            )

            if participant["phone"]:
                text += (
                    f" — {participant['phone']}"
                )

            text += "\n"

        text += "\n"

    if not has_bookings:
        text += "Пока никто не записан."

    send_message(
        user_id,
        text,
        admin_keyboard()
    )


# ============================================================
# ДОБАВЛЕНИЕ ТРЕНИРОВКИ АДМИНИСТРАТОРОМ
# ============================================================

def start_add_training(user_id):
    user_states[user_id] = {
        "state": "admin_add_date"
    }

    send_message(
        user_id,
        "➕ Добавление тренировки\n\n"
        "Введите дату в формате:\n"
        "ДД.ММ.ГГГГ\n\n"
        "Например: 15.10.2026",
        back_keyboard()
    )


def process_add_training_date(
    user_id,
    text
):
    try:
        date_object = datetime.strptime(
            text.strip(),
            "%d.%m.%Y"
        )

    except ValueError:
        send_message(
            user_id,
            "❌ Неверный формат даты.\n\n"
            "Введите, например:\n"
            "15.10.2026",
            back_keyboard()
        )
        return

    state = user_states.get(
        user_id,
        {}
    )

    state["date"] = (
        date_object.strftime("%Y-%m-%d")
    )

    state["state"] = "admin_add_start"

    user_states[user_id] = state

    send_message(
        user_id,
        "Введите время начала.\n\n"
        "Например: 19:00",
        back_keyboard()
    )


def process_add_training_start(
    user_id,
    text
):
    try:
        datetime.strptime(
            text.strip(),
            "%H:%M"
        )

    except ValueError:
        send_message(
            user_id,
            "❌ Неверное время.\n\n"
            "Введите в формате 19:00.",
            back_keyboard()
        )
        return

    state = user_states.get(
        user_id,
        {}
    )

    state["start"] = text.strip()
    state["state"] = "admin_add_end"

    user_states[user_id] = state

    send_message(
        user_id,
        "Введите время окончания.\n\n"
        "Например: 20:30",
        back_keyboard()
    )


def process_add_training_end(
    user_id,
    text
):
    try:
        datetime.strptime(
            text.strip(),
            "%H:%M"
        )

    except ValueError:
        send_message(
            user_id,
            "❌ Неверное время.\n\n"
            "Введите в формате 20:30.",
            back_keyboard()
        )
        return

    state = user_states.get(
        user_id,
        {}
    )

    state["end"] = text.strip()
    state["state"] = "admin_add_category"

    user_states[user_id] = state

    send_message(
        user_id,
        "Выберите категорию:",
        keyboard(
            [
                [
                    ("👨 Взрослые", "primary"),
                    ("👶 Дети", "primary"),
                ],
                [
                    ("⬅️ Назад", "secondary"),
                ],
            ]
        )
    )


def process_add_training_category(
    user_id,
    text
):
    if text == "👨 Взрослые":
        category = "adults"

    elif text == "👶 Дети":
        category = "children"

    else:
        return

    state = user_states.get(
        user_id,
        {}
    )

    state["category"] = category
    state["state"] = "admin_add_age"

    user_states[user_id] = state

    send_message(
        user_id,
        "Введите возраст.\n\n"
        "Например:\n"
        "18+\n"
        "11–14 лет\n"
        "5–9 лет",
        back_keyboard()
    )


def process_add_training_age(
    user_id,
    text
):
    state = user_states.get(
        user_id,
        {}
    )

    state["age"] = text.strip()
    state["state"] = "admin_add_format"

    user_states[user_id] = state

    send_message(
        user_id,
        "Введите формат.\n\n"
        "Например:\n"
        "Группа\n"
        "MIXED\n"
        "Техничка",
        back_keyboard()
    )


def process_add_training_format(
    user_id,
    text
):
    state = user_states.get(
        user_id,
        {}
    )

    state["format"] = text.strip()
    state["state"] = "admin_add_level"

    user_states[user_id] = state

    send_message(
        user_id,
        "Введите уровень.\n\n"
        "Например:\n"
        "Начальный\n"
        "Средний\n"
        "Средний+\n"
        "Продвинутый",
        back_keyboard()
    )


def process_add_training_level(
    user_id,
    text
):
    state = user_states.get(
        user_id,
        {}
    )

    state["level"] = text.strip()
    state["state"] = "admin_add_coach"

    user_states[user_id] = state

    send_message(
        user_id,
        "Введите имя тренера.",
        back_keyboard()
    )


def process_add_training_coach(
    user_id,
    text
):
    state = user_states.get(
        user_id,
        {}
    )

    state["coach"] = text.strip()
    state["state"] = "admin_add_capacity"

    user_states[user_id] = state

    send_message(
        user_id,
        "Введите максимальное количество участников.\n\n"
        "Например: 10",
        back_keyboard()
    )


def process_add_training_capacity(
    user_id,
    text
):
    try:
        capacity = int(text.strip())

        if capacity <= 0:
            raise ValueError

    except ValueError:
        send_message(
            user_id,
            "❌ Введите положительное целое число.",
            back_keyboard()
        )
        return

    state = user_states.get(
        user_id,
        {}
    )

    state["capacity"] = capacity
    state["state"] = "admin_add_price"

    user_states[user_id] = state

    send_message(
        user_id,
        "Введите стоимость в рублях.\n\n"
        "Например: 1200",
        back_keyboard()
    )


def process_add_training_price(
    user_id,
    text
):
    try:
        price = int(text.strip())

        if price < 0:
            raise ValueError

    except ValueError:
        send_message(
            user_id,
            "❌ Введите стоимость числом.",
            back_keyboard()
        )
        return

    state = user_states.get(
        user_id,
        {}
    )

    state["price"] = price

    with db_lock:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO trainings (
                date,
                start_time,
                end_time,
                category,
                age,
                format,
                level,
                coach,
                capacity,
                price,
                active
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                state["date"],
                state["start"],
                state["end"],
                state["category"],
                state["age"],
                state["format"],
                state["level"],
                state["coach"],
                state["capacity"],
                price,
            )
        )

        conn.commit()
        training_id = cursor.lastrowid
        conn.close()

    training = get_training(
        training_id
    )

    user_states.pop(
        user_id,
        None
    )

    send_message(
        user_id,
        "✅ Тренировка добавлена!\n\n"
        + training_text(training),
        admin_keyboard()
    )


# ============================================================
# ИНДИВИДУАЛЬНАЯ ТРЕНИРОВКА
# ============================================================

def request_individual_training(
    user_id
):
    user_states[user_id] = {
        "state": "individual_request"
    }

    send_message(
        user_id,
        "🎯 Индивидуальная тренировка\n\n"
        "Напишите одним сообщением:\n"
        "• ваше имя\n"
        "• желаемую дату/время\n"
        "• ваш уровень\n"
        "• что хотите улучшить\n\n"
        "Я передам заявку тренеру.",
        back_keyboard()
    )


def process_individual_request(
    user_id,
    text
):
    user_name = get_user_name(
        user_id
    )

    admin_text = (
        "🎯 ЗАЯВКА НА ИНДИВИДУАЛЬНУЮ ТРЕНИРОВКУ\n\n"
        f"👤 Пользователь: {user_name}\n"
        f"ID: {user_id}\n\n"
        f"Сообщение:\n{text}"
    )

    for admin_id in ADMINS:
        send_message(
            admin_id,
            admin_text
        )

    user_states.pop(
        user_id,
        None
    )

    send_message(
        user_id,
        "✅ Заявка отправлена тренеру.\n\n"
        "Мы свяжемся с вами.",
        main_keyboard(user_id)
    )


# ============================================================
# ВОПРОС
# ============================================================

def request_question(user_id):
    user_states[user_id] = {
        "state": "question"
    }

    send_message(
        user_id,
        "❓ Напишите ваш вопрос одним сообщением.\n\n"
        "Я передам его администратору.",
        back_keyboard()
    )


def process_question(
    user_id,
    text
):
    user_name = get_user_name(
        user_id
    )

    admin_text = (
        "❓ НОВЫЙ ВОПРОС\n\n"
        f"👤 {user_name}\n"
        f"ID: {user_id}\n\n"
        f"{text}"
    )

    for admin_id in ADMINS:
        send_message(
            admin_id,
            admin_text
        )

    user_states.pop(
        user_id,
        None
    )

    send_message(
        user_id,
        "✅ Вопрос отправлен администратору.",
        main_keyboard(user_id)
    )


# ============================================================
# ЦЕНЫ / ЛОКАЦИЯ
# ============================================================

def show_prices(user_id):
    text = (
        "💰 ЦЕНЫ\n\n"
        "👶 Дети — 600 ₽ за тренировку.\n\n"
        "👨 Взрослые:\n"
        "• 1–6 человек — 1200 ₽/чел.\n"
        "• 7 человек и больше — 1000 ₽/чел.\n\n"
        "Минимальный размер взрослой группы — "
        "4 человека."
    )

    send_message(
        user_id,
        text,
        main_keyboard(user_id)
    )


def show_location(user_id):
    text = (
        "📍 ГДЕ ТРЕНИРУЕМСЯ\n\n"
        "☀️ Летом:\n"
        "Парк Гагарина.\n\n"
        "❄️ Зимой:\n"
        "СК «Арена»\n"
        "ул. Молодогвардейцев, 7\n\n"
        "Тренировки проходят на песке."
    )

    send_message(
        user_id,
        text,
        main_keyboard(user_id)
    )


# ============================================================
# ПОЛЬЗОВАТЕЛЬСКИЙ РЕЖИМ
# ============================================================

def show_main_menu(user_id):
    user_states.pop(
        user_id,
        None
    )

    send_message(
        user_id,
        "🏐 VOLLEY WAVE\n\n"
        "Школа пляжного волейбола.\n\n"
        "Выберите нужный раздел:",
        main_keyboard(user_id)
    )


# ============================================================
# ОБРАБОТКА СООБЩЕНИЙ
# ============================================================

def handle_message(
    user_id,
    text
):
    text = (text or "").strip()

    print(
        "HANDLE MESSAGE:",
        user_id,
        repr(text),
        flush=True
    )

    save_user(user_id)

    state = user_states.get(
        user_id,
        {}
    )

    current_state = state.get(
        "state"
    )

    # --------------------------------------------------------
    # ГЛАВНОЕ МЕНЮ
    # --------------------------------------------------------

    if text in (
        "Начать",
        "start",
        "/start",
        "Привет",
        "привет",
    ):
        show_main_menu(user_id)
        return

    if text == "🏠 Главное меню":
        show_main_menu(user_id)
        return

    # --------------------------------------------------------
    # АДМИН
    # --------------------------------------------------------

    if text == "⚙️ Админ-панель":
        if user_id not in ADMINS:
            show_main_menu(user_id)
            return

        user_states.pop(
            user_id,
            None
        )

        send_message(
            user_id,
            "⚙️ АДМИН-ПАНЕЛЬ",
            admin_keyboard()
        )
        return

    if text == "👤 Режим пользователя":
        if user_id not in ADMINS:
            return

        show_main_menu(user_id)
        return

    if text == "➕ Добавить тренировку":
        if user_id not in ADMINS:
            return

        start_add_training(user_id)
        return

    if text == "📋 Расписание":
        if user_id in ADMINS and current_state is None:
            show_admin_schedule(user_id)
            return

        # Пользовательское расписание
        send_message(
            user_id,
            "Какое расписание показать?",
            category_keyboard()
        )

        user_states[user_id] = {
            "state": "schedule_category"
        }

        return

    if text == "👥 Записи":
        if user_id not in ADMINS:
            return

        show_admin_bookings(user_id)
        return

    # --------------------------------------------------------
    # ОБЩИЕ РАЗДЕЛЫ
    # --------------------------------------------------------

    if text == "🏐 Записаться":
        user_states[user_id] = {
            "state": "booking_category"
        }

        send_message(
            user_id,
            "Кого записываем?",
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
        request_individual_training(user_id)
        return

    if text == "❓ Задать вопрос":
        request_question(user_id)
        return

    # --------------------------------------------------------
    # НАЗАД
    # --------------------------------------------------------

    if text == "⬅️ Назад":
        if user_id in ADMINS:
            if current_state and current_state.startswith(
                "admin_add_"
            ):
                send_message(
                    user_id,
                    "⚙️ АДМИН-ПАНЕЛЬ",
                    admin_keyboard()
                )

                user_states.pop(
                    user_id,
                    None
                )
                return

        show_main_menu(user_id)
        return

    # --------------------------------------------------------
    # ДОБАВЛЕНИЕ ТРЕНИРОВКИ
    # --------------------------------------------------------

    if current_state == "admin_add_date":
        process_add_training_date(
            user_id,
            text
        )
        return

    if current_state == "admin_add_start":
        process_add_training_start(
            user_id,
            text
        )
        return

    if current_state == "admin_add_end":
        process_add_training_end(
            user_id,
            text
        )
        return

    if current_state == "admin_add_category":
        process_add_training_category(
            user_id,
            text
        )
        return

    if current_state == "admin_add_age":
        process_add_training_age(
            user_id,
            text
        )
        return

    if current_state == "admin_add_format":
        process_add_training_format(
            user_id,
            text
        )
        return

    if current_state == "admin_add_level":
        process_add_training_level(
            user_id,
            text
        )
        return

    if current_state == "admin_add_coach":
        process_add_training_coach(
            user_id,
            text
        )
        return

    if current_state == "admin_add_capacity":
        process_add_training_capacity(
            user_id,
            text
        )
        return

    if current_state == "admin_add_price":
        process_add_training_price(
            user_id,
            text
        )
        return

    # --------------------------------------------------------
    # РАСПИСАНИЕ
    # --------------------------------------------------------

    if current_state == "schedule_category":
        if text == "👨 Взрослые":
            show_schedule(
                user_id,
                "adults"
            )
            return

        if text == "👶 Дети":
            show_schedule(
                user_id,
                "children"
            )
            return

    # --------------------------------------------------------
    # ЗАПИСЬ — КАТЕГОРИЯ
    # --------------------------------------------------------

    if current_state == "booking_category":
        if text == "👨 Взрослые":
            show_booking_days(
                user_id,
                "adults"
            )
            return

        if text == "👶 Дети":
            show_booking_days(
                user_id,
                "children"
            )
            return

    # --------------------------------------------------------
    # ЗАПИСЬ — ДЕНЬ
    # --------------------------------------------------------

    if current_state == "booking_day":
        weekday = weekday_from_text(
            text
        )

        if weekday is not None:
            show_booking_trainings(
                user_id,
                state["category"],
                weekday
            )
            return

    # --------------------------------------------------------
    # ЗАПИСЬ — ВЫБОР ТРЕНИРОВКИ
    # --------------------------------------------------------

    if current_state == "booking_training":
        training_id = find_training_from_button(
            user_id,
            text
        )

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
        if text == "✅ Записаться":
            do_booking(
                user_id,
                state["training_id"]
            )
            return

    # --------------------------------------------------------
    # МОИ ТРЕНИРОВКИ
    # --------------------------------------------------------

    if current_state == "my_training":
        training_id = state.get(
            "trainings",
            {}
        ).get(text)

        if training_id:
            show_my_training_details(
                user_id,
                training_id
            )
            return

    if current_state == "my_training_detail":
        training_id = state.get(
            "training_id"
        )

        if text == "❌ Отменить запись":
            cancel_my_training(
                user_id,
                training_id
            )
            return

        if text == "🚫 Отмена недоступна (<24 ч)":
            send_message(
                user_id,
                "🚫 Отменить запись можно только "
                "не позднее чем за 24 часа до начала.",
                main_keyboard(user_id)
            )
            return

    # --------------------------------------------------------
    # ИНДИВИДУАЛЬНАЯ ТРЕНИРОВКА
    # --------------------------------------------------------

    if current_state == "individual_request":
        process_individual_request(
            user_id,
            text
        )
        return

    # --------------------------------------------------------
    # ВОПРОС
    # --------------------------------------------------------

    if current_state == "question":
        process_question(
            user_id,
            text
        )
        return

    # --------------------------------------------------------
    # ЕСЛИ НИЧЕГО НЕ ПОДОШЛО
    # --------------------------------------------------------

    send_message(
        user_id,
        "Не совсем понял команду.\n\n"
        "Выберите действие из меню:",
        main_keyboard(user_id)
    )


# ============================================================
# CALLBACK VK
# ============================================================

@app.route(
    "/callback",
    methods=["POST"]
)
def callback():

    # ========================================================
    # КРИТИЧЕСКАЯ ДИАГНОСТИКА
    # ========================================================

    print(
        "🔥 CALLBACK REACHED",
        flush=True
    )

    data = request.get_json(
        silent=True
    ) or {}

    # ВАЖНО:
    # секрет и токены специально не выводим.
    safe_data = dict(data)

    if "secret" in safe_data:
        safe_data["secret"] = "***"

    print(
        "🔥 RAW CALLBACK DATA:",
        safe_data,
        flush=True
    )

    print(
        "================ CALLBACK ================",
        flush=True
    )

    print(
        "EVENT TYPE:",
        data.get("type"),
        flush=True
    )

    print(
        "CALLBACK KEYS:",
        list(data.keys()),
        flush=True
    )

    # ========================================================
    # ПРОВЕРКА SECRET
    # ========================================================

    received_secret = data.get(
        "secret"
    )

    if VK_SECRET_KEY:
        if received_secret != VK_SECRET_KEY:
            print(
                "❌ SECRET MISMATCH",
                flush=True
            )

            return "ok"

    # ========================================================
    # ПОДТВЕРЖДЕНИЕ CALLBACK
    # ========================================================

    if data.get("type") == "confirmation":

        print(
            "🔥 CONFIRMATION REQUEST",
            flush=True
        )

        return (
            VK_CONFIRMATION_TOKEN
            or ""
        )

    # ========================================================
    # НОВОЕ СООБЩЕНИЕ
    # ========================================================

    if data.get("type") != "message_new":

        print(
            "ℹ️ EVENT IGNORED:",
            data.get("type"),
            flush=True
        )

        return "ok"

    obj = data.get(
        "object",
        {}
    )

    print(
        "OBJECT TYPE:",
        type(obj),
        flush=True
    )

    if isinstance(obj, dict):
        print(
            "OBJECT KEYS:",
            list(obj.keys()),
            flush=True
        )

    # ========================================================
    # ПОЛУЧАЕМ USER ID
    # ========================================================

    user_id = obj.get(
        "from_id"
    )

    if not user_id:
        user_id = obj.get(
            "user_id"
        )

    text = obj.get(
        "text",
        ""
    )

    print(
        "PARSED USER ID:",
        user_id,
        flush=True
    )

    print(
        "PARSED TEXT:",
        repr(text),
        flush=True
    )

    if not user_id:

        print(
            "❌ USER ID NOT FOUND",
            flush=True
        )

        return "ok"

    # ========================================================
    # ОБРАБОТКА
    # ========================================================

    try:

        handle_message(
            int(user_id),
            text
        )

    except Exception as error:

        print(
            "🔥 BOT ERROR:",
            repr(error),
            flush=True
        )

        try:
            send_message(
                int(user_id),
                "Произошла техническая ошибка.\n"
                "Попробуйте ещё раз."
            )

        except Exception as send_error:

            print(
                "🔥 ERROR SENDING ERROR MESSAGE:",
                repr(send_error),
                flush=True
            )

    print(
        "🔥 CALLBACK FINISHED",
        flush=True
    )

    return "ok"


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/")
def index():
    return "VOLLEY WAVE VK BOT OK"


# ============================================================
# ЗАПУСК
# ============================================================

init_db()


if __name__ == "__main__":

    port = int(
        os.getenv(
            "PORT",
            "10000"
        )
    )

    print(
        "======================================",
        flush=True
    )

    print(
        "VOLLEY WAVE VK BOT STARTED",
        flush=True
    )

    print(
        "PORT:",
        port,
        flush=True
    )

    print(
        "GROUP ID:",
        GROUP_ID,
        flush=True
    )

    print(
        "VK TOKEN:",
        "SET" if VK_TOKEN else "NOT SET",
        flush=True
    )

    print(
        "VK SECRET:",
        "SET" if VK_SECRET_KEY else "NOT SET",
        flush=True
    )

    print(
        "VK CONFIRMATION:",
        "SET" if VK_CONFIRMATION_TOKEN else "NOT SET",
        flush=True
    )

    print(
        "======================================",
        flush=True
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
