import os
import json
import sqlite3
import logging
from datetime import datetime, date, timedelta

import requests
from flask import Flask, request


# ============================================================
# CONFIG
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

DB_FILE = "volley_wave.db"

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("volley_wave")


# ============================================================
# CONSTANTS
# ============================================================

WEEKDAYS = [
    "Понедельник",
    "Вторник",
    "Среда",
    "Четверг",
    "Пятница",
    "Суббота",
    "Воскресенье",
]

WEEKDAYS_SHORT = [
    "Пн",
    "Вт",
    "Ср",
    "Чт",
    "Пт",
    "Сб",
    "Вс",
]

MONTHS = [
    "",
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
]

LEVELS = [
    "Начальный",
    "Средний",
    "Продвинутый",
]

FORMATS = [
    "Техничка",
    "MIXED",
    "Женская",
    "Мужская",
    "Общая",
]

CHILDREN_PRICE = 600
ADULT_PRICE = 1200

WINTER_LOCATION = 'СК «Арена», ул. Молодогвардейцев, 7'
SUMMER_LOCATION = "Парк Гагарина"

USER_STATE = {}


# ============================================================
# DATABASE
# ============================================================

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def table_exists(conn, name):
    row = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type='table' AND name=?
        """,
        (name,),
    ).fetchone()

    return row is not None


def ensure_column(conn, table, column, definition):
    columns = [
        row["name"]
        for row in conn.execute(
            f"PRAGMA table_info({table})"
        ).fetchall()
    ]

    if column not in columns:
        conn.execute(
            f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
        )


def init_database():
    conn = get_db()

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vk_id INTEGER UNIQUE NOT NULL,
            first_name TEXT DEFAULT '',
            last_name TEXT DEFAULT '',
            is_blocked INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS trainings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            training_number INTEGER UNIQUE,
            training_date TEXT NOT NULL,
            weekday TEXT,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            title TEXT,
            category TEXT,
            age_group TEXT,
            level TEXT,
            format TEXT,
            coach TEXT,
            capacity INTEGER DEFAULT 10,
            price INTEGER DEFAULT 0,
            location TEXT,
            status TEXT DEFAULT 'active',
            template_id INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            training_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            status TEXT DEFAULT 'registered',
            registered_at TEXT DEFAULT CURRENT_TIMESTAMP,
            cancelled_at TEXT,
            cancellation_reason TEXT,
            UNIQUE(training_id, user_id)
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS admin_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_vk_id INTEGER,
            action TEXT,
            entity_type TEXT,
            entity_id INTEGER,
            details TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    ensure_column(
        conn,
        "trainings",
        "level",
        "TEXT",
    )

    ensure_column(
        conn,
        "trainings",
        "format",
        "TEXT",
    )

    ensure_column(
        conn,
        "trainings",
        "age_group",
        "TEXT",
    )

    ensure_column(
        conn,
        "trainings",
        "coach",
        "TEXT",
    )

    ensure_column(
        conn,
        "trainings",
        "capacity",
        "INTEGER DEFAULT 10",
    )

    ensure_column(
        conn,
        "trainings",
        "price",
        "INTEGER DEFAULT 0",
    )

    ensure_column(
        conn,
        "trainings",
        "location",
        "TEXT",
    )

    conn.commit()
    conn.close()

    logger.info("Database initialized")


def ensure_user(user_id):
    conn = get_db()

    conn.execute(
        """
        INSERT INTO users (vk_id)
        VALUES (?)
        ON CONFLICT(vk_id)
        DO UPDATE SET updated_at=CURRENT_TIMESTAMP
        """,
        (user_id,),
    )

    conn.commit()
    conn.close()


def get_internal_user_id(vk_id):
    ensure_user(vk_id)

    conn = get_db()

    row = conn.execute(
        """
        SELECT id
        FROM users
        WHERE vk_id=?
        """,
        (vk_id,),
    ).fetchone()

    conn.close()

    return row["id"]


# ============================================================
# CATEGORY / LABEL HELPERS
# ============================================================

def normalize_category(value):
    if not value:
        return None

    value = str(value).strip().lower()

    if value in {
        "children",
        "child",
        "kids",
        "дети",
        "детская",
        "👧 дети",
    }:
        return "children"

    if value in {
        "adults",
        "adult",
        "взрослые",
        "взрослый",
        "🧑 взрослые",
    }:
        return "adults"

    return value


def category_label(category):
    category = normalize_category(category)

    if category == "children":
        return "👧 Дети"

    if category == "adults":
        return "🧑 Взрослые"

    return "Все"


def category_from_text(text):
    if text == "👧 Дети":
        return "children"

    if text == "🧑 Взрослые":
        return "adults"

    return None


# ============================================================
# DATE HELPERS
# ============================================================

def format_date_long(value):
    if isinstance(value, str):
        value = datetime.strptime(
            value,
            "%Y-%m-%d",
        ).date()

    return (
        f"{WEEKDAYS[value.weekday()]}, "
        f"{value.day} {MONTHS[value.month]} "
        f"{value.year}"
    )


def format_date_short(value):
    if isinstance(value, str):
        value = datetime.strptime(
            value,
            "%Y-%m-%d",
        ).date()

    return (
        f"{WEEKDAYS_SHORT[value.weekday()]} "
        f"{value.day:02d}.{value.month:02d}"
    )


def parse_date(text):
    formats = [
        "%d.%m.%Y",
        "%d-%m-%Y",
        "%Y-%m-%d",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(
                text.strip(),
                fmt,
            ).date()
        except ValueError:
            pass

    return None


# ============================================================
# VK
# ============================================================

def vk_api(method, params):
    params = dict(params)
    params["access_token"] = VK_TOKEN
    params["v"] = VK_API_VERSION

    try:
        response = requests.post(
            f"https://api.vk.com/method/{method}",
            data=params,
            timeout=20,
        )

        data = response.json()

        if "error" in data:
            logger.error(
                "VK API error in %s: %s",
                method,
                data,
            )
            return None

        return data.get("response")

    except Exception as e:
        logger.exception(
            "VK API exception: %s",
            e,
        )
        return None


def button(label, color="secondary"):
    return {
        "action": {
            "type": "text",
            "label": label,
        },
        "color": color,
    }


def send_message(user_id, text, keyboard=None):
    params = {
        "user_id": user_id,
        "random_id": 0,
        "message": text,
    }

    if keyboard is not None:
        params["keyboard"] = json.dumps(
            keyboard,
            ensure_ascii=False,
        )

    return vk_api(
        "messages.send",
        params,
    )


# ============================================================
# KEYBOARDS
# ============================================================

def main_keyboard(user_id):
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
            button("🎯 Индивидуальная", "secondary"),
        ],
        [
            button("❓ Задать вопрос", "secondary"),
        ],
    ]

    if user_id in ADMINS:
        rows.append(
            [
                button("⚙️ Админ-панель", "negative"),
            ]
        )

    return {
        "one_time": False,
        "buttons": rows,
    }


def back_keyboard(label="⬅️ Назад"):
    return {
        "one_time": False,
        "buttons": [
            [
                button(label, "secondary"),
            ]
        ],
    }


def category_keyboard(back="⬅️ Назад"):
    return {
        "one_time": False,
        "buttons": [
            [
                button("👧 Дети", "primary"),
                button("🧑 Взрослые", "primary"),
            ],
            [
                button(back, "secondary"),
            ],
        ],
    }


def level_keyboard():
    return {
        "one_time": False,
        "buttons": [
            [
                button("Начальный", "primary"),
                button("Средний", "primary"),
            ],
            [
                button("Продвинутый", "primary"),
            ],
            [
                button("⬅️ Отмена", "secondary"),
            ],
        ],
    }


def format_keyboard():
    return {
        "one_time": False,
        "buttons": [
            [
                button("Техничка", "primary"),
                button("MIXED", "primary"),
            ],
            [
                button("Женская", "primary"),
                button("Мужская", "primary"),
            ],
            [
                button("Общая", "primary"),
            ],
            [
                button("⬅️ Отмена", "secondary"),
            ],
        ],
    }


# ============================================================
# STATE
# ============================================================

def set_state(user_id, state, **data):
    USER_STATE[user_id] = {
        "state": state,
        **data,
    }

    logger.info(
        "STATE user=%s -> %s",
        user_id,
        state,
    )


def get_state(user_id):
    return USER_STATE.get(
        user_id,
        {"state": "main"},
    )


def clear_state(user_id):
    USER_STATE.pop(user_id, None)


# ============================================================
# TRAININGS
# ============================================================

def get_next_training_number(conn):
    row = conn.execute(
        """
        SELECT COALESCE(MAX(training_number), 0) + 1 AS n
        FROM trainings
        """
    ).fetchone()

    return row["n"]


def get_training(training_id):
    conn = get_db()

    row = conn.execute(
        """
        SELECT *
        FROM trainings
        WHERE id=?
        """,
        (training_id,),
    ).fetchone()

    conn.close()

    return row


def get_training_by_number(number):
    conn = get_db()

    row = conn.execute(
        """
        SELECT *
        FROM trainings
        WHERE training_number=?
        """,
        (number,),
    ).fetchone()

    conn.close()

    return row


def create_training(
    training_date,
    start_time,
    end_time,
    title,
    category,
    age_group,
    level,
    training_format,
    coach,
    capacity,
    price,
):
    category = normalize_category(category)

    conn = get_db()

    existing = conn.execute(
        """
        SELECT id
        FROM trainings
        WHERE training_date=?
          AND start_time=?
          AND end_time=?
          AND title=?
          AND category=?
          AND level=?
          AND format=?
          AND status != 'cancelled'
        LIMIT 1
        """,
        (
            training_date,
            start_time,
            end_time,
            title,
            category,
            level,
            training_format,
        ),
    ).fetchone()

    if existing:
        conn.close()
        return existing["id"]

    d = datetime.strptime(
        training_date,
        "%Y-%m-%d",
    ).date()

    number = get_next_training_number(conn)

    cursor = conn.execute(
        """
        INSERT INTO trainings (
            training_number,
            training_date,
            weekday,
            start_time,
            end_time,
            title,
            category,
            age_group,
            level,
            format,
            coach,
            capacity,
            price,
            location,
            status
        )
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, 'active'
        )
        """,
        (
            number,
            training_date,
            WEEKDAYS[d.weekday()],
            start_time,
            end_time,
            title,
            category,
            age_group,
            level,
            training_format,
            coach,
            capacity,
            price,
            WINTER_LOCATION,
        ),
    )

    training_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return training_id


def get_week_start():
    today = date.today()
    return today - timedelta(
        days=today.weekday()
    )


def get_week_trainings(category=None):
    monday = get_week_start()
    sunday = monday + timedelta(days=6)

    conn = get_db()

    sql = """
        SELECT *
        FROM trainings
        WHERE training_date >= ?
          AND training_date <= ?
          AND status='active'
    """

    params = [
        monday.strftime("%Y-%m-%d"),
        sunday.strftime("%Y-%m-%d"),
    ]

    category = normalize_category(category)

    if category in ("children", "adults"):
        sql += " AND category=?"
        params.append(category)

    sql += """
        ORDER BY training_date, start_time, id
    """

    rows = conn.execute(
        sql,
        params,
    ).fetchall()

    conn.close()

    return rows


def get_future_trainings(category=None):
    conn = get_db()

    sql = """
        SELECT *
        FROM trainings
        WHERE training_date >= ?
          AND status='active'
    """

    params = [
        date.today().strftime("%Y-%m-%d")
    ]

    category = normalize_category(category)

    if category in ("children", "adults"):
        sql += " AND category=?"
        params.append(category)

    sql += """
        ORDER BY training_date, start_time, id
    """

    rows = conn.execute(
        sql,
        params,
    ).fetchall()

    conn.close()

    return rows


# ============================================================
# REGISTRATIONS
# ============================================================

def registration_count(training_id):
    conn = get_db()

    row = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM registrations
        WHERE training_id=?
          AND status='registered'
        """,
        (training_id,),
    ).fetchone()

    conn.close()

    return row["count"]


