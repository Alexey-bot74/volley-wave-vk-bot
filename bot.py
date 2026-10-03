import os
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
        import json

        params["keyboard"] = json.dumps(
            keyboard,
            ensure_ascii=False,
        )

    return vk_api(
        "messages.send",
        **params,
    )


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
    """
    Оставлено для совместимости
    со старым кодом.

    В Version №2 расписание показывает
    ближайшие 7 дней от сегодняшней даты.
    """
    return date.today()


def get_week_trainings(category=None):
    """
    Возвращает тренировки на ближайшие
    7 дней, включая сегодняшний день.
    """

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

    for row in rows:
        if row["training_date"] not in dates:
            dates.append(
                row["training_date"]
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
        "🎯 ИНДИВИДУАЛЬНЫЕ ТРЕНИРОВКИ\n\n"
        "Персональная работа с тренером "
        "по технике, физической подготовке "
        "и игровым элементам пляжного волейбола.",
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
        "Мы передадим его администратору.",
        back_keyboard(),
    )


def send_question_to_admins(
    user_id,
    text,
):
    ensure_user(user_id)

    for admin_id in ADMINS:
        send_message(
            admin_id,
            "❓ НОВЫЙ ВОПРОС\n\n"
            f"От VK ID: {user_id}\n\n"
            f"{text}",
            admin_keyboard(),
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
            "⛔ Доступ запрещён.",
            main_keyboard(user_id),
        )
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


# ============================================================
# ADMIN SCHEDULE
# ============================================================

def show_admin_schedule_categories(
    user_id,
):
    set_state(
        user_id,
        "admin_schedule_category",
    )

    send_message(
        user_id,
        "📅 АДМИН — РАСПИСАНИЕ\n\n"
        "Выберите категорию:",
        category_keyboard(
            "⬅️ Админ-панель"
        ),
    )


def show_admin_schedule(
    user_id,
    category=None,
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
            "admin_schedule_category",
        )

        send_message(
            user_id,
            "На ближайшие 7 дней "
            "тренировок этой категории нет.",
            category_keyboard(
                "⬅️ Админ-панель"
            ),
        )

        return

    start_date = date.today()

    end_date = (
        start_date
        + timedelta(days=6)
    )

    text = (
        "📅 АДМИН — РАСПИСАНИЕ\n"
        f"{category_label(category)}\n"
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
            f"№{row['training_number']} "
            f"{row['start_time']}–"
            f"{row['end_time']}\n"
            f"{category_label(row['category'])}\n"
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
        "admin_schedule_category",
        category=category,
    )

    send_message(
        user_id,
        text,
        category_keyboard(
            "⬅️ Админ-панель"
        ),
    )


# ============================================================
# ADMIN CREATE
# ============================================================

def start_create_training(
    user_id,
):
    set_state(
        user_id,
        "create_date",
    )

    send_message(
        user_id,
        "➕ СОЗДАНИЕ ТРЕНИРОВКИ\n\n"
        "Введите дату в формате:\n"
        "ДД.ММ.ГГГГ\n\n"
        "Например: 15.10.2026",
        back_keyboard(
            "⬅️ Отмена"
        ),
    )


def create_date_step(
    user_id,
    text,
):
    parsed = parse_date(text)

    if not parsed:
        send_message(
            user_id,
            "❌ Не удалось распознать дату.\n\n"
            "Введите её в формате ДД.ММ.ГГГГ.",
            back_keyboard(
                "⬅️ Отмена"
            ),
        )
        return

    if parsed < date.today():
        send_message(
            user_id,
            "❌ Нельзя создать тренировку "
            "на прошедшую дату.",
            back_keyboard(
                "⬅️ Отмена"
            ),
        )
        return

    set_state(
        user_id,
        "create_time",
        training_date=parsed.strftime(
            "%Y-%m-%d"
        ),
    )

    send_message(
        user_id,
        "⏰ Введите время тренировки.\n\n"
        "Например:\n"
        "19:00-20:30",
        back_keyboard(
            "⬅️ Отмена"
        ),
    )


