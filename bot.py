import os
import sqlite3
import logging
from datetime import datetime, date, timedelta
import json

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

WINTER_LOCATION = "СК «Арена», ул. Молодогвардейцев, 7"
SUMMER_LOCATION = "Парк Гагарина"

USER_STATE = {}


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

logger = logging.getLogger(__name__)


# ============================================================
# FLASK
# ============================================================

app = Flask(__name__)


# ============================================================
# DATABASE
# ============================================================

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def table_exists(conn, table_name):
    row = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type='table'
          AND name=?
        """,
        (table_name,),
    ).fetchone()

    return row is not None


def ensure_column(
    conn,
    table_name,
    column_name,
    column_type,
):
    if not table_exists(conn, table_name):
        return

    columns = conn.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    names = {
        column["name"]
        for column in columns
    }

    if column_name not in names:
        conn.execute(
            f"""
            ALTER TABLE {table_name}
            ADD COLUMN {column_name} {column_type}
            """
        )


def init_database():
    conn = get_db()

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vk_id INTEGER UNIQUE,
            first_name TEXT,
            last_name TEXT,
            created_at TEXT
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS trainings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            training_number INTEGER,
            training_date TEXT,
            weekday TEXT,
            start_time TEXT,
            end_time TEXT,
            title TEXT,
            category TEXT,
            age_group TEXT,
            level TEXT,
            format TEXT,
            coach TEXT,
            capacity INTEGER,
            price INTEGER,
            location TEXT,
            status TEXT DEFAULT 'active',
            template_id INTEGER,
            created_at TEXT,
            updated_at TEXT
        )
        """
    )

    conn.execute(
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

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS admin_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_vk_id INTEGER,
            action TEXT,
            created_at TEXT
        )
        """
    )

    ensure_column(
        conn,
        "trainings",
        "category",
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
        "coach",
        "TEXT",
    )

    ensure_column(
        conn,
        "trainings",
        "capacity",
        "INTEGER",
    )

    ensure_column(
        conn,
        "trainings",
        "price",
        "INTEGER",
    )

    ensure_column(
        conn,
        "trainings",
        "location",
        "TEXT",
    )

    ensure_column(
        conn,
        "trainings",
        "status",
        "TEXT",
    )

    ensure_column(
        conn,
        "trainings",
        "template_id",
        "INTEGER",
    )

    conn.commit()
    conn.close()


# ============================================================
# USERS
# ============================================================

def ensure_user(user_id):
    conn = get_db()

    row = conn.execute(
        """
        SELECT *
        FROM users
        WHERE vk_id=?
        """,
        (user_id,),
    ).fetchone()

    if row is None:
        conn.execute(
            """
            INSERT INTO users (
                vk_id,
                created_at
            )
            VALUES (?, ?)
            """,
            (
                user_id,
                datetime.now().isoformat(),
            ),
        )

        conn.commit()

    conn.close()


def get_internal_user_id(user_id):
    conn = get_db()

    row = conn.execute(
        """
        SELECT id
        FROM users
        WHERE vk_id=?
        """,
        (user_id,),
    ).fetchone()

    conn.close()

    if row:
        return row["id"]

    return None


# ============================================================
# CATEGORY
# ============================================================

def normalize_category(value):
    if value is None:
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
# DATES
# ============================================================

def parse_date(value):
    if not value:
        return None

    try:
        return datetime.strptime(
            value,
            "%Y-%m-%d",
        ).date()

    except ValueError:
        pass

    try:
        return datetime.strptime(
            value,
            "%d.%m.%Y",
        ).date()

    except ValueError:
        return None


def format_date_long(value):
    if isinstance(value, str):
        value = parse_date(value)

    if not value:
        return ""

    return (
        f"{WEEKDAYS[value.weekday()]}, "
        f"{value.day} {MONTHS[value.month]}"
    )


def format_date_short(value):
    if isinstance(value, str):
        value = parse_date(value)

    if not value:
        return ""

    return (
        f"{value.day:02d}."
        f"{value.month:02d}"
    )


# ============================================================
# VK API
# ============================================================

def vk_api(method, **params):
    params["access_token"] = VK_TOKEN
    params["v"] = VK_API_VERSION

    logger.info(
        "VK API REQUEST: method=%s params=%s",
        method,
        {
            key: value
            for key, value in params.items()
            if key != "access_token"
        },
    )

    try:
        response = requests.post(
            f"https://api.vk.com/method/{method}",
            data=params,
            timeout=15,
        )

        logger.info(
            "VK API HTTP STATUS: %s",
            response.status_code,
        )

        response.raise_for_status()

        data = response.json()

        logger.info(
            "VK API RESPONSE: method=%s response=%s",
            method,
            data,
        )

        if "error" in data:
            logger.error(
                "VK API ERROR: method=%s error=%s",
                method,
                data["error"],
            )

        return data

    except requests.RequestException:
        logger.exception(
            "VK API REQUEST ERROR: method=%s",
            method,
        )

        return {
            "error": {
                "error_code": -1,
                "error_msg": "Ошибка HTTP-запроса к VK API",
            }
        }

    except ValueError:
        logger.exception(
            "VK API INVALID JSON: method=%s response=%s",
            method,
            response.text,
        )

        return {
            "error": {
                "error_code": -2,
                "error_msg": "VK API вернул некорректный JSON",
            }
        }


def send_message(
    user_id,
    message,
    keyboard=None,
):
    params = {
        "user_id": user_id,
        "random_id": 0,
        "message": message,
    }

    if keyboard:
        params["keyboard"] = json.dumps(
            keyboard,
            ensure_ascii=False,
        )

    return vk_api(
        "messages.send",
        **params,
    )


# ============================================================
# BUTTON
# ============================================================

def button(
    label,
    color="secondary",
):
    return {
        "action": {
            "type": "text",
            "label": label,
        },
        "color": color,
    }


# ============================================================
# KEYBOARDS
# ============================================================

def main_keyboard(user_id=None):
    buttons = [
        [
            button(
                "🏐 Записаться",
                "primary",
            ),
            button(
                "📅 Расписание",
                "primary",
            ),
        ],
        [
            button(
                "👤 Мои тренировки",
                "primary",
            ),
            button(
                "💰 Цены",
                "secondary",
            ),
        ],
        [
            button(
                "📍 Где тренируемся",
                "secondary",
            ),
            button(
                "🎯 Индивидуальная",
                "secondary",
            ),
        ],
        [
            button(
                "❓ Задать вопрос",
                "secondary",
            ),
        ],
    ]

    if user_id in ADMINS:
        buttons.append(
            [
                button(
                    "⚙️ Админ-панель",
                    "secondary",
                )
            ]
        )

    return {
        "one_time": False,
        "buttons": buttons,
    }


def back_keyboard(
    label="⬅️ Назад",
):
    return {
        "one_time": False,
        "buttons": [
            [
                button(
                    label,
                    "secondary",
                )
            ]
        ],
    }


def category_keyboard(
    back_label="⬅️ Назад",
):
    return {
        "one_time": False,
        "buttons": [
            [
                button(
                    "👧 Дети",
                    "primary",
                ),
                button(
                    "🧑 Взрослые",
                    "primary",
                ),
            ],
            [
                button(
                    back_label,
                    "secondary",
                )
            ],
        ],
    }


def level_keyboard():
    return {
        "one_time": False,
        "buttons": [
            [
                button(
                    "Начальный",
                    "primary",
                ),
                button(
                    "Средний",
                    "primary",
                ),
            ],
            [
                button(
                    "Продвинутый",
                    "primary",
                )
            ],
            [
                button(
                    "⬅️ Отмена",
                    "secondary",
                )
            ],
        ],
    }


def format_keyboard():
    return {
        "one_time": False,
        "buttons": [
            [
                button(
                    "Техничка",
                    "primary",
                ),
                button(
                    "MIXED",
                    "primary",
                ),
            ],
            [
                button(
                    "Женская",
                    "primary",
                ),
                button(
                    "Мужская",
                    "primary",
                ),
            ],
            [
                button(
                    "Общая",
                    "primary",
                )
            ],
            [
                button(
                    "⬅️ Отмена",
                    "secondary",
                )
            ],
        ],
    }


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
                )
            ],
            [
                button(
                    "🏠 Главное меню",
                    "secondary",
                )
            ],
        ],
    }


# ============================================================
# STATE
# ============================================================

def set_state(
    user_id,
    state,
    **data,
):
    USER_STATE[user_id] = {
        "state": state,
        **data,
    }


def get_state(user_id):
    return USER_STATE.get(
        user_id,
        {
            "state": "main",
        },
    )


def clear_state(user_id):
    USER_STATE.pop(
        user_id,
        None,
    )


# ============================================================
# TRAININGS
# ============================================================

def get_next_training_number():
    conn = get_db()

    row = conn.execute(
        """
        SELECT MAX(training_number)
        AS max_number
        FROM trainings
        """
    ).fetchone()

    conn.close()

    if row and row["max_number"]:
        return row["max_number"] + 1

    return 1


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
          AND status='active'
        ORDER BY training_date
        LIMIT 1
        """,
        (number,),
    ).fetchone()

    conn.close()

    return row