def get_registration(training_id, vk_id):
    internal_id = get_internal_user_id(vk_id)

    conn = get_db()

    row = conn.execute(
        """
        SELECT *
        FROM registrations
        WHERE training_id=?
          AND user_id=?
        LIMIT 1
        """,
        (
            training_id,
            internal_id,
        ),
    ).fetchone()

    conn.close()

    return row


def register_user(training_id, vk_id):
    internal_id = get_internal_user_id(vk_id)

    conn = get_db()

    training = conn.execute(
        """
        SELECT *
        FROM trainings
        WHERE id=?
        """,
        (training_id,),
    ).fetchone()

    if not training:
        conn.close()
        return False, "not_found"

    if training["status"] != "active":
        conn.close()
        return False, "cancelled"

    existing = conn.execute(
        """
        SELECT *
        FROM registrations
        WHERE training_id=?
          AND user_id=?
        LIMIT 1
        """,
        (
            training_id,
            internal_id,
        ),
    ).fetchone()

    if existing and existing["status"] == "registered":
        conn.close()
        return False, "already"

    count = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM registrations
        WHERE training_id=?
          AND status='registered'
        """,
        (training_id,),
    ).fetchone()["count"]

    if count >= training["capacity"]:
        conn.close()
        return False, "full"

    if existing:
        conn.execute(
            """
            UPDATE registrations
            SET status='registered',
                registered_at=CURRENT_TIMESTAMP,
                cancelled_at=NULL,
                cancellation_reason=NULL
            WHERE id=?
            """,
            (existing["id"],),
        )
    else:
        conn.execute(
            """
            INSERT INTO registrations (
                training_id,
                user_id,
                status
            )
            VALUES (?, ?, 'registered')
            """,
            (
                training_id,
                internal_id,
            ),
        )

    conn.commit()
    conn.close()

    return True, "ok"


def cancel_user_registration(
    training_id,
    vk_id,
):
    internal_id = get_internal_user_id(vk_id)

    conn = get_db()

    registration = conn.execute(
        """
        SELECT *
        FROM registrations
        WHERE training_id=?
          AND user_id=?
          AND status='registered'
        LIMIT 1
        """,
        (
            training_id,
            internal_id,
        ),
    ).fetchone()

    if not registration:
        conn.close()
        return False, "not_found"

    training = conn.execute(
        """
        SELECT *
        FROM trainings
        WHERE id=?
        """,
        (training_id,),
    ).fetchone()

    if not training:
        conn.close()
        return False, "not_found"

    try:
        training_dt = datetime.strptime(
            f"{training['training_date']} "
            f"{training['start_time']}",
            "%Y-%m-%d %H:%M",
        )

        hours_left = (
            training_dt - datetime.now()
        ).total_seconds() / 3600

        if hours_left < 24:
            conn.close()
            return False, "too_late"

    except Exception:
        pass

    conn.execute(
        """
        UPDATE registrations
        SET status='cancelled',
            cancelled_at=CURRENT_TIMESTAMP,
            cancellation_reason='user'
        WHERE id=?
        """,
        (registration["id"],),
    )

    conn.commit()
    conn.close()

    return True, "ok"


def get_user_trainings(vk_id):
    internal_id = get_internal_user_id(vk_id)

    conn = get_db()

    rows = conn.execute(
        """
        SELECT
            r.id AS registration_id,
            r.status AS registration_status,
            t.*
        FROM registrations r
        JOIN trainings t
            ON t.id=r.training_id
        WHERE r.user_id=?
          AND r.status='registered'
          AND t.status='active'
          AND t.training_date >= ?
        ORDER BY
            t.training_date,
            t.start_time
        """,
        (
            internal_id,
            date.today().strftime("%Y-%m-%d"),
        ),
    ).fetchall()

    conn.close()

    return rows


def get_participants(training_id):
    conn = get_db()

    rows = conn.execute(
        """
        SELECT
            u.vk_id,
            u.first_name,
            u.last_name,
            r.registered_at
        FROM registrations r
        JOIN users u
            ON u.id=r.user_id
        WHERE r.training_id=?
          AND r.status='registered'
        ORDER BY r.registered_at, r.id
        """,
        (training_id,),
    ).fetchall()

    conn.close()

    return rows


# ============================================================
# ADMIN LOG
# ============================================================

def admin_log(
    admin_id,
    action,
    entity_type="",
    entity_id=None,
    details="",
):
    try:
        conn = get_db()

        conn.execute(
            """
            INSERT INTO admin_logs (
                admin_vk_id,
                action,
                entity_type,
                entity_id,
                details
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                admin_id,
                action,
                entity_type,
                entity_id,
                details,
            ),
        )

        conn.commit()
        conn.close()

    except Exception as e:
        logger.error(
            "Admin log error: %s",
            e,
        )