def create_time_step(
    user_id,
    text,
):
    value = text.strip()

    if "-" not in value:
        send_message(
            user_id,
            "❌ Формат времени:\n"
            "19:00-20:30",
            back_keyboard(
                "⬅️ Отмена"
            ),
        )
        return

    parts = value.split(
        "-",
        1,
    )

    start_time = parts[0].strip()
    end_time = parts[1].strip()

    try:
        datetime.strptime(
            start_time,
            "%H:%M",
        )

        datetime.strptime(
            end_time,
            "%H:%M",
        )

    except ValueError:
        send_message(
            user_id,
            "❌ Проверьте время.\n\n"
            "Пример: 19:00-20:30",
            back_keyboard(
                "⬅️ Отмена"
            ),
        )
        return

    state = get_state(user_id)

    set_state(
        user_id,
        "create_category",
        training_date=state[
            "training_date"
        ],
        start_time=start_time,
        end_time=end_time,
    )

    send_message(
        user_id,
        "👥 Выберите категорию:",
        category_keyboard(
            "⬅️ Отмена"
        ),
    )


def create_category_step(
    user_id,
    text,
):
    category = category_from_text(
        text
    )

    if not category:
        send_message(
            user_id,
            "Выберите категорию "
            "кнопкой ниже.",
            category_keyboard(
                "⬅️ Отмена"
            ),
        )
        return

    state = get_state(user_id)

    set_state(
        user_id,
        "create_title",
        training_date=state[
            "training_date"
        ],
        start_time=state[
            "start_time"
        ],
        end_time=state[
            "end_time"
        ],
        category=category,
    )

    send_message(
        user_id,
        "📝 Введите название тренировки.\n\n"
        "Например:\n"
        "Тренировка по технике",
        back_keyboard(
            "⬅️ Отмена"
        ),
    )


def create_title_step(
    user_id,
    text,
):
    state = get_state(user_id)

    set_state(
        user_id,
        "create_level",
        **{
            **state,
            "title": text.strip(),
        },
    )

    send_message(
        user_id,
        "📊 Выберите уровень:",
        level_keyboard(),
    )


def create_level_step(
    user_id,
    text,
):
    if text not in LEVELS:
        send_message(
            user_id,
            "Выберите уровень кнопкой ниже.",
            level_keyboard(),
        )
        return

    state = get_state(user_id)

    set_state(
        user_id,
        "create_format",
        **{
            **state,
            "level": text,
        },
    )

    send_message(
        user_id,
        "🏐 Выберите формат:",
        format_keyboard(),
    )


def create_format_step(
    user_id,
    text,
):
    if text not in FORMATS:
        send_message(
            user_id,
            "Выберите формат кнопкой ниже.",
            format_keyboard(),
        )
        return

    state = get_state(user_id)

    set_state(
        user_id,
        "create_capacity",
        **{
            **state,
            "format": text,
        },
    )

    send_message(
        user_id,
        "👥 Введите количество мест.\n\n"
        "Например: 8",
        back_keyboard(
            "⬅️ Отмена"
        ),
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
            "❌ Введите положительное "
            "целое число.",
            back_keyboard(
                "⬅️ Отмена"
            ),
        )
        return

    state = get_state(user_id)

    set_state(
        user_id,
        "create_price",
        **{
            **state,
            "capacity": capacity,
        },
    )

    category = normalize_category(
        state.get("category")
    )

    default_price = (
        CHILDREN_PRICE
        if category == "children"
        else ADULT_PRICE
    )

    send_message(
        user_id,
        "💰 Введите стоимость тренировки.\n\n"
        f"По умолчанию для выбранной категории: "
        f"{default_price} ₽\n\n"
        "Можно ввести другую сумму.",
        back_keyboard(
            "⬅️ Отмена"
        ),
    )


