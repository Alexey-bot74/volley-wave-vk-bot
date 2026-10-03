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
    148372158,
    172892670,
}

DB_PATH = "volley_wave.db"

PARTICIPANTS_PAGE_SIZE = 8
SCHEDULE_DAYS = 14
GENERATION_WEEKS = 6


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)


# ============================================================
# FLASK
# ============================================================

app = Flask(__name__)


# ============================================================
# WEEKDAYS
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

WEEKDAYS_SHORT = {
    0: "Пн",
    1: "Вт",
    2: "Ср",
    3: "Чт",
    4: "Пт",
    5: "Сб",
    6: "Вс",
}


# ============================================================
# USER STATES
# ============================================================

USER_STATES = {}


def set_state(user_id, state, data=None):
    USER_STATES[user_id] = {
        "state": state,
        "data": data or {}
    }


def get_state(user_id):
    return USER_STATES.get(
        user_id,
        {
            "state": None,
            "data": {}
        }
    )


def clear_state(user_id):
    USER_STATES.pop(user_id, None)


# ============================================================
# DATABASE
# ============================================================

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()

    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vk_id INTEGER UNIQUE NOT NULL,
                first_name TEXT,
                last_name TEXT,
                phone TEXT,
                is_blocked INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS training_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                weekday INTEGER NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                age_group TEXT,
                level TEXT,
                format TEXT,
                coach TEXT,
                capacity INTEGER DEFAULT 10,
                price INTEGER DEFAULT 0,
                location TEXT,
                active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS trainings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                training_number INTEGER UNIQUE,
                training_date TEXT NOT NULL,
                weekday TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
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
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                training_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                status TEXT DEFAULT 'active',
                registered_at TEXT DEFAULT CURRENT_TIMESTAMP,
                cancelled_at TEXT,
                cancellation_reason TEXT,
                UNIQUE(training_id, user_id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS waitlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                training_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                position INTEGER,
                status TEXT DEFAULT 'waiting',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(training_id, user_id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                registration_id INTEGER NOT NULL,
                status TEXT,
                marked_by INTEGER,
                marked_at TEXT,
                comment TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                training_id INTEGER,
                amount INTEGER,
                status TEXT,
                payment_method TEXT,
                external_id TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS admin_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_vk_id INTEGER NOT NULL,
                action TEXT,
                entity_type TEXT,
                entity_id INTEGER,
                details TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                training_id INTEGER,
                notification_type TEXT,
                scheduled_for TEXT,
                sent_at TEXT,
                status TEXT
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_trainings_date
            ON trainings(training_date)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_registrations_training
            ON registrations(training_id)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_registrations_user
            ON registrations(user_id)
        """)

        conn.commit()

    finally:
        conn.close()

    logger.info("Database initialized")


# ============================================================
# DEFAULT TRAINING TEMPLATES
# ============================================================

DEFAULT_TEMPLATES = [
    # MONDAY
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
        "level": "Любой",
        "format": "Группа",
        "coach": "Алексей",
        "capacity": 10,
        "price": 1200,
    },

    # TUESDAY
    {
        "weekday": 1,
        "start_time": "09:00",
        "end_time": "11:00",
        "title": "Взрослая тренировка",
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

    # WEDNESDAY
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
        "title": "Детская тренировка 5–9 лет",
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
        "title": "Взрослая тренировка",
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

    # THURSDAY
    {
        "weekday": 3,
        "start_time": "09:00",
        "end_time": "11:00",
        "title": "Взрослая тренировка",
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
        "title": "Взрослая тренировка",
        "category": "adults",
        "age_group": "18+",
        "level": "Средний",
        "format": "Группа",
        "coach": "Алексей",
        "capacity": 8,
        "price": 1200,
    },

    # FRIDAY
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
        "title": "Детская тренировка 5–10 лет",
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
        "level": "Любой",
        "format": "Группа",
        "coach": "Алексей",
        "capacity": 10,
        "price": 1200,
    },
]


# ============================================================
# VK API
# ============================================================

def vk_api(method, **params):
    if not VK_TOKEN:
        logger.error("VK_TOKEN is missing")
        return None

    params["access_token"] = VK_TOKEN
    params["v"] = VK_API_VERSION

    try:
        response = requests.post(
            f"https://api.vk.com/method/{method}",
            data=params,
            timeout=15
        )

        result = response.json()

        if "error" in result:
            logger.error(
                "VK API error in %s:\n%s",
                method,
                result
            )
            return None

        return result.get("response")

    except Exception as exc:
        logger.exception(
            "VK API request failed: %s",
            exc
        )
        return None


def send_message(user_id, message, keyboard=None):
    params = {
        "user_id": user_id,
        "random_id": 0,
        "message": message,
    }

    if keyboard is not None:
        params["keyboard"] = json.dumps(
            keyboard,
            ensure_ascii=False
        )

    return vk_api("messages.send", **params)


# ============================================================
# KEYBOARD
# ============================================================

def button(label, color="secondary"):
    return {
        "action": {
            "type": "text",
            "label": label
        },
        "color": color
    }


def main_keyboard(user_id):
    rows = [
        [
            button("🏐 Записаться", "primary"),
            button("📅 Расписание", "primary"),
        ],
        [
            button("👤 Мои тренировки", "primary"),
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
        rows.append([
            button("⚙️ Админ-панель", "positive")
        ])

    return {
        "one_time": False,
        "buttons": rows
    }


def admin_keyboard():
    return {
        "one_time": False,
        "buttons": [
            [
                button("📅 Расписание", "primary"),
                button("👥 Участники тренировок", "primary"),
            ],
            [
                button("➕ Создать тренировку", "positive"),
            ],
            [
                button("🏠 Главное меню", "secondary"),
            ],
        ]
    }


# ============================================================
# USERS
# ============================================================

def save_user(user_id):
    response = vk_api(
        "users.get",
        user_ids=user_id,
        fields=""
    )

    first_name = ""
    last_name = ""

    if response:
        first_name = response[0].get("first_name", "")
        last_name = response[0].get("last_name", "")

    conn = get_connection()

    try:
        conn.execute(
            """
            INSERT INTO users (
                vk_id,
                first_name,
                last_name
            )
            VALUES (?, ?, ?)
            ON CONFLICT(vk_id)
            DO UPDATE SET
                first_name = excluded.first_name,
                last_name = excluded.last_name,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                user_id,
                first_name,
                last_name
            )
        )

        conn.commit()

    except Exception:
        logger.exception("Failed to save user")

    finally:
        conn.close()