# ============================================================
# TRAINING DETAILS
# ============================================================

def training_details_text(training):
    count = registration_count(
        training["id"]
    )

    return (
        f"🏐 Тренировка №{training['training_number']}\n\n"
        f"📅 {format_date_long(training['training_date'])}\n"
        f"⏰ {training['start_time']}–{training['end_time']}\n"
        f"👥 {category_label(training['category'])}\n"
        f"🎯 {training['title']}\n"
        f"📊 Уровень: {training['level']}\n"
        f"🏖 Формат: {training['format']}\n"
        f"👤 Возраст: {training['age_group']}\n"
        f"👨‍🏫 Тренер: {training['coach']}\n"
        f"📍 {training['location']}\n"
        f"💰 Стоимость: {training['price']} ₽\n\n"
        f"👥 Записано: {count}/{training['capacity']}"
    )


# ============================================================
# BOOKING
# ============================================================

def start_booking(user_id):
    set_state(
        user_id,
        "booking_category",
    )

    send_message(
        user_id,
        "🏐 ЗАПИСЬ НА ТРЕНИРОВКУ\n\n"
        "Выберите категорию:",
        category_keyboard(),
    )


def show_booking_dates(user_id, category):
    category = normalize_category(category)

    trainings = get_future_trainings(
        category
    )

    if not trainings:
        send_message(
            user_id,
            "На ближайшее время тренировок нет.",
            category_keyboard(),
        )
        return

    dates = []

    for training in trainings:
        if training["training_date"] not in dates:
            dates.append(
                training["training_date"]
            )

        if len(dates) >= 14:
            break

    rows = []

    # Максимум 7 строк с датами + назад.
    # VK ограничение не превышаем.
    for date_string in dates[:7]:
        rows.append(
            [
                button(
                    format_date_short(
                        date_string
                    ),
                    "primary",
                )
            ]
        )

    rows.append(
        [
            button(
                "⬅️ К категориям",
                "secondary",
            )
        ]
    )

    set_state(
        user_id,
        "booking_date",
        category=category,
        dates=dates,
    )

    send_message(
        user_id,
        f"{category_label(category)}\n\n"
        "Выберите дату:",
        {
            "one_time": False,
            "buttons": rows,
        },
    )


