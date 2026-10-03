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
# PRICES / LOCATIONS
# ============================================================

CHILD_PRICE = 600
ADULT_PRICE = 1200
ADULT_LARGE_GROUP_PRICE = 1000

SUMMER_LOCATION = "Парк Гагарина"
WINTER_LOCATION = 'СК «Арена», ул. Молодогвардейцев, 7'

# Сколько дат максимум показываем на одной странице.
# Вместе с кнопками навигации и "Назад" остаётся безопасный
# запас относительно ограничения VK.
DATES_PER_PAGE = 6

# Сколько тренировок показываем на странице участников.
TRAININGS_PER_PAGE = 6

# ============================================================
# DEFAULT TEMPLATES
# ============================================================

DEFAULT_TEMPLATES = [
    {
        "weekday": 0,
        "start_time": "09:00",
        "end_time": "11:00",
        "title": "Детская тренировка",
        "category": "children",
        "age_group": "9–13 лет",
        "level": "Начальный / средний",
        "format": "Группа",
        "coach": "Алексей",
        "capacity": 10,
        "price": 600,
    },
    {
        "weekday": 0,
        "start_time": "17:00",
        "end_time": "19:00",
        "title": "Детская тренировка",
        "category": "children",
        "age_group": "11–14 лет",
        "level": "Средний",
        "format": "Группа",
        "coach": "Алексей",
        "capacity": 10,
        "price": 600,
    },
    {
        "weekday": 0,
        "start_time": "19:00",
        "end_time": "20:30",
        "title": "Техническая тренировка",
        "category": "adults",
        "age_group": "18+",
        "level": "Техническая",
        "format": "Группа",
        "coach": "Алексей",
        "capacity": 10,
        "price": 1200,
    },
    {
        "weekday": 1,
        "start_time": "09:00",
        "end_time": "11:00",
        "title": "Общая тренировка",
        "category": "adults",
        "age_group": "18+",
        "level": "Общий",
        "format": "Группа",
        "coach": "Алексей",
        "capacity": 8,
        "price": 1200,
    },
    {
        "weekday": 1,
        "start_time": "17:00",
        "end_time": "18:30",
        "title": "Детская тренировка",
        "category": "children",
        "age_group": "11–14 лет",
        "level": "Средний",
        "format": "Группа",
        "coach": "Алексей",
        "capacity": 10,
        "price": 600,
    },
    {
        "weekday": 1,
        "start_time": "19:30",
        "end_time": "21:00",
        "title": "Женская тренировка",
        "category": "adults",
        "age_group": "18+",
        "level": "Средний+",
        "format": "Женская группа",
        "coach": "Алексей",
        "capacity": 8,
        "price": 1200,
    },
    {
        "weekday": 2,
        "start_time": "09:00",
        "end_time": "11:00",
        "title": "Детская тренировка",
        "category": "children",
        "age_group": "9–14 лет",
        "level": "Начальный / средний",
        "format": "Группа",
        "coach": "Алексей",
        "capacity": 10,
        "price": 600,
    },
    {
        "weekday": 2,
        "start_time": "17:00",
        "end_time": "18:00",
        "title": "Детская тренировка",
        "category": "children",
        "age_group": "5–9 лет",
        "level": "Начальный",
        "format": "Группа",
        "coach": "Ксения",
        "capacity": 10,
        "price": 600,
    },
    {
        "weekday": 2,
        "start_time": "18:00",
        "end_time": "19:30",
        "title": "Продвинутая тренировка",
        "category": "adults",
        "age_group": "18+",
        "level": "Продвинутый",
        "format": "Группа",
        "coach": "Алексей",
        "capacity": 8,
        "price": 1200,
    },
    {
        "weekday": 2,
        "start_time": "19:30",
        "end_time": "21:00",
        "title": "MIXED",
        "category": "adults",
        "age_group": "18+",
        "level": "Средний+",
        "format": "MIXED",
        "coach": "Алексей",
        "capacity": 8,
        "price": 1200,
    },
    {
        "weekday": 3,
        "start_time": "09:00",
        "end_time": "11:00",
        "title": "Общая тренировка",
        "category": "adults",
        "age_group": "18+",
        "level": "Общий",
        "format": "Группа",
        "coach": "Алексей",
        "capacity": 8,
        "price": 1200,
    },
    {
        "weekday": 3,
        "start_time": "17:00",
        "end_time": "19:00",
        "title": "Детская тренировка",
        "category": "children",
        "age_group": "11–14 лет",
        "level": "Средний",
        "format": "Группа",
        "coach": "Алексей",
        "capacity": 10,
        "price": 600,
    },
    {
        "weekday": 3,
        "start_time": "19:00",
        "end_time": "20:30",
        "title": "Групповая тренировка",
        "category": "adults",
        "age_group": "18+",
        "level": "Средний",
        "format": "Группа",
        "coach": "Алексей",
        "capacity": 8,
        "price": 1200,
    },
    {
        "weekday": 4,
        "start_time": "09:00",
        "end_time": "11:00",
        "title": "Детская тренировка",
        "category": "children",
        "age_group": "9–14 лет",
        "level": "Начальный / средний",
        "format": "Группа",
        "coach": "Алексей",
        "capacity": 10,
        "price": 600,
    },
    {
        "weekday": 4,
        "start_time": "17:00",
        "end_time": "18:00",
        "title": "Детская тренировка",
        "category": "children",
        "age_group": "5–10 лет",
        "level": "Начальный",
        "format": "Группа",
        "coach": "Ксения",
        "capacity": 10,
        "price": 600,
    },
    {
        "weekday": 4,
        "start_time": "17:00",
        "end_time": "19:00",
        "title": "Детская тренировка",
        "category": "children",
        "age_group": "11–14 лет",
        "level": "Средний",
        "format": "Группа",
        "coach": "Алексей",
        "capacity": 10,
        "price": 600,
    },
    {
        "weekday": 4,
        "start_time": "19:00",
        "end_time": "20:30",
        "title": "Техническая тренировка",
        "category": "adults",
        "age_group": "18+",
        "level": "Техническая",
        "format": "Группа",
        "coach": "Алексей",
        "capacity": 10,
        "price": 1200,
    },
]

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

# ============================================================
# DATABASE
# ============================================================