def create_training(data):
    conn = get_db()

    now = datetime.now().isoformat()

    training_number = get_next_training_number()

    training_date = data["training_date"]

    parsed = parse_date(training_date)

    weekday = ""

    if parsed:
        weekday = WEEKDAYS[parsed.weekday()]

    conn.execute(
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
            status,
            template_id,
            created_at,
            updated_at
        )
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        (
            training_number,
            training_date,
            weekday,
            data.get("start_time"),
            data.get("end_time"),
            data.get("title"),
            normalize_category(
                data.get("category")
            ),
            data.get("age_group"),
            data.get("level"),
            data.get("format"),
            data.get("coach"),
            data.get("capacity", 8),
            data.get("price", 0),
            data.get(
                "location",
                WINTER_LOCATION,
            ),
            "active",
            data.get("template_id"),
            now,
            now,
        ),
    )

    training_id = conn.execute(
        "SELECT last_insert_rowid()"
    ).fetchone()[0]

    conn.commit()
    conn.close()

    return training_id


# ============================================================
# SCHEDULE
# ============================================================

def get_week_start():
    return date.today()


def get_week_trainings(category=None):
    start_date = date.today()

    end_date = start_date + timedelta(
        days=6
    )

    conn = get_db()

    sql = """
        SELECT *
        FROM trainings
        WHERE training_date >= ?
          AND training_date <= ?
          AND status='active'
    """

    params = [
        start_date.strftime(
            "%Y-%m-%d"
        ),
        end_date.strftime(
            "%Y-%m-%d"
        ),
    ]

    category = normalize_category(
        category
    )

    if category in (
        "children",
        "adults",
    ):
        sql += """
            AND category=?
        """

        params.append(category)

    sql += """
        ORDER BY training_date,
                 start_time,
                 id
    """

    rows = conn.execute(
        sql,
        params,
    ).fetchall()

    conn.close()

    return rows