def show_booking_trainings(
    user_id,
    category,
    date_string,
):
    category = normalize_category(category)

    conn = get_db()

    rows = conn.execute(
        """
        SELECT *
        FROM trainings
        WHERE training_date=?
          AND category=?
          AND status='active'
        ORDER BY start_time, id
        """,
        (
            date_string,
            category,
        ),
    ).fetchall()

    conn.close()

    if not rows:
        send_message(
            user_id,
            "На выбранную дату тренировок нет.",
            back_keyboard("⬅️ К датам"),
        )
        return

    buttons = []

    for training in rows:
        count = registration_count(
            training["id"]
        )

        buttons.append(
            [
                button(
                    f"{training['start_time']}–"
                    f"{training['end_time']} "
                    f"({count}/{training['capacity']})",
                    "primary",
                )
            ]
        )

    buttons.append(
        [
            button(
                "⬅️ К датам",
                "secondary",
            )
        ]
    )

    set_state(
        user_id,
        "booking_training",
        category=category,
        date=date_string,
        training_ids=[
            row["id"]
            for row in rows
        ],
    )

    send_message(
        user_id,
        f"{category_label(category)}\n"
        f"📅 {format_date_long(date_string)}\n\n"
        "Выберите тренировку:",
        {
            "one_time": False,
            "buttons": buttons,
        },
    )


def show_booking_details(
    user_id,
    training_id,
):
    training = get_training(
        training_id
    )

    if not training:
        send_message(
            user_id,
            "❌ Тренировка не найдена.",
        )
        return

    registration = get_registration(
        training_id,
        user_id,
    )

    if (
        registration
        and registration["status"] == "registered"
    ):
        keyboard = {
            "one_time": False,
            "buttons": [
                [
                    button(
                        "❌ Отменить запись",
                        "negative",
                    )
                ],
                [
                    button(
                        "⬅️ Назад",
                        "secondary",
                    )
                ],
            ],
        }
    elif (
        registration
        and registration["status"] == "cancelled"
    ):
        keyboard = {
            "one_time": False,
            "buttons": [
                [
                    button(
                        "✅ Записаться снова",
                        "primary",
                    )
                ],
                [
                    button(
                        "⬅️ Назад",
                        "secondary",
                    )
                ],
            ],
        }
    elif (
        registration_count(training_id)
        >= training["capacity"]
    ):
        keyboard = back_keyboard()
    else:
        keyboard = {
            "one_time": False,
            "buttons": [
                [
                    button(
                        "✅ Записаться",
                        "primary",
                    )
                ],
                [
                    button(
                        "⬅️ Назад",
                        "secondary",
                    )
                ],
            ],
        }

    set_state(
        user_id,
        "training_details",
        training_id=training_id,
    )

    send_message(
        user_id,
        training_details_text(training),
        keyboard,
    )


# ============================================================
# MY TRAININGS
# ============================================================

def show_my_trainings(user_id):
    rows = get_user_trainings(
        user_id
    )

    if not rows:
        send_message(
            user_id,
            "👤 МОИ ТРЕНИРОВКИ\n\n"
            "У вас нет предстоящих тренировок.",
            {
                "one_time": False,
                "buttons": [
                    [
                        button(
                            "🏐 Записаться",
                            "primary",
                        )
                    ],
                    [
                        button(
                            "⬅️ Главное меню",
                            "secondary",
                        )
                    ],
                ],
            },
        )
        return

    text = "👤 МОИ ТРЕНИРОВКИ\n\n"

    buttons = []

    for row in rows:
        text += (
            f"🏐 №{row['training_number']}\n"
            f"📅 {format_date_long(row['training_date'])}\n"
            f"⏰ {row['start_time']}–{row['end_time']}\n"
            f"🎯 {row['title']}\n"
            f"🏖 {row['format']}\n\n"
        )

        buttons.append(
            [
                button(
                    f"№{row['training_number']} "
                    f"{row['start_time']}",
                    "primary",
                )
            ]
        )

    buttons.append(
        [
            button(
                "⬅️ Главное меню",
                "secondary",
            )
        ]
    )

    set_state(
        user_id,
        "my_trainings",
        training_ids=[
            row["id"]
            for row in rows
        ],
    )

    send_message(
        user_id,
        text,
        {
            "one_time": False,
            "buttons": buttons,
        },
    )


# ============================================================
# SCHEDULE
# ============================================================

def show_schedule_categories(user_id):
    set_state(
        user_id,
        "schedule_category",
    )

    send_message(
        user_id,
        "📅 РАСПИСАНИЕ\n\n"
        "Покажу расписание на всю текущую неделю.\n\n"
        "Выберите категорию:",
        category_keyboard(),
    )


def show_week_schedule(
    user_id,
    category,
):
    category = normalize_category(category)

    rows = get_week_trainings(
        category
    )

    if not rows:
        send_message(
            user_id,
            "На этой неделе тренировок нет.",
            back_keyboard(),
        )
        return

    text = (
        f"📅 РАСПИСАНИЕ — {category_label(category)}\n"
        f"Неделя с {format_date_short(get_week_start())}\n\n"
    )

    current_date = None

    for training in rows:
        if training["training_date"] != current_date:
            current_date = training["training_date"]

            text += (
                f"━━ {format_date_long(current_date)} ━━\n"
            )

        count = registration_count(
            training["id"]
        )

        text += (
            f"🏐 №{training['training_number']} "
            f"{training['start_time']}–"
            f"{training['end_time']}\n"
            f"🎯 {training['title']}\n"
            f"📊 {training['level']} · "
            f"{training['format']}\n"
            f"👥 {count}/{training['capacity']} · "
            f"{training['price']} ₽\n\n"
        )

    # Здесь специально НЕТ кнопки на каждый день.
    # Расписание отображается целиком одним сообщением.
    send_message(
        user_id,
        text,
        {
            "one_time": False,
            "buttons": [
                [
                    button(
                        "🏐 Записаться",
                        "primary",
                    )
                ],
                [
                    button(
                        "⬅️ Назад",
                        "secondary",
                    )
                ],
            ],
        },
    )


# ============================================================
# INDIVIDUAL
# ============================================================

def show_individual(user_id):
    set_state(
        user_id,
        "individual",
    )

    send_message(
        user_id,
        "🎯 ИНДИВИДУАЛЬНАЯ ТРЕНИРОВКА\n\n"
        "Индивидуальная тренировка под вашу задачу:\n"
        "• техника\n"
        "• приём\n"
        "• защита\n"
        "• атака\n"
        "• подача\n"
        "• блок\n"
        "• игровая подготовка\n\n"
        "Нажмите кнопку ниже, чтобы связаться "
        "с администратором.",
        {
            "one_time": False,
            "buttons": [
                [
                    button(
                        "✉️ Написать администратору",
                        "primary",
                    )
                ],
                [
                    button(
                        "⬅️ Назад",
                        "secondary",
                    )
                ],
            ],
        },
    )


# ============================================================
# PRICES / LOCATION
# ============================================================