def db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def table_exists(conn, table_name):
    row = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type='table' AND name=?
        """,
        (table_name,),
    ).fetchone()
    return row is not None


def column_names(conn, table_name):
    if not table_exists(conn, table_name):
        return []
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return [row["name"] for row in rows]


def init_database():
    conn = db()

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
        CREATE TABLE IF NOT EXISTS waitlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            training_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            position INTEGER DEFAULT 1,
            status TEXT DEFAULT 'waiting',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
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

    conn.commit()
    conn.close()


def ensure_user(user_id):
    conn = db()

    conn.execute(
        """
        INSERT INTO users (vk_id)
        VALUES (?)
        ON CONFLICT(vk_id) DO UPDATE SET
            updated_at=CURRENT_TIMESTAMP
        """,
        (user_id,),
    )

    conn.commit()
    conn.close()


def update_user_name(user_id, first_name="", last_name=""):
    conn = db()

    conn.execute(
        """
        UPDATE users
        SET first_name=?,
            last_name=?,
            updated_at=CURRENT_TIMESTAMP
        WHERE vk_id=?
        """,
        (first_name or "", last_name or "", user_id),
    )

    conn.commit()
    conn.close()


def get_user_id(user_id):
    conn = db()
    row = conn.execute(
        "SELECT id FROM users WHERE vk_id=?",
        (user_id,),
    ).fetchone()
    conn.close()

    if row:
        return row["id"]

    ensure_user(user_id)

    conn = db()
    row = conn.execute(
        "SELECT id FROM users WHERE vk_id=?",
        (user_id,),
    ).fetchone()
    conn.close()

    return row["id"]


# ============================================================
# TRAININGS
# ============================================================


def normalize_category(category):
    """
    Приводим разные варианты к двум значениям БД.
    Это ключевое исправление проблемы "Дети -> adults".
    """

    if not category:
        return None

    value = str(category).strip().lower()

    if value in {
        "children",
        "child",
        "kids",
        "дети",
        "детская",
        "👧 дети",
        "👧дети",
    }:
        return "children"

    if value in {
        "adults",
        "adult",
        "взрослые",
        "взрослый",
        "🧑 взрослые",
        "🧑взрослые",
    }:
        return "adults"

    return value


def category_label(category):
    category = normalize_category(category)

    if category == "children":
        return "👧 Дети"

    if category == "adults":
        return "🧑 Взрослые"

    return "🏠 Все тренировки"


def get_next_training_number(conn):
    row = conn.execute(
        """
        SELECT COALESCE(MAX(training_number), 0) + 1 AS next_number
        FROM trainings
        """
    ).fetchone()

    return int(row["next_number"])


def get_location_for_date(training_date):
    """
    Пока используем зимнюю площадку.
    При необходимости потом можно сделать автоматическое
    переключение по сезону.
    """
    return WINTER_LOCATION


def create_training(
    conn,
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
    template_id=None,
):
    existing = conn.execute(
        """
        SELECT id
        FROM trainings
        WHERE training_date=?
          AND start_time=?
          AND end_time=?
          AND title=?
          AND category=?
          AND age_group=?
          AND status != 'cancelled'
        LIMIT 1
        """,
        (
            training_date,
            start_time,
            end_time,
            title,
            normalize_category(category),
            age_group,
        ),
    ).fetchone()

    if existing:
        return existing["id"]

    number = get_next_training_number(conn)

    d = datetime.strptime(training_date, "%Y-%m-%d").date()

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
            status,
            template_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)
        """,
        (
            number,
            training_date,
            WEEKDAYS[d.weekday()],
            start_time,
            end_time,
            title,
            normalize_category(category),
            age_group,
            level,
            training_format,
            coach,
            capacity,
            price,
            get_location_for_date(training_date),
            template_id,
        ),
    )

    return cursor.lastrowid


def generate_trainings(weeks=6):
    """
    Создаёт расписание на ближайшие 6 недель.
    Существующие тренировки не дублируются.
    """

    conn = db()

    start = date.today()

    # Генерируем с ближайшего понедельника.
    monday = start - timedelta(days=start.weekday())

    created = 0

    for week in range(weeks):
        for template in DEFAULT_TEMPLATES:
            training_date = monday + timedelta(
                days=week * 7 + template["weekday"]
            )

            if training_date < start:
                continue

            training_date_str = training_date.strftime("%Y-%m-%d")

            before = conn.execute(
                """
                SELECT id
                FROM trainings
                WHERE training_date=?
                  AND start_time=?
                  AND end_time=?
                  AND title=?
                  AND category=?
                  AND age_group=?
                  AND status != 'cancelled'
                LIMIT 1
                """,
                (
                    training_date_str,
                    template["start_time"],
                    template["end_time"],
                    template["title"],
                    template["category"],
                    template["age_group"],
                ),
            ).fetchone()

            if before:
                continue

            create_training(
                conn=conn,
                training_date=training_date_str,
                start_time=template["start_time"],
                end_time=template["end_time"],
                title=template["title"],
                category=template["category"],
                age_group=template["age_group"],
                level=template["level"],
                training_format=template["format"],
                coach=template["coach"],
                capacity=template["capacity"],
                price=template["price"],
            )

            created += 1

    conn.commit()
    conn.close()

    logger.info("Training generation complete. Created: %s", created)


def get_trainings_for_category(
    category=None,
    start_date=None,
    end_date=None,
):
    category = normalize_category(category)

    if start_date is None:
        start_date = date.today()

    if end_date is None:
        end_date = start_date + timedelta(days=14)

    conn = db()

    sql = """
        SELECT *
        FROM trainings
        WHERE training_date >= ?
          AND training_date <= ?
          AND status = 'active'
    """

    params = [
        start_date.strftime("%Y-%m-%d"),
        end_date.strftime("%Y-%m-%d"),
    ]

    if category in ("children", "adults"):
        sql += " AND category = ?"
        params.append(category)

    sql += """
        ORDER BY training_date, start_time, id
    """

    rows = conn.execute(sql, params).fetchall()
    conn.close()

    return rows


def get_training(training_id):
    conn = db()

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


def get_training_by_number(training_number):
    conn = db()

    row = conn.execute(
        """
        SELECT *
        FROM trainings
        WHERE training_number=?
        """,
        (training_number,),
    ).fetchone()

    conn.close()
    return row


# ============================================================
# REGISTRATIONS
# ============================================================


def get_registration(training_id, user_vk_id):
    user_id = get_user_id(user_vk_id)

    conn = db()

    row = conn.execute(
        """
        SELECT *
        FROM registrations
        WHERE training_id=?
          AND user_id=?
        LIMIT 1
        """,
        (training_id, user_id),
    ).fetchone()

    conn.close()
    return row