def get_future_trainings(
    category=None,
):
    conn = get_db()

    sql = """
        SELECT *
        FROM trainings
        WHERE training_date >= ?
          AND status='active'
    """

    params = [
        date.today().strftime(
            "%Y-%m-%d"
        )
    ]

    category = normalize_category(
        category
    )

    if category in (
        "children",
        "adults",
    ):
        sql += """
            AND category=?
        """

        params.append(category)

    sql += """
        ORDER BY training_date,
                 start_time,
                 id
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

def registration_count(
    training_id,
):
    conn = get_db()

    row = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM registrations
        WHERE training_id=?
        """,
        (training_id,),
    ).fetchone()

    conn.close()

    return row["count"]


def get_registration(
    training_id,
    user_id,
):
    internal_id = get_internal_user_id(
        user_id
    )

    if internal_id is None:
        return None

    conn = get_db()

    row = conn.execute(
        """
        SELECT *
        FROM registrations
        WHERE training_id=?
          AND user_id=?
        """,
        (
            training_id,
            internal_id,
        ),
    ).fetchone()

    conn.close()

    return row


def register_user(
    training_id,
    user_id,
):
    ensure_user(user_id)

    internal_id = get_internal_user_id(
        user_id
    )

    training = get_training(
        training_id
    )

    if not training:
        return "not_found"

    existing = get_registration(
        training_id,
        user_id,
    )

    if existing:
        return "already"

    count = registration_count(
        training_id
    )

    if count >= training["capacity"]:
        return "full"

    conn = get_db()

    try:
        conn.execute(
            """
            INSERT INTO registrations (
                training_id,
                user_id,
                created_at
            )
            VALUES (?, ?, ?)
            """,
            (
                training_id,
                internal_id,
                datetime.now().isoformat(),
            ),
        )

        conn.commit()

    except sqlite3.IntegrityError:
        conn.close()
        return "already"

    conn.close()

    return "ok"


def cancel_user_registration(
    training_id,
    user_id,
):
    registration = get_registration(
        training_id,
        user_id,
    )

    if not registration:
        return False, "not_found"

    training = get_training(
        training_id
    )

    if not training:
        return False, "not_found"

    try:
        training_dt = datetime.strptime(
            f"{training['training_date']} "
            f"{training['start_time']}",
            "%Y-%m-%d %H:%M",
        )

    except Exception:
        training_dt = None

    if training_dt:
        hours = (
            training_dt - datetime.now()
        ).total_seconds() / 3600

        if hours < 24:
            return False, "too_late"

    conn = get_db()

    conn.execute(
        """
        DELETE FROM registrations
        WHERE training_id=?
          AND user_id=?
        """,
        (
            training_id,
            get_internal_user_id(
                user_id
            ),
        ),
    )

    conn.commit()
    conn.close()

    return True, "ok"


def get_user_trainings(
    user_id,
):
    internal_id = get_internal_user_id(
        user_id
    )

    if internal_id is None:
        return []

    conn = get_db()

    rows = conn.execute(
        """
        SELECT t.*
        FROM trainings t
        JOIN registrations r
          ON r.training_id=t.id
        WHERE r.user_id=?
          AND t.status='active'
        ORDER BY t.training_date,
                 t.start_time
        """,
        (internal_id,),
    ).fetchall()

    conn.close()

    return rows


def get_participants(
    training_id,
):
    conn = get_db()

    rows = conn.execute(
        """
        SELECT
            u.vk_id,
            u.first_name,
            u.last_name
        FROM registrations r
        JOIN users u
          ON u.id=r.user_id
        WHERE r.training_id=?
        ORDER BY r.created_at
        """,
        (training_id,),
    ).fetchall()

    conn.close()

    return rows


# ============================================================
# TRAINING TEXT
# ============================================================

def training_details_text(
    training,
):
    count = registration_count(
        training["id"]
    )

    category = category_label(
        training["category"]
    )

    return (
        f"🏐 ТРЕНИРОВКА №"
        f"{training['training_number']}\n\n"
        f"📆 "
        f"{format_date_long(training['training_date'])}\n"
        f"⏰ "
        f"{training['start_time']}–"
        f"{training['end_time']}\n\n"
        f"{category}\n"
        f"🎯 "
        f"{training['title']}\n"
        f"📊 Уровень: "
        f"{training['level'] or '—'}\n"
        f"🏐 Формат: "
        f"{training['format'] or '—'}\n"
        f"👨‍🏫 Тренер: "
        f"{training['coach'] or '—'}\n"
        f"📍 "
        f"{training['location'] or '—'}\n\n"
        f"💰 "
        f"{training['price']} ₽\n"
        f"👥 Места: "
        f"{count}/"
        f"{training['capacity']}\n"
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


def show_booking_dates(
    user_id,
    category,
):
    rows = get_future_trainings(
        category
    )

    if not rows:
        send_message(
            user_id,
            "Свободных тренировок "
            "пока нет.",
            back_keyboard(),
        )
        return

    dates = []

    for value in rows:
        training_date = value["training_date"]

        if training_date not in dates:
            dates.append(
                training_date
            )

    dates = dates[:10]

    buttons = []

    for value in dates:
        parsed = parse_date(value)

        label = format_date_long(
            parsed
        )

        buttons.append(
            [
                button(
                    label,
                    "primary",
                )
            ]
        )

    buttons.append(
        [
            button(
                "⬅️ Назад",
                "secondary",
            )
        ]
    )

    set_state(
        user_id,
        "booking_date",
        category=category,
    )

    send_message(
        user_id,
        "📆 Выберите дату:",
        {
            "one_time": False,
            "buttons": buttons,
        },
    )


def show_booking_trainings(
    user_id,
    category,
    training_date,
):
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
            training_date,
            category,
        ),
    ).fetchall()

    conn.close()

    if not rows:
        send_message(
            user_id,
            "На эту дату тренировок нет.",
            back_keyboard(),
        )
        return

    buttons = []

    for row in rows:
        count = registration_count(
            row["id"]
        )

        label = (
            f"№{row['training_number']} "
            f"{row['start_time']} "
            f"({count}/{row['capacity']})"
        )

        buttons.append(
            [
                button(
                    label,
                    "primary",
                )
            ]
        )

    buttons.append(
        [
            button(
                "⬅️ Назад",
                "secondary",
            )
        ]
    )

    set_state(
        user_id,
        "booking_training",
        category=category,
        training_date=training_date,
    )

    send_message(
        user_id,
        "🏐 Выберите тренировку:",
        {
            "one_time": False,
            "buttons": buttons,
        },
    )