def show_prices(user_id):
    send_message(
        user_id,
        "💰 ЦЕНЫ\n\n"
        "👧 Дети — 600 ₽ за тренировку.\n\n"
        "🧑 Взрослые:\n"
        "1200 ₽/человек.\n"
        "При группе от 7 человек — 1000 ₽/человек.",
        back_keyboard(),
    )


def show_locations(user_id):
    send_message(
        user_id,
        "📍 ГДЕ ТРЕНИРУЕМСЯ\n\n"
        f"❄️ Зимой:\n{WINTER_LOCATION}\n\n"
        f"☀️ Летом:\n{SUMMER_LOCATION}",
        back_keyboard(),
    )


# ============================================================
# QUESTION / ADMIN CONTACT
# ============================================================

def start_question(user_id, source="question"):
    set_state(
        user_id,
        "question",
        source=source,
    )

    send_message(
        user_id,
        "✉️ Напишите сообщение администратору "
        "следующим сообщением.\n\n"
        "Мы получим его и свяжемся с вами.",
        back_keyboard(),
    )


# ============================================================
# ADMIN
# ============================================================

def admin_keyboard():
    return {
        "one_time": False,
        "buttons": [
            [
                button(
                    "📅 Расписание",
                    "primary",
                ),
                button(
                    "👥 Участники",
                    "primary",
                ),
            ],
            [
                button(
                    "➕ Создать тренировку",
                    "primary",
                ),
            ],
            [
                button(
                    "🏠 Главное меню",
                    "secondary",
                ),
            ],
        ],
    }


def show_admin(user_id):
    if user_id not in ADMINS:
        return

    set_state(
        user_id,
        "admin",
    )

    send_message(
        user_id,
        "⚙️ АДМИН-ПАНЕЛЬ\n\n"
        "Выберите действие:",
        admin_keyboard(),
    )


def show_admin_schedule(user_id):
    rows = get_week_trainings()

    if not rows:
        send_message(
            user_id,
            "На этой неделе тренировок нет.",
            admin_keyboard(),
        )
        return

    text = "📅 АДМИН — РАСПИСАНИЕ\n\n"

    current_date = None

    for training in rows:
        if training["training_date"] != current_date:
            current_date = training["training_date"]

            text += (
                f"━━ {format_date_long(current_date)} ━━\n"
            )

        count = registration_count(
            training["id"]
        )

        text += (
            f"№{training['training_number']} "
            f"{training['start_time']}–"
            f"{training['end_time']} — "
            f"{training['title']}\n"
            f"{category_label(training['category'])} · "
            f"{training['level']} · "
            f"{training['format']}\n"
            f"👥 {count}/{training['capacity']}\n\n"
        )

    send_message(
        user_id,
        text,
        admin_keyboard(),
    )


def show_admin_participants(user_id):
    rows = get_future_trainings()

    if not rows:
        send_message(
            user_id,
            "Предстоящих тренировок нет.",
            admin_keyboard(),
        )
        return

    # Максимум 8 кнопок + назад.
    # Для остальных показываем вторую страницу.
    page = get_state(user_id).get(
        "page",
        0,
    )

    per_page = 7

    total_pages = (
        len(rows) + per_page - 1
    ) // per_page

    page = max(
        0,
        min(page, total_pages - 1),
    )

    start = page * per_page
    current = rows[
        start:start + per_page
    ]

    buttons = []

    for training in current:
        count = registration_count(
            training["id"]
        )

        buttons.append(
            [
                button(
                    f"№{training['training_number']} "
                    f"{format_date_short(training['training_date'])} "
                    f"{training['start_time']} "
                    f"({count})",
                    "primary",
                )
            ]
        )

    navigation = []

    if page > 0:
        navigation.append(
            button(
                "◀️ Назад",
                "secondary",
            )
        )

    if page < total_pages - 1:
        navigation.append(
            button(
                "Далее ▶️",
                "secondary",
            )
        )

    if navigation:
        buttons.append(navigation)

    buttons.append(
        [
            button(
                "⬅️ Админ-панель",
                "secondary",
            )
        ]
    )

    set_state(
        user_id,
        "admin_participants",
        page=page,
        training_ids=[
            row["id"]
            for row in rows
        ],
    )

    send_message(
        user_id,
        "👥 УЧАСТНИКИ ТРЕНИРОВОК\n\n"
        f"Страница {page + 1} из {total_pages}\n"
        "Выберите тренировку:",
        {
            "one_time": False,
            "buttons": buttons,
        },
    )


def show_admin_training(
    user_id,
    training_id,
):
    training = get_training(
        training_id
    )

    if not training:
        send_message(
            user_id,
            "Тренировка не найдена.",
        )
        return

    participants = get_participants(
        training_id
    )

    text = (
        f"👥 ТРЕНИРОВКА №{training['training_number']}\n\n"
        f"📅 {format_date_long(training['training_date'])}\n"
        f"⏰ {training['start_time']}–{training['end_time']}\n"
        f"🎯 {training['title']}\n"
        f"📊 {training['level']}\n"
        f"🏖 {training['format']}\n\n"
        f"👥 Участников: "
        f"{len(participants)}/{training['capacity']}\n\n"
    )

    if participants:
        for i, person in enumerate(
            participants,
            start=1,
        ):
            name = (
                f"{person['first_name'] or ''} "
                f"{person['last_name'] or ''}"
            ).strip()

            if not name:
                name = "Без имени"

            text += f"{i}. {name}\n"
    else:
        text += "Пока никто не записан."

    send_message(
        user_id,
        text,
        {
            "one_time": False,
            "buttons": [
                [
                    button(
                        "⬅️ К тренировкам",
                        "secondary",
                    )
                ],
                [
                    button(
                        "⚙️ Админ-панель",
                        "secondary",
                    )
                ],
            ],
        },
    )


# ============================================================
# ADMIN CREATE TRAINING
# ============================================================

def start_create_training(user_id):
    set_state(
        user_id,
        "create_date",
    )

    send_message(
        user_id,
        "➕ СОЗДАНИЕ ТРЕНИРОВКИ\n\n"
        "Введите дату:\n\n"
        "Например:\n"
        "05.10.2026",
        back_keyboard("⬅️ Отмена"),
    )