def get_active_registration_count(training_id):
    conn = db()

    row = conn.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM registrations
        WHERE training_id=?
          AND status='registered'
        """,
        (training_id,),
    ).fetchone()

    conn.close()

    return int(row["cnt"])


def get_training_participants(training_id):
    conn = db()

    rows = conn.execute(
        """
        SELECT
            r.id,
            r.user_id,
            r.status,
            r.registered_at,
            u.vk_id,
            u.first_name,
            u.last_name
        FROM registrations r
        JOIN users u ON u.id=r.user_id
        WHERE r.training_id=?
          AND r.status='registered'
        ORDER BY r.registered_at, r.id
        """,
        (training_id,),
    ).fetchall()

    conn.close()

    return rows


def add_registration(training_id, user_vk_id):
    user_id = get_user_id(user_vk_id)

    conn = db()

    existing = conn.execute(
        """
        SELECT *
        FROM registrations
        WHERE training_id=?
          AND user_id=?
        LIMIT 1
        """,
        (training_id, user_id),
    ).fetchone()

    if existing and existing["status"] == "registered":
        conn.close()
        return False, "already"

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

    count_row = conn.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM registrations
        WHERE training_id=?
          AND status='registered'
        """,
        (training_id,),
    ).fetchone()

    count = int(count_row["cnt"])

    if count >= int(training["capacity"]):
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
            (training_id, user_id),
        )

    conn.commit()
    conn.close()

    return True, "ok"


def cancel_registration(training_id, user_vk_id):
    user_id = get_user_id(user_vk_id)

    conn = db()

    row = conn.execute(
        """
        SELECT *
        FROM registrations
        WHERE training_id=?
          AND user_id=?
          AND status='registered'
        LIMIT 1
        """,
        (training_id, user_id),
    ).fetchone()

    if not row:
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
        training_datetime = datetime.strptime(
            f"{training['training_date']} {training['start_time']}",
            "%Y-%m-%d %H:%M",
        )

        hours_left = (
            training_datetime - datetime.now()
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
        (row["id"],),
    )

    conn.commit()
    conn.close()

    return True, "ok"


def get_user_upcoming_registrations(user_vk_id):
    user_id = get_user_id(user_vk_id)

    conn = db()

    rows = conn.execute(
        """
        SELECT
            r.id AS registration_id,
            r.status AS registration_status,
            t.*
        FROM registrations r
        JOIN trainings t ON t.id=r.training_id
        WHERE r.user_id=?
          AND r.status='registered'
          AND t.status='active'
          AND t.training_date >= ?
        ORDER BY t.training_date, t.start_time
        """,
        (
            user_id,
            date.today().strftime("%Y-%m-%d"),
        ),
    ).fetchall()

    conn.close()

    return rows


# ============================================================
# ADMIN LOG
# ============================================================


def admin_log(admin_id, action, entity_type="", entity_id=None, details=""):
    try:
        conn = db()

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
        logger.error("Admin log error: %s", e)


# ============================================================
# VK API
# ============================================================


def vk_api(method, params):
    if not VK_TOKEN:
        logger.error("VK_TOKEN is missing")
        return None

    params = dict(params)
    params["access_token"] = VK_TOKEN
    params["v"] = VK_API_VERSION

    try:
        response = requests.post(
            f"https://api.vk.com/method/{method}",
            data=params,
            timeout=15,
        )

        data = response.json()

        if "error" in data:
            logger.error(
                "VK API error in %s:\n%s",
                method,
                data,
            )
            return None

        return data.get("response")

    except Exception as e:
        logger.error(
            "VK API exception in %s: %s",
            method,
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


def send_message(user_id, message, keyboard=None):
    params = {
        "user_id": user_id,
        "random_id": 0,
        "message": message,
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
            button("🎯 Индивидуальная тренировка", "secondary"),
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


def send_main_menu(user_id, text="🏐 VOLLEY WAVE\n\nВыберите действие:"):
    send_message(
        user_id,
        text,
        main_keyboard(user_id),
    )


def booking_category_keyboard():
    return {
        "one_time": False,
        "buttons": [
            [
                button("👧 Дети", "primary"),
                button("🧑 Взрослые", "primary"),
            ],
            [
                button("⬅️ Назад", "secondary"),
            ],
        ],
    }


def schedule_category_keyboard():
    return {
        "one_time": False,
        "buttons": [
            [
                button("👧 Дети", "primary"),
                button("🧑 Взрослые", "primary"),
            ],
            [
                button("🏠 Все тренировки", "secondary"),
            ],
            [
                button("⬅️ Назад", "secondary"),
            ],
        ],
    }


# ============================================================
# BOOKING DATE PAGINATION
# ============================================================


def unique_training_dates(trainings):
    result = []

    seen = set()

    for training in trainings:
        value = training["training_date"]

        if value not in seen:
            seen.add(value)
            result.append(value)

    return result


def format_date_short(date_string):
    d = datetime.strptime(
        date_string,
        "%Y-%m-%d",
    ).date()

    return f"{WEEKDAYS_SHORT[d.weekday()]} {d.day:02d}.{d.month:02d}"


def format_date_long(date_string):
    d = datetime.strptime(
        date_string,
        "%Y-%m-%d",
    ).date()

    return (
        f"{WEEKDAYS[d.weekday()]}, "
        f"{d.day} {MONTHS[d.month]} {d.year}"
    )


def dates_keyboard(
    dates,
    category,
    page=0,
    back_label="⬅️ Назад",
):
    total_pages = max(
        1,
        (len(dates) + DATES_PER_PAGE - 1)
        // DATES_PER_PAGE,
    )

    page = max(
        0,
        min(page, total_pages - 1),
    )

    start = page * DATES_PER_PAGE
    page_dates = dates[
        start:start + DATES_PER_PAGE
    ]

    rows = []

    for date_string in page_dates:
        rows.append(
            [
                button(
                    format_date_short(date_string),
                    "primary",
                )
            ]
        )

    navigation = []

    if page > 0:
        navigation.append(
            button("◀️ Предыдущие", "secondary")
        )

    if page < total_pages - 1:
        navigation.append(
            button("Следующие ▶️", "secondary")
        )

    if navigation:
        rows.append(navigation)

    rows.append(
        [
            button(back_label, "secondary"),
        ]
    )

    return {
        "one_time": False,
        "buttons": rows,
    }


def parse_date_button(text):
    """
    Не используется для определения даты.
    Даты хранятся в памяти пользователя через state.
    Оставлено для совместимости.
    """
    return None


# ============================================================
# USER STATE
# ============================================================

USER_STATE = {}


def set_state(user_id, state, **data):
    USER_STATE[user_id] = {
        "state": state,
        **data,
    }


def get_state(user_id):
    return USER_STATE.get(
        user_id,
        {"state": "main"},
    )


def clear_state(user_id):
    USER_STATE.pop(user_id, None)


# ============================================================
# BOOKING FLOW
# ============================================================


def show_booking_categories(user_id):
    set_state(
        user_id,
        "booking_category",
    )

    send_message(
        user_id,
        "🏐 ЗАПИСЬ НА ТРЕНИРОВКУ\n\n"
        "Выберите категорию:",
        booking_category_keyboard(),
    )


def show_booking_dates(user_id, category, page=0):
    category = normalize_category(category)

    logger.info(
        "DIRECT BOOKING QUERY user=%s category=%s",
        user_id,
        category,
    )

    trainings = get_trainings_for_category(
        category=category,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=14),
    )

    logger.info(
        "DIRECT BOOKING RESULT category=%s count=%s",
        category,
        len(trainings),
    )

    dates = unique_training_dates(trainings)

    if not dates:
        send_message(
            user_id,
            f"{category_label(category)}\n\n"
            "На ближайшие 14 дней тренировок нет.",
            {
                "one_time": False,
                "buttons": [
                    [
                        button("⬅️ Назад", "secondary"),
                    ]
                ],
            },
        )
        return

    set_state(
        user_id,
        "booking_date",
        category=category,
        dates=dates,
        page=page,
    )

    total_pages = max(
        1,
        (len(dates) + DATES_PER_PAGE - 1)
        // DATES_PER_PAGE,
    )

    text = (
        f"{category_label(category)}\n\n"
        "Выберите дату тренировки:"
    )

    if total_pages > 1:
        text += f"\n\nСтраница {page + 1} из {total_pages}"

    send_message(
        user_id,
        text,
        dates_keyboard(
            dates,
            category,
            page,
        ),
    )


def show_booking_trainings(user_id, category, date_string):
    category = normalize_category(category)

    conn = db()

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
            "На выбранную дату тренировок не найдено.",
            {
                "one_time": False,
                "buttons": [
                    [
                        button("⬅️ Назад", "secondary"),
                    ]
                ],
            },
        )
        return

    set_state(
        user_id,
        "booking_training",
        category=category,
        date=date_string,
    )

    rows_buttons = []

    for training in rows:
        count = get_active_registration_count(
            training["id"]
        )

        label = (
            f"{training['start_time']}–"
            f"{training['end_time']} "
            f"({count}/{training['capacity']})"
        )

        rows_buttons.append(
            [
                button(label, "primary")
            ]
        )

    rows_buttons.append(
        [
            button("⬅️ К датам", "secondary"),
        ]
    )

    send_message(
        user_id,
        f"{category_label(category)}\n"
        f"📅 {format_date_long(date_string)}\n\n"
        "Выберите тренировку:",
        {
            "one_time": False,
            "buttons": rows_buttons,
        },
    )