def show_booking_details(
    user_id,
    training,
):
    set_state(
        user_id,
        "booking_confirm",
        training_id=training["id"],
    )

    count = registration_count(
        training["id"]
    )

    buttons = [
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
    ]

    send_message(
        user_id,
        training_details_text(
            training
        )
        + "\n"
        + (
            "❗ Мест больше нет."
            if count >= training["capacity"]
            else "Записаться можно ниже."
        ),
        {
            "one_time": False,
            "buttons": buttons,
        },
    )


# ============================================================
# SCHEDULE
# ============================================================

def show_schedule_categories(
    user_id,
):
    set_state(
        user_id,
        "schedule_category",
    )

    send_message(
        user_id,
        "📅 РАСПИСАНИЕ\n\n"
        "Покажу тренировки "
        "на ближайшие 7 дней.\n\n"
        "Выберите категорию:",
        category_keyboard(),
    )


def show_week_schedule(
    user_id,
    category,
):
    category = normalize_category(
        category
    )

    rows = get_week_trainings(
        category
    )

    if not rows:
        set_state(
            user_id,
            "schedule_category",
        )

        send_message(
            user_id,
            "На ближайшие 7 дней "
            "тренировок этой категории нет.",
            category_keyboard(),
        )

        return

    start_date = date.today()

    end_date = (
        start_date
        + timedelta(days=6)
    )

    text = (
        f"📅 РАСПИСАНИЕ — "
        f"{category_label(category)}\n"
        f"Ближайшие 7 дней: "
        f"{format_date_short(start_date)}"
        f" — "
        f"{format_date_short(end_date)}\n\n"
    )

    current_date = None

    for row in rows:
        if row["training_date"] != current_date:
            current_date = row[
                "training_date"
            ]

            text += (
                f"📆 "
                f"{format_date_long(current_date)}\n"
            )

        count = registration_count(
            row["id"]
        )

        text += (
            f"🏐 №"
            f"{row['training_number']} "
            f"{row['start_time']}–"
            f"{row['end_time']}\n"
            f"{row['title'] or 'Тренировка'}\n"
            f"Уровень: "
            f"{row['level'] or '—'}\n"
            f"Формат: "
            f"{row['format'] or '—'}\n"
            f"Мест: "
            f"{count}/"
            f"{row['capacity']}\n"
            f"💰 "
            f"{row['price']} ₽\n\n"
        )

    set_state(
        user_id,
        "schedule",
        category=category,
    )

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
# MY TRAININGS
# ============================================================

def show_my_trainings(
    user_id,
):
    rows = get_user_trainings(
        user_id
    )

    if not rows:
        send_message(
            user_id,
            "👤 У вас пока нет активных записей.",
            main_keyboard(user_id),
        )
        return

    text = "👤 МОИ ТРЕНИРОВКИ\n\n"

    for row in rows:
        text += (
            f"🏐 №{row['training_number']}\n"
            f"📆 "
            f"{format_date_long(row['training_date'])}\n"
            f"⏰ "
            f"{row['start_time']}–"
            f"{row['end_time']}\n"
            f"{row['title'] or 'Тренировка'}\n"
            f"📍 "
            f"{row['location'] or '—'}\n\n"
        )

    send_message(
        user_id,
        text,
        main_keyboard(user_id),
    )


# ============================================================
# PRICES
# ============================================================

def show_prices(
    user_id,
):
    send_message(
        user_id,
        "💰 ЦЕНЫ\n\n"
        "👧 Детские тренировки — "
        f"{CHILDREN_PRICE} ₽\n"
        "🧑 Взрослые тренировки — "
        f"{ADULT_PRICE} ₽\n\n"
        "Стоимость конкретной тренировки "
        "всегда указана в расписании.",
        main_keyboard(user_id),
    )


# ============================================================
# LOCATION
# ============================================================

def show_location(
    user_id,
):
    send_message(
        user_id,
        "📍 ГДЕ ТРЕНИРУЕМСЯ\n\n"
        f"Зимой:\n{WINTER_LOCATION}\n\n"
        f"Летом:\n{SUMMER_LOCATION}",
        main_keyboard(user_id),
    )


# ============================================================
# INDIVIDUAL
# ============================================================