def create_date_step(
    user_id,
    text,
):
    parsed = parse_date(text)

    if not parsed:
        send_message(
            user_id,
            "❌ Не понимаю дату.\n\n"
            "Введите в формате ДД.ММ.ГГГГ\n"
            "Например: 05.10.2026",
        )
        return

    set_state(
        user_id,
        "create_time",
        training_date=parsed.strftime(
            "%Y-%m-%d"
        ),
    )

    # ВАЖНО:
    # после даты НЕТ кнопок с датами.
    send_message(
        user_id,
        f"📅 {format_date_long(parsed)}\n\n"
        "Теперь введите время:\n\n"
        "Например:\n"
        "17:00-19:00",
        back_keyboard("⬅️ Отмена"),
    )


def create_time_step(
    user_id,
    text,
):
    value = text.strip()

    parts = value.split("-")

    if len(parts) != 2:
        send_message(
            user_id,
            "❌ Неверный формат.\n\n"
            "Введите, например:\n"
            "17:00-19:00",
        )
        return

    start = parts[0].strip()
    end = parts[1].strip()

    try:
        datetime.strptime(
            start,
            "%H:%M",
        )

        datetime.strptime(
            end,
            "%H:%M",
        )
    except ValueError:
        send_message(
            user_id,
            "❌ Время указано неправильно.\n\n"
            "Пример: 17:00-19:00",
        )
        return

    state = get_state(user_id)

    set_state(
        user_id,
        "create_category",
        training_date=state[
            "training_date"
        ],
        start_time=start,
        end_time=end,
    )

    send_message(
        user_id,
        "Выберите категорию:",
        category_keyboard(
            "⬅️ Отмена"
        ),
    )


def create_category_step(
    user_id,
    category,
):
    state = get_state(user_id)

    set_state(
        user_id,
        "create_title",
        **state,
        category=category,
    )

    send_message(
        user_id,
        "Введите название тренировки.\n\n"
        "Например:\n"
        "Техническая тренировка",
        back_keyboard("⬅️ Отмена"),
    )


def create_title_step(
    user_id,
    text,
):
    state = get_state(user_id)

    set_state(
        user_id,
        "create_level",
        **state,
        title=text.strip(),
    )

    send_message(
        user_id,
        "Выберите уровень:",
        level_keyboard(),
    )


def create_level_step(
    user_id,
    level,
):
    if level not in LEVELS:
        send_message(
            user_id,
            "Выберите уровень кнопкой.",
            level_keyboard(),
        )
        return

    state = get_state(user_id)

    set_state(
        user_id,
        "create_format",
        **state,
        level=level,
    )

    send_message(
        user_id,
        "Выберите формат:",
        format_keyboard(),
    )


def create_format_step(
    user_id,
    training_format,
):
    if training_format not in FORMATS:
        send_message(
            user_id,
            "Выберите формат кнопкой.",
            format_keyboard(),
        )
        return

    state = get_state(user_id)

    set_state(
        user_id,
        "create_capacity",
        **state,
        training_format=training_format,
    )

    send_message(
        user_id,
        "Введите максимальное количество участников.\n\n"
        "Например: 10",
        back_keyboard("⬅️ Отмена"),
    )


def create_capacity_step(
    user_id,
    text,
):
    try:
        capacity = int(
            text.strip()
        )

        if capacity <= 0:
            raise ValueError

    except ValueError:
        send_message(
            user_id,
            "❌ Введите положительное число.\n\n"
            "Например: 10",
        )
        return

    state = get_state(user_id)

    set_state(
        user_id,
        "create_price",
        **state,
        capacity=capacity,
    )

    send_message(
        user_id,
        "Введите стоимость тренировки в рублях.\n\n"
        "Например: 1200",
        back_keyboard("⬅️ Отмена"),
    )


def create_price_step(
    user_id,
    text,
):
    try:
        price = int(
            text.strip()
            .replace("₽", "")
            .replace(" ", "")
        )

        if price < 0:
            raise ValueError

    except ValueError:
        send_message(
            user_id,
            "❌ Введите стоимость числом.\n\n"
            "Например: 1200",
        )
        return

    state = get_state(user_id)

    category = state["category"]

    age_group = (
        "5–14 лет"
        if category == "children"
        else "18+"
    )

    training_id = create_training(
        training_date=state[
            "training_date"
        ],
        start_time=state[
            "start_time"
        ],
        end_time=state[
            "end_time"
        ],
        title=state["title"],
        category=category,
        age_group=age_group,
        level=state["level"],
        training_format=state[
            "training_format"
        ],
        coach="Алексей",
        capacity=state["capacity"],
        price=price,
    )

    training = get_training(
        training_id
    )

    admin_log(
        user_id,
        "create_training",
        "training",
        training_id,
        f"№{training['training_number']}",
    )

    clear_state(user_id)

    send_message(
        user_id,
        "✅ ТРЕНИРОВКА СОЗДАНА\n\n"
        f"🏐 №{training['training_number']}\n"
        f"📅 {format_date_long(training['training_date'])}\n"
        f"⏰ {training['start_time']}–{training['end_time']}\n"
        f"👥 {category_label(training['category'])}\n"
        f"🎯 {training['title']}\n"
        f"📊 {training['level']}\n"
        f"🏖 {training['format']}\n"
        f"👤 {training['age_group']}\n"
        f"👥 До {training['capacity']} человек\n"
        f"💰 {training['price']} ₽",
        admin_keyboard(),
    )


# ============================================================
# MESSAGE HANDLER
# ============================================================

