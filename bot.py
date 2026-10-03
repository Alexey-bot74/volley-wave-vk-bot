import os
import sqlite3
import logging
import random
from datetime import datetime, date, timedelta

import requests
from flask import Flask, request


# ============================================================
# VOLLEY WAVE VK BOT
# VERSION №6
# ============================================================

VERSION = "№6"

VK_TOKEN = os.getenv("VK_TOKEN", "").strip()
VK_CONFIRMATION_TOKEN = os.getenv(
    "VK_CONFIRMATION_TOKEN",
    "",
).strip()
VK_SECRET_KEY = os.getenv(
    "VK_SECRET_KEY",
    "",
).strip()

VK_API_VERSION = "5.199"

GROUP_ID = 221776135

DB_NAME = "volley_wave.db"

ADMINS = {
    87984447,
    172892670,
    148372158,
}

ADMIN_CONTACT_ID = 87984447

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


# ============================================================
# MEMORY STATE
# ============================================================

USER_STATES = {}


# ============================================================
# CONSTANTS
# ============================================================

BACK = "⬅️ Назад"

WEEKDAYS_RU = [
    "Понедельник",
    "Вторник",
    "Среда",
    "Четверг",
    "Пятница",
    "Суббота",
    "Воскресенье",
]


# ============================================================
# DATABASE
# ============================================================