def find_training_by_time_on_date(
    date_string,
    text,
    category,
):
    conn = db()

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
            normalize_category(category),
        ),
    ).fetchall()

    conn.close()

    for training in rows:
        label = (
            f"{training['start_time']}–"
            f"{training['end_time']}"
        )

        if text.startswith(label):
            return training

    return None


def show_training_details(user_id, training_id):
    training = get_training(training_id)

    if not training:
        send_message(
            user_id,
            "❌ Тренировка не найдена.",
        )
        return

    count = get_active_registration_count(
        training_id
    )

    participants = get_training_participants(
        training_id
    )

    lines = [
        f"🏐 Тренировка №{training['training_number']}",
        "",
        f"📅 {format_date_long(training['training_date'])}",
        f"⏰ {training['start_time']}–{training['end_time']}",
        f"👥 {category_label(training['category'])}",
        f"🎯 {training['title']}",
        f"📊 Уровень: {training['level']}",
        f"👤 Возраст: {training['age_group']}",
        f"🏖 Формат: {training['format']}",
        f"👨‍🏫 Тренер: {training['coach']}",
        f"📍 {training['location']}",
        f"💰 Стоимость: {training['price']} ₽",
        "",
        f"👥 Записано: {count}/{training['capacity']}",
    ]

    if participants:
        lines.append("")
        lines.append("Участники:")

        for index, person in enumerate(
            participants,
            start=1,
        ):
            name = (
                f"{person['first_name'] or ''} "
                f"{person['last_name'] or ''}"
            ).strip()

            if not name:
                name = "Участник"

            lines.append(
                f"{index}. {name}"
            )

    registration = get_registration(
        training_id,
        user_id,
    )

    if registration and registration["status"] == "registered":
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
                    button("⬅️ Назад", "secondary"),
                ],
            ],
        }
    elif count >= training["capacity"]:
        keyboard = {
            "one_time": False,
            "buttons": [
                [
                    button("⬅️ Назад", "secondary"),
                ]
            ],
        }
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
                    button("⬅️ Назад", "secondary"),
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
        "\n".join(lines),
        keyboard,
    )


# ============================================================
# MY TRAININGS
# ============================================================


def show_my_trainings(user_id):
    rows = get_user_upcoming_registrations(
        user_id
    )

    if not rows:
        send_message(
            user_id,
            "👤 МОИ ТРЕНИРОВКИ\n\n"
            "У вас пока нет предстоящих тренировок.",
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
        return

    lines = [
        "👤 МОИ ТРЕНИРОВКИ",
        "",
    ]

    buttons = []

    for training in rows:
        lines.append(
            f"🏐 №{training['training_number']} — "
            f"{format_date_long(training['training_date'])}"
        )

        lines.append(
            f"⏰ {training['start_time']}–"
            f"{training['end_time']}"
        )

        lines.append(
            f"🎯 {training['title']}"
        )

        lines.append("")

        buttons.append(
            [
                button(
                    f"№{training['training_number']} "
                    f"{training['start_time']}",
                    "primary",
                )
            ]
        )

    buttons.append(
        [
            button("⬅️ Назад", "secondary"),
        ]
    )

    set_state(
        user_id,
        "my_trainings",
    )

    send_message(
        user_id,
        "\n".join(lines),
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
        "Выберите категорию:",
        schedule_category_keyboard(),
    )


def show_schedule_dates(user_id, category, page=0):
    category = normalize_category(category)

    trainings = get_trainings_for_category(
        category=category,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=14),
    )

    dates = unique_training_dates(trainings)

    if not dates:
        send_message(
            user_id,
            "На ближайшие 14 дней тренировок нет.",
            {
                "one_time": False,
                "buttons": [
                    [
                        button(
                            "⬅️ Назад",
                            "secondary",
                        )
                    ]
                ],
            },
        )
        return

    set_state(
        user_id,
        "schedule_date",
        category=category,
        dates=dates,
        page=page,
    )

    send_message(
        user_id,
        f"📅 {category_label(category)}\n\n"
        "Выберите дату:",
        dates_keyboard(
            dates,
            category,
            page,
        ),
    )