def handle_message(
    user_id,
    text,
):
    text = (text or "").strip()

    ensure_user(user_id)

    state = get_state(user_id)
    state_name = state.get(
        "state"
    )

    logger.info(
        "MESSAGE user=%s text=%r state=%s",
        user_id,
        text,
        state_name,
    )

    # ========================================================
    # GLOBAL BACK / MAIN MENU
    # ========================================================

    if text in {
        "🏠 Главное меню",
        "Начать",
        "/start",
        "Старт",
    }:
        clear_state(user_id)
        send_message(
            user_id,
            "🏐 VOLLEY WAVE\n\n"
            "Выберите действие:",
            main_keyboard(user_id),
        )
        return

    # ========================================================
    # ADMIN STATES — ДО ОБЩИХ КНОПОК
    # ========================================================

    if user_id in ADMINS:

        # ----------------------------------------------------
        # CREATE DATE
        # ----------------------------------------------------

        if state_name == "create_date":
            if text == "⬅️ Отмена":
                clear_state(user_id)
                show_admin(user_id)
                return

            create_date_step(
                user_id,
                text,
            )
            return

        # ----------------------------------------------------
        # CREATE TIME
        # ----------------------------------------------------

        if state_name == "create_time":
            if text == "⬅️ Отмена":
                clear_state(user_id)
                show_admin(user_id)
                return

            create_time_step(
                user_id,
                text,
            )
            return

        # ----------------------------------------------------
        # CREATE CATEGORY
        # ----------------------------------------------------

        if state_name == "create_category":
            if text == "⬅️ Отмена":
                clear_state(user_id)
                show_admin(user_id)
                return

            category = category_from_text(
                text
            )

            if category:
                create_category_step(
                    user_id,
                    category,
                )
            else:
                send_message(
                    user_id,
                    "Выберите категорию кнопкой.",
                    category_keyboard(
                        "⬅️ Отмена"
                    ),
                )

            return

        # ----------------------------------------------------
        # CREATE TITLE
        # ----------------------------------------------------

        if state_name == "create_title":
            if text == "⬅️ Отмена":
                clear_state(user_id)
                show_admin(user_id)
                return

            create_title_step(
                user_id,
                text,
            )
            return

        # ----------------------------------------------------
        # CREATE LEVEL
        # ----------------------------------------------------

        if state_name == "create_level":
            if text == "⬅️ Отмена":
                clear_state(user_id)
                show_admin(user_id)
                return

            create_level_step(
                user_id,
                text,
            )
            return

        # ----------------------------------------------------
        # CREATE FORMAT
        # ----------------------------------------------------

        if state_name == "create_format":
            if text == "⬅️ Отмена":
                clear_state(user_id)
                show_admin(user_id)
                return

            create_format_step(
                user_id,
                text,
            )
            return

        # ----------------------------------------------------
        # CREATE CAPACITY
        # ----------------------------------------------------

        if state_name == "create_capacity":
            if text == "⬅️ Отмена":
                clear_state(user_id)
                show_admin(user_id)
                return

            create_capacity_step(
                user_id,
                text,
            )
            return

        # ----------------------------------------------------
        # CREATE PRICE
        # ----------------------------------------------------

        if state_name == "create_price":
            if text == "⬅️ Отмена":
                clear_state(user_id)
                show_admin(user_id)
                return

            create_price_step(
                user_id,
                text,
            )
            return

        # ----------------------------------------------------
        # ADMIN PARTICIPANTS
        # ----------------------------------------------------

        if state_name == "admin_participants":

            if text == "⬅️ Админ-панель":
                show_admin(user_id)
                return

            if text == "◀️ Назад":
                current = int(
                    state.get("page", 0)
                )

                set_state(
                    user_id,
                    "admin_participants",
                    page=current - 1,
                    training_ids=state.get(
                        "training_ids",
                        [],
                    ),
                )

                show_admin_participants(
                    user_id
                )
                return

            if text == "Далее ▶️":
                current = int(
                    state.get("page", 0)
                )

                set_state(
                    user_id,
                    "admin_participants",
                    page=current + 1,
                    training_ids=state.get(
                        "training_ids",
                        [],
                    ),
                )

                show_admin_participants(
                    user_id
                )
                return

            if text.startswith("№"):
                try:
                    number = int(
                        text.split()[0]
                        .replace("№", "")
                    )
                except ValueError:
                    number = None

                if number is not None:
                    training = get_training_by_number(
                        number
                    )

                    if training:
                        show_admin_training(
                            user_id,
                            training["id"],
                        )
                        return

        # ----------------------------------------------------
        # ADMIN
        # ----------------------------------------------------

        if state_name == "admin":

            if text == "📅 Расписание":
                show_admin_schedule(
                    user_id
                )
                return

            if text == "👥 Участники":
                show_admin_participants(
                    user_id
                )
                return

            if text == "➕ Создать тренировку":
                start_create_training(
                    user_id
                )
                return

        # ----------------------------------------------------
        # ADMIN TRAINING
        # ----------------------------------------------------

        if state_name == "admin_training":
            if text == "⬅️ Админ-панель":
                show_admin(user_id)
                return

            if text == "⬅️ К тренировкам":
                show_admin_participants(
                    user_id
                )
                return

    # ========================================================
    # BOOKING STATES
    # ========================================================

    if state_name == "booking_category":

        if text == "⬅️ Назад":
            clear_state(user_id)
            send_message(
                user_id,
                "🏐 VOLLEY WAVE\n\n"
                "Выберите действие:",
                main_keyboard(user_id),
            )
            return

        category = category_from_text(
            text
        )

        if category:
            show_booking_dates(
                user_id,
                category,
            )
            return

    if state_name == "booking_date":

        category = state.get(
            "category"
        )

        if text == "⬅️ К категориям":
            start_booking(user_id)
            return

        dates = state.get(
            "dates",
            [],
        )

        for date_string in dates:
            if text == format_date_short(
                date_string
            ):
                show_booking_trainings(
                    user_id,
                    category,
                    date_string,
                )
                return

    if state_name == "booking_training":

        if text == "⬅️ К датам":
            show_booking_dates(
                user_id,
                state["category"],
            )
            return

        category = state[
            "category"
        ]

        date_string = state[
            "date"
        ]

        conn = get_db()

        rows = conn.execute(
            """
            SELECT *
            FROM trainings
            WHERE training_date=?
              AND category=?
              AND status='active'
            ORDER BY start_time
            """,
            (
                date_string,
                category,
            ),
        ).fetchall()

        conn.close()

        for training in rows:
            label = (
                f"{training['start_time']}–"
                f"{training['end_time']}"
            )

            if text.startswith(label):
                show_booking_details(
                    user_id,
                    training["id"],
                )
                return

    # ========================================================
    # TRAINING DETAILS
    # ========================================================

    if state_name == "training_details":

        training_id = state.get(
            "training_id"
        )

        training = get_training(
            training_id
        )

        if not training:
            send_message(
                user_id,
                "Тренировка не найдена.",
            )
            clear_state(user_id)
            return

        if text == "⬅️ Назад":
            show_booking_trainings(
                user_id,
                training["category"],
                training["training_date"],
            )
            return

        if text in {
            "✅ Записаться",
            "✅ Записаться снова",
        }:

            ok, result = register_user(
                training_id,
                user_id,
            )

            if result == "ok":
                send_message(
                    user_id,
                    "✅ Вы успешно записаны!\n\n"
                    + training_details_text(
                        training
                    ),
                    main_keyboard(user_id),
                )

            elif result == "already":
                send_message(
                    user_id,
                    "Вы уже записаны на эту тренировку.",
                )

            elif result == "full":
                send_message(
                    user_id,
                    "❌ Группа заполнена.",
                )

            else:
                send_message(
                    user_id,
                    "❌ Не удалось записаться.",
                )

            return

        if text == "❌ Отменить запись":

            ok, result = cancel_user_registration(
                training_id,
                user_id,
            )

            if result == "ok":
                send_message(
                    user_id,
                    "✅ Запись отменена.",
                    main_keyboard(user_id),
                )

            elif result == "too_late":
                send_message(
                    user_id,
                    "❌ Отменить запись можно "
                    "не позднее чем за 24 часа "
                    "до тренировки.",
                )

            else:
                send_message(
                    user_id,
                    "❌ Активная запись не найдена.",
                )

            return

    # ========================================================
    # MY TRAININGS
    # ========================================================

    if state_name == "my_trainings":

        if text == "⬅️ Главное меню":
            clear_state(user_id)
            send_message(
                user_id,
                "🏐 VOLLEY WAVE\n\n"
                "Выберите действие:",
                main_keyboard(user_id),
            )
            return

        if text.startswith("№"):
            try:
                number = int(
                    text.split()[0]
                    .replace("№", "")
                )
            except ValueError:
                number = None

            if number is not None:
                training = get_training_by_number(
                    number
                )

                if training:
                    show_booking_details(
                        user_id,
                        training["id"],
                    )
                    return

        # Ничего неизвестного здесь не отправляем.
        show_my_trainings(user_id)
        return

    # ========================================================
    # SCHEDULE
    # ========================================================

    if state_name == "schedule_category":

        if text == "⬅️ Назад":
            clear_state(user_id)
            send_message(
                user_id,
                "🏐 VOLLEY WAVE\n\n"
                "Выберите действие:",
                main_keyboard(user_id),
            )
            return

        category = category_from_text(
            text
        )

        if category:
            set_state(
                user_id,
                "schedule",
                category=category,
            )

            show_week_schedule(
                user_id,
                category,
            )
            return

    # ========================================================
    # INDIVIDUAL
    # ========================================================

    if state_name == "individual":

        if text == "✉️ Написать администратору":
            start_question(
                user_id,
                "individual",
            )
            return

        if text == "⬅️ Назад":
            clear_state(user_id)
            send_message(
                user_id,
                "🏐 VOLLEY WAVE\n\n"
                "Выберите действие:",
                main_keyboard(user_id),
            )
            return

    # ========================================================
    # QUESTION
    # ========================================================

    if state_name == "question":

        if text == "⬅️ Назад":
            clear_state(user_id)
            send_message(
                user_id,
                "🏐 VOLLEY WAVE\n\n"
                "Выберите действие:",
                main_keyboard(user_id),
            )
            return

        # Сообщение пользователя здесь можно
        # в дальнейшем автоматически отправлять
        # администраторам через VK.
        logger.info(
            "USER MESSAGE TO ADMIN user=%s text=%r",
            user_id,
            text,
        )

        for admin_id in ADMINS:
            send_message(
                admin_id,
                "✉️ НОВОЕ СООБЩЕНИЕ\n\n"
                f"От пользователя VK ID: {user_id}\n\n"
                f"{text}",
            )

        clear_state(user_id)

        send_message(
            user_id,
            "✅ Сообщение отправлено администратору.\n\n"
            "Мы свяжемся с вами.",
            main_keyboard(user_id),
        )

        return

    # ========================================================
    # GLOBAL MENU
    # ========================================================

    if text == "🏐 Записаться":
        start_booking(user_id)
        return

    if text == "📅 Расписание":
        show_schedule_categories(
            user_id
        )
        return

    if text == "👤 Мои тренировки":
        clear_state(user_id)
        show_my_trainings(
            user_id
        )
        return

    if text == "💰 Цены":
        clear_state(user_id)
        show_prices(user_id)
        return

    if text == "📍 Где тренируемся":
        clear_state(user_id)
        show_locations(user_id)
        return

    if text == "🎯 Индивидуальная":
        show_individual(user_id)
        return

    if text == "❓ Задать вопрос":
        start_question(
            user_id,
            "question",
        )
        return

    if text == "⚙️ Админ-панель":
        if user_id in ADMINS:
            show_admin(user_id)
        else:
            send_message(
                user_id,
                "🏐 VOLLEY WAVE\n\n"
                "Выберите действие:",
                main_keyboard(user_id),
            )
        return

    # ========================================================
    # FALLBACK
    # ========================================================

    send_message(
        user_id,
        "Не совсем понял команду.\n\n"
        "Выберите действие:",
        main_keyboard(user_id),
    )