def get_db():
    connection = sqlite3.connect(
        DB_NAME,
        timeout=30,
    )
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    connection = get_db()

    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            state TEXT DEFAULT 'main',
            category TEXT,
            created_at TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS trainings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            training_number INTEGER,
            training_date TEXT,
            weekday TEXT,
            start_time TEXT,
            end_time TEXT,
            category TEXT,
            format TEXT,
            level TEXT,
            capacity INTEGER,
            price INTEGER,
            location TEXT,
            active INTEGER DEFAULT 1,
            created_at TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            training_id INTEGER,
            user_id INTEGER,
            created_at TEXT,
            UNIQUE(training_id, user_id)
        )
        """
    )

    connection.commit()

    migrate_database(connection)

    connection.close()

    logging.info(
        "Database initialized"
    )


def migrate_database(connection):
    cursor = connection.cursor()

    cursor.execute(
        "PRAGMA table_info(trainings)"
    )

    columns = {
        row["name"]
        for row in cursor.fetchall()
    }

    required_columns = {
        "training_number": "INTEGER",
        "weekday": "TEXT",
        "active": "INTEGER DEFAULT 1",
        "created_at": "TEXT",
    }

    for column, definition in required_columns.items():
        if column not in columns:
            cursor.execute(
                f"""
                ALTER TABLE trainings
                ADD COLUMN {column} {definition}
                """
            )

    connection.commit()

    cursor.execute(
        """
        SELECT
            id,
            training_date,
            category,
            weekday,
            active
        FROM trainings
        """
    )

    rows = cursor.fetchall()

    for row in rows:
        parsed_date = parse_date(
            row["training_date"]
        )

        if parsed_date:
            normalized_date = (
                parsed_date.isoformat()
            )

            weekday = WEEKDAYS_RU[
                parsed_date.weekday()
            ]
        else:
            normalized_date = (
                row["training_date"]
            )
            weekday = row["weekday"]

        category = normalize_category(
            row["category"]
        )

        active = (
            1
            if row["active"] is None
            else row["active"]
        )

        cursor.execute(
            """
            UPDATE trainings
            SET
                training_date = ?,
                weekday = ?,
                category = ?,
                active = ?
            WHERE id = ?
            """,
            (
                normalized_date,
                weekday,
                category,
                active,
                row["id"],
            ),
        )

    cursor.execute(
        """
        SELECT
            id,
            training_number
        FROM trainings
        ORDER BY id
        """
    )

    rows = cursor.fetchall()

    next_number = 1

    for row in rows:
        if not row["training_number"]:
            cursor.execute(
                """
                UPDATE trainings
                SET training_number = ?
                WHERE id = ?
                """,
                (
                    next_number,
                    row["id"],
                ),
            )

        next_number += 1

    connection.commit()


# ============================================================
# DATE / TIME HELPERS
# ============================================================

def parse_date(value):
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    value = str(value).strip()

    if not value:
        return None

    formats = [
        "%Y-%m-%d",
        "%d.%m.%Y",
        "%Y/%m/%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(
                value[:10],
                fmt,
            ).date()
        except ValueError:
            continue

    try:
        return datetime.fromisoformat(
            value.replace("Z", "+00:00")
        ).date()
    except ValueError:
        return None


def parse_time(value):
    if value is None:
        return None

    value = (
        str(value)
        .strip()
        .replace(".", ":")
    )

    parts = value.split(":")

    if len(parts) != 2:
        return None

    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError:
        return None

    if hour < 0 or hour > 23:
        return None

    if minute < 0 or minute > 59:
        return None

    return f"{hour:02d}:{minute:02d}"


def time_to_minutes(value):
    parsed = parse_time(value)

    if not parsed:
        return 0

    hour, minute = map(
        int,
        parsed.split(":"),
    )

    return hour * 60 + minute


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_category(value):
    text = str(value or "").strip().lower()

    if "дет" in text:
        return "Детская"

    if "взрос" in text:
        return "Взрослая"

    return str(value or "").strip()


# ============================================================
# PRICES
# ============================================================

def get_training_price(
    category,
    capacity,
):
    category = normalize_category(
        category
    )

    try:
        capacity = int(capacity)
    except (ValueError, TypeError):
        return None

    if category == "Детская":
        return 600

    if category == "Взрослая":
        if capacity < 4:
            return None

        if capacity >= 6:
            return 1000

        return 1200

    return None


# ============================================================
# VK KEYBOARDS
# ============================================================

def text_button(
    label,
    color="secondary",
):
    return {
        "action": {
            "type": "text",
            "label": str(label)[:40],
        },
        "color": color,
    }


def link_button(
    label,
    link,
    color="primary",
):
    return {
        "action": {
            "type": "open_link",
            "link": link,
            "label": str(label)[:40],
        },
        "color": color,
    }


def make_keyboard(
    rows,
    inline=False,
):
    return {
        "one_time": False,
        "inline": inline,
        "buttons": rows,
    }


def main_keyboard(user_id):
    rows = [
        [
            text_button(
                "📅 Расписание",
                "primary",
            )
        ],
        [
            text_button(
                "📝 Записаться",
                "primary",
            )
        ],
        [
            text_button(
                "💰 Цены",
            )
        ],
        [
            text_button(
                "🏐 Индивидуальная тренировка",
            )
        ],
    ]

    if user_id in ADMINS:
        rows.append(
            [
                text_button(
                    "⚙️ Админ-панель",
                )
            ]
        )

    return make_keyboard(rows)


def back_keyboard():
    return make_keyboard(
        [
            [
                text_button(BACK)
            ]
        ]
    )


def category_keyboard():
    return make_keyboard(
        [
            [
                text_button("👧 Детские")
            ],
            [
                text_button("🧑 Взрослые")
            ],
            [
                text_button(BACK)
            ],
        ]
    )


def admin_keyboard():
    return make_keyboard(
        [
            [
                text_button(
                    "➕ Создать тренировку",
                    "primary",
                )
            ],
            [
                text_button(
                    "📋 Все тренировки"
                )
            ],
            [
                text_button(
                    "👥 Записи"
                )
            ],
            [
                text_button(BACK)
            ],
        ]
    )


def create_category_keyboard():
    return make_keyboard(
        [
            [
                text_button(
                    "👧 Детская"
                )
            ],
            [
                text_button(
                    "🧑 Взрослая"
                )
            ],
            [
                text_button(BACK)
            ],
        ]
    )


def format_keyboard():
    return make_keyboard(
        [
            [
                text_button("Техничка")
            ],
            [
                text_button("MIXED")
            ],
            [
                text_button("Женская")
            ],
            [
                text_button("Мужская")
            ],
            [
                text_button("Общая")
            ],
            [
                text_button(BACK)
            ],
        ]
    )


def level_keyboard():
    return make_keyboard(
        [
            [
                text_button(
                    "Начинающие"
                )
            ],
            [
                text_button(
                    "Средний"
                )
            ],
            [
                text_button(
                    "Продвинутый"
                )
            ],
            [
                text_button(
                    "Любой уровень"
                )
            ],
            [
                text_button(BACK)
            ],
        ]
    )


# ============================================================
# VK API
# ============================================================

def vk_send(
    user_id,
    message,
    keyboard=None,
):
    if not VK_TOKEN:
        logging.error(
            "VK_TOKEN is empty"
        )
        return False

    params = {
        "access_token": VK_TOKEN,
        "v": VK_API_VERSION,
        "user_id": int(user_id),
        "random_id": random.randint(
            1,
            2147483646,
        ),
        "message": str(message),
    }

    if keyboard is not None:
        params["keyboard"] = keyboard

    try:
        response = requests.post(
            "https://api.vk.com/method/messages.send",
            data=params,
            timeout=15,
        )

        result = response.json()

        logging.info(
            "VK SEND user=%s result=%s",
            user_id,
            result,
        )

        if "error" in result:
            logging.error(
                "VK API error: %s",
                result["error"],
            )
            return False

        return True

    except Exception:
        logging.exception(
            "VK SEND exception"
        )
        return False


# ============================================================
# USER STATE
# ============================================================

def set_state(
    user_id,
    state,
    **data,
):
    current = {
        "state": state,
        **data,
    }

    USER_STATES[int(user_id)] = current

    connection = get_db()

    connection.execute(
        """
        INSERT INTO users(
            user_id,
            state,
            category,
            created_at
        )
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET
            state = excluded.state,
            category = COALESCE(
                excluded.category,
                users.category
            )
        """,
        (
            int(user_id),
            state,
            data.get("category"),
            datetime.now().isoformat(),
        ),
    )

    connection.commit()
    connection.close()


def clear_state(user_id):
    USER_STATES.pop(
        int(user_id),
        None,
    )

    connection = get_db()

    connection.execute(
        """
        INSERT INTO users(
            user_id,
            state,
            created_at
        )
        VALUES (?, 'main', ?)
        ON CONFLICT(user_id)
        DO UPDATE SET
            state = 'main'
        """,
        (
            int(user_id),
            datetime.now().isoformat(),
        ),
    )

    connection.commit()
    connection.close()


def get_state(user_id):
    user_id = int(user_id)

    if user_id in USER_STATES:
        return USER_STATES[user_id]

    connection = get_db()

    row = connection.execute(
        """
        SELECT
            state,
            category
        FROM users
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()

    connection.close()

    if row:
        result = {
            "state": row["state"] or "main",
        }

        if row["category"]:
            result["category"] = (
                row["category"]
            )

    else:
        result = {
            "state": "main"
        }

    USER_STATES[user_id] = result

    return result


def save_user_category(
    user_id,
    category,
):
    connection = get_db()

    connection.execute(
        """
        INSERT INTO users(
            user_id,
            state,
            category,
            created_at
        )
        VALUES (?, 'main', ?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET
            category = excluded.category
        """,
        (
            int(user_id),
            normalize_category(category),
            datetime.now().isoformat(),
        ),
    )

    connection.commit()
    connection.close()


# ============================================================
# TRAININGS
# ============================================================