def create_price_step(
    user_id,
    text,
):
    try:
        price = int(
            text.strip()
        )

        if price < 0:
            raise ValueError

    except ValueError:
        send_message(
            user_id,
            "❌ Введите стоимость числом.",
            back_keyboard(
                "⬅️ Отмена"
            ),
        )
        return

    state = get_state(user_id)

    category = normalize_category(
        state.get("category")
    )

    location = WINTER_LOCATION

    training_id = create_training(
        {
            "training_date": state[
                "training_date"
            ],
            "start_time": state[
                "start_time"
            ],
            "end_time": state[
                "end_time"
            ],
            "title": state.get(
                "title"
            ),
            "category": category,
            "level": state.get(
                "level"
            ),
            "format": state.get(
                "format"
            ),
            "capacity": state.get(
                "capacity",
                8,
            ),
            "price": price,
            "location": location,
            "coach": "",
        }
    )

    training = get_training(
        training_id
    )

    if user_id in ADMINS:
        conn = get_db()

        conn.execute(
            """
            INSERT INTO admin_logs (
                admin_vk_id,
                action,
                created_at
            )
            VALUES (?, ?, ?)
            """,
            (
                user_id,
                (
                    "Создана тренировка "
                    f"№{training['training_number']}"
                ),
                datetime.now().isoformat(),
            ),
        )

        conn.commit()
        conn.close()

    clear_state(user_id)

    send_message(
        user_id,
        "✅ ТРЕНИРОВКА СОЗДАНА!\n\n"
        + training_details_text(
            training
        ),
        admin_keyboard(),
    )


# ============================================================
# ADMIN PARTICIPANTS
# ============================================================

def show_admin_participants(
    user_id,
):
    rows = get_future_trainings()

    if not rows:
        send_message(
            user_id,
            "Тренировок пока нет.",
            admin_keyboard(),
        )
        return

    buttons = []

    for row in rows[:8]:
        count = registration_count(
            row["id"]
        )

        buttons.append(
            [
                button(
                    f"№{row['training_number']} "
                    f"{format_date_short(row['training_date'])} "
                    f"{row['start_time']} "
                    f"({count}/{row['capacity']})",
                    "primary",
                )
            ]
        )

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
    )

    send_message(
        user_id,
        "👥 УЧАСТНИКИ\n\n"
        "Выберите тренировку:",
        {
            "one_time": False,
            "buttons": buttons,
        },
    )


def show_admin_training(
    user_id,
    training,
):
    participants = get_participants(
        training["id"]
    )

    text = (
        f"👥 ТРЕНИРОВКА №"
        f"{training['training_number']}\n\n"
        f"{format_date_long(training['training_date'])}\n"
        f"{training['start_time']}–"
        f"{training['end_time']}\n\n"
        f"Участников: "
        f"{len(participants)}/"
        f"{training['capacity']}\n\n"
    )

    if not participants:
        text += "Пока никто не записан."

    else:
        for index, person in enumerate(
            participants,
            start=1,
        ):
            name = (
                f"{person['first_name'] or ''} "
                f"{person['last_name'] or ''}"
            ).strip()

            if not name:
                name = (
                    f"VK ID "
                    f"{person['vk_id']}"
                )

            text += (
                f"{index}. {name}\n"
            )

    set_state(
        user_id,
        "admin_training",
        training_id=training["id"],
    )

    send_message(
        user_id,
        text,
        back_keyboard(
            "⬅️ Участники"
        ),
    )


# ============================================================
# HANDLE MESSAGE
# ============================================================