def show_schedule_for_date(
    user_id,
    category,
    date_string,
):
    category = normalize_category(category)

    conn = db()

    rows = conn.execute(
        """
        SELECT *
        FROM trainings
        WHERE training_date=?
          AND status='active'
        """
        + (
            " AND category=? "
            if category in ("children", "adults")
            else " "
        )
        + """
        ORDER BY start_time, id
        """,
        (
            (
                date_string,
                category,
            )
            if category in ("children", "adults")
            else (date_string,)
        ),
    ).fetchall()

    conn.close()

    if not rows:
        send_message(
            user_id,
            "На эту дату тренировок нет.",
        )
        return

    lines = [
        f"📅 {format_date_long(date_string)}",
        "",
    ]

    for training in rows:
        count = get_active_registration_count(
            training["id"]
        )

        lines.extend(
            [
                f"🏐 Тренировка №{training['training_number']}",
                f"⏰ {training['start_time']}–{training['end_time']}",
                f"🎯 {training['title']}",
                f"👥 {count}/{training['capacity']}",
                f"💰 {training['price']} ₽",
                "",
            ]
        )

    buttons = []

    for training in rows:
        buttons.append(
            [
                button(
                    f"№{training['training_number']} "
                    f"{training['start_time']}",
                    "primary",
                )
            ]
        )

    buttons.append(
        [
            button("⬅️ К датам", "secondary"),
        ]
    )

    set_state(
        user_id,
        "schedule_training",
        category=category,
        date=date_string,
    )

    send_message(
        user_id,
        "\n".join(lines),
        {
            "one_time": False,
            "buttons": buttons,
        },
    )


# ============================================================
# ADMIN PANEL
# ============================================================


def admin_keyboard():
    return {
        "one_time": False,
        "buttons": [
            [
                button("📅 Расписание", "primary"),
                button("👥 Участники тренировок", "primary"),
            ],
            [
                button("➕ Создать тренировку", "primary"),
            ],
            [
                button("🏠 Главное меню", "secondary"),
            ],
        ],
    }


def show_admin_panel(user_id):
    if user_id not in ADMINS:
        send_main_menu(user_id)
        return

    set_state(
        user_id,
        "admin_panel",
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


def show_admin_schedule(user_id):
    if user_id not in ADMINS:
        return

    trainings = get_trainings_for_category(
        category=None,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=14),
    )

    if not trainings:
        send_message(
            user_id,
            "📅 На ближайшие 14 дней тренировок нет.",
            {
                "one_time": False,
                "buttons": [
                    [
                        button(
                            "⬅️ В админ-панель",
                            "secondary",
                        )
                    ]
                ],
            },
        )
        return

    dates = unique_training_dates(trainings)

    set_state(
        user_id,
        "admin_schedule_dates",
        dates=dates,
        page=0,
    )

    send_message(
        user_id,
        "📅 АДМИН — РАСПИСАНИЕ\n\n"
        "Выберите дату:",
        dates_keyboard(
            dates,
            "all",
            0,
            "⬅️ В админ-панель",
        ),
    )