def next_training_number(
    connection,
):
    row = connection.execute(
        """
        SELECT
            COALESCE(
                MAX(training_number),
                0
            ) + 1 AS number
        FROM trainings
        """
    ).fetchone()

    return int(row["number"])


def get_training(training_id):
    if not training_id:
        return None

    connection = get_db()

    row = connection.execute(
        """
        SELECT *
        FROM trainings
        WHERE id = ?
        """,
        (int(training_id),),
    ).fetchone()

    connection.close()

    return row


def registered_count(
    training_id,
):
    connection = get_db()

    row = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM registrations
        WHERE training_id = ?
        """,
        (int(training_id),),
    ).fetchone()

    connection.close()

    return int(row["count"])


def free_places(
    training_id,
):
    training = get_training(
        training_id
    )

    if not training:
        return 0

    return max(
        int(training["capacity"])
        - registered_count(training_id),
        0,
    )


def get_future_trainings(
    category=None,
):
    """
    КРИТИЧЕСКИ ВАЖНО:

    Здесь НЕ используется SQL:
        training_date >= ?

    Потому что в старой базе даты могли
    храниться в разных форматах.

    Мы получаем все активные тренировки,
    преобразуем дату Python-ом и только
    потом фильтруем.

    Именно это исправляет ситуацию,
    когда расписание есть в БД,
    но бот пишет, что его нет.
    """

    today = date.today()

    connection = get_db()

    rows = connection.execute(
        """
        SELECT *
        FROM trainings
        WHERE COALESCE(active, 1) = 1
        """
    ).fetchall()

    connection.close()

    result = []

    wanted_category = None

    if category:
        wanted_category = normalize_category(
            category
        )

    for row in rows:
        parsed_date = parse_date(
            row["training_date"]
        )

        if not parsed_date:
            logging.error(
                "BAD TRAINING DATE "
                "id=%s date=%r",
                row["id"],
                row["training_date"],
            )
            continue

        if parsed_date < today:
            continue

        row_category = normalize_category(
            row["category"]
        )

        if (
            wanted_category
            and row_category != wanted_category
        ):
            continue

        start_time = (
            parse_time(
                row["start_time"]
            )
            or str(row["start_time"])
        )

        end_time = (
            parse_time(
                row["end_time"]
            )
            or str(row["end_time"])
        )

        result.append(
            {
                "id": row["id"],
                "training_number": (
                    row["training_number"]
                    or row["id"]
                ),
                "training_date": parsed_date,
                "weekday": WEEKDAYS_RU[
                    parsed_date.weekday()
                ],
                "start_time": start_time,
                "end_time": end_time,
                "category": row_category,
                "format": row["format"] or "—",
                "level": row["level"] or "—",
                "capacity": int(
                    row["capacity"] or 0
                ),
                "price": int(
                    row["price"] or 0
                ),
                "location": (
                    row["location"]
                    or "—"
                ),
            }
        )

    result.sort(
        key=lambda item: (
            item["training_date"],
            time_to_minutes(
                item["start_time"]
            ),
            item["id"],
        )
    )

    logging.info(
        "TRAININGS FOUND category=%r count=%s",
        category,
        len(result),
    )

    return result


def training_text(
    training,
):
    if isinstance(
        training,
        sqlite3.Row,
    ):
        training_id = training["id"]

        training_date = parse_date(
            training["training_date"]
        )

        number = (
            training["training_number"]
            or training_id
        )

        start_time = (
            parse_time(
                training["start_time"]
            )
            or str(training["start_time"])
        )

        end_time = (
            parse_time(
                training["end_time"]
            )
            or str(training["end_time"])
        )

        training_format = (
            training["format"]
            or "—"
        )

        level = (
            training["level"]
            or "—"
        )

        capacity = int(
            training["capacity"] or 0
        )

        price = int(
            training["price"] or 0
        )

        location = (
            training["location"]
            or "—"
        )

    else:
        training_id = training["id"]

        training_date = training[
            "training_date"
        ]

        number = training[
            "training_number"
        ]

        start_time = training[
            "start_time"
        ]

        end_time = training[
            "end_time"
        ]

        training_format = training[
            "format"
        ]

        level = training[
            "level"
        ]

        capacity = int(
            training["capacity"]
        )

        price = int(
            training["price"]
        )

        location = training[
            "location"
        ]

    if training_date:
        date_text = training_date.strftime(
            "%d.%m.%Y"
        )

        weekday = WEEKDAYS_RU[
            training_date.weekday()
        ]
    else:
        date_text = "—"
        weekday = "—"

    free = free_places(
        training_id
    )

    return (
        f"🏐 Тренировка №{number}\n\n"
        f"📅 Дата: {date_text}\n"
        f"🗓 День: {weekday}\n"
        f"🕐 Время: "
        f"{start_time}–{end_time}\n"
        f"🏐 Формат: {training_format}\n"
        f"📊 Уровень: {level}\n"
        f"👥 Мест: {capacity}\n"
        f"💳 Стоимость: {price} ₽\n"
        f"📍 Место: {location}\n"
        f"🟢 Свободно: {free}"
    )


# ============================================================
# MAIN MENU
# ============================================================

def show_main(user_id):
    clear_state(user_id)

    vk_send(
        user_id,
        "🏐 VOLLEY WAVE\n\n"
        "Выберите действие:",
        main_keyboard(user_id),
    )


# ============================================================
# PRICES
# ============================================================

def show_prices(user_id):
    set_state(
        user_id,
        "prices",
    )

    vk_send(
        user_id,
        "💰 Цены\n\n"
        "👧 Детские — 600 ₽.\n\n"
        "🧑 Взрослые:\n"
        "• минимальный набор — 4 человека;\n"
        "• 4–5 человек — 1200 ₽ с человека;\n"
        "• от 6 человек — 1000 ₽ с человека.",
        back_keyboard(),
    )


# ============================================================
# INDIVIDUAL TRAINING
# ============================================================

def show_individual(user_id):
    set_state(
        user_id,
        "individual",
    )

    admin_link = (
        f"https://vk.com/id{ADMIN_CONTACT_ID}"
    )

    vk_send(
        user_id,
        "🏐 Индивидуальная тренировка\n\n"
        "Чтобы договориться об "
        "индивидуальной тренировке, "
        "напишите администратору.",
        make_keyboard(
            [
                [
                    link_button(
                        "✉️ Написать администратору",
                        admin_link,
                        "primary",
                    )
                ],
                [
                    text_button(BACK)
                ],
            ]
        ),
    )


# ============================================================
# SCHEDULE
# ============================================================

def show_schedule_menu(user_id):
    set_state(
        user_id,
        "schedule_category",
    )

    vk_send(
        user_id,
        "📅 Расписание\n\n"
        "Выберите направление:",
        category_keyboard(),
    )


def show_schedule(
    user_id,
    category,
):
    category = normalize_category(
        category
    )

    trainings = get_future_trainings(
        category
    )

    logging.info(
        "SHOW SCHEDULE "
        "user=%s category=%s count=%s",
        user_id,
        category,
        len(trainings),
    )

    if not trainings:
        vk_send(
            user_id,
            "📅 Расписание\n\n"
            f"{category}\n\n"
            "Пока тренировок нет.",
            back_keyboard(),
        )
        return

    message_parts = [
        "📅 Расписание",
        "",
        category,
        "",
    ]

    for training in trainings:
        message_parts.append(
            training_text(training)
        )
        message_parts.append(
            "\n────────────\n"
        )

    vk_send(
        user_id,
        "\n".join(
            message_parts
        ).strip(),
        back_keyboard(),
    )


# ============================================================
# BOOKING
# ============================================================

def show_booking_menu(user_id):
    set_state(
        user_id,
        "booking_category",
    )

    vk_send(
        user_id,
        "📝 Запись на тренировку\n\n"
        "Выберите направление:",
        category_keyboard(),
    )


def show_booking_dates(
    user_id,
    category,
):
    category = normalize_category(
        category
    )

    trainings = get_future_trainings(
        category
    )

    if not trainings:
        vk_send(
            user_id,
            "📝 Запись\n\n"
            "Подходящих тренировок "
            "пока нет.",
            back_keyboard(),
        )
        return

    dates = []

    for training in trainings:
        current_date = training[
            "training_date"
        ]

        if current_date not in dates:
            dates.append(
                current_date
            )

    rows = []

    for current_date in dates:
        rows.append(
            [
                text_button(
                    current_date.strftime(
                        "%d.%m.%Y"
                    )
                    + " — "
                    + WEEKDAYS_RU[
                        current_date.weekday()
                    ]
                )
            ]
        )

    rows.append(
        [
            text_button(BACK)
        ]
    )

    set_state(
        user_id,
        "booking_date",
        category=category,
    )

    vk_send(
        user_id,
        "📅 Выберите дату:",
        make_keyboard(rows),
    )


def show_booking_trainings(
    user_id,
    category,
    selected_date,
):
    parsed_date = parse_date(
        selected_date
    )

    if not parsed_date:
        show_booking_dates(
            user_id,
            category,
        )
        return

    trainings = [
        training
        for training in get_future_trainings(
            category
        )
        if training["training_date"]
        == parsed_date
    ]

    if not trainings:
        vk_send(
            user_id,
            "На эту дату тренировок "
            "нет.",
            back_keyboard(),
        )
        return

    rows = []

    for training in trainings:
        free = free_places(
            training["id"]
        )

        if free > 0:
            label = (
                f"№{training['training_number']} "
                f"{training['start_time']}-"
                f"{training['end_time']} "
                f"({free} мест)"
            )
        else:
            label = (
                f"№{training['training_number']} "
                f"{training['start_time']}-"
                f"{training['end_time']} "
                "(НЕТ МЕСТ)"
            )

        rows.append(
            [
                text_button(label)
            ]
        )

    rows.append(
        [
            text_button(BACK)
        ]
    )

    set_state(
        user_id,
        "booking_training",
        category=normalize_category(
            category
        ),
        selected_date=parsed_date.isoformat(),
    )

    vk_send(
        user_id,
        "🏐 Выберите тренировку:",
        make_keyboard(rows),
    )


def find_training_from_button(
    category,
    selected_date,
    text,
):
    parsed_date = parse_date(
        selected_date
    )

    if not parsed_date:
        return None

    trainings = [
        training
        for training in get_future_trainings(
            category
        )
        if training["training_date"]
        == parsed_date
    ]

    for training in trainings:
        prefix = (
            f"№{training['training_number']} "
        )

        if text.startswith(prefix):
            return training

    return None


def show_booking_confirmation(
    user_id,
    training,
):
    set_state(
        user_id,
        "booking_confirm",
        training_id=training["id"],
    )

    if free_places(
        training["id"]
    ) <= 0:
        vk_send(
            user_id,
            "❌ На тренировке "
            "нет свободных мест.",
            back_keyboard(),
        )
        return

    vk_send(
        user_id,
        training_text(training)
        + "\n\n"
        + "Записаться?",
        make_keyboard(
            [
                [
                    text_button(
                        "✅ Записаться",
                        "primary",
                    )
                ],
                [
                    text_button(BACK)
                ],
            ]
        ),
    )


def register_user(
    user_id,
    training_id,
):
    training = get_training(
        training_id
    )

    if not training:
        return (
            False,
            "Тренировка не найдена."
        )

    if not training["active"]:
        return (
            False,
            "Тренировка закрыта."
        )

    if free_places(
        training_id
    ) <= 0:
        return (
            False,
            "Свободных мест больше нет."
        )

    connection = get_db()

    try:
        connection.execute(
            """
            INSERT INTO registrations(
                training_id,
                user_id,
                created_at
            )
            VALUES (?, ?, ?)
            """,
            (
                int(training_id),
                int(user_id),
                datetime.now().isoformat(),
            ),
        )

        connection.commit()

    except sqlite3.IntegrityError:
        connection.close()

        return (
            False,
            "Вы уже записаны "
            "на эту тренировку."
        )

    except Exception:
        connection.rollback()
        connection.close()

        logging.exception(
            "Registration error"
        )

        return (
            False,
            "Не удалось записать вас. "
            "Попробуйте ещё раз."
        )

    connection.close()

    return True, "ok"


def notify_admins(
    user_id,
    training_id,
):
    training = get_training(
        training_id
    )

    if not training:
        return

    count = registered_count(
        training_id
    )

    training_date = parse_date(
        training["training_date"]
    )

    date_text = (
        training_date.strftime(
            "%d.%m.%Y"
        )
        if training_date
        else str(
            training["training_date"]
        )
    )

    message = (
        "📝 Новая запись!\n\n"
        f"Пользователь: id{user_id}\n"
        f"Тренировка №"
        f"{training['training_number'] or training['id']}\n"
        f"Дата: {date_text}\n"
        f"Время: "
        f"{training['start_time']}-"
        f"{training['end_time']}\n"
        f"Участников: "
        f"{count}/{training['capacity']}"
    )

    for admin_id in ADMINS:
        vk_send(
            admin_id,
            message,
        )


# ============================================================
# ADMIN
# ============================================================

def show_admin(user_id):
    if user_id not in ADMINS:
        show_main(user_id)
        return

    set_state(
        user_id,
        "admin",
    )

    vk_send(
        user_id,
        "⚙️ Админ-панель",
        admin_keyboard(),
    )


def start_create_training(
    user_id,
):
    if user_id not in ADMINS:
        show_main(user_id)
        return

    set_state(
        user_id,
        "create_category",
    )

    vk_send(
        user_id,
        "➕ Создание тренировки\n\n"
        "Выберите направление:",
        create_category_keyboard(),
    )


def create_ask_date(
    user_id,
    category,
):
    set_state(
        user_id,
        "create_date",
        category=category,
    )

    vk_send(
        user_id,
        "📅 Дата\n\n"
        "Введите дату:\n"
        "например, 05.10.2026",
        back_keyboard(),
    )


def create_ask_time(
    user_id,
    data,
):
    set_state(
        user_id,
        "create_time",
        **data,
    )

    vk_send(
        user_id,
        "🕐 Время\n\n"
        "Введите начало и конец:\n"
        "19:00-20:30",
        back_keyboard(),
    )


def create_ask_format(
    user_id,
    data,
):
    set_state(
        user_id,
        "create_format",
        **data,
    )

    vk_send(
        user_id,
        "🏐 Формат:",
        format_keyboard(),
    )


def create_ask_level(
    user_id,
    data,
):
    set_state(
        user_id,
        "create_level",
        **data,
    )

    vk_send(
        user_id,
        "📊 Уровень:",
        level_keyboard(),
    )


def create_ask_capacity(
    user_id,
    data,
):
    set_state(
        user_id,
        "create_capacity",
        **data,
    )

    if data["category"] == "Взрослая":
        message = (
            "👥 Сколько мест?\n\n"
            "Минимум — 4 человека."
        )
    else:
        message = (
            "👥 Сколько мест?"
        )

    vk_send(
        user_id,
        message,
        back_keyboard(),
    )


def create_ask_location(
    user_id,
    data,
):
    price = get_training_price(
        data["category"],
        data["capacity"],
    )

    if price is None:
        vk_send(
            user_id,
            "❌ Нельзя создать "
            "взрослую тренировку "
            "менее чем на 4 человека.",
            back_keyboard(),
        )
        return

    data = dict(data)
    data["price"] = price

    set_state(
        user_id,
        "create_location",
        **data,
    )

    vk_send(
        user_id,
        f"💳 Стоимость: {price} ₽\n\n"
        "📍 Место\n\n"
        "Введите место проведения:",
        back_keyboard(),
    )


def save_training(
    data,
):
    parsed_date = parse_date(
        data["training_date"]
    )

    start_time = parse_time(
        data["start_time"]
    )

    end_time = parse_time(
        data["end_time"]
    )

    if not parsed_date:
        return None

    if not start_time or not end_time:
        return None

    connection = get_db()

    try:
        number = next_training_number(
            connection
        )

        cursor = connection.execute(
            """
            INSERT INTO trainings(
                training_number,
                training_date,
                weekday,
                start_time,
                end_time,
                category,
                format,
                level,
                capacity,
                price,
                location,
                active,
                created_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, 1, ?
            )
            """,
            (
                number,
                parsed_date.isoformat(),
                WEEKDAYS_RU[
                    parsed_date.weekday()
                ],
                start_time,
                end_time,
                normalize_category(
                    data["category"]
                ),
                data["format"],
                data["level"],
                int(data["capacity"]),
                int(data["price"]),
                data["location"],
                datetime.now().isoformat(),
            ),
        )

        training_id = cursor.lastrowid

        connection.commit()

        return training_id

    except Exception:
        connection.rollback()

        logging.exception(
            "Create training error"
        )

        return None

    finally:
        connection.close()


def finish_create_training(
    user_id,
    data,
):
    training_id = save_training(
        data
    )

    if not training_id:
        vk_send(
            user_id,
            "❌ Не удалось создать "
            "тренировку.\n\n"
            "Проверьте дату, время "
            "и остальные данные.",
            back_keyboard(),
        )
        return

    training = get_training(
        training_id
    )

    clear_state(
        user_id
    )

    if not training:
        vk_send(
            user_id,
            "✅ Тренировка создана.",
            main_keyboard(user_id),
        )
        return

    vk_send(
        user_id,
        "✅ Тренировка создана!\n\n"
        + training_text(training),
        main_keyboard(user_id),
    )


def show_all_trainings(
    user_id,
):
    trainings = get_future_trainings()

    if not trainings:
        vk_send(
            user_id,
            "📋 Будущих тренировок "
            "пока нет.",
            admin_keyboard(),
        )
        return

    parts = [
        "📋 Будущие тренировки",
        "",
    ]

    for training in trainings:
        parts.append(
            training_text(training)
        )
        parts.append(
            "\n────────────\n"
        )

    vk_send(
        user_id,
        "\n".join(parts).strip(),
        admin_keyboard(),
    )


def show_registration_trainings(
    user_id,
):
    trainings = get_future_trainings()

    if not trainings:
        vk_send(
            user_id,
            "👥 Будущих тренировок "
            "пока нет.",
            admin_keyboard(),
        )
        return

    rows = []

    for training in trainings:
        count = registered_count(
            training["id"]
        )

        label = (
            f"№{training['training_number']} "
            f"{training['training_date'].strftime('%d.%m')} "
            f"{training['start_time']} "
            f"{count}/{training['capacity']}"
        )

        rows.append(
            [
                text_button(label)
            ]
        )

    rows.append(
        [
            text_button(BACK)
        ]
    )

    set_state(
        user_id,
        "admin_registration_training",
    )

    vk_send(
        user_id,
        "👥 Выберите тренировку:",
        make_keyboard(rows),
    )


def show_participants(
    user_id,
    text,
):
    trainings = get_future_trainings()

    selected = None

    for training in trainings:
        if text.startswith(
            f"№{training['training_number']} "
        ):
            selected = training
            break

    if not selected:
        vk_send(
            user_id,
            "Тренировка не найдена.",
            back_keyboard(),
        )
        return

    connection = get_db()

    rows = connection.execute(
        """
        SELECT
            user_id,
            created_at
        FROM registrations
        WHERE training_id = ?
        ORDER BY id
        """,
        (selected["id"],),
    ).fetchall()

    connection.close()

    lines = [
        training_text(selected),
        "",
        f"👥 Записано: "
        f"{len(rows)}/"
        f"{selected['capacity']}",
        "",
    ]

    if not rows:
        lines.append(
            "Записей пока нет."
        )
    else:
        for index, row in enumerate(
            rows,
            1,
        ):
            lines.append(
                f"{index}. id{row['user_id']}"
            )

    set_state(
        user_id,
        "admin_registration_training",
    )

    vk_send(
        user_id,
        "\n".join(lines),
        back_keyboard(),
    )


# ============================================================
# CREATE TRAINING STATE
# ============================================================

def handle_create_state(
    user_id,
    state,
    text,
):
    data = get_state(
        user_id
    )

    if text == BACK:
        show_admin(user_id)
        return

    if state == "create_category":

        if text == "👧 Детская":
            create_ask_date(
                user_id,
                "Детская",
            )
            return

        if text == "🧑 Взрослая":
            create_ask_date(
                user_id,
                "Взрослая",
            )
            return

        vk_send(
            user_id,
            "Выберите направление "
            "кнопкой.",
            create_category_keyboard(),
        )

        return

    if state == "create_date":

        parsed = parse_date(text)

        if not parsed:
            vk_send(
                user_id,
                "❌ Неверная дата.\n\n"
                "Пример:\n"
                "05.10.2026",
            )
            return

        new_data = {
            "category": data[
                "category"
            ],
            "training_date": (
                parsed.isoformat()
            ),
        }

        create_ask_time(
            user_id,
            new_data,
        )

        return

    if state == "create_time":

        clean_text = (
            text
            .strip()
            .replace(" ", "")
            .replace("–", "-")
            .replace("—", "-")
        )

        parts = clean_text.split("-")

        if len(parts) != 2:
            vk_send(
                user_id,
                "❌ Неверный формат.\n\n"
                "Пример:\n"
                "19:00-20:30",
            )
            return

        start_time = parse_time(
            parts[0]
        )

        end_time = parse_time(
            parts[1]
        )

        if not start_time or not end_time:
            vk_send(
                user_id,
                "❌ Проверьте время.\n\n"
                "Пример:\n"
                "19:00-20:30",
            )
            return

        new_data = dict(data)

        new_data["start_time"] = (
            start_time
        )

        new_data["end_time"] = (
            end_time
        )

        create_ask_format(
            user_id,
            new_data,
        )

        return

    if state == "create_format":

        allowed = {
            "Техничка",
            "MIXED",
            "Женская",
            "Мужская",
            "Общая",
        }

        if text not in allowed:
            vk_send(
                user_id,
                "Выберите формат "
                "кнопкой.",
                format_keyboard(),
            )
            return

        new_data = dict(data)
        new_data["format"] = text

        create_ask_level(
            user_id,
            new_data,
        )

        return

    if state == "create_level":

        allowed = {
            "Начинающие",
            "Средний",
            "Продвинутый",
            "Любой уровень",
        }

        if text not in allowed:
            vk_send(
                user_id,
                "Выберите уровень "
                "кнопкой.",
                level_keyboard(),
            )
            return

        new_data = dict(data)
        new_data["level"] = text

        create_ask_capacity(
            user_id,
            new_data,
        )

        return

    if state == "create_capacity":

        try:
            capacity = int(
                text.strip()
            )
        except ValueError:
            vk_send(
                user_id,
                "❌ Введите количество "
                "мест числом.",
            )
            return

        if capacity <= 0:
            vk_send(
                user_id,
                "❌ Количество мест "
                "должно быть больше 0.",
            )
            return

        if (
            data["category"]
            == "Взрослая"
            and capacity < 4
        ):
            vk_send(
                user_id,
                "❌ Для взрослой "
                "тренировки минимум "
                "4 места.",
            )
            return

        new_data = dict(data)

        new_data["capacity"] = (
            capacity
        )

        create_ask_location(
            user_id,
            new_data,
        )

        return

    if state == "create_location":

        location = text.strip()

        if not location:
            vk_send(
                user_id,
                "❌ Укажите место "
                "проведения.",
            )
            return

        price = get_training_price(
            data["category"],
            data["capacity"],
        )

        if price is None:
            vk_send(
                user_id,
                "❌ Не удалось определить "
                "стоимость.",
                back_keyboard(),
            )
            return

        new_data = dict(data)

        new_data["location"] = location
        new_data["price"] = price

        finish_create_training(
            user_id,
            new_data,
        )

        return


# ============================================================
# MESSAGE HANDLER
# ============================================================

def handle_message(
    user_id,
    text,
):
    user_id = int(user_id)

    text = str(
        text or ""
    ).strip()

    state_data = get_state(
        user_id
    )

    state = state_data.get(
        "state",
        "main",
    )

    logging.info(
        "HANDLE MESSAGE "
        "user=%s state=%s text=%r",
        user_id,
        state,
        text,
    )

    # --------------------------------------------------------
    # CREATE TRAINING
    # --------------------------------------------------------

    if state.startswith(
        "create_"
    ):
        handle_create_state(
            user_id,
            state,
            text,
        )
        return

    # --------------------------------------------------------
    # BACK
    # --------------------------------------------------------

    if text == BACK:

        if state in {
            "prices",
            "individual",
            "schedule_category",
            "booking_category",
            "admin",
        }:
            show_main(user_id)
            return

        if state == "booking_date":
            show_booking_menu(
                user_id
            )
            return

        if state == "booking_training":
            category = state_data.get(
                "category"
            )

            if category:
                show_booking_dates(
                    user_id,
                    category,
                )
            else:
                show_booking_menu(
                    user_id
                )

            return

        if state == "booking_confirm":

            training = get_training(
                state_data.get(
                    "training_id"
                )
            )

            if training:

                parsed_date = parse_date(
                    training[
                        "training_date"
                    ]
                )

                show_booking_trainings(
                    user_id,
                    normalize_category(
                        training[
                            "category"
                        ]
                    ),
                    parsed_date.isoformat(),
                )

            else:
                show_booking_menu(
                    user_id
                )

            return

        if state == "admin_registration_training":
            show_admin(user_id)
            return

        show_main(user_id)
        return

    # --------------------------------------------------------
    # MAIN MENU
    # --------------------------------------------------------

    if text == "📅 Расписание":
        show_schedule_menu(
            user_id
        )
        return

    if text == "📝 Записаться":
        show_booking_menu(
            user_id
        )
        return

    if text == "💰 Цены":
        show_prices(
            user_id
        )
        return

    if text == "🏐 Индивидуальная тренировка":
        show_individual(
            user_id
        )
        return

    if (
        text == "⚙️ Админ-панель"
        and user_id in ADMINS
    ):
        show_admin(
            user_id
        )
        return

    # --------------------------------------------------------
    # ADMIN MENU
    # --------------------------------------------------------

    if (
        user_id in ADMINS
        and text == "➕ Создать тренировку"
    ):
        start_create_training(
            user_id
        )
        return

    if (
        user_id in ADMINS
        and text == "📋 Все тренировки"
    ):
        show_all_trainings(
            user_id
        )
        return

    if (
        user_id in ADMINS
        and text == "👥 Записи"
    ):
        show_registration_trainings(
            user_id
        )
        return

    # --------------------------------------------------------
    # SCHEDULE CATEGORY
    # --------------------------------------------------------

    if state == "schedule_category":

        if text == "👧 Детские":
            category = "Детская"

        elif text == "🧑 Взрослые":
            category = "Взрослая"

        else:
            vk_send(
                user_id,
                "Выберите направление "
                "кнопкой.",
                category_keyboard(),
            )
            return

        save_user_category(
            user_id,
            category,
        )

        show_schedule(
            user_id,
            category,
        )

        return

    # --------------------------------------------------------
    # BOOKING CATEGORY
    # --------------------------------------------------------

    if state == "booking_category":

        if text == "👧 Детские":
            category = "Детская"

        elif text == "🧑 Взрослые":
            category = "Взрослая"

        else:
            vk_send(
                user_id,
                "Выберите направление "
                "кнопкой.",
                category_keyboard(),
            )
            return

        save_user_category(
            user_id,
            category,
        )

        show_booking_dates(
            user_id,
            category,
        )

        return

    # --------------------------------------------------------
    # BOOKING DATE
    # --------------------------------------------------------

    if state == "booking_date":

        parsed_date = parse_date(
            text
        )

        if not parsed_date:
            vk_send(
                user_id,
                "Выберите дату "
                "кнопкой.",
            )
            return

        category = state_data.get(
            "category"
        )

        show_booking_trainings(
            user_id,
            category,
            parsed_date.isoformat(),
        )

        return

    # --------------------------------------------------------
    # BOOKING TRAINING
    # --------------------------------------------------------

    if state == "booking_training":

        training = find_training_from_button(
            state_data.get(
                "category"
            ),
            state_data.get(
                "selected_date"
            ),
            text,
        )

        if not training:
            vk_send(
                user_id,
                "Выберите тренировку "
                "кнопкой.",
            )
            return

        show_booking_confirmation(
            user_id,
            training,
        )

        return

    # --------------------------------------------------------
    # BOOKING CONFIRMATION
    # --------------------------------------------------------

    if state == "booking_confirm":

        if text != "✅ Записаться":
            vk_send(
                user_id,
                "Нажмите кнопку "
                "«✅ Записаться».",
            )
            return

        training_id = state_data.get(
            "training_id"
        )

        success, message = register_user(
            user_id,
            training_id,
        )

        if not success:
            vk_send(
                user_id,
                "❌ " + message,
                back_keyboard(),
            )
            return

        notify_admins(
            user_id,
            training_id,
        )

        clear_state(
            user_id
        )

        vk_send(
            user_id,
            "✅ Вы записаны "
            "на тренировку!",
            main_keyboard(user_id),
        )

        return

    # --------------------------------------------------------
    # ADMIN REGISTRATIONS
    # --------------------------------------------------------

    if (
        state == "admin_registration_training"
        and user_id in ADMINS
    ):
        show_participants(
            user_id,
            text,
        )
        return

    # --------------------------------------------------------
    # FALLBACK
    # --------------------------------------------------------

    vk_send(
        user_id,
        "🏐 VOLLEY WAVE\n\n"
        "Выберите действие:",
        main_keyboard(user_id),
    )


# ============================================================
# VK CALLBACK
# ============================================================

def process_vk_event(
    data,
):
    if not isinstance(
        data,
        dict,
    ):
        logging.error(
            "VK event is not dict"
        )
        return "ok"

    event_type = data.get(
        "type"
    )

    logging.info(
        "VK EVENT TYPE: %r",
        event_type,
    )

    # --------------------------------------------------------
    # CONFIRMATION
    # --------------------------------------------------------

    if event_type == "confirmation":
        logging.info(
            "VK confirmation request"
        )

        return (
            VK_CONFIRMATION_TOKEN
        )

    # --------------------------------------------------------
    # SECRET
    # --------------------------------------------------------

    received_secret = data.get(
        "secret"
    )

    if (
        VK_SECRET_KEY
        and received_secret
        != VK_SECRET_KEY
    ):
        logging.error(
            "VK SECRET MISMATCH"
        )

        logging.error(
            "Received secret: %r",
            received_secret,
        )

        return "ok"

    # --------------------------------------------------------
    # IGNORE OTHER EVENTS
    # --------------------------------------------------------

    if event_type != "message_new":
        return "ok"

    # --------------------------------------------------------
    # OBJECT
    # --------------------------------------------------------

    obj = data.get(
        "object"
    )

    if not isinstance(
        obj,
        dict,
    ):
        logging.error(
            "VK object is not dict: %r",
            obj,
        )
        return "ok"

    # --------------------------------------------------------
    # NEW VK FORMAT
    # --------------------------------------------------------

    message = obj.get(
        "message"
    )

    if isinstance(
        message,
        dict,
    ):
        user_id = message.get(
            "from_id"
        )

        text = message.get(
            "text",
            "",
        )

    # --------------------------------------------------------
    # FALLBACK OLD FORMAT
    # --------------------------------------------------------

    else:
        user_id = obj.get(
            "from_id"
        )

        text = obj.get(
            "text",
            "",
        )

    if not user_id:
        logging.error(
            "Cannot find user_id in VK event: %r",
            data,
        )
        return "ok"

    text = str(
        text or ""
    ).strip()

    logging.info(
        "VK MESSAGE: "
        "user_id=%s text=%r",
        user_id,
        text,
    )

    try:
        handle_message(
            int(user_id),
            text,
        )

    except Exception:
        logging.exception(
            "HANDLE MESSAGE ERROR"
        )

        try:
            vk_send(
                int(user_id),
                "⚠️ Произошла ошибка. "
                "Попробуйте ещё раз.",
                main_keyboard(
                    int(user_id)
                ),
            )
        except Exception:
            logging.exception(
                "ERROR MESSAGE SEND FAILED"
            )

    return "ok"


# ============================================================
# FLASK CALLBACK
# ============================================================

@app.route(
    "/callback",
    methods=["POST"],
)
def callback():
    try:
        data = request.get_json(
            silent=True
        )

        logging.info(
            "========== VK CALLBACK =========="
        )

        logging.info(
            "RAW CALLBACK: %r",
            data,
        )

        result = process_vk_event(
            data
        )

        logging.info(
            "CALLBACK RESPONSE: %r",
            result,
        )

        return result

    except Exception:
        logging.exception(
            "CALLBACK CRITICAL ERROR"
        )

        return "ok"


# ============================================================
# HEALTH
# ============================================================

@app.route(
    "/",
    methods=["GET"],
)
def index():
    return (
        f"VOLLEY WAVE VK BOT "
        f"{VERSION} WORKING",
        200,
    )


@app.route(
    "/health",
    methods=["GET"],
)
def health():
    return (
        "OK",
        200,
    )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    logging.info(
        "===================================="
    )

    logging.info(
        "VOLLEY WAVE VK BOT %s",
        VERSION,
    )

    logging.info(
        "GROUP_ID: %s",
        GROUP_ID,
    )

    logging.info(
        "VK API VERSION: %s",
        VK_API_VERSION,
    )

    logging.info(
        "VK TOKEN PRESENT: %s",
        bool(VK_TOKEN),
    )

    logging.info(
        "VK CONFIRMATION PRESENT: %s",
        bool(VK_CONFIRMATION_TOKEN),
    )

    logging.info(
        "VK SECRET PRESENT: %s",
        bool(VK_SECRET_KEY),
    )

    logging.info(
        "===================================="
    )

    init_db()

    port = int(
        os.getenv(
            "PORT",
            "10000",
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
    )