# ============================================================
# CALLBACK
# ============================================================

@app.route(
    "/callback",
    methods=["POST"],
)
def callback():
    try:
        data = request.get_json(
            force=True,
            silent=True,
        ) or {}

        logger.info(
            "VK EVENT: %s",
            data,
        )

        event_type = data.get(
            "type"
        )

        # VK confirmation
        if event_type == "confirmation":
            return (
                VK_CONFIRMATION_TOKEN or "",
                200,
                {
                    "Content-Type":
                    "text/plain"
                },
            )

        # Secret
        if VK_SECRET_KEY:
            if data.get("secret") != VK_SECRET_KEY:
                logger.warning(
                    "Invalid secret"
                )
                return (
                    "invalid secret",
                    403,
                )

        # Message
        if event_type == "message_new":

            obj = data.get(
                "object",
                {},
            )

            message = obj.get(
                "message",
                {},
            )

            user_id = (
                message.get("from_id")
                or obj.get("from_id")
            )

            text = (
                message.get("text")
                or obj.get("text")
                or ""
            )

            if user_id:
                logger.info(
                    "MESSAGE_NEW user=%s text=%r",
                    user_id,
                    text,
                )

                handle_message(
                    user_id,
                    text,
                )

            return "ok", 200

        return "ok", 200

    except Exception as e:
        logger.exception(
            "Callback error: %s",
            e,
        )

        return "ok", 200


# ============================================================
# STARTUP
# ============================================================

def startup():
    logger.info(
        "Starting VOLLEY WAVE VK BOT..."
    )

    logger.info(
        "Group ID: %s",
        GROUP_ID,
    )

    logger.info(
        "Admins: %s",
        list(ADMINS),
    )

    init_database()

    logger.info(
        "Database ready"
    )

    conn = get_db()

    count = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM trainings
        WHERE training_date >= ?
          AND status='active'
        """,
        (
            date.today().strftime(
                "%Y-%m-%d"
            ),
        ),
    ).fetchone()["count"]

    conn.close()

    logger.info(
        "Upcoming trainings in DB: %s",
        count,
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    startup()

    port = int(
        os.environ.get(
            "PORT",
            "10000",
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
    )