def show_individual(
    user_id,
):
    send_message(
        user_id,
        "🎯 ИНДИВИДУАЛЬНАЯ ТРЕНИРОВКА\n\n"
        "Для записи на индивидуальную "
        "тренировку напишите администратору.",
        main_keyboard(user_id),
    )


# ============================================================
# QUESTION
# ============================================================

def start_question(
    user_id,
):
    set_state(
        user_id,
        "question",
    )

    send_message(
        user_id,
        "❓ Напишите ваш вопрос одним сообщением.\n\n"
        "После этого тренер или администратор "
        "сможет вам ответить.",
        back_keyboard("⬅️ Отмена"),
    )


# ============================================================
# ADMIN
# ============================================================

def show_admin(
    user_id,
):
    if user_id not in ADMINS:
        send_message(
            user_id,
            "Нет доступа.",
            main_keyboard(user_id),
        )
        return

    set_state(
        user_id,
        "admin",
    )

    send_message(
        user_id,
        "⚙️ АДМИН-ПАНЕЛЬ",
        admin_keyboard(),
    )


def show_admin_schedule(
    user_id,
):
    if user_id not in ADMINS:
        return

    rows = get_future_trainings()

    if not rows:
        send_message(
            user_id,
            "Тренировок нет.",
            admin_keyboard(),
        )
        return

    text = "📅 БЛИЖАЙШИЕ ТРЕНИРОВКИ\n\n"

    for row in rows[:30]:
        count = registration_count(
            row["id"]
        )

        text += (
            f"№{row['training_number']} "
            f"{format_date_short(row['training_date'])} "
            f"{row['start_time']}–"
            f"{row['end_time']}\n"
            f"{row['title'] or 'Тренировка'}\n"
            f"{category_label(row['category'])}\n"
            f"Мест: {count}/{row['capacity']}\n\n"
        )

    send_message(
        user_id,
        text,
        admin_keyboard(),
    )


def show_admin_participants(
    user_id,
):
    if user_id not in ADMINS:
        return

    rows = get_future_trainings()

    if not rows:
        send_message(
            user_id,
            "Тренировок нет.",
            admin_keyboard(),
        )
        return

    buttons = []

    for row in rows[:20]:
        buttons.append(
            [
                button(
                    f"№{row['training_number']} "
                    f"{format_date_short(row['training_date'])} "
                    f"{row['start_time']}",
                    "primary",
                )
            ]
        )

    buttons.append(
        [
            button(
                "🏠 Главное меню",
                "secondary",
            )
        ]
    )

    set_state(
        user_id,
        "admin_participants",
    )

    send_message(
        user_id,
        "👥 Выберите тренировку:",
        {
            "one_time": False,
            "buttons": buttons,
        },
    )


def show_participants(
    user_id,
    training,
):
    if user_id not in ADMINS:
        return

    rows = get_participants(
        training["id"]
    )

    text = (
        f"👥 УЧАСТНИКИ\n\n"
        f"№{training['training_number']}\n"
        f"{format_date_long(training['training_date'])}\n"
        f"{training['start_time']}–"
        f"{training['end_time']}\n\n"
    )

    if not rows:
        text += "Пока никто не записан."

    else:
        for index, row in enumerate(
            rows,
            start=1,
        ):
            first_name = (
                row["first_name"]
                or ""
            )

            last_name = (
                row["last_name"]
                or ""
            )

            name = (
                f"{first_name} "
                f"{last_name}"
            ).strip()

            if not name:
                name = (
                    f"VK ID "
                    f"{row['vk_id']}"
                )

            text += (
                f"{index}. {name}\n"
            )

    send_message(
        user_id,
        text,
        admin_keyboard(),
    )


# ============================================================
# CREATE TRAINING
# ============================================================

def start_create_training(
    user_id,
):
    if user_id not in ADMINS:
        return

    set_state(
        user_id,
        "create_date",
        data={},
    )

    send_message(
        user_id,
        "➕ СОЗДАНИЕ ТРЕНИРОВКИ\n\n"
        "Введите дату в формате:\n"
        "ДД.ММ.ГГГГ",
        back_keyboard("⬅️ Отмена"),
    )


def create_training_finish(
    user_id,
):
    state = get_state(
        user_id
    )

    data = state.get(
        "data",
        {},
    )

    training_id = create_training(
        data
    )

    training = get_training(
        training_id
    )

    clear_state(user_id)

    send_message(
        user_id,
        "✅ Тренировка создана!\n\n"
        + training_details_text(
            training
        ),
        admin_keyboard(),
    )


# ============================================================
# MESSAGE HANDLER
# ============================================================