def is_blocked(user_id):
    conn = get_connection()

    try:
        row = conn.execute(
            """
            SELECT is_blocked
            FROM users
            WHERE vk_id = ?
            """,
            (user_id,)
        ).fetchone()

        return bool(row and row["is_blocked"])

    finally:
        conn.close()


# ============================================================
# TEMPLATES
# ============================================================

def ensure_default_templates():
    conn = get_connection()

    try:
        count = conn.execute(
            "SELECT COUNT(*) AS count FROM training_templates"
        ).fetchone()["count"]

        if count > 0:
            return

        logger.info("Creating default training templates...")

        for item in DEFAULT_TEMPLATES:
            conn.execute(
                """
                INSERT INTO training_templates (
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
                    active
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    item["weekday"],
                    item["start_time"],
                    item["end_time"],
                    item["title"],
                    item["category"],
                    item["age_group"],
                    item["level"],
                    item["format"],
                    item["coach"],
                    item["capacity"],
                    item["price"],
                    "СК «Арена», ул. Молодогвардейцев, 7",
                )
            )

        conn.commit()

        logger.info(
            "Default templates created: %s",
            len(DEFAULT_TEMPLATES)
        )

    except Exception:
        conn.rollback()
        logger.exception("Template initialization failed")

    finally:
        conn.close()


# ============================================================
# TRAINING GENERATION
# ============================================================

def next_training_number(conn):
    row = conn.execute(
        """
        SELECT COALESCE(MAX(training_number), 0) + 1 AS next_number
        FROM trainings
        """
    ).fetchone()

    return row["next_number"]


def create_training_directly(
    training_date,
    template
):
    conn = get_connection()

    try:
        existing = conn.execute(
            """
            SELECT id
            FROM trainings
            WHERE training_date = ?
              AND start_time = ?
              AND end_time = ?
              AND title = ?
              AND category = ?
              AND age_group = ?
            LIMIT 1
            """,
            (
                training_date.isoformat(),
                template["start_time"],
                template["end_time"],
                template["title"],
                template["category"],
                template["age_group"],
            )
        ).fetchone()

        if existing:
            return False

        number = next_training_number(conn)

        location = (
            "СК «Арена», ул. Молодогвардейцев, 7"
        )

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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                number,
                training_date.isoformat(),
                WEEKDAYS[training_date.weekday()],
                template["start_time"],
                template["end_time"],
                template["title"],
                template["category"],
                template["age_group"],
                template["level"],
                template["format"],
                template["coach"],
                template["capacity"],
                template["price"],
                location,
                template.get("id"),
            )
        )

        conn.commit()
        return True

    except Exception:
        conn.rollback()

        logger.exception(
            "Failed to create training %s %s",
            training_date,
            template.get("title")
        )

        return False

    finally:
        conn.close()


def generate_default_trainings(weeks=6):
    created = 0

    today = date.today()
    end_date = today + timedelta(days=weeks * 7)

    current = today

    while current <= end_date:
        for template in DEFAULT_TEMPLATES:
            if template["weekday"] != current.weekday():
                continue

            if create_training_directly(
                current,
                template
            ):
                created += 1

        current += timedelta(days=1)

    logger.info(
        "Training generation complete. Created: %s",
        created
    )

    return created


def ensure_schedule():
    logger.info("Checking training schedule...")

    ensure_default_templates()

    created = generate_default_trainings(
        GENERATION_WEEKS
    )

    logger.info(
        "Schedule check finished. Created %s new trainings.",
        created
    )

    conn = get_connection()

    try:
        row = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM trainings
            WHERE training_date >= ?
              AND status != 'cancelled'
            """,
            (date.today().isoformat(),)
        ).fetchone()

        count = row["count"]

        logger.info(
            "Upcoming trainings in DB: %s",
            count
        )

        first = conn.execute(
            """
            SELECT training_number, training_date, start_time
            FROM trainings
            WHERE training_date >= ?
              AND status != 'cancelled'
            ORDER BY training_date, start_time
            LIMIT 1
            """,
            (date.today().isoformat(),)
        ).fetchone()

        if first:
            logger.info(
                "First upcoming training: №%s %s %s",
                first["training_number"],
                first["training_date"],
                first["start_time"]
            )

    finally:
        conn.close()


# ============================================================
# TRAININGS
# ============================================================

def get_training(training_id):
    conn = get_connection()

    try:
        row = conn.execute(
            """
            SELECT *
            FROM trainings
            WHERE id = ?
            """,
            (training_id,)
        ).fetchone()

        return dict(row) if row else None

    finally:
        conn.close()


def get_training_by_number(number):
    conn = get_connection()

    try:
        row = conn.execute(
            """
            SELECT *
            FROM trainings
            WHERE training_number = ?
            """,
            (number,)
        ).fetchone()

        return dict(row) if row else None

    finally:
        conn.close()


def get_schedule_direct(
    category="all",
    days=SCHEDULE_DAYS
):
    today = date.today()
    end_date = today + timedelta(days=days)

    conn = get_connection()

    try:
        params = [
            today.isoformat(),
            end_date.isoformat()
        ]

        query = """
            SELECT *
            FROM trainings
            WHERE training_date >= ?
              AND training_date <= ?
              AND status != 'cancelled'
        """

        if category == "children":
            query += """
                AND LOWER(category) = 'children'
            """

        elif category == "adults":
            query += """
                AND LOWER(category) = 'adults'
            """

        query += """
            ORDER BY training_date, start_time, id
        """

        rows = conn.execute(
            query,
            params
        ).fetchall()

        result = [dict(row) for row in rows]

        logger.info(
            "DIRECT SCHEDULE QUERY from=%s to=%s category=%s",
            today.isoformat(),
            end_date.isoformat(),
            category
        )

        logger.info(
            "DIRECT SCHEDULE RESULT category=%s count=%s",
            category,
            len(result)
        )

        return result

    finally:
        conn.close()


# ============================================================
# REGISTRATIONS
# ============================================================