def show_admin_schedule_date(
    user_id,
    date_string,
):
    if user_id not in ADMINS:
        return

    conn = db()

    rows = conn.execute(
        """
        SELECT *
        FROM trainings
        WHERE training_date=?
        ORDER BY start_time, id
        """,
        (date_string,),
    ).fetchall()

    conn.close()

    if not rows:
        send_message(
            user_id,
            "На эту дату тренировок нет.",
        )
        return

    lines = [
        f"📅 {format_date_long(date_string)}",
        "",
    ]

    buttons = []

    for training in rows:
        count = get_active_registration_count(
            training["id"]
        )

        lines.append(
            f"№{training['training_number']} "
            f"{training['start_time']}–"
            f"{training['end_time']} — "
            f"{training['title']} — "
            f"{count}/{training['capacity']}"
        )

        buttons.append(
            [
                button(
                    f"№{training['training_number']} "
                    f"{training['start_time']}",
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
        "admin_schedule_training",
        date=date_string,
    )

    send_message(
        user_id,
        "\n".join(lines),
        {
            "one_time": False,
            "buttons": buttons,
        },
    )


# ============================================================
# ADMIN PARTICIPANTS
# ============================================================


def show_admin_participants(user_id, page=0):
    if user_id not in ADMINS:
        return

    trainings = get_trainings_for_category(
        category=None,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=14),
    )

    if not trainings:
        send_message(
            user_id,
            "На ближайшие 14 дней тренировок нет.",
            {
                "one_time": False,
                "buttons": [
                    [
                        button(
                            "⬅️ В админ-панель",
                            "secondary",
                        )
                    ]
                ],
            },
        )
        return

    total_pages = max(
        1,
        (len(trainings) + TRAININGS_PER_PAGE - 1)
        // TRAININGS_PER_PAGE,
    )

    page = max(
        0,
        min(page, total_pages - 1),
    )

    start = page * TRAININGS_PER_PAGE

    page_trainings = trainings[
        start:start + TRAININGS_PER_PAGE
    ]

    buttons = []

    for training in page_trainings:
        count = get_active_registration_count(
            training["id"]
        )

        label = (
            f"№{training['training_number']} "
            f"{format_date_short(training['training_date'])} "
            f"{training['start_time']} "
            f"({count})"
        )

        buttons.append(
            [
                button(label, "primary")
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
                "Вперёд ▶️",
                "secondary",
            )
        )

    if navigation:
        buttons.append(navigation)

    buttons.append(
        [
            button(
                "⬅️ В админ-панель",
                "secondary",
            )
        ]
    )

    set_state(
        user_id,
        "admin_participants",
        trainings=[dict(x) for x in trainings],
        page=page,
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


def show_admin_training_participants(
    user_id,
    training_id,
):
    if user_id not in ADMINS:
        return

    training = get_training(training_id)

    if not training:
        send_message(
            user_id,
            "Тренировка не найдена.",
        )
        return

    participants = get_training_participants(
        training_id
    )

    lines = [
        f"👥 Тренировка №{training['training_number']}",
        "",
        f"📅 {format_date_long(training['training_date'])}",
        f"⏰ {training['start_time']}–{training['end_time']}",
        f"🎯 {training['title']}",
        "",
        f"Записано: {len(participants)}/{training['capacity']}",
        "",
    ]

    if not participants:
        lines.append(
            "Пока никто не записан."
        )
    else:
        for index, participant in enumerate(
            participants,
            start=1,
        ):
            name = (
                f"{participant['first_name'] or ''} "
                f"{participant['last_name'] or ''}"
            ).strip()

            if not name:
                name = "Без имени"

            lines.append(
                f"{index}. {name}"
            )

    send_message(
        user_id,
        "\n".join(lines),
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

    set_state(
        user_id,
        "admin_training_participants",
        training_id=training_id,
    )


# ============================================================
# ADMIN CREATE TRAINING
# ============================================================


def show_admin_create_training(user_id):
    if user_id not in ADMINS:
        return

    set_state(
        user_id,
        "admin_create_date",
    )

    send_message(
        user_id,
        "➕ СОЗДАНИЕ ТРЕНИРОВКИ\n\n"
        "Введите дату в формате:\n"
        "ДД.ММ.ГГГГ\n\n"
        "Например: 10.10.2026",
        {
            "one_time": False,
            "buttons": [
                [
                    button(
                        "⬅️ В админ-панель",
                        "secondary",
                    )
                ]
            ],
        },
    )


def create_admin_training_date(
    user_id,
    text,
):
    try:
        d = datetime.strptime(
            text.strip(),
            "%d.%m.%Y",
        ).date()

    except ValueError:
        send_message(
            user_id,
            "❌ Неверный формат даты.\n\n"
            "Используйте ДД.ММ.ГГГГ",
        )
        return

    set_state(
        user_id,
        "admin_create_time",
        training_date=d.strftime("%Y-%m-%d"),
    )

    send_message(
        user_id,
        "Введите время в формате:\n"
        "17:00-19:00",
        {
            "one_time": False,
            "buttons": [
                [
                    button(
                        "⬅️ В админ-панель",
                        "secondary",
                    )
                ]
            ],
        },
    )


def create_admin_training_time(
    user_id,
    text,
):
    try:
        parts = text.strip().split("-")

        if len(parts) != 2:
            raise ValueError

        start_time = parts[0].strip()
        end_time = parts[1].strip()

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
            "❌ Неверный формат времени.\n\n"
            "Пример: 17:00-19:00",
        )
        return

    state = get_state(user_id)

    set_state(
        user_id,
        "admin_create_category",
        training_date=state["training_date"],
        start_time=start_time,
        end_time=end_time,
    )

    send_message(
        user_id,
        "Выберите категорию:",
        {
            "one_time": False,
            "buttons": [
                [
                    button("👧 Дети", "primary"),
                    button("🧑 Взрослые", "primary"),
                ],
                [
                    button(
                        "⬅️ В админ-панель",
                        "secondary",
                    )
                ],
            ],
        },
    )


def create_admin_training_category(
    user_id,
    category,
):
    category = normalize_category(category)

    state = get_state(user_id)

    set_state(
        user_id,
        "admin_create_title",
        training_date=state["training_date"],
        start_time=state["start_time"],
        end_time=state["end_time"],
        category=category,
    )

    send_message(
        user_id,
        "Введите название тренировки:",
    )


def create_admin_training_title(
    user_id,
    title,
):
    state = get_state(user_id)

    set_state(
        user_id,
        "admin_create_capacity",
        **state,
        title=title.strip(),
    )

    send_message(
        user_id,
        "Введите максимальное количество участников:",
    )


def create_admin_training_capacity(
    user_id,
    text,
):
    try:
        capacity = int(text.strip())

        if capacity < 1:
            raise ValueError

    except ValueError:
        send_message(
            user_id,
            "❌ Введите целое число больше 0.",
        )
        return

    state = get_state(user_id)

    set_state(
        user_id,
        "admin_create_price",
        **state,
        capacity=capacity,
    )

    send_message(
        user_id,
        "Введите стоимость тренировки в рублях:",
    )


def create_admin_training_price(
    user_id,
    text,
):
    try:
        price = int(
            text.strip().replace("₽", "")
        )

        if price < 0:
            raise ValueError

    except ValueError:
        send_message(
            user_id,
            "❌ Введите стоимость числом.",
        )
        return

    state = get_state(user_id)

    conn = db()

    training_id = create_training(
        conn=conn,
        training_date=state["training_date"],
        start_time=state["start_time"],
        end_time=state["end_time"],
        title=state["title"],
        category=state["category"],
        age_group=(
            "9–14 лет"
            if state["category"] == "children"
            else "18+"
        ),
        level="Общий",
        training_format="Группа",
        coach="Алексей",
        capacity=state["capacity"],
        price=price,
    )

    conn.commit()
    conn.close()

    training = get_training(training_id)

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
        "✅ Тренировка создана!\n\n"
        f"🏐 №{training['training_number']}\n"
        f"📅 {format_date_long(training['training_date'])}\n"
        f"⏰ {training['start_time']}–{training['end_time']}\n"
        f"🎯 {training['title']}\n"
        f"{category_label(training['category'])}\n"
        f"👥 До {training['capacity']} человек\n"
        f"💰 {training['price']} ₽",
        admin_keyboard(),
    )


# ============================================================
# STATIC PAGES
# ============================================================


def show_prices(user_id):
    send_message(
        user_id,
        "💰 ЦЕНЫ VOLLEY WAVE\n\n"
        "👧 Дети — 600 ₽ за тренировку\n\n"
        "🧑 Взрослые:\n"
        "1–6 человек — 1200 ₽/человек\n"
        "7+ человек — 1000 ₽/человек\n\n"
        "Минимальная группа взрослых — 4 человека.",
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


def show_locations(user_id):
    send_message(
        user_id,
        "📍 ГДЕ ТРЕНИРУЕМСЯ\n\n"
        "❄️ Зимой:\n"
        f"{WINTER_LOCATION}\n\n"
        "☀️ В тёплое время года:\n"
        f"{SUMMER_LOCATION}",
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


def show_individual(user_id):
    send_message(
        user_id,
        "🎯 ИНДИВИДУАЛЬНАЯ ТРЕНИРОВКА\n\n"
        "Индивидуальная тренировка под вашу "
        "задачу: техника, приём, защита, атака, "
        "подача, блок или игровая подготовка.\n\n"
        "Чтобы договориться о времени, "
        "напишите администратору.",
        {
            "one_time": False,
            "buttons": [
                [
                    button(
                        "⬅️ Назад",
                        "secondary",
                    )
                ]
            ],
        },
    )


def show_question(user_id):
    send_message(
        user_id,
        "❓ ЗАДАТЬ ВОПРОС\n\n"
        "Напишите свой вопрос следующим сообщением. "
        "Мы ответим вам.",
        {
            "one_time": False,
            "buttons": [
                [
                    button(
                        "⬅️ Назад",
                        "secondary",
                    )
                ]
            ],
        },
    )

    set_state(
        user_id,
        "question",
    )


# ============================================================
# MESSAGE HANDLERS
# ============================================================


def handle_text(user_id, text):
    text = (text or "").strip()

    ensure_user(user_id)

    logger.info(
        "MESSAGE user=%s text=%r",
        user_id,
        text,
    )

    state = get_state(user_id)
    state_name = state.get("state")

    # --------------------------------------------------------
    # MAIN MENU
    # --------------------------------------------------------

    if text in {
        "Начать",
        "Старт",
        "start",
        "/start",
        "🏠 Главное меню",
    }:
        clear_state(user_id)
        send_main_menu(user_id)
        return

    # --------------------------------------------------------
    # ADMIN PANEL
    # --------------------------------------------------------

    if text == "⚙️ Админ-панель":
        if user_id in ADMINS:
            show_admin_panel(user_id)
        else:
            send_main_menu(user_id)
        return

    # --------------------------------------------------------
    # BOOKING ENTRY
    # --------------------------------------------------------

    if text == "🏐 Записаться":
        show_booking_categories(user_id)
        return

    # --------------------------------------------------------
    # BOOKING CATEGORY
    # --------------------------------------------------------

    if text == "👧 Дети":
        logger.info(
            "BOOKING CATEGORY CHILDREN user=%s",
            user_id,
        )

        show_booking_dates(
            user_id,
            "children",
            0,
        )
        return

    if text == "🧑 Взрослые":
        logger.info(
            "BOOKING CATEGORY ADULTS user=%s",
            user_id,
        )

        show_booking_dates(
            user_id,
            "adults",
            0,
        )
        return

    # --------------------------------------------------------
    # BOOKING DATE NAVIGATION
    # --------------------------------------------------------

    if state_name == "booking_date":
        category = state.get("category")
        dates = state.get("dates", [])
        page = int(state.get("page", 0))

        if text == "◀️ Предыдущие":
            show_booking_dates(
                user_id,
                category,
                page - 1,
            )
            return

        if text == "Следующие ▶️":
            show_booking_dates(
                user_id,
                category,
                page + 1,
            )
            return

        if text == "⬅️ Назад":
            show_booking_categories(user_id)
            return

        # Проверяем конкретную дату.
        for date_string in dates:
            if text == format_date_short(date_string):
                show_booking_trainings(
                    user_id,
                    category,
                    date_string,
                )
                return

    # --------------------------------------------------------
    # BOOKING TRAINING
    # --------------------------------------------------------

    if state_name == "booking_training":
        category = state.get("category")
        date_string = state.get("date")

        if text == "⬅️ К датам":
            show_booking_dates(
                user_id,
                category,
                0,
            )
            return

        training = find_training_by_time_on_date(
            date_string,
            text,
            category,
        )

        if training:
            show_training_details(
                user_id,
                training["id"],
            )
            return

    # --------------------------------------------------------
    # TRAINING DETAILS
    # --------------------------------------------------------

    if state_name == "training_details":
        training_id = state.get("training_id")

        if text == "⬅️ Назад":
            training = get_training(training_id)

            if training:
                show_booking_trainings(
                    user_id,
                    training["category"],
                    training["training_date"],
                )
            else:
                show_booking_categories(user_id)

            return

        if text == "✅ Записаться":
            ok, result = add_registration(
                training_id,
                user_id,
            )

            if result == "ok":
                training = get_training(
                    training_id
                )

                admin_log(
                    user_id,
                    "registration",
                    "training",
                    training_id,
                )

                send_message(
                    user_id,
                    "✅ Вы успешно записаны!\n\n"
                    f"🏐 Тренировка №{training['training_number']}\n"
                    f"📅 {format_date_long(training['training_date'])}\n"
                    f"⏰ {training['start_time']}–"
                    f"{training['end_time']}\n"
                    f"💰 {training['price']} ₽",
                    {
                        "one_time": False,
                        "buttons": [
                            [
                                button(
                                    "👤 Мои тренировки",
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

            elif result == "already":
                send_message(
                    user_id,
                    "Вы уже записаны на эту тренировку.",
                )

            elif result == "full":
                send_message(
                    user_id,
                    "❌ Группа уже заполнена.",
                )

            elif result == "cancelled":
                send_message(
                    user_id,
                    "❌ Эта тренировка отменена.",
                )

            else:
                send_message(
                    user_id,
                    "❌ Не удалось записаться.",
                )

            return

        if text == "❌ Отменить запись":
            ok, result = cancel_registration(
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
                    "❌ Отменить запись можно не позднее "
                    "чем за 24 часа до тренировки.",
                )

            else:
                send_message(
                    user_id,
                    "❌ Активная запись не найдена.",
                )

            return

    # --------------------------------------------------------
    # MY TRAININGS
    # --------------------------------------------------------

    if text == "👤 Мои тренировки":
        show_my_trainings(user_id)
        return

    # --------------------------------------------------------
    # PRICES / LOCATION / INDIVIDUAL / QUESTION
    # --------------------------------------------------------

    if text == "💰 Цены":
        show_prices(user_id)
        return

    if text == "📍 Где тренируемся":
        show_locations(user_id)
        return

    if text == "🎯 Индивидуальная тренировка":
        show_individual(user_id)
        return

    if text == "❓ Задать вопрос":
        show_question(user_id)
        return

    # --------------------------------------------------------
    # SCHEDULE
    # --------------------------------------------------------

    if text == "📅 Расписание":
        show_schedule_categories(user_id)
        return

    if state_name == "schedule_category":
        if text == "👧 Дети":
            show_schedule_dates(
                user_id,
                "children",
                0,
            )
            return

        if text == "🧑 Взрослые":
            show_schedule_dates(
                user_id,
                "adults",
                0,
            )
            return

        if text == "🏠 Все тренировки":
            show_schedule_dates(
                user_id,
                "all",
                0,
            )
            return

        if text == "⬅️ Назад":
            send_main_menu(user_id)
            return

    if state_name == "schedule_date":
        category = state.get("category")
        dates = state.get("dates", [])
        page = int(state.get("page", 0))

        if text == "◀️ Предыдущие":
            show_schedule_dates(
                user_id,
                category,
                page - 1,
            )
            return

        if text == "Следующие ▶️":
            show_schedule_dates(
                user_id,
                category,
                page + 1,
            )
            return

        if text == "⬅️ Назад":
            show_schedule_categories(user_id)
            return

        for date_string in dates:
            if text == format_date_short(date_string):
                show_schedule_for_date(
                    user_id,
                    category,
                    date_string,
                )
                return

    # --------------------------------------------------------
    # ADMIN SCHEDULE
    # --------------------------------------------------------

    if user_id in ADMINS:

        if text == "📅 Расписание" and state_name == "admin_panel":
            show_admin_schedule(user_id)
            return

        if state_name == "admin_schedule_dates":

            dates = state.get("dates", [])
            page = int(state.get("page", 0))

            if text == "◀️ Предыдущие":
                show_admin_schedule_dates(
                    user_id,
                    page - 1,
                )
                return

            if text == "Следующие ▶️":
                show_admin_schedule_dates(
                    user_id,
                    page + 1,
                )
                return

            if text == "⬅️ В админ-панель":
                show_admin_panel(user_id)
                return

            for date_string in dates:
                if text == format_date_short(date_string):
                    show_admin_schedule_date(
                        user_id,
                        date_string,
                    )
                    return

        if state_name == "admin_schedule_training":
            if text == "⬅️ К датам":
                show_admin_schedule(user_id)
                return

            if text.startswith("№"):
                number_text = text.split()[0]

                try:
                    number = int(
                        number_text.replace(
                            "№",
                            "",
                        )
                    )
                except ValueError:
                    number = None

                if number:
                    training = get_training_by_number(
                        number
                    )

                    if training:
                        show_admin_training_participants(
                            user_id,
                            training["id"],
                        )
                        return

        # ----------------------------------------------------
        # ADMIN PARTICIPANTS
        # ----------------------------------------------------

        if (
            text == "👥 Участники тренировок"
            and state_name == "admin_panel"
        ):
            show_admin_participants(
                user_id,
                0,
            )
            return

        if state_name == "admin_participants":

            page = int(
                state.get("page", 0)
            )

            if text == "◀️ Назад":
                show_admin_participants(
                    user_id,
                    page - 1,
                )
                return

            if text == "Вперёд ▶️":
                show_admin_participants(
                    user_id,
                    page + 1,
                )
                return

            if text == "⬅️ В админ-панель":
                show_admin_panel(user_id)
                return

            if text.startswith("№"):
                number_text = text.split()[0]

                try:
                    number = int(
                        number_text.replace(
                            "№",
                            "",
                        )
                    )
                except ValueError:
                    number = None

                if number:
                    training = get_training_by_number(
                        number
                    )

                    if training:
                        show_admin_training_participants(
                            user_id,
                            training["id"],
                        )
                        return

        # ----------------------------------------------------
        # ADMIN CREATE
        # ----------------------------------------------------

        if (
            text == "➕ Создать тренировку"
            and state_name == "admin_panel"
        ):
            show_admin_create_training(user_id)
            return

        if state_name == "admin_create_date":
            if text == "⬅️ В админ-панель":
                show_admin_panel(user_id)
                return

            create_admin_training_date(
                user_id,
                text,
            )
            return

        if state_name == "admin_create_time":
            if text == "⬅️ В админ-панель":
                show_admin_panel(user_id)
                return

            create_admin_training_time(
                user_id,
                text,
            )
            return

        if state_name == "admin_create_category":
            if text == "👧 Дети":
                create_admin_training_category(
                    user_id,
                    "children",
                )
                return

            if text == "🧑 Взрослые":
                create_admin_training_category(
                    user_id,
                    "adults",
                )
                return

            if text == "⬅️ В админ-панель":
                show_admin_panel(user_id)
                return

        if state_name == "admin_create_title":
            create_admin_training_title(
                user_id,
                text,
            )
            return

        if state_name == "admin_create_capacity":
            create_admin_training_capacity(
                user_id,
                text,
            )
            return

        if state_name == "admin_create_price":
            create_admin_training_price(
                user_id,
                text,
            )
            return

    # --------------------------------------------------------
    # QUESTION
    # --------------------------------------------------------

    if state_name == "question":
        if text == "⬅️ Назад":
            clear_state(user_id)
            send_main_menu(user_id)
            return

        send_message(
            user_id,
            "Спасибо! Вопрос получен.\n\n"
            "Администратор ответит вам.",
            main_keyboard(user_id),
        )

        clear_state(user_id)
        return

    # --------------------------------------------------------
    # FALLBACK
    # --------------------------------------------------------

    send_main_menu(
        user_id,
        "Не совсем понял команду.\n\n"
        "Выберите действие:",
    )


# ============================================================
# ADMIN SCHEDULE PAGINATION HELPER
# ============================================================


def show_admin_schedule_dates(
    user_id,
    page=0,
):
    if user_id not in ADMINS:
        return

    trainings = get_trainings_for_category(
        category=None,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=14),
    )

    dates = unique_training_dates(trainings)

    if not dates:
        send_message(
            user_id,
            "На ближайшие 14 дней тренировок нет.",
        )
        return

    total_pages = max(
        1,
        (len(dates) + DATES_PER_PAGE - 1)
        // DATES_PER_PAGE,
    )

    page = max(
        0,
        min(page, total_pages - 1),
    )

    set_state(
        user_id,
        "admin_schedule_dates",
        dates=dates,
        page=page,
    )

    keyboard = dates_keyboard(
        dates,
        "all",
        page,
        "⬅️ В админ-панель",
    )

    send_message(
        user_id,
        "📅 АДМИН — РАСПИСАНИЕ\n\n"
        f"Страница {page + 1} из {total_pages}\n"
        "Выберите дату:",
        keyboard,
    )


# ============================================================
# VK CALLBACK
# ============================================================


@app.route("/callback", methods=["POST"])
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

        event_type = data.get("type")

        # -----------------------------------------------
        # CONFIRMATION
        # -----------------------------------------------

        if event_type == "confirmation":
            return (
                VK_CONFIRMATION_TOKEN or "",
                200,
                {"Content-Type": "text/plain"},
            )

        # -----------------------------------------------
        # SECRET CHECK
        # -----------------------------------------------

        if VK_SECRET_KEY:
            received_secret = data.get(
                "secret"
            )

            if received_secret != VK_SECRET_KEY:
                logger.warning(
                    "Invalid secret key"
                )
                return "invalid secret", 403

        # -----------------------------------------------
        # MESSAGE NEW
        # -----------------------------------------------

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

                ensure_user(user_id)

                handle_text(
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

        # VK должен получить HTTP 200,
        # иначе начнёт повторно отправлять событие.
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
        "Database initialized"
    )

    generate_trainings(
        weeks=6
    )

    # Проверяем количество ближайших тренировок.
    trainings = get_trainings_for_category(
        category=None,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=14),
    )

    logger.info(
        "Upcoming trainings in DB: %s",
        len(trainings),
    )

    if trainings:
        first = trainings[0]

        logger.info(
            "First upcoming training: №%s %s %s",
            first["training_number"],
            first["training_date"],
            first["start_time"],
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