def handle_message(
    user_id,
    text,
):
    ensure_user(user_id)

    state_data = get_state(
        user_id
    )

    state = state_data.get(
        "state",
        "main",
    )

    logger.info(
        "VK %s | state=%s | text=%s",
        user_id,
        state,
        text,
    )

    # --------------------------------------------------------
    # MAIN MENU
    # --------------------------------------------------------

    if text == "🏠 Главное меню":
        clear_state(user_id)

        send_message(
            user_id,
            "🏐 VOLLEY WAVE\n\n"
            "Выберите действие:",
            main_keyboard(user_id),
        )

        return

    if text in {
        "⬅️ Назад",
        "⬅️ Отмена",
    } and state == "main":
        send_message(
            user_id,
            "🏐 Главное меню:",
            main_keyboard(user_id),
        )
        return

    # --------------------------------------------------------
    # QUESTION
    # --------------------------------------------------------

    if state == "question":
        if text in {
            "⬅️ Назад",
            "⬅️ Отмена",
        }:
            clear_state(user_id)

            send_message(
                user_id,
                "🏐 Главное меню:",
                main_keyboard(user_id),
            )

            return

        for admin_id in ADMINS:
            send_message(
                admin_id,
                f"❓ ВОПРОС ОТ VK ID {user_id}\n\n"
                f"{text}",
            )

        clear_state(user_id)

        send_message(
            user_id,
            "✅ Вопрос отправлен.\n"
            "Мы ответим вам в ближайшее время.",
            main_keyboard(user_id),
        )

        return

    # --------------------------------------------------------
    # MAIN BUTTONS
    # --------------------------------------------------------

    if text == "🏐 Записаться":
        start_booking(user_id)
        return

    if text == "📅 Расписание":
        show_schedule_categories(
            user_id
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

    if text == "🎯 Индивидуальная":
        show_individual(user_id)
        return

    if text == "❓ Задать вопрос":
        start_question(user_id)
        return

    if (
        text == "⚙️ Админ-панель"
        and user_id in ADMINS
    ):
        show_admin(user_id)
        return

    # --------------------------------------------------------
    # BOOKING CATEGORY
    # --------------------------------------------------------

    if state == "booking_category":
        if text == "⬅️ Назад":
            clear_state(user_id)

            send_message(
                user_id,
                "🏐 Главное меню:",
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

    # --------------------------------------------------------
    # BOOKING DATE
    # --------------------------------------------------------

    if state == "booking_date":
        if text == "⬅️ Назад":
            start_booking(user_id)
            return

        category = state_data.get(
            "category"
        )

        rows = get_future_trainings(
            category
        )

        selected_date = None

        for row in rows:
            if (
                format_date_long(
                    row["training_date"]
                )
                == text
            ):
                selected_date = (
                    row["training_date"]
                )
                break

        if selected_date:
            show_booking_trainings(
                user_id,
                category,
                selected_date,
            )
            return

    # --------------------------------------------------------
    # BOOKING TRAINING
    # --------------------------------------------------------

    if state == "booking_training":
        if text == "⬅️ Назад":
            show_booking_dates(
                user_id,
                state_data.get(
                    "category"
                ),
            )
            return

        category = state_data.get(
            "category"
        )

        training_date = state_data.get(
            "training_date"
        )

        rows = []

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
                training_date,
                category,
            ),
        ).fetchall()

        conn.close()

        selected_training = None

        for row in rows:
            label = (
                f"№{row['training_number']} "
                f"{row['start_time']} "
                f"({registration_count(row['id'])}/"
                f"{row['capacity']})"
            )

            if label == text:
                selected_training = row
                break

        if selected_training:
            show_booking_details(
                user_id,
                selected_training,
            )
            return

    # --------------------------------------------------------
    # BOOKING CONFIRM
    # --------------------------------------------------------

    if state == "booking_confirm":
        if text == "⬅️ Назад":
            category = state_data.get(
                "category"
            )

            training_id = state_data.get(
                "training_id"
            )

            training = get_training(
                training_id
            )

            if training:
                show_booking_trainings(
                    user_id,
                    training["category"],
                    training["training_date"],
                )
            else:
                start_booking(user_id)

            return

        if text == "✅ Записаться":
            training_id = state_data.get(
                "training_id"
            )

            result = register_user(
                training_id,
                user_id,
            )

            training = get_training(
                training_id
            )

            if result == "ok":
                clear_state(user_id)

                send_message(
                    user_id,
                    "✅ Вы записаны на тренировку!\n\n"
                    + training_details_text(
                        training
                    ),
                    main_keyboard(user_id),
                )

                return

            if result == "already":
                send_message(
                    user_id,
                    "Вы уже записаны на эту тренировку.",
                    main_keyboard(user_id),
                )
                return

            if result == "full":
                send_message(
                    user_id,
                    "❗ На тренировке больше нет свободных мест.",
                    main_keyboard(user_id),
                )
                return

            send_message(
                user_id,
                "Не удалось записать вас на тренировку.",
                main_keyboard(user_id),
            )

            return

    # --------------------------------------------------------
    # SCHEDULE CATEGORY
    # --------------------------------------------------------

    if state == "schedule_category":
        if text == "⬅️ Назад":
            clear_state(user_id)

            send_message(
                user_id,
                "🏐 Главное меню:",
                main_keyboard(user_id),
            )

            return

        category = category_from_text(
            text
        )

        if category:
            show_week_schedule(
                user_id,
                category,
            )
            return

    # --------------------------------------------------------
    # SCHEDULE
    # --------------------------------------------------------

    if state == "schedule":
        if text == "⬅️ Назад":
            show_schedule_categories(
                user_id
            )
            return

    # --------------------------------------------------------
    # ADMIN
    # --------------------------------------------------------

    if state == "admin":
        if user_id not in ADMINS:
            return

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

        if text == "🏠 Главное меню":
            clear_state(user_id)

            send_message(
                user_id,
                "🏐 Главное меню:",
                main_keyboard(user_id),
            )

            return

    # --------------------------------------------------------
    # ADMIN PARTICIPANTS
    # --------------------------------------------------------

    if state == "admin_participants":
        if user_id not in ADMINS:
            return

        if text == "🏠 Главное меню":
            show_admin(user_id)
            return

        rows = get_future_trainings()

        for row in rows[:20]:
            label = (
                f"№{row['training_number']} "
                f"{format_date_short(row['training_date'])} "
                f"{row['start_time']}"
            )

            if label == text:
                show_participants(
                    user_id,
                    row,
                )
                return

    # --------------------------------------------------------
    # CREATE TRAINING — DATE
    # --------------------------------------------------------

    if state == "create_date":
        if text in {
            "⬅️ Отмена",
            "⬅️ Назад",
        }:
            show_admin(user_id)
            return

        parsed = parse_date(text)

        if not parsed:
            send_message(
                user_id,
                "❗ Неверный формат даты.\n\n"
                "Введите дату так:\n"
                "ДД.ММ.ГГГГ",
                back_keyboard("⬅️ Отмена"),
            )
            return

        state_data["data"][
            "training_date"
        ] = parsed.strftime(
            "%Y-%m-%d"
        )

        set_state(
            user_id,
            "create_start_time",
            data=state_data["data"],
        )

        send_message(
            user_id,
            "Введите время начала.\n"
            "Например: 19:00",
            back_keyboard("⬅️ Отмена"),
        )

        return

    # --------------------------------------------------------
    # CREATE TRAINING — START
    # --------------------------------------------------------

    if state == "create_start_time":
        if text in {
            "⬅️ Отмена",
            "⬅️ Назад",
        }:
            start_create_training(
                user_id
            )
            return

        try:
            datetime.strptime(
                text,
                "%H:%M",
            )

        except ValueError:
            send_message(
                user_id,
                "❗ Неверный формат времени.\n"
                "Например: 19:00",
                back_keyboard("⬅️ Отмена"),
            )
            return

        state_data["data"][
            "start_time"
        ] = text

        set_state(
            user_id,
            "create_end_time",
            data=state_data["data"],
        )

        send_message(
            user_id,
            "Введите время окончания.\n"
            "Например: 20:30",
            back_keyboard("⬅️ Отмена"),
        )

        return

    # --------------------------------------------------------
    # CREATE TRAINING — END
    # --------------------------------------------------------

    if state == "create_end_time":
        if text in {
            "⬅️ Отмена",
            "⬅️ Назад",
        }:
            set_state(
                user_id,
                "create_start_time",
                data=state_data["data"],
            )

            send_message(
                user_id,
                "Введите время начала.\n"
                "Например: 19:00",
                back_keyboard("⬅️ Отмена"),
            )

            return

        try:
            datetime.strptime(
                text,
                "%H:%M",
            )

        except ValueError:
            send_message(
                user_id,
                "❗ Неверный формат времени.\n"
                "Например: 20:30",
                back_keyboard("⬅️ Отмена"),
            )
            return

        state_data["data"][
            "end_time"
        ] = text

        set_state(
            user_id,
            "create_title",
            data=state_data["data"],
        )

        send_message(
            user_id,
            "Введите название тренировки:",
            back_keyboard("⬅️ Отмена"),
        )

        return

    # --------------------------------------------------------
    # CREATE TRAINING — TITLE
    # --------------------------------------------------------

    if state == "create_title":
        if text in {
            "⬅️ Отмена",
            "⬅️ Назад",
        }:
            set_state(
                user_id,
                "create_end_time",
                data=state_data["data"],
            )

            send_message(
                user_id,
                "Введите время окончания.\n"
                "Например: 20:30",
                back_keyboard("⬅️ Отмена"),
            )

            return

        state_data["data"][
            "title"
        ] = text

        set_state(
            user_id,
            "create_category",
            data=state_data["data"],
        )

        send_message(
            user_id,
            "Выберите категорию:",
            category_keyboard(
                "⬅️ Отмена"
            ),
        )

        return

    # --------------------------------------------------------
    # CREATE TRAINING — CATEGORY
    # --------------------------------------------------------

    if state == "create_category":
        if text in {
            "⬅️ Отмена",
            "⬅️ Назад",
        }:
            set_state(
                user_id,
                "create_title",
                data=state_data["data"],
            )

            send_message(
                user_id,
                "Введите название тренировки:",
                back_keyboard("⬅️ Отмена"),
            )

            return

        category = category_from_text(
            text
        )

        if not category:
            return

        state_data["data"][
            "category"
        ] = category

        set_state(
            user_id,
            "create_level",
            data=state_data["data"],
        )

        send_message(
            user_id,
            "Выберите уровень:",
            level_keyboard(),
        )

        return

    # --------------------------------------------------------
    # CREATE TRAINING — LEVEL
    # --------------------------------------------------------

    if state == "create_level":
        if text in {
            "⬅️ Отмена",
            "⬅️ Назад",
        }:
            set_state(
                user_id,
                "create_category",
                data=state_data["data"],
            )

            send_message(
                user_id,
                "Выберите категорию:",
                category_keyboard(
                    "⬅️ Отмена"
                ),
            )

            return

        if text not in LEVELS:
            return

        state_data["data"][
            "level"
        ] = text

        set_state(
            user_id,
            "create_format",
            data=state_data["data"],
        )

        send_message(
            user_id,
            "Выберите формат:",
            format_keyboard(),
        )

        return

    # --------------------------------------------------------
    # CREATE TRAINING — FORMAT
    # --------------------------------------------------------

    if state == "create_format":
        if text in {
            "⬅️ Отмена",
            "⬅️ Назад",
        }:
            set_state(
                user_id,
                "create_level",
                data=state_data["data"],
            )

            send_message(
                user_id,
                "Выберите уровень:",
                level_keyboard(),
            )

            return

        if text not in FORMATS:
            return

        state_data["data"][
            "format"
        ] = text

        set_state(
            user_id,
            "create_coach",
            data=state_data["data"],
        )

        send_message(
            user_id,
            "Введите имя тренера:",
            back_keyboard("⬅️ Отмена"),
        )

        return

    # --------------------------------------------------------
    # CREATE TRAINING — COACH
    # --------------------------------------------------------

    if state == "create_coach":
        if text in {
            "⬅️ Отмена",
            "⬅️ Назад",
        }:
            set_state(
                user_id,
                "create_format",
                data=state_data["data"],
            )

            send_message(
                user_id,
                "Выберите формат:",
                format_keyboard(),
            )

            return

        state_data["data"][
            "coach"
        ] = text

        set_state(
            user_id,
            "create_capacity",
            data=state_data["data"],
        )

        send_message(
            user_id,
            "Введите количество мест.\n"
            "Например: 8",
            back_keyboard("⬅️ Отмена"),
        )

        return

    # --------------------------------------------------------
    # CREATE TRAINING — CAPACITY
    # --------------------------------------------------------

    if state == "create_capacity":
        if text in {
            "⬅️ Отмена",
            "⬅️ Назад",
        }:
            set_state(
                user_id,
                "create_coach",
                data=state_data["data"],
            )

            send_message(
                user_id,
                "Введите имя тренера:",
                back_keyboard("⬅️ Отмена"),
            )

            return

        try:
            capacity = int(text)

            if capacity <= 0:
                raise ValueError

        except ValueError:
            send_message(
                user_id,
                "❗ Введите положительное число.\n"
                "Например: 8",
                back_keyboard("⬅️ Отмена"),
            )
            return

        state_data["data"][
            "capacity"
        ] = capacity

        set_state(
            user_id,
            "create_price",
            data=state_data["data"],
        )

        send_message(
            user_id,
            "Введите стоимость тренировки.\n"
            "Например: 600",
            back_keyboard("⬅️ Отмена"),
        )

        return

    # --------------------------------------------------------
    # CREATE TRAINING — PRICE
    # --------------------------------------------------------

    if state == "create_price":
        if text in {
            "⬅️ Отмена",
            "⬅️ Назад",
        }:
            set_state(
                user_id,
                "create_capacity",
                data=state_data["data"],
            )

            send_message(
                user_id,
                "Введите количество мест.\n"
                "Например: 8",
                back_keyboard("⬅️ Отмена"),
            )

            return

        try:
            price = int(text)

            if price < 0:
                raise ValueError

        except ValueError:
            send_message(
                user_id,
                "❗ Введите стоимость числом.\n"
                "Например: 600",
                back_keyboard("⬅️ Отмена"),
            )
            return

        state_data["data"][
            "price"
        ] = price

        state_data["data"][
            "location"
        ] = WINTER_LOCATION

        create_training_finish(
            user_id
        )

        return

    # --------------------------------------------------------
    # FALLBACK
    # --------------------------------------------------------

    clear_state(user_id)

    send_message(
        user_id,
        "Не совсем понял сообщение.\n\n"
        "🏐 Главное меню:",
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
            silent=True
        )

        logger.info(
            "VK CALLBACK DATA: %s",
            data,
        )

        if not data:
            logger.warning(
                "VK CALLBACK: пустой запрос"
            )
            return "ok"

        event_type = data.get(
            "type"
        )

        logger.info(
            "VK EVENT TYPE: %s",
            event_type,
        )

        if event_type == "confirmation":
            logger.info(
                "VK CALLBACK: confirmation"
            )

            return (
                VK_CONFIRMATION_TOKEN
                or ""
            )

        if event_type != "message_new":
            logger.info(
                "VK CALLBACK: событие пропущено: %s",
                event_type,
            )

            return "ok"

        object_data = data.get(
            "object",
            {},
        )

        logger.info(
            "VK MESSAGE OBJECT: %s",
            object_data,
        )

        message_data = object_data.get(
            "message",
            {},
        )

        user_id = message_data.get(
            "from_id"
        )

        text = message_data.get(
            "text",
            "",
        )

        text = str(
            text or ""
        ).strip()

        logger.info(
            "VK MESSAGE: user_id=%s text=%r",
            user_id,
            text,
        )

        if not user_id:
            logger.error(
                "VK MESSAGE: отсутствует from_id"
            )

            return "ok"

        try:
            handle_message(
                int(user_id),
                text,
            )

            logger.info(
                "VK MESSAGE HANDLED: user_id=%s text=%r",
                user_id,
                text,
            )

        except Exception:
            logger.exception(
                "ОШИБКА ОБРАБОТКИ СООБЩЕНИЯ: "
                "user_id=%s text=%r",
                user_id,
                text,
            )

            try:
                send_message(
                    int(user_id),
                    "⚠️ Произошла техническая ошибка.\n"
                    "Попробуйте ещё раз.",
                    main_keyboard(
                        int(user_id)
                    ),
                )

            except Exception:
                logger.exception(
                    "НЕ УДАЛОСЬ ОТПРАВИТЬ "
                    "СООБЩЕНИЕ ОБ ОШИБКЕ"
                )

        return "ok"

    except Exception:
        logger.exception(
            "КРИТИЧЕСКАЯ ОШИБКА CALLBACK"
        )

        return "ok"


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route(
    "/",
    methods=["GET"],
)
def index():
    return "VOLLEY WAVE VK BOT OK", 200


# ============================================================
# STARTUP
# ============================================================

def startup():
    init_database()

    logger.info(
        "VOLLEY WAVE VK BOT VERSION №3 started"
    )


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