def get_registration_count(training_id):
    conn = get_connection()

    try:
        row = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM registrations
            WHERE training_id = ?
              AND status = 'active'
            """,
            (training_id,)
        ).fetchone()

        return row["count"]

    finally:
        conn.close()


def get_registration(training_id, user_id):
    conn = get_connection()

    try:
        row = conn.execute(
            """
            SELECT *
            FROM registrations
            WHERE training_id = ?
              AND user_id = ?
              AND status = 'active'
            """,
            (
                training_id,
                user_id
            )
        ).fetchone()

        return dict(row) if row else None

    finally:
        conn.close()


def add_registration(training_id, user_id):
    training = get_training(training_id)

    if not training:
        return False, "Тренировка не найдена."

    if training["status"] != "active":
        return False, "Эта тренировка недоступна для записи."

    existing = get_registration(
        training_id,
        user_id
    )

    if existing:
        return False, "Вы уже записаны на эту тренировку."

    count = get_registration_count(training_id)

    if count >= training["capacity"]:
        return False, "Мест на тренировке больше нет."

    conn = get_connection()

    try:
        conn.execute(
            """
            INSERT INTO registrations (
                training_id,
                user_id,
                status
            )
            VALUES (?, ?, 'active')
            """,
            (
                training_id,
                user_id
            )
        )

        conn.commit()

        return True, "Вы успешно записаны!"

    except sqlite3.IntegrityError:
        return False, "Вы уже записаны на эту тренировку."

    except Exception:
        conn.rollback()
        logger.exception("Registration error")
        return False, "Не удалось записаться."

    finally:
        conn.close()


def get_user_registrations(user_id):
    conn = get_connection()

    try:
        rows = conn.execute(
            """
            SELECT
                r.*,
                t.training_number,
                t.training_date,
                t.weekday,
                t.start_time,
                t.end_time,
                t.title,
                t.category,
                t.age_group,
                t.level,
                t.format,
                t.coach,
                t.capacity,
                t.price,
                t.location,
                t.status AS training_status
            FROM registrations r
            JOIN trainings t
                ON t.id = r.training_id
            WHERE r.user_id = ?
              AND r.status = 'active'
              AND t.training_date >= ?
            ORDER BY t.training_date, t.start_time
            """,
            (
                user_id,
                date.today().isoformat()
            )
        ).fetchall()

        return [dict(row) for row in rows]

    finally:
        conn.close()


def cancel_registration(
    training_id,
    user_id,
    reason="Отмена пользователем"
):
    training = get_training(training_id)

    if not training:
        return False, "Тренировка не найдена."

    try:
        training_datetime = datetime.strptime(
            f"{training['training_date']} {training['start_time']}",
            "%Y-%m-%d %H:%M"
        )
    except Exception:
        return False, "Не удалось определить время тренировки."

    if training_datetime - datetime.now() < timedelta(hours=24):
        return False, (
            "Отменить запись можно не позднее чем "
            "за 24 часа до тренировки."
        )

    conn = get_connection()

    try:
        row = conn.execute(
            """
            SELECT id
            FROM registrations
            WHERE training_id = ?
              AND user_id = ?
              AND status = 'active'
            """,
            (
                training_id,
                user_id
            )
        ).fetchone()

        if not row:
            return False, "Активная запись не найдена."

        conn.execute(
            """
            UPDATE registrations
            SET
                status = 'cancelled',
                cancelled_at = CURRENT_TIMESTAMP,
                cancellation_reason = ?
            WHERE id = ?
            """,
            (
                reason,
                row["id"]
            )
        )

        conn.commit()

        return True, "Запись отменена."

    except Exception:
        conn.rollback()
        logger.exception("Cancellation error")
        return False, "Не удалось отменить запись."

    finally:
        conn.close()


# ============================================================
# FORMATTING
# ============================================================

def format_training(training):
    try:
        dt = datetime.strptime(
            training["training_date"],
            "%Y-%m-%d"
        )

        date_text = (
            f"{WEEKDAYS[dt.weekday()]}, "
            f"{dt.day} "
            f"{[
                'января',
                'февраля',
                'марта',
                'апреля',
                'мая',
                'июня',
                'июля',
                'августа',
                'сентября',
                'октября',
                'ноября',
                'декабря'
            ][dt.month - 1]} "
            f"{dt.year}"
        )

    except Exception:
        date_text = training["training_date"]

    count = get_registration_count(
        training["id"]
    )

    return (
        f"🏐 Тренировка №{training['training_number']}\n\n"
        f"📅 {date_text}\n"
        f"⏰ {training['start_time']}–{training['end_time']}\n"
        f"👥 {training['format']}\n"
        f"🎯 {training['level']}\n"
        f"👦 Возраст: {training['age_group']}\n"
        f"👨‍🏫 Тренер: {training['coach']}\n"
        f"📍 {training['location']}\n"
        f"💰 {training['price']} ₽\n"
        f"👤 Мест: {count}/{training['capacity']}"
    )


# ============================================================
# MAIN MENU
# ============================================================

def show_main_menu(user_id):
    clear_state(user_id)

    send_message(
        user_id,
        "🏐 VOLLEY WAVE\n\n"
        "Выберите нужный раздел:",
        main_keyboard(user_id)
    )


def show_prices(user_id):
    send_message(
        user_id,
        "💰 ЦЕНЫ\n\n"
        "👧 Дети — 600 ₽ / тренировка\n\n"
        "🧑 Взрослые:\n"
        "1–6 человек — 1200 ₽ / человек\n"
        "7+ человек — 1000 ₽ / человек\n\n"
        "Минимальный состав взрослой группы — 4 человека.",
        {
            "one_time": False,
            "buttons": [
                [
                    button("⬅️ Главное меню", "secondary")
                ]
            ]
        }
    )


def show_location(user_id):
    send_message(
        user_id,
        "📍 ГДЕ ТРЕНИРУЕМСЯ\n\n"
        "Зимой:\n"
        "СК «Арена»\n"
        "ул. Молодогвардейцев, 7\n\n"
        "Летом:\n"
        "Парк Гагарина.",
        {
            "one_time": False,
            "buttons": [
                [
                    button("⬅️ Главное меню", "secondary")
                ]
            ]
        }
    )


def show_individual(user_id):
    send_message(
        user_id,
        "🎯 ИНДИВИДУАЛЬНАЯ ТРЕНИРОВКА\n\n"
        "Индивидуальные тренировки проводятся "
        "по предварительной договорённости.\n\n"
        "Напишите в сообщении удобные для вас "
        "дни и время — тренер свяжется с вами.",
        {
            "one_time": False,
            "buttons": [
                [
                    button("⬅️ Главное меню", "secondary")
                ]
            ]
        }
    )


def show_question(user_id):
    send_message(
        user_id,
        "❓ ЗАДАТЬ ВОПРОС\n\n"
        "Напишите ваш вопрос следующим сообщением.",
        {
            "one_time": False,
            "buttons": [
                [
                    button("⬅️ Главное меню", "secondary")
                ]
            ]
        }
    )

    set_state(
        user_id,
        "question"
    )


# ============================================================
# SCHEDULE
# ============================================================

def show_schedule_categories(user_id):
    logger.info(
        "SHOW SCHEDULE CATEGORIES user=%s",
        user_id
    )

    set_state(
        user_id,
        "schedule_category"
    )

    send_message(
        user_id,
        "📅 РАСПИСАНИЕ\n\n"
        "Выберите категорию:",
        {
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
            ]
        }
    )


def show_schedule(user_id, category):
    logger.info(
        "SHOW SCHEDULE user=%s category=%s",
        user_id,
        category
    )

    trainings = get_schedule_direct(
        category,
        SCHEDULE_DAYS
    )

    if not trainings:
        send_message(
            user_id,
            "📅 РАСПИСАНИЕ\n\n"
            "На ближайшие 14 дней тренировок "
            "этой категории нет.",
            {
                "one_time": False,
                "buttons": [
                    [
                        button("⬅️ Расписание", "secondary"),
                        button("🏠 Главное меню", "secondary"),
                    ]
                ]
            }
        )
        return

    text = "📅 РАСПИСАНИЕ\n\n"

    current_date = None

    for training in trainings:
        if training["training_date"] != current_date:
            current_date = training["training_date"]

            try:
                dt = datetime.strptime(
                    current_date,
                    "%Y-%m-%d"
                )

                text += (
                    f"\n📅 {WEEKDAYS[dt.weekday()]}, "
                    f"{dt.strftime('%d.%m')}\n"
                )

            except Exception:
                text += f"\n📅 {current_date}\n"

        count = get_registration_count(
            training["id"]
        )

        text += (
            f"🏐 №{training['training_number']} "
            f"{training['start_time']}–"
            f"{training['end_time']} "
            f"— {training['title']} "
            f"({count}/{training['capacity']})\n"
        )

    send_message(
        user_id,
        text,
        {
            "one_time": False,
            "buttons": [
                [
                    button("🏐 Записаться", "primary")
                ],
                [
                    button("⬅️ Расписание", "secondary"),
                    button("🏠 Главное меню", "secondary"),
                ]
            ]
        }
    )


# ============================================================
# BOOKING
# ============================================================

def show_booking_categories(user_id):
    set_state(
        user_id,
        "booking_category"
    )

    send_message(
        user_id,
        "🏐 ЗАПИСЬ НА ТРЕНИРОВКУ\n\n"
        "Выберите категорию:",
        {
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
                ]
            ]
        }
    )


def show_booking_dates(user_id, category):
    trainings = get_schedule_direct(
        category,
        SCHEDULE_DAYS
    )

    if not trainings:
        send_message(
            user_id,
            "В ближайшие 14 дней тренировок нет.",
            {
                "one_time": False,
                "buttons": [
                    [
                        button("⬅️ Назад", "secondary")
                    ]
                ]
            }
        )
        return

    dates = []

    for training in trainings:
        if training["training_date"] not in dates:
            dates.append(
                training["training_date"]
            )

    set_state(
        user_id,
        "booking_date",
        {
            "category": category
        }
    )

    rows = []

    for item in dates[:10]:
        try:
            dt = datetime.strptime(
                item,
                "%Y-%m-%d"
            )

            label = (
                f"{WEEKDAYS_SHORT[dt.weekday()]} "
                f"{dt.strftime('%d.%m')}"
            )

        except Exception:
            label = item

        rows.append([
            button(label, "primary")
        ])

    rows.append([
        button("⬅️ Назад", "secondary")
    ])

    send_message(
        user_id,
        "📅 Выберите день:",
        {
            "one_time": False,
            "buttons": rows
        }
    )


def show_booking_trainings(
    user_id,
    category,
    selected_date
):
    conn = get_connection()

    try:
        query = """
            SELECT *
            FROM trainings
            WHERE training_date = ?
              AND status != 'cancelled'
        """

        params = [
            selected_date
        ]

        if category == "children":
            query += " AND category = 'children'"

        elif category == "adults":
            query += " AND category = 'adults'"

        query += """
            ORDER BY start_time, id
        """

        rows = conn.execute(
            query,
            params
        ).fetchall()

        trainings = [dict(row) for row in rows]

    finally:
        conn.close()

    if not trainings:
        send_message(
            user_id,
            "На выбранный день тренировок нет.",
            {
                "one_time": False,
                "buttons": [
                    [
                        button("⬅️ Назад", "secondary")
                    ]
                ]
            }
        )
        return

    set_state(
        user_id,
        "booking_training",
        {
            "category": category,
            "date": selected_date
        }
    )

    rows = []

    for training in trainings:
        count = get_registration_count(
            training["id"]
        )

        rows.append([
            button(
                f"№{training['training_number']} "
                f"{training['start_time']}–"
                f"{training['end_time']} "
                f"({count}/{training['capacity']})",
                "primary"
            )
        ])

    rows.append([
        button("⬅️ Назад", "secondary")
    ])

    send_message(
        user_id,
        "🏐 Выберите тренировку:",
        {
            "one_time": False,
            "buttons": rows
        }
    )


def find_training_from_button(text):
    if not text.startswith("№"):
        return None

    try:
        number = int(
            text.split()[0][1:]
        )

        return get_training_by_number(
            number
        )

    except Exception:
        return None


def show_training_for_booking(
    user_id,
    training
):
    count = get_registration_count(
        training["id"]
    )

    already = get_registration(
        training["id"],
        user_id
    )

    if already:
        action_text = "❌ Отменить запись"
    elif count >= training["capacity"]:
        action_text = "⏳ Встать в лист ожидания"
    else:
        action_text = "✅ Записаться"

    set_state(
        user_id,
        "training_action",
        {
            "training_id": training["id"]
        }
    )

    buttons = [
        [
            button(action_text, "primary")
        ],
        [
            button("⬅️ Назад", "secondary")
        ]
    ]

    send_message(
        user_id,
        format_training(training),
        {
            "one_time": False,
            "buttons": buttons
        }
    )


# ============================================================
# MY TRAININGS
# ============================================================

def show_my_trainings(user_id):
    trainings = get_user_registrations(
        user_id
    )

    if not trainings:
        send_message(
            user_id,
            "👤 МОИ ТРЕНИРОВКИ\n\n"
            "У вас пока нет предстоящих тренировок.",
            {
                "one_time": False,
                "buttons": [
                    [
                        button("🏐 Записаться", "primary")
                    ],
                    [
                        button("⬅️ Главное меню", "secondary")
                    ]
                ]
            }
        )
        return

    text = "👤 МОИ ТРЕНИРОВКИ\n\n"

    for training in trainings:
        text += (
            f"🏐 №{training['training_number']}\n"
            f"📅 {training['weekday']}, "
            f"{training['training_date']}\n"
            f"⏰ {training['start_time']}–"
            f"{training['end_time']}\n"
            f"📍 {training['location']}\n\n"
        )

    send_message(
        user_id,
        text,
        {
            "one_time": False,
            "buttons": [
                [
                    button("🏠 Главное меню", "secondary")
                ]
            ]
        }
    )


# ============================================================
# ADMIN
# ============================================================

def is_admin(user_id):
    return user_id in ADMINS


def show_admin_menu(user_id):
    if not is_admin(user_id):
        show_main_menu(user_id)
        return

    clear_state(user_id)

    send_message(
        user_id,
        "⚙️ АДМИН-ПАНЕЛЬ\n\n"
        "Выберите действие:",
        admin_keyboard()
    )


def admin_show_schedule(user_id):
    trainings = get_schedule_direct(
        "all",
        SCHEDULE_DAYS
    )

    if not trainings:
        send_message(
            user_id,
            "📅 РАСПИСАНИЕ\n\n"
            "Нет тренировок.",
            {
                "one_time": False,
                "buttons": [
                    [
                        button("⬅️ Админ-панель", "secondary")
                    ]
                ]
            }
        )
        return

    text = "📅 РАСПИСАНИЕ\n\n"

    for training in trainings:
        count = get_registration_count(
            training["id"]
        )

        try:
            dt = datetime.strptime(
                training["training_date"],
                "%Y-%m-%d"
            )

            date_text = (
                f"{WEEKDAYS_SHORT[dt.weekday()]} "
                f"{dt.strftime('%d.%m')}"
            )

        except Exception:
            date_text = training["training_date"]

        text += (
            f"№{training['training_number']} "
            f"{date_text} "
            f"{training['start_time']}–"
            f"{training['end_time']} "
            f"({count}/{training['capacity']})\n"
        )

    send_message(
        user_id,
        text,
        {
            "one_time": False,
            "buttons": [
                [
                    button("⬅️ Админ-панель", "secondary")
                ]
            ]
        }
    )


def admin_show_participants_list(
    user_id,
    page=0
):
    logger.info(
        "ADMIN %s opened participants list page=%s",
        user_id,
        page
    )

    today = date.today()
    end_date = today + timedelta(
        days=SCHEDULE_DAYS
    )

    conn = get_connection()

    try:
        rows = conn.execute(
            """
            SELECT *
            FROM trainings
            WHERE training_date >= ?
              AND training_date <= ?
              AND status != 'cancelled'
            ORDER BY training_date, start_time, id
            """,
            (
                today.isoformat(),
                end_date.isoformat()
            )
        ).fetchall()

        trainings = [
            dict(row)
            for row in rows
        ]

    finally:
        conn.close()

    logger.info(
        "ADMIN PARTICIPANTS LIST trainings=%s",
        len(trainings)
    )

    if not trainings:
        send_message(
            user_id,
            "👥 УЧАСТНИКИ ТРЕНИРОВОК\n\n"
            "На ближайшие 14 дней тренировок нет.",
            {
                "one_time": False,
                "buttons": [
                    [
                        button("⬅️ Админ-панель", "secondary")
                    ]
                ]
            }
        )
        return

    total_pages = (
        len(trainings) +
        PARTICIPANTS_PAGE_SIZE -
        1
    ) // PARTICIPANTS_PAGE_SIZE

    page = max(
        0,
        min(
            page,
            total_pages - 1
        )
    )

    start = (
        page *
        PARTICIPANTS_PAGE_SIZE
    )

    end = start + PARTICIPANTS_PAGE_SIZE

    page_trainings = trainings[start:end]

    buttons = []

    for training in page_trainings:
        count = get_registration_count(
            training["id"]
        )

        try:
            dt = datetime.strptime(
                training["training_date"],
                "%Y-%m-%d"
            )

            date_text = dt.strftime(
                "%d.%m"
            )

            weekday = WEEKDAYS_SHORT[
                dt.weekday()
            ]

        except Exception:
            date_text = training["training_date"]
            weekday = ""

        label = (
            f"№{training['training_number']} "
            f"{weekday}, "
            f"{date_text} "
            f"{training['start_time']} "
            f"({count}/{training['capacity']})"
        )

        buttons.append([
            button(
                label,
                "primary"
            )
        ])

    navigation = []

    if page > 0:
        navigation.append(
            button(
                "⬅️ Назад",
                "secondary"
            )
        )

    if page < total_pages - 1:
        navigation.append(
            button(
                "➡️ Далее",
                "secondary"
            )
        )

    if navigation:
        buttons.append(navigation)

    buttons.append([
        button(
            "⬅️ Админ-панель",
            "secondary"
        )
    ])

    set_state(
        user_id,
        "admin_participants",
        {
            "page": page
        }
    )

    send_message(
        user_id,
        "👥 УЧАСТНИКИ ТРЕНИРОВОК\n\n"
        f"Страница {page + 1} из {total_pages}\n\n"
        "Выберите тренировку:",
        {
            "one_time": False,
            "buttons": buttons
        }
    )


def admin_show_participants(
    user_id,
    training
):
    conn = get_connection()

    try:
        rows = conn.execute(
            """
            SELECT
                r.id,
                r.user_id,
                r.registered_at,
                u.first_name,
                u.last_name
            FROM registrations r
            LEFT JOIN users u
                ON u.vk_id = r.user_id
            WHERE r.training_id = ?
              AND r.status = 'active'
            ORDER BY r.registered_at
            """,
            (training["id"],)
        ).fetchall()

        participants = [
            dict(row)
            for row in rows
        ]

    finally:
        conn.close()

    text = (
        f"👥 УЧАСТНИКИ ТРЕНИРОВКИ №"
        f"{training['training_number']}\n\n"
        f"📅 {training['training_date']}\n"
        f"⏰ {training['start_time']}–"
        f"{training['end_time']}\n\n"
    )

    if not participants:
        text += "Пока никто не записан."

    else:
        for index, person in enumerate(
            participants,
            start=1
        ):
            name = (
                f"{person.get('first_name', '')} "
                f"{person.get('last_name', '')}"
            ).strip()

            if not name:
                name = f"VK ID {person['user_id']}"

            text += (
                f"{index}. {name}\n"
            )

    send_message(
        user_id,
        text,
        {
            "one_time": False,
            "buttons": [
                [
                    button(
                        "⬅️ К тренировкам",
                        "secondary"
                    )
                ],
                [
                    button(
                        "⚙️ Админ-панель",
                        "secondary"
                    )
                ]
            ]
        }
    )


# ============================================================
# ADMIN CREATE TRAINING
# ============================================================

def admin_create_training_start(user_id):
    set_state(
        user_id,
        "admin_create_date"
    )

    send_message(
        user_id,
        "➕ СОЗДАНИЕ ТРЕНИРОВКИ\n\n"
        "Введите дату в формате:\n"
        "05.10.2026",
        {
            "one_time": False,
            "buttons": [
                [
                    button("⬅️ Отмена", "secondary")
                ]
            ]
        }
    )


def admin_create_training_date(
    user_id,
    text
):
    try:
        dt = datetime.strptime(
            text.strip(),
            "%d.%m.%Y"
        )

    except ValueError:
        send_message(
            user_id,
            "❌ Неверный формат даты.\n\n"
            "Введите, например:\n"
            "05.10.2026"
        )
        return

    set_state(
        user_id,
        "admin_create_start",
        {
            "date": dt.strftime("%Y-%m-%d")
        }
    )

    send_message(
        user_id,
        "Введите время начала:\n"
        "Например: 17:00",
        {
            "one_time": False,
            "buttons": [
                [
                    button("⬅️ Отмена", "secondary")
                ]
            ]
        }
    )


def admin_create_training_start_time(
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
            "❌ Неверное время.\n"
            "Используйте формат 17:00."
        )
        return

    state = get_state(user_id)

    data = dict(
        state.get("data", {})
    )

    data["start_time"] = text.strip()

    set_state(
        user_id,
        "admin_create_end",
        data
    )

    send_message(
        user_id,
        "Введите время окончания:\n"
        "Например: 19:00",
        {
            "one_time": False,
            "buttons": [
                [
                    button("⬅️ Отмена", "secondary")
                ]
            ]
        }
    )


def admin_create_training_end_time(
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
            "❌ Неверное время.\n"
            "Используйте формат 19:00."
        )
        return

    state = get_state(user_id)

    data = dict(
        state.get("data", {})
    )

    data["end_time"] = text.strip()

    set_state(
        user_id,
        "admin_create_title",
        data
    )

    send_message(
        user_id,
        "Введите название тренировки:",
        {
            "one_time": False,
            "buttons": [
                [
                    button("⬅️ Отмена", "secondary")
                ]
            ]
        }
    )


def admin_create_training_title(
    user_id,
    text
):
    state = get_state(user_id)

    data = dict(
        state.get("data", {})
    )

    data["title"] = text.strip()

    set_state(
        user_id,
        "admin_create_category",
        data
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
                    button("⬅️ Отмена", "secondary")
                ]
            ]
        }
    )


def admin_create_training_category(
    user_id,
    text
):
    if text == "👧 Дети":
        category = "children"

    elif text == "🧑 Взрослые":
        category = "adults"

    else:
        send_message(
            user_id,
            "Выберите категорию кнопкой."
        )
        return

    state = get_state(user_id)

    data = dict(
        state.get("data", {})
    )

    data["category"] = category

    set_state(
        user_id,
        "admin_create_capacity",
        data
    )

    send_message(
        user_id,
        "Введите количество мест:\n"
        "Например: 10"
    )


def admin_create_training_capacity(
    user_id,
    text
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
            "❌ Введите положительное число."
        )
        return

    state = get_state(user_id)

    data = dict(
        state.get("data", {})
    )

    data["capacity"] = capacity

    set_state(
        user_id,
        "admin_create_price",
        data
    )

    send_message(
        user_id,
        "Введите стоимость тренировки:\n"
        "Например: 600"
    )


def admin_create_training_price(
    user_id,
    text
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
            "❌ Введите стоимость числом."
        )
        return

    state = get_state(user_id)

    data = dict(
        state.get("data", {})
    )

    data["price"] = price

    set_state(
        user_id,
        "admin_create_age",
        data
    )

    send_message(
        user_id,
        "Введите возрастную группу:\n"
        "Например: 11–14 лет"
    )


def admin_create_training_age(
    user_id,
    text
):
    state = get_state(user_id)

    data = dict(
        state.get("data", {})
    )

    data["age_group"] = text.strip()

    set_state(
        user_id,
        "admin_create_level",
        data
    )

    send_message(
        user_id,
        "Введите уровень:\n"
        "Например: Средний"
    )


def admin_create_training_level(
    user_id,
    text
):
    state = get_state(user_id)

    data = dict(
        state.get("data", {})
    )

    data["level"] = text.strip()

    set_state(
        user_id,
        "admin_create_coach",
        data
    )

    send_message(
        user_id,
        "Введите имя тренера:\n"
        "Например: Алексей"
    )


def admin_create_training_coach(
    user_id,
    text
):
    state = get_state(user_id)

    data = dict(
        state.get("data", {})
    )

    data["coach"] = text.strip()

    set_state(
        user_id,
        "admin_create_confirm",
        data
    )

    summary = (
        "➕ НОВАЯ ТРЕНИРОВКА\n\n"
        f"📅 {data['date']}\n"
        f"⏰ {data['start_time']}–{data['end_time']}\n"
        f"🏐 {data['title']}\n"
        f"👥 {'Дети' if data['category'] == 'children' else 'Взрослые'}\n"
        f"👦 {data['age_group']}\n"
        f"🎯 {data['level']}\n"
        f"👨‍🏫 {data['coach']}\n"
        f"👤 Мест: {data['capacity']}\n"
        f"💰 Цена: {data['price']} ₽\n\n"
        "Создать тренировку?"
    )

    send_message(
        user_id,
        summary,
        {
            "one_time": False,
            "buttons": [
                [
                    button("✅ Создать", "positive"),
                    button("❌ Отмена", "secondary"),
                ]
            ]
        }
    )


def admin_create_training_confirm(
    user_id
):
    state = get_state(user_id)

    data = state.get(
        "data",
        {}
    )

    conn = get_connection()

    try:
        existing = conn.execute(
            """
            SELECT id
            FROM trainings
            WHERE training_date = ?
              AND start_time = ?
              AND end_time = ?
              AND title = ?
            LIMIT 1
            """,
            (
                data["date"],
                data["start_time"],
                data["end_time"],
                data["title"]
            )
        ).fetchone()

        if existing:
            send_message(
                user_id,
                "❌ Такая тренировка уже существует."
            )
            return

        number = next_training_number(conn)

        dt = datetime.strptime(
            data["date"],
            "%Y-%m-%d"
        )

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
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                number,
                data["date"],
                WEEKDAYS[dt.weekday()],
                data["start_time"],
                data["end_time"],
                data["title"],
                data["category"],
                data["age_group"],
                data["level"],
                "Группа",
                data["coach"],
                data["capacity"],
                data["price"],
                "СК «Арена», ул. Молодогвардейцев, 7",
            )
        )

        conn.commit()

        logger.info(
            "ADMIN %s created training №%s",
            user_id,
            number
        )

        send_message(
            user_id,
            f"✅ Тренировка №{number} создана!",
            {
                "one_time": False,
                "buttons": [
                    [
                        button(
                            "⚙️ Админ-панель",
                            "primary"
                        )
                    ]
                ]
            }
        )

    except Exception:
        conn.rollback()

        logger.exception(
            "Admin training creation failed"
        )

        send_message(
            user_id,
            "❌ Не удалось создать тренировку.\n\n"
            "Ошибка записана в Logs Render."
        )

    finally:
        conn.close()

    clear_state(user_id)


# ============================================================
# CALLBACK
# ============================================================

@app.route("/", methods=["GET"])
def index():
    return "VOLLEY WAVE VK BOT OK", 200


@app.route("/callback", methods=["POST"])
def callback():
    try:
        data = request.get_json(
            silent=True
        ) or {}

        logger.info(
            "VK EVENT: %s",
            data
        )

        if data.get("type") == "confirmation":
            return (
                VK_CONFIRMATION_TOKEN or "",
                200
            )

        if data.get("type") != "message_new":
            return "ok", 200

        obj = data.get(
            "object",
            {}
        )

        message = obj.get(
            "message",
            {}
        )

        user_id = (
            message.get("from_id")
            or obj.get("from_id")
        )

        text = (
            message.get("text")
            or obj.get("text")
            or ""
        ).strip()

        if not user_id:
            return "ok", 200

        logger.info(
            "MESSAGE_NEW user=%s text=%r",
            user_id,
            text
        )

        save_user(user_id)

        if is_blocked(user_id):
            return "ok", 200

        handle_message(
            user_id,
            text
        )

        return "ok", 200

    except Exception:
        logger.exception(
            "Callback processing error"
        )

        return "ok", 200


# ============================================================
# MESSAGE HANDLER
# ============================================================

def handle_message(
    user_id,
    text
):
    logger.info(
        "MESSAGE user=%s text=%r",
        user_id,
        text
    )

    # --------------------------------------------------------
    # GLOBAL NAVIGATION
    # --------------------------------------------------------

    if text in (
        "🏠 Главное меню",
        "Главное меню"
    ):
        show_main_menu(user_id)
        return

    if text in (
        "⬅️ Главное меню",
        "Назад в главное меню"
    ):
        show_main_menu(user_id)
        return

    if text in (
        "⚙️ Админ-панель",
        "Админ-панель"
    ):
        if is_admin(user_id):
            show_admin_menu(user_id)
        else:
            show_main_menu(user_id)

        return

    if text in (
        "⬅️ Админ-панель",
    ):
        if is_admin(user_id):
            show_admin_menu(user_id)
        else:
            show_main_menu(user_id)

        return

    # --------------------------------------------------------
    # ADMIN PARTICIPANTS PAGINATION
    # --------------------------------------------------------

    state = get_state(user_id)

    if (
        is_admin(user_id)
        and state["state"] == "admin_participants"
    ):
        if text == "➡️ Далее":
            page = state["data"].get(
                "page",
                0
            ) + 1

            admin_show_participants_list(
                user_id,
                page
            )
            return

        if text == "⬅️ Назад":
            page = max(
                0,
                state["data"].get(
                    "page",
                    0
                ) - 1
            )

            admin_show_participants_list(
                user_id,
                page
            )
            return

    # --------------------------------------------------------
    # ADMIN CREATE
    # --------------------------------------------------------

    if (
        is_admin(user_id)
        and state["state"] == "admin_create_date"
    ):
        if text == "⬅️ Отмена":
            show_admin_menu(user_id)
        else:
            admin_create_training_date(
                user_id,
                text
            )

        return

    if (
        is_admin(user_id)
        and state["state"] == "admin_create_start"
    ):
        if text == "⬅️ Отмена":
            show_admin_menu(user_id)
        else:
            admin_create_training_start_time(
                user_id,
                text
            )

        return

    if (
        is_admin(user_id)
        and state["state"] == "admin_create_end"
    ):
        if text == "⬅️ Отмена":
            show_admin_menu(user_id)
        else:
            admin_create_training_end_time(
                user_id,
                text
            )

        return

    if (
        is_admin(user_id)
        and state["state"] == "admin_create_title"
    ):
        if text == "⬅️ Отмена":
            show_admin_menu(user_id)
        else:
            admin_create_training_title(
                user_id,
                text
            )

        return

    if (
        is_admin(user_id)
        and state["state"] == "admin_create_category"
    ):
        if text == "⬅️ Отмена":
            show_admin_menu(user_id)
        else:
            admin_create_training_category(
                user_id,
                text
            )

        return

    if (
        is_admin(user_id)
        and state["state"] == "admin_create_capacity"
    ):
        if text == "⬅️ Отмена":
            show_admin_menu(user_id)
        else:
            admin_create_training_capacity(
                user_id,
                text
            )

        return

    if (
        is_admin(user_id)
        and state["state"] == "admin_create_price"
    ):
        if text == "⬅️ Отмена":
            show_admin_menu(user_id)
        else:
            admin_create_training_price(
                user_id,
                text
            )

        return

    if (
        is_admin(user_id)
        and state["state"] == "admin_create_age"
    ):
        if text == "⬅️ Отмена":
            show_admin_menu(user_id)
        else:
            admin_create_training_age(
                user_id,
                text
            )

        return

    if (
        is_admin(user_id)
        and state["state"] == "admin_create_level"
    ):
        if text == "⬅️ Отмена":
            show_admin_menu(user_id)
        else:
            admin_create_training_level(
                user_id,
                text
            )

        return

    if (
        is_admin(user_id)
        and state["state"] == "admin_create_coach"
    ):
        if text == "⬅️ Отмена":
            show_admin_menu(user_id)
        else:
            admin_create_training_coach(
                user_id,
                text
            )

        return

    if (
        is_admin(user_id)
        and state["state"] == "admin_create_confirm"
    ):
        if text == "✅ Создать":
            admin_create_training_confirm(
                user_id
            )
        else:
            show_admin_menu(user_id)

        return

    # --------------------------------------------------------
    # MAIN MENU
    # --------------------------------------------------------

    if text == "🏐 Записаться":
        show_booking_categories(user_id)
        return

    if text == "📅 Расписание":
        show_schedule_categories(user_id)
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
        show_individual(user_id)
        return

    if text == "❓ Задать вопрос":
        show_question(user_id)
        return

    # --------------------------------------------------------
    # ADMIN MENU
    # --------------------------------------------------------

    if is_admin(user_id):

        if text == "📅 Расписание":
            admin_show_schedule(user_id)
            return

        if text == "👥 Участники тренировок":
            logger.info(
                "ADMIN PARTICIPANTS BUTTON user=%s",
                user_id
            )

            admin_show_participants_list(
                user_id,
                0
            )

            return

        if text == "➕ Создать тренировку":
            admin_create_training_start(
                user_id
            )
            return

    # --------------------------------------------------------
    # SCHEDULE CATEGORY
    # --------------------------------------------------------

    if state["state"] == "schedule_category":

        logger.info(
            "STATE user=%s state=schedule_category data=%s",
            user_id,
            state["data"]
        )

        if text == "👧 Дети":
            show_schedule(
                user_id,
                "children"
            )
            return

        if text == "🧑 Взрослые":
            show_schedule(
                user_id,
                "adults"
            )
            return

        if text == "🏠 Все тренировки":
            show_schedule(
                user_id,
                "all"
            )
            return

        if text == "⬅️ Назад":
            show_main_menu(user_id)
            return

    # --------------------------------------------------------
    # BOOKING CATEGORY
    # --------------------------------------------------------

    if state["state"] == "booking_category":

        if text == "👧 Дети":
            show_booking_dates(
                user_id,
                "children"
            )
            return

        if text == "🧑 Взрослые":
            show_booking_dates(
                user_id,
                "adults"
            )
            return

        if text == "🏠 Все тренировки":
            show_booking_dates(
                user_id,
                "all"
            )
            return

        if text == "⬅️ Назад":
            show_main_menu(user_id)
            return

    # --------------------------------------------------------
    # BOOKING DATE
    # --------------------------------------------------------

    if state["state"] == "booking_date":

        if text == "⬅️ Назад":
            show_booking_categories(
                user_id
            )
            return

        category = state["data"].get(
            "category",
            "all"
        )

        trainings = get_schedule_direct(
            category,
            SCHEDULE_DAYS
        )

        selected_date = None

        for training in trainings:
            try:
                dt = datetime.strptime(
                    training["training_date"],
                    "%Y-%m-%d"
                )

                label = (
                    f"{WEEKDAYS_SHORT[dt.weekday()]} "
                    f"{dt.strftime('%d.%m')}"
                )

                if label == text:
                    selected_date = (
                        training["training_date"]
                    )
                    break

            except Exception:
                continue

        if selected_date:
            show_booking_trainings(
                user_id,
                category,
                selected_date
            )

        return

    # --------------------------------------------------------
    # BOOKING TRAINING
    # --------------------------------------------------------

    if state["state"] == "booking_training":

        if text == "⬅️ Назад":
            show_booking_dates(
                user_id,
                state["data"].get(
                    "category",
                    "all"
                )
            )
            return

        training = find_training_from_button(
            text
        )

        if training:
            show_training_for_booking(
                user_id,
                training
            )

        return

    # --------------------------------------------------------
    # TRAINING ACTION
    # --------------------------------------------------------

    if state["state"] == "training_action":

        training_id = state["data"].get(
            "training_id"
        )

        training = get_training(
            training_id
        )

        if not training:
            show_main_menu(user_id)
            return

        if text == "⬅️ Назад":
            show_main_menu(user_id)
            return

        if text == "✅ Записаться":
            success, message = add_registration(
                training_id,
                user_id
            )

            send_message(
                user_id,
                (
                    f"✅ {message}"
                    if success
                    else f"❌ {message}"
                ),
                {
                    "one_time": False,
                    "buttons": [
                        [
                            button(
                                "👤 Мои тренировки",
                                "primary"
                            )
                        ],
                        [
                            button(
                                "🏠 Главное меню",
                                "secondary"
                            )
                        ]
                    ]
                }
            )

            clear_state(user_id)
            return

        if text == "❌ Отменить запись":
            success, message = cancel_registration(
                training_id,
                user_id
            )

            send_message(
                user_id,
                (
                    f"✅ {message}"
                    if success
                    else f"❌ {message}"
                ),
                {
                    "one_time": False,
                    "buttons": [
                        [
                            button(
                                "👤 Мои тренировки",
                                "primary"
                            )
                        ],
                        [
                            button(
                                "🏠 Главное меню",
                                "secondary"
                            )
                        ]
                    ]
                }
            )

            clear_state(user_id)
            return

        return

    # --------------------------------------------------------
    # QUESTION
    # --------------------------------------------------------

    if state["state"] == "question":
        if text == "⬅️ Главное меню":
            show_main_menu(user_id)
            return

        send_message(
            user_id,
            "Спасибо! Ваш вопрос получен.\n"
            "Администратор свяжется с вами.",
            {
                "one_time": False,
                "buttons": [
                    [
                        button(
                            "🏠 Главное меню",
                            "secondary"
                        )
                    ]
                ]
            }
        )

        clear_state(user_id)
        return

    # --------------------------------------------------------
    # ADMIN TRAINING NUMBER
    # --------------------------------------------------------

    if is_admin(user_id):
        training = find_training_from_button(
            text
        )

        if training:
            admin_show_participants(
                user_id,
                training
            )
            return

    # --------------------------------------------------------
    # UNKNOWN
    # --------------------------------------------------------

    show_main_menu(user_id)


# ============================================================
# STARTUP
# ============================================================

def startup():
    logger.info(
        "Starting VOLLEY WAVE VK BOT..."
    )

    logger.info(
        "Group ID: %s",
        GROUP_ID
    )

    logger.info(
        "Admins: %s",
        list(ADMINS)
    )

    init_db()

    ensure_schedule()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    startup()

    app.run(
        host="0.0.0.0",
        port=int(
            os.getenv(
                "PORT",
                "10000"
            )
        ),
        debug=False
    )