def handle_message(
    user_id,
    text,
):
    ensure_user(user_id)

    text = (text or "").strip()

    state = get_state(user_id)
    state_name = state.get(
        "state",
        "main",
    )

    logger.info(
        "VK %s | state=%s | text=%s",
        user_id,
        state_name,
        text,
    )

    # ========================================================
    # START / MAIN
    # ========================================================

    if text in {
        "/start",
        "Начать",
        "Старт",
        "🏠 Главное меню",
    }:
        clear_state(user_id)

        send_message(
            user_id,
            "🏐 VOLLEY WAVE\n\n"
            "Школа пляжного волейбола.\n\n"
            "Выберите действие:",
            main_keyboard(user_id),
        )

        return

    # ========================================================
    # CANCEL / BACK
    # ========================================================

    if text in {
        "⬅️ Отмена",
        "Отмена",
    }:
        clear_state(user_id)

        if user_id in ADMINS:
            send_message(
                user_id,
                "Действие отменено.",
                admin_keyboard(),
            )

        else:
            send_message(
                user_id,
                "Действие отменено.",
                main_keyboard(user_id),
            )

        return

    # ========================================================
    # SCHEDULE CATEGORY
    # ========================================================

    if state_name == "schedule_category":

        if text == "⬅️ Назад":
            clear_state(user_id)

            send_message(
                user_id,
                "🏐 Главное меню",
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

        send_message(
            user_id,
            "Выберите категорию кнопкой ниже.",
            category_keyboard(),
        )

        return

    # ========================================================
    # SCHEDULE
    # ========================================================

    if state_name == "schedule":

        if text == "⬅️ Назад":
            show_schedule_categories(
                user_id
            )
            return

        if text == "🏐 Записаться":
            start_booking(user_id)
            return

        category = state.get(
            "category"
        )

        if category:
            show_week_schedule(
                user_id,
                category,
            )

        else:
            show_schedule_categories(
                user_id
            )

        return

    # ========================================================
    # BOOKING CATEGORY
    # ========================================================

    if state_name == "booking_category":

        if text == "⬅️ Назад":
            clear_state(user_id)

            send_message(
                user_id,
                "🏠 Главное меню",
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

        send_message(
            user_id,
            "Выберите категорию.",
            category_keyboard(),
        )

        return

    # ========================================================
    # BOOKING DATE
    # ========================================================

    if state_name == "booking_date":

        if text == "⬅️ Назад":
            start_booking(user_id)
            return

        category = state.get(
            "category"
        )

        rows = get_future_trainings(
            category
        )

        selected_date = None

        for row in rows:
            label = format_date_long(
                row["training_date"]
            )

            if text == label:
                selected_date = row[
                    "training_date"
                ]
                break

        if selected_date:
            show_booking_trainings(
                user_id,
                category,
                selected_date,
            )
            return

        send_message(
            user_id,
            "Выберите дату кнопкой.",
        )

        return

    # ========================================================
    # BOOKING TRAINING
    # ========================================================

    if state_name == "booking_training":

        if text == "⬅️ Назад":
            show_booking_dates(
                user_id,
                state.get(
                    "category"
                ),
            )
            return

        category = state.get(
            "category"
        )

        training_date = state.get(
            "training_date"
        )

        rows = get_future_trainings(
            category
        )

        for row in rows:

            if (
                row["training_date"]
                != training_date
            ):
                continue

            label = (
                f"№{row['training_number']} "
                f"{row['start_time']} "
                f"("
                f"{registration_count(row['id'])}/"
                f"{row['capacity']}"
                f")"
            )

            if text == label:
                show_booking_details(
                    user_id,
                    row,
                )
                return

        send_message(
            user_id,
            "Выберите тренировку "
            "кнопкой ниже.",
        )

        return

    # ========================================================
    # BOOKING CONFIRM
    # ========================================================

    if state_name == "booking_confirm":

        training_id = state.get(
            "training_id"
        )

        training = get_training(
            training_id
        )

        if not training:
            clear_state(user_id)

            send_message(
                user_id,
                "❌ Тренировка не найдена.",
                main_keyboard(user_id),
            )

            return

        if text == "⬅️ Назад":
            start_booking(user_id)
            return

        if text == "✅ Записаться":

            result = register_user(
                training_id,
                user_id,
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

            elif result == "already":
                send_message(
                    user_id,
                    "Вы уже записаны "
                    "на эту тренировку.",
                    main_keyboard(user_id),
                )

            elif result == "full":
                send_message(
                    user_id,
                    "❌ Все места уже заняты.",
                    main_keyboard(user_id),
                )

            else:
                send_message(
                    user_id,
                    "❌ Не удалось записаться.",
                    main_keyboard(user_id),
                )

            return

        send_message(
            user_id,
            "Используйте кнопки ниже.",
            {
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
            },
        )

        return

    # ========================================================
    # MY TRAININGS
    # ========================================================

    if text == "👤 Мои тренировки":
        show_my_trainings(user_id)
        return

    # ========================================================
    # PRICES
    # ========================================================

    if text == "💰 Цены":
        show_prices(user_id)
        return

    # ========================================================
    # LOCATION
    # ========================================================

    if text == "📍 Где тренируемся":
        show_location(user_id)
        return

    # ========================================================
    # INDIVIDUAL
    # ========================================================

    if text == "🎯 Индивидуальная":
        show_individual(user_id)
        return

    # ========================================================
    # QUESTION
    # ========================================================

    if state_name == "question":

        if text == "⬅️ Назад":
            clear_state(user_id)

            send_message(
                user_id,
                "🏠 Главное меню",
                main_keyboard(user_id),
            )

            return

        send_question_to_admins(
            user_id,
            text,
        )

        clear_state(user_id)

        send_message(
            user_id,
            "✅ Вопрос отправлен администратору.",
            main_keyboard(user_id),
        )

        return

    if text == "❓ Задать вопрос":
        start_question(user_id)
        return

    # ========================================================
    # ADMIN SCHEDULE CATEGORY
    # ========================================================

    if state_name == "admin_schedule_category":

        if text == "⬅️ Админ-панель":
            show_admin(user_id)
            return

        category = category_from_text(
            text
        )

        if category:
            show_admin_schedule(
                user_id,
                category,
            )

            return

        send_message(
            user_id,
            "Выберите категорию кнопкой ниже.",
            category_keyboard(
                "⬅️ Админ-панель"
            ),
        )

        return

    # ========================================================
    # ADMIN CREATE DATE
    # ========================================================

    if state_name == "create_date":

        if text == "⬅️ Отмена":
            show_admin(user_id)
            return

        create_date_step(
            user_id,
            text,
        )

        return

    # ========================================================
    # ADMIN CREATE TIME
    # ========================================================

    if state_name == "create_time":

        if text == "⬅️ Отмена":
            show_admin(user_id)
            return

        create_time_step(
            user_id,
            text,
        )

        return

    # ========================================================
    # ADMIN CREATE CATEGORY
    # ========================================================

    if state_name == "create_category":

        if text == "⬅️ Отмена":
            show_admin(user_id)
            return

        create_category_step(
            user_id,
            text,
        )

        return

    # ========================================================
    # ADMIN CREATE TITLE
    # ========================================================

    if state_name == "create_title":

        if text == "⬅️ Отмена":
            show_admin(user_id)
            return

        create_title_step(
            user_id,
            text,
        )

        return

    # ========================================================
    # ADMIN CREATE LEVEL
    # ========================================================

    if state_name == "create_level":

        if text == "⬅️ Отмена":
            show_admin(user_id)
            return

        create_level_step(
            user_id,
            text,
        )

        return

    # ========================================================
    # ADMIN CREATE FORMAT
    # ========================================================

    if state_name == "create_format":

        if text == "⬅️ Отмена":
            show_admin(user_id)
            return

        create_format_step(
            user_id,
            text,
        )

        return

    # ========================================================
    # ADMIN CREATE CAPACITY
    # ========================================================

    if state_name == "create_capacity":

        if text == "⬅️ Отмена":
            show_admin(user_id)
            return

        create_capacity_step(
            user_id,
            text,
        )

        return

    # ========================================================
    # ADMIN CREATE PRICE
    # ========================================================

    if state_name == "create_price":

        if text == "⬅️ Отмена":
            show_admin(user_id)
            return

        create_price_step(
            user_id,
            text,
        )

        return

    # ========================================================
    # ADMIN PARTICIPANTS
    # ========================================================

    if state_name == "admin_participants":

        if text == "⬅️ Админ-панель":
            show_admin(user_id)
            return

        rows = get_future_trainings()

        for row in rows[:8]:

            count = registration_count(
                row["id"]
            )

            label = (
                f"№{row['training_number']} "
                f"{format_date_short(row['training_date'])} "
                f"{row['start_time']} "
                f"({count}/{row['capacity']})"
            )

            if text == label:
                show_admin_training(
                    user_id,
                    row,
                )

                return

        send_message(
            user_id,
            "Выберите тренировку кнопкой.",
            admin_keyboard(),
        )

        return

    # ========================================================
    # ADMIN TRAINING
    # ========================================================

    if state_name == "admin_training":

        if text == "⬅️ Участники":
            show_admin_participants(
                user_id
            )
            return

        show_admin(user_id)
        return

    # ========================================================
    # ADMIN MAIN
    # ========================================================

    if state_name == "admin":

        if text == "📅 Расписание":
            show_admin_schedule_categories(
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
                "🏠 Главное меню",
                main_keyboard(user_id),
            )

            return

        show_admin(user_id)
        return

    # ========================================================
    # ADMIN ENTRY
    # ========================================================

    if text == "⚙️ Админ-панель":

        if user_id in ADMINS:
            show_admin(user_id)

        else:
            send_message(
                user_id,
                "⛔ Доступ запрещён.",
                main_keyboard(user_id),
            )

        return

    # ========================================================
    # BOOKING ENTRY
    # ========================================================

    if text == "🏐 Записаться":
        start_booking(user_id)
        return

    # ========================================================
    # SCHEDULE ENTRY
    # ========================================================

    if text == "📅 Расписание":
        show_schedule_categories(
            user_id
        )
        return

    # ========================================================
    # UNKNOWN
    # ========================================================

    send_message(
        user_id,
        "Не совсем понял команду 🤔\n\n"
        "Выберите действие кнопками ниже.",
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

        # Подтверждение Callback API VK
        if event_type == "confirmation":

            logger.info(
                "VK CALLBACK: confirmation"
            )

            return (
                VK_CONFIRMATION_TOKEN
                or ""
            )

        # Нас интересуют только новые сообщения
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

        handle_message(
            int(user_id),
            text,
        )

        logger.info(
            "VK MESSAGE HANDLED: user_id=%s text=%r",
            user_id,
            text,
        )

        return "ok"

    except Exception:

        logger.exception(
            "КРИТИЧЕСКАЯ ОШИБКА CALLBACK"
        )

        return "ok"
    event_type = data.get(
        "type"
    )

    if event_type == "confirmation":
        return (
            VK_CONFIRMATION_TOKEN
            or ""
        )

    if event_type != "message_new":
        return "ok"

    object_data = data.get(
        "object",
        {},
    )

    user_id = object_data.get(
        "from_id"
    )

    text = object_data.get(
        "text",
        "",
    )

    if not user_id:
        return "ok"

    try:
        handle_message(
            user_id,
            text,
        )

    except Exception:
        logger.exception(
            "Ошибка обработки сообщения"
        )

        try:
            send_message(
                user_id,
                "⚠️ Произошла техническая ошибка.\n"
                "Попробуйте ещё раз.",
                main_keyboard(user_id),
            )

        except Exception:
            logger.exception(
                "Не удалось отправить сообщение "
                "об ошибке"
            )

    return "ok"


# ============================================================
# STARTUP
# ============================================================

def startup():
    init_database()

    logger.info(
        "VOLLEY WAVE VK BOT VERSION №2 started"
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
