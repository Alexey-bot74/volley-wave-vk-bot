import os
import json
import re
import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from flask import Flask, request


# =========================================================
# НАСТРОЙКИ
# =========================================================

app = Flask(__name__)

DB_NAME = "volley_wave.db"
VK_API_VERSION = "5.199"

CONFIRMATION_TOKEN = os.getenv("VK_CONFIRMATION_TOKEN")
SECRET_KEY = os.getenv("VK_SECRET_KEY")
VK_TOKEN = os.getenv("VK_TOKEN")

TIMEZONE = ZoneInfo("Asia/Yekaterinburg")


# =========================================================
# АДМИНИСТРАТОРЫ
# =========================================================

ADMIN_IDS = {
    87984447,
    172892670,
    148372158
}


# =========================================================
# ДНИ НЕДЕЛИ
# =========================================================

DAYS = {
    1: "ПОНЕДЕЛЬНИК",
    2: "ВТОРНИК",
    3: "СРЕДА",
    4: "ЧЕТВЕРГ",
    5: "ПЯТНИЦА",
    6: "СУББОТА",
    7: "ВОСКРЕСЕНЬЕ"
}

DAY_NAMES = {
    "Понедельник": 1,
    "Вторник": 2,
    "Среда": 3,
    "Четверг": 4,
    "Пятница": 5
}

DAY_NAMES_REVERSE = {
    1: "Понедельник",
    2: "Вторник",
    3: "Среда",
    4: "Четверг",
    5: "Пятница",
    6: "Суббота",
    7: "Воскресенье"
}


# =========================================================
# СОСТОЯНИЯ ПОЛЬЗОВАТЕЛЕЙ
# =========================================================

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


# =========================================================
# DATABASE
# =========================================================

def get_connection():
    connection = sqlite3.connect(
        DB_NAME,
        timeout=30
    )

    connection.row_factory = sqlite3.Row

    return connection


def column_exists(
    connection,
    table_name,
    column_name
):
    rows = connection.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    for row in rows:
        if row["name"] == column_name:
            return True

    return False


def add_column_if_missing(
    connection,
    table_name,
    column_name,
    column_type,
    default=None
):
    if column_exists(
        connection,
        table_name,
        column_name
    ):
        return

    if default is None:

        connection.execute(
            f"""
            ALTER TABLE {table_name}
            ADD COLUMN {column_name} {column_type}
            """
        )

    else:

        safe_default = str(default).replace(
            "'",
            "''"
        )

        connection.execute(
            f"""
            ALTER TABLE {table_name}
            ADD COLUMN {column_name} {column_type}
            DEFAULT '{safe_default}'
            """
        )


def init_db():

    connection = get_connection()

    # -----------------------------------------------------
    # ТРЕНИРОВКИ
    # -----------------------------------------------------

    connection.execute("""
        CREATE TABLE IF NOT EXISTS trainings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day_of_week INTEGER NOT NULL,
            time TEXT NOT NULL,
            title TEXT NOT NULL,
            level TEXT,
            age_group TEXT,
            price INTEGER NOT NULL,
            capacity INTEGER NOT NULL,
            category TEXT,
            trainer TEXT
        )
    """)

    add_column_if_missing(
        connection,
        "trainings",
        "category",
        "TEXT",
        "adult"
    )

    add_column_if_missing(
        connection,
        "trainings",
        "trainer",
        "TEXT",
        "Тренер не указан"
    )

    # -----------------------------------------------------
    # ЗАПИСИ
    # -----------------------------------------------------

    connection.execute("""
        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            training_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            name TEXT,
            phone TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(training_id, user_id)
        )
    """)

    # -----------------------------------------------------
    # ВОПРОСЫ
    # -----------------------------------------------------

    connection.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            user_name TEXT,
            question TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            answered INTEGER DEFAULT 0
        )
    """)

    # -----------------------------------------------------
    # ПЕРВОНАЧАЛЬНОЕ РАСПИСАНИЕ
    # -----------------------------------------------------

    count = connection.execute(
        "SELECT COUNT(*) FROM trainings"
    ).fetchone()[0]

    if count == 0:

        schedule = [

            # ПОНЕДЕЛЬНИК

            (
                1,
                "09:00-11:00",
                "Детская тренировка",
                "",
                "9-13 лет",
                600,
                10,
                "child",
                "Тренер не указан"
            ),

            (
                1,
                "17:00-19:00",
                "Детская тренировка",
                "",
                "11-14 лет",
                600,
                10,
                "child",
                "Тренер не указан"
            ),

            (
                1,
                "19:00-20:30",
                "Техничка",
                "любой уровень",
                "",
                1200,
                10,
                "adult",
                "Тренер не указан"
            ),

            # ВТОРНИК

            (
                2,
                "09:00-11:00",
                "Общая тренировка",
                "любой уровень",
                "",
                1200,
                8,
                "adult",
                "Тренер не указан"
            ),

            (
                2,
                "17:00-18:30",
                "Детская тренировка",
                "",
                "11-14 лет",
                600,
                10,
                "child",
                "Тренер не указан"
            ),

            (
                2,
                "19:30-21:00",
                "Женская тренировка",
                "средний+",
                "",
                1200,
                8,
                "adult",
                "Тренер не указан"
            ),

            # СРЕДА

            (
                3,
                "09:00-11:00",
                "Детская тренировка",
                "",
                "9-14 лет",
                600,
                10,
                "child",
                "Тренер не указан"
            ),

            (
                3,
                "17:00-18:00",
                "Детская тренировка",
                "",
                "5-9 лет",
                600,
                10,
                "child",
                "Тренер не указан"
            ),

            (
                3,
                "18:00-19:30",
                "Тренировка",
                "продвинутый",
                "",
                1200,
                8,
                "adult",
                "Тренер не указан"
            ),

            (
                3,
                "19:30-21:00",
                "MIXED",
                "средний+",
                "",
                1200,
                3,
                "adult",
                "Тренер не указан"
            ),

            # ЧЕТВЕРГ

            (
                4,
                "09:00-11:00",
                "Общая тренировка",
                "любой уровень",
                "",
                1200,
                8,
                "adult",
                "Тренер не указан"
            ),

            (
                4,
                "17:00-19:00",
                "Детская тренировка",
                "",
                "11-14 лет",
                600,
                10,
                "child",
                "Тренер не указан"
            ),

            (
                4,
                "19:00-20:30",
                "Тренировка",
                "средний",
                "",
                1200,
                8,
                "adult",
                "Тренер не указан"
            ),

            # ПЯТНИЦА

            (
                5,
                "09:00-11:00",
                "Детская тренировка",
                "",
                "9-14 лет",
                600,
                10,
                "child",
                "Тренер не указан"
            ),

            (
                5,
                "17:00-18:00",
                "Детская тренировка",
                "",
                "5-10 лет",
                600,
                10,
                "child",
                "Тренер не указан"
            ),

            (
                5,
                "17:00-19:00",
                "Детская тренировка",
                "",
                "11-14 лет",
                600,
                10,
                "child",
                "Тренер не указан"
            ),

            (
                5,
                "19:00-20:30",
                "Техничка",
                "любой уровень",
                "",
                1200,
                10,
                "adult",
                "Тренер не указан"
            )
        ]

        connection.executemany(
            """
            INSERT INTO trainings
            (
                day_of_week,
                time,
                title,
                level,
                age_group,
                price,
                capacity,
                category,
                trainer
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            schedule
        )

    else:

        connection.execute("""
            UPDATE trainings
            SET category =
                CASE
                    WHEN
                        title LIKE '%Дет%'
                        OR (
                            age_group IS NOT NULL
                            AND age_group != ''
                        )
                    THEN 'child'
                    ELSE COALESCE(
                        category,
                        'adult'
                    )
                END
            WHERE category IS NULL
               OR category = ''
        """)

        connection.execute("""
            UPDATE trainings
            SET trainer = 'Тренер не указан'
            WHERE trainer IS NULL
               OR trainer = ''
        """)

    connection.commit()
    connection.close()


# =========================================================
# DATABASE FUNCTIONS
# =========================================================

def get_trainings():

    connection = get_connection()

    rows = connection.execute("""
        SELECT *
        FROM trainings
        ORDER BY day_of_week, time
    """).fetchall()

    connection.close()

    return rows


def get_training_by_id(training_id):

    connection = get_connection()

    row = connection.execute(
        """
        SELECT *
        FROM trainings
        WHERE id = ?
        """,
        (training_id,)
    ).fetchone()

    connection.close()

    return row


def get_trainings_by_day(
    day_number,
    category=None
):

    connection = get_connection()

    if category:

        rows = connection.execute(
            """
            SELECT *
            FROM trainings
            WHERE day_of_week = ?
              AND category = ?
            ORDER BY time
            """,
            (
                day_number,
                category
            )
        ).fetchall()

    else:

        rows = connection.execute(
            """
            SELECT *
            FROM trainings
            WHERE day_of_week = ?
            ORDER BY time
            """,
            (day_number,)
        ).fetchall()

    connection.close()

    return rows


def get_registration_count(
    training_id
):

    connection = get_connection()

    row = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM registrations
        WHERE training_id = ?
        """,
        (training_id,)
    ).fetchone()

    connection.close()

    return row["count"]


def get_registrations(
    training_id
):

    connection = get_connection()

    rows = connection.execute(
        """
        SELECT *
        FROM registrations
        WHERE training_id = ?
        ORDER BY created_at
        """,
        (training_id,)
    ).fetchall()

    connection.close()

    return rows


def get_user_registrations(
    user_id
):

    connection = get_connection()

    rows = connection.execute(
        """
        SELECT
            registrations.id AS registration_id,
            registrations.training_id,
            registrations.user_id,
            registrations.name,
            registrations.phone,
            registrations.created_at,
            trainings.day_of_week,
            trainings.time,
            trainings.title,
            trainings.level,
            trainings.age_group,
            trainings.price,
            trainings.capacity,
            trainings.category,
            trainings.trainer
        FROM registrations
        JOIN trainings
            ON registrations.training_id =
               trainings.id
        WHERE registrations.user_id = ?
        ORDER BY
            trainings.day_of_week,
            trainings.time
        """,
        (user_id,)
    ).fetchall()

    connection.close()

    return rows


def user_is_registered(
    training_id,
    user_id
):

    connection = get_connection()

    row = connection.execute(
        """
        SELECT id
        FROM registrations
        WHERE training_id = ?
          AND user_id = ?
        """,
        (
            training_id,
            user_id
        )
    ).fetchone()

    connection.close()

    return row is not None


def get_user_phone(
    user_id
):

    connection = get_connection()

    row = connection.execute(
        """
        SELECT phone
        FROM registrations
        WHERE user_id = ?
          AND phone IS NOT NULL
          AND phone != ''
        ORDER BY id DESC
        LIMIT 1
        """,
        (user_id,)
    ).fetchone()

    connection.close()

    if row:
        return row["phone"]

    return None


def add_registration(
    training_id,
    user_id,
    name,
    phone
):

    connection = get_connection()

    try:

        connection.execute(
            """
            INSERT INTO registrations
            (
                training_id,
                user_id,
                name,
                phone
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                training_id,
                user_id,
                name,
                phone
            )
        )

        connection.commit()

        result = True

    except sqlite3.IntegrityError:

        result = False

    connection.close()

    return result


def delete_registration(
    training_id,
    user_id
):

    connection = get_connection()

    cursor = connection.execute(
        """
        DELETE FROM registrations
        WHERE training_id = ?
          AND user_id = ?
        """,
        (
            training_id,
            user_id
        )
    )

    connection.commit()

    result = cursor.rowcount > 0

    connection.close()

    return result


def add_question(
    user_id,
    user_name,
    question
):

    connection = get_connection()

    connection.execute(
        """
        INSERT INTO questions
        (
            user_id,
            user_name,
            question
        )
        VALUES (?, ?, ?)
        """,
        (
            user_id,
            user_name,
            question
        )
    )

    connection.commit()
    connection.close()


def update_training(
    training_id,
    field,
    value
):

    allowed_fields = {
        "day_of_week",
        "time",
        "title",
        "level",
        "age_group",
        "price",
        "capacity",
        "category",
        "trainer"
    }

    if field not in allowed_fields:
        return False

    connection = get_connection()

    connection.execute(
        f"""
        UPDATE trainings
        SET {field} = ?
        WHERE id = ?
        """,
        (
            value,
            training_id
        )
    )

    connection.commit()
    connection.close()

    return True


def create_training(
    day_of_week,
    time,
    title,
    level,
    age_group,
    price,
    capacity,
    category,
    trainer
):

    connection = get_connection()

    cursor = connection.execute(
        """
        INSERT INTO trainings
        (
            day_of_week,
            time,
            title,
            level,
            age_group,
            price,
            capacity,
            category,
            trainer
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            day_of_week,
            time,
            title,
            level,
            age_group,
            price,
            capacity,
            category,
            trainer
        )
    )

    connection.commit()

    training_id = cursor.lastrowid

    connection.close()

    return training_id


def delete_training(
    training_id
):

    connection = get_connection()

    connection.execute(
        """
        DELETE FROM registrations
        WHERE training_id = ?
        """,
        (training_id,)
    )

    connection.execute(
        """
        DELETE FROM trainings
        WHERE id = ?
        """,
        (training_id,)
    )

    connection.commit()
    connection.close()


# =========================================================
# ИНИЦИАЛИЗАЦИЯ БАЗЫ
# =========================================================

init_db()


# =========================================================
# VK API
# =========================================================

def send_message(
    user_id,
    message,
    keyboard=None
):

    url = (
        "https://api.vk.com/method/"
        "messages.send"
    )

    params = {
        "access_token": VK_TOKEN,
        "v": VK_API_VERSION,
        "user_id": user_id,
        "random_id": 0,
        "message": message
    }

    if keyboard:
        params["keyboard"] = keyboard

    try:

        response = requests.get(
            url,
            params=params,
            timeout=15
        )

        print(
            "VK RESPONSE:",
            response.text
        )

    except Exception as error:

        print(
            "VK SEND ERROR:",
            error
        )


def get_vk_user_name(
    user_id
):

    url = (
        "https://api.vk.com/method/"
        "users.get"
    )

    params = {
        "access_token": VK_TOKEN,
        "v": VK_API_VERSION,
        "user_ids": user_id
    }

    try:

        response = requests.get(
            url,
            params=params,
            timeout=15
        )

        data = response.json()

        if data.get("response"):

            user = data["response"][0]

            name = (
                f"{user.get('first_name', '')} "
                f"{user.get('last_name', '')}"
            ).strip()

            if name:
                return name

    except Exception as error:

        print(
            "VK USER ERROR:",
            error
        )

    return f"Участник {user_id}"


# =========================================================
# KEYBOARDS
# =========================================================

def make_keyboard(buttons):

    return json.dumps(
        {
            "one_time": False,
            "buttons": buttons
        },
        ensure_ascii=False
    )


def button(label):

    return {
        "action": {
            "type": "text",
            "label": label
        }
    }


def main_keyboard():

    return make_keyboard([

        [
            button("🏐 Записаться"),
            button("📅 Расписание")
        ],

        [
            button("👤 Мои тренировки"),
            button("💰 Цены")
        ],

        [
            button("👶 Детские группы"),
            button("📍 Где тренируемся")
        ],

        [
            button("❓ Задать вопрос")
        ]

    ])


def schedule_type_keyboard():

    return make_keyboard([

        [
            button("👨 Взрослые"),
            button("👶 Дети")
        ],

        [
            button("🏠 Главное меню")
        ]

    ])


def days_keyboard():

    return make_keyboard([

        [
            button("Понедельник"),
            button("Вторник")
        ],

        [
            button("Среда"),
            button("Четверг")
        ],

        [
            button("Пятница")
        ],

        [
            button("🏠 Главное меню")
        ]

    ])


def training_list_keyboard(
    trainings,
    back_label="⬅️ Назад"
):

    buttons = []

    for training in trainings:

        registered = get_registration_count(
            training["id"]
        )

        available = max(
            training["capacity"] -
            registered,
            0
        )

        label = (
            f"#{training['id']} "
            f"{training['time']} "
            f"({available} мест)"
        )

        buttons.append(
            [
                button(label)
            ]
        )

    buttons.append(
        [
            button(back_label)
        ]
    )

    return make_keyboard(buttons)


def training_keyboard(
    training_id,
    available,
    registered_by_user
):

    buttons = []

    if (
        available > 0
        and not registered_by_user
    ):

        buttons.append(
            [
                button(
                    f"✅ Записаться #{training_id}"
                )
            ]
        )

    if registered_by_user:

        buttons.append(
            [
                button(
                    f"❌ Отменить #{training_id}"
                )
            ]
        )

    buttons.extend([

        [
            button("⬅️ Назад")
        ],

        [
            button("🏠 Главное меню")
        ]

    ])

    return make_keyboard(buttons)


def my_trainings_keyboard(
    registrations
):

    buttons = []

    for registration in registrations:

        buttons.append(
            [
                button(
                    f"❌ Отменить "
                    f"#{registration['training_id']}"
                )
            ]
        )

    buttons.append(
        [
            button("🏠 Главное меню")
        ]
    )

    return make_keyboard(buttons)


# =========================================================
# ADMIN KEYBOARDS
# =========================================================

def admin_keyboard():

    return make_keyboard([

        [
            button("📅 Управление расписанием")
        ],

        [
            button("👥 Записи на тренировки")
        ],

        [
            button("➕ Добавить тренировку")
        ],

        [
            button("📊 Общая информация")
        ],

        [
            button("🏠 Главное меню")
        ]

    ])


def admin_training_keyboard():

    return make_keyboard([

        [
            button("✏️ Изменить тренировку")
        ],

        [
            button("🗑 Удалить тренировку")
        ],

        [
            button("⬅️ Админ-панель")
        ]

    ])


def admin_edit_keyboard():

    return make_keyboard([

        [
            button("🗓 День"),
            button("🕐 Время")
        ],

        [
            button("🏐 Название"),
            button("👨‍🏫 Тренер")
        ],

        [
            button("💰 Цена"),
            button("👥 Места")
        ],

        [
            button("🎯 Уровень"),
            button("👶 Возраст")
        ],

        [
            button("👤 Тип")
        ],

        [
            button("⬅️ Назад")
        ]

    ])


# =========================================================
# ДАТА И ВРЕМЯ ТРЕНИРОВКИ
# =========================================================

def get_next_training_datetime(
    training
):

    now = datetime.now(
        TIMEZONE
    )

    day_of_week = training[
        "day_of_week"
    ]

    time_string = training[
        "time"
    ]

    try:

        start_time = (
            time_string
            .split("-")[0]
        )

        hour, minute = map(
            int,
            start_time.split(":")
        )

    except Exception:

        return None

    days_ahead = (
        day_of_week -
        now.isoweekday()
    ) % 7

    candidate = (
        now +
        timedelta(days=days_ahead)
    ).replace(
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0
    )

    if candidate <= now:

        candidate += timedelta(
            days=7
        )

    return candidate


def format_date_for_user(dt):

    if not dt:
        return "дата не определена"

    return dt.strftime(
        "%d.%m.%Y"
    )


def cancellation_allowed(
    training
):

    training_datetime = (
        get_next_training_datetime(
            training
        )
    )

    if not training_datetime:
        return False

    now = datetime.now(
        TIMEZONE
    )

    remaining = (
        training_datetime -
        now
    )

    return remaining >= timedelta(
        hours=24
    )


def hours_until_training(
    training
):

    training_datetime = (
        get_next_training_datetime(
            training
        )
    )

    if not training_datetime:
        return 0

    now = datetime.now(
        TIMEZONE
    )

    seconds = (
        training_datetime -
        now
    ).total_seconds()

    return max(
        int(seconds // 3600),
        0
    )


# =========================================================
# ФОРМАТИРОВАНИЕ
# =========================================================

def format_training_title(
    training
):

    title = training["title"]

    if training["level"]:

        title += (
            f" — {training['level']}"
        )

    if training["age_group"]:

        title += (
            f" ({training['age_group']})"
        )

    return title


def format_training_info(
    training
):

    registered = get_registration_count(
        training["id"]
    )

    available = max(
        training["capacity"] -
        registered,
        0
    )

    next_datetime = (
        get_next_training_datetime(
            training
        )
    )

    category = (
        "👶 Детская"
        if training["category"] == "child"
        else "👨 Взрослая"
    )

    lines = [

        f"🏐 {format_training_title(training)}",
        "",
        category,
        f"📅 {DAY_NAMES_REVERSE.get(training['day_of_week'], '')}",
        f"🗓 {format_date_for_user(next_datetime)}",
        f"🕐 {training['time']}",
        f"👨‍🏫 Тренер: {training['trainer']}",
        f"💰 Стоимость: {training['price']} ₽",
        f"👥 Свободно: {available} из {training['capacity']}",
        ""
    ]

    if registered == 0:

        lines.append(
            "👤 Пока никто не записан."
        )

    else:

        lines.append(
            f"👤 Записано: {registered}"
        )

        lines.append("")

        registrations = get_registrations(
            training["id"]
        )

        for number, registration in enumerate(
            registrations,
            1
        ):

            name = (
                registration["name"]
                or
                f"Участник "
                f"{registration['user_id']}"
            )

            lines.append(
                f"{number}. {name}"
            )

    if available == 0:

        lines.append("")
        lines.append(
            "❌ Свободных мест нет."
        )

    return "\n".join(lines)


def format_schedule(
    category=None
):

    trainings = get_trainings()

    if category:

        trainings = [
            training
            for training in trainings
            if training["category"] ==
            category
        ]

    if not trainings:

        return (
            "📅 Расписание пока пустое."
        )

    if category == "child":

        title = (
            "👶 ДЕТСКОЕ РАСПИСАНИЕ"
        )

    elif category == "adult":

        title = (
            "👨 ВЗРОСЛОЕ РАСПИСАНИЕ"
        )

    else:

        title = (
            "📅 РАСПИСАНИЕ VOLLEY WAVE"
        )

    lines = [
        title,
        "",
        "Базовое расписание:"
    ]

    current_day = None

    for training in trainings:

        day = training[
            "day_of_week"
        ]

        if day != current_day:

            current_day = day

            lines.append("")
            lines.append(
                f"━━ {DAYS.get(day, '')} ━━"
            )

        registered = get_registration_count(
            training["id"]
        )

        available = max(
            training["capacity"] -
            registered,
            0
        )

        lines.append("")

        lines.append(
            f"🕐 {training['time']} — "
            f"{format_training_title(training)}"
        )

        lines.append(
            f"👨‍🏫 {training['trainer']}"
        )

        lines.append(
            f"💰 {training['price']} ₽ | "
            f"👥 свободно: {available}"
        )

    return "\n".join(lines)


def format_my_trainings(
    user_id
):

    registrations = get_user_registrations(
        user_id
    )

    if not registrations:

        return (
            "👤 МОИ ТРЕНИРОВКИ\n\n"
            "У вас пока нет записей."
        ), None

    lines = [
        "👤 МОИ ТРЕНИРОВКИ",
        ""
    ]

    for registration in registrations:

        training = get_training_by_id(
            registration["training_id"]
        )

        if not training:
            continue

        next_datetime = (
            get_next_training_datetime(
                training
            )
        )

        lines.append(
            f"🏐 {format_training_title(training)}"
        )

        lines.append(
            f"📅 {DAY_NAMES_REVERSE.get(training['day_of_week'], '')}"
        )

        lines.append(
            f"🗓 {format_date_for_user(next_datetime)}"
        )

        lines.append(
            f"🕐 {training['time']}"
        )

        lines.append(
            f"👨‍🏫 {training['trainer']}"
        )

        lines.append(
            f"💰 {training['price']} ₽"
        )

        lines.append("")

    return (
        "\n".join(lines),
        registrations
    )


# =========================================================
# ТЕЛЕФОН
# =========================================================

def normalize_phone(text):

    cleaned = re.sub(
        r"[^\d+]",
        "",
        text
    )

    if (
        cleaned.startswith("8")
        and len(cleaned) == 11
    ):

        cleaned = (
            "+7" +
            cleaned[1:]
        )

    elif (
        cleaned.startswith("7")
        and len(cleaned) == 11
    ):

        cleaned = "+" + cleaned

    if re.fullmatch(
        r"\+7\d{10}",
        cleaned
    ):

        return cleaned

    return None


# =========================================================
# ADMIN
# =========================================================

def is_admin(user_id):

    return user_id in ADMIN_IDS


def admin_training_text(
    training
):

    registrations = get_registrations(
        training["id"]
    )

    available = max(
        training["capacity"] -
        len(registrations),
        0
    )

    next_datetime = (
        get_next_training_datetime(
            training
        )
    )

    lines = [

        f"⚙️ ТРЕНИРОВКА #{training['id']}",
        "",
        f"🏐 {training['title']}",
        f"🗓 {DAY_NAMES_REVERSE.get(training['day_of_week'], '')}",
        f"📅 {format_date_for_user(next_datetime)}",
        f"🕐 {training['time']}",
        (
            "👤 Тип: "
            + (
                "Дети"
                if training["category"] == "child"
                else "Взрослые"
            )
        ),
        (
            "🎯 Уровень: "
            + (
                training["level"]
                or
                "не указан"
            )
        ),
        (
            "👶 Возраст: "
            + (
                training["age_group"]
                or
                "не указан"
            )
        ),
        f"👨‍🏫 Тренер: {training['trainer']}",
        f"💰 Цена: {training['price']} ₽",
        f"👥 Мест: {training['capacity']}",
        f"📝 Записано: {len(registrations)}",
        f"🟢 Свободно: {available}",
        ""
    ]

    if registrations:

        lines.append(
            "СПИСОК УЧАСТНИКОВ:"
        )

        for number, registration in enumerate(
            registrations,
            1
        ):

            name = (
                registration["name"]
                or
                f"ID {registration['user_id']}"
            )

            phone = (
                registration["phone"]
                or
                "телефон не указан"
            )

            lines.append(
                f"{number}. {name} — {phone}"
            )

    else:

        lines.append(
            "Участников пока нет."
        )

    return "\n".join(lines)


def send_admin_schedule(
    user_id
):

    trainings = get_trainings()

    if not trainings:

        send_message(
            user_id,
            "📅 Расписание пустое.",
            admin_keyboard()
        )

        return

    buttons = []

    for training in trainings:

        category = (
            "👶"
            if training["category"] == "child"
            else "👨"
        )

        label = (
            f"{category} #{training['id']} "
            f"{training['time']} "
            f"{training['title'][:20]}"
        )

        buttons.append(
            [
                button(label)
            ]
        )

    buttons.append(
        [
            button("⬅️ Админ-панель")
        ]
    )

    send_message(
        user_id,
        "⚙️ УПРАВЛЕНИЕ РАСПИСАНИЕМ\n\n"
        "Выберите тренировку:",
        make_keyboard(buttons)
    )


def admin_statistics():

    connection = get_connection()

    trainings_count = connection.execute(
        "SELECT COUNT(*) FROM trainings"
    ).fetchone()[0]

    clients_count = connection.execute(
        """
        SELECT COUNT(DISTINCT user_id)
        FROM registrations
        """
    ).fetchone()[0]

    registrations_count = connection.execute(
        """
        SELECT COUNT(*)
        FROM registrations
        """
    ).fetchone()[0]

    questions_count = connection.execute(
        """
        SELECT COUNT(*)
        FROM questions
        WHERE answered = 0
        """
    ).fetchone()[0]

    connection.close()

    return (
        "📊 ОБЩАЯ ИНФОРМАЦИЯ\n\n"
        f"🏐 Тренировок в расписании: "
        f"{trainings_count}\n"
        f"👥 Клиентов: {clients_count}\n"
        f"📝 Всего записей: "
        f"{registrations_count}\n"
        f"❓ Неотвеченных вопросов: "
        f"{questions_count}"
    )


# =========================================================
# CALLBACK
# =========================================================

@app.route(
    "/callback",
    methods=["POST"]
)
def callback():

    data = request.json or {}

    print(
        "VK EVENT:",
        data
    )

    if SECRET_KEY:

        if data.get("secret") != SECRET_KEY:

            return (
                "invalid secret",
                403
            )

    if data.get("type") == "confirmation":

        return (
            CONFIRMATION_TOKEN
            or
            ""
        )

    if data.get("type") != "message_new":

        return "ok"

    obj = data.get(
        "object",
        {}
    )

    message = obj.get(
        "message",
        {}
    )

    user_id = message.get(
        "from_id"
    )

    text = message.get(
        "text",
        ""
    ).strip()

    print(
        "USER ID:",
        user_id
    )

    print(
        "TEXT:",
        text
    )

    if not user_id:

        return "ok"

    current_state = get_state(
        user_id
    )

    state = current_state[
        "state"
    ]

    state_data = current_state[
        "data"
    ]


    # =====================================================
    # ВВОД ТЕЛЕФОНА
    # =====================================================

    if state == "registration_phone":

        phone = normalize_phone(
            text
        )

        if not phone:

            send_message(
                user_id,
                "❌ Не удалось распознать номер.\n\n"
                "Введите номер например:\n"
                "+79991234567"
            )

            return "ok"

        training_id = state_data.get(
            "training_id"
        )

        training = get_training_by_id(
            training_id
        )

        if not training:

            clear_state(user_id)

            send_message(
                user_id,
                "❌ Тренировка больше недоступна.",
                main_keyboard()
            )

            return "ok"

        if user_is_registered(
            training_id,
            user_id
        ):

            clear_state(user_id)

            send_message(
                user_id,
                "ℹ️ Вы уже записаны.",
                main_keyboard()
            )

            return "ok"

        registered = get_registration_count(
            training_id
        )

        if registered >= training["capacity"]:

            clear_state(user_id)

            send_message(
                user_id,
                "❌ Пока вы вводили номер, "
                "места закончились.",
                main_keyboard()
            )

            return "ok"

        user_name = get_vk_user_name(
            user_id
        )

        success = add_registration(
            training_id,
            user_id,
            user_name,
            phone
        )

        clear_state(user_id)

        if success:

            available = max(
                training["capacity"] -
                get_registration_count(
                    training_id
                ),
                0
            )

            send_message(
                user_id,

                "✅ Вы записаны!\n\n"
                f"🏐 "
                f"{format_training_title(training)}\n"
                f"📅 "
                f"{DAY_NAMES_REVERSE.get(training['day_of_week'], '')}\n"
                f"🕐 {training['time']}\n"
                f"👨‍🏫 {training['trainer']}\n"
                f"💰 {training['price']} ₽\n\n"
                f"👥 Свободных мест: "
                f"{available}",

                main_keyboard()
            )

        else:

            send_message(
                user_id,
                "ℹ️ Вы уже записаны.",
                main_keyboard()
            )

        return "ok"


    # =====================================================
    # ВОПРОС
    # =====================================================

    if state == "question":

        user_name = get_vk_user_name(
            user_id
        )

        add_question(
            user_id,
            user_name,
            text
        )

        clear_state(
            user_id
        )

        send_message(
            user_id,

            "✅ Вопрос отправлен.\n\n"
            "Администратор VOLLEY WAVE "
            "ответит вам.",

            main_keyboard()
        )

        admin_message = (
            "❓ НОВЫЙ ВОПРОС\n\n"
            f"👤 {user_name}\n"
            f"VK ID: {user_id}\n\n"
            f"{text}"
        )

        for admin_id in ADMIN_IDS:

            send_message(
                admin_id,
                admin_message,
                admin_keyboard()
            )

        return "ok"


    # =====================================================
    # АДМИН: ДОБАВЛЕНИЕ
    # =====================================================

    if (
        is_admin(user_id)
        and
        state == "admin_add"
    ):

        step = state_data.get(
            "step"
        )

        if step == "day":

            if text not in DAY_NAMES:

                send_message(
                    user_id,
                    "Выберите день кнопкой.",
                    days_keyboard()
                )

                return "ok"

            state_data["day"] = (
                DAY_NAMES[text]
            )

            state_data["step"] = "time"

            set_state(
                user_id,
                "admin_add",
                state_data
            )

            send_message(
                user_id,
                "🕐 Введите время.\n\n"
                "Например:\n"
                "19:00-20:30"
            )

            return "ok"

        if step == "time":

            if not re.fullmatch(
                r"\d{2}:\d{2}-\d{2}:\d{2}",
                text
            ):

                send_message(
                    user_id,
                    "❌ Неверный формат.\n\n"
                    "Введите например:\n"
                    "19:00-20:30"
                )

                return "ok"

            state_data["time"] = text
            state_data["step"] = "title"

            set_state(
                user_id,
                "admin_add",
                state_data
            )

            send_message(
                user_id,
                "🏐 Введите название тренировки."
            )

            return "ok"

        if step == "title":

            state_data["title"] = text
            state_data["step"] = "category"

            set_state(
                user_id,
                "admin_add",
                state_data
            )

            send_message(
                user_id,
                "👤 Выберите тип тренировки:",
                make_keyboard([
                    [
                        button("👨 Взрослые"),
                        button("👶 Дети")
                    ]
                ])
            )

            return "ok"

        if step == "category":

            if text == "👶 Дети":

                category = "child"

            elif text == "👨 Взрослые":

                category = "adult"

            else:

                send_message(
                    user_id,
                    "Выберите тип кнопкой."
                )

                return "ok"

            state_data["category"] = category
            state_data["step"] = "level"

            set_state(
                user_id,
                "admin_add",
                state_data
            )

            send_message(
                user_id,
                "🎯 Введите уровень.\n\n"
                "Если не нужен — напишите:\n"
                "нет"
            )

            return "ok"

        if step == "level":

            state_data["level"] = (
                ""
                if text.lower() == "нет"
                else text
            )

            state_data["step"] = "age"

            set_state(
                user_id,
                "admin_add",
                state_data
            )

            send_message(
                user_id,
                "👶 Введите возрастную группу.\n\n"
                "Например:\n"
                "11-14 лет\n\n"
                "Если не нужна — напишите:\n"
                "нет"
            )

            return "ok"

        if step == "age":

            state_data["age_group"] = (
                ""
                if text.lower() == "нет"
                else text
            )

            state_data["step"] = "trainer"

            set_state(
                user_id,
                "admin_add",
                state_data
            )

            send_message(
                user_id,
                "👨‍🏫 Введите имя тренера."
            )

            return "ok"

        if step == "trainer":

            state_data["trainer"] = text
            state_data["step"] = "price"

            set_state(
                user_id,
                "admin_add",
                state_data
            )

            send_message(
                user_id,
                "💰 Введите стоимость в рублях.\n\n"
                "Например:\n"
                "1200"
            )

            return "ok"

        if step == "price":

            if not text.isdigit():

                send_message(
                    user_id,
                    "❌ Введите стоимость числом."
                )

                return "ok"

            state_data["price"] = int(text)
            state_data["step"] = "capacity"

            set_state(
                user_id,
                "admin_add",
                state_data
            )

            send_message(
                user_id,
                "👥 Введите количество мест.\n\n"
                "Например:\n"
                "10"
            )

            return "ok"

        if step == "capacity":

            if not text.isdigit():

                send_message(
                    user_id,
                    "❌ Введите количество мест числом."
                )

                return "ok"

            state_data["capacity"] = int(text)

            training_id = create_training(
                state_data["day"],
                state_data["time"],
                state_data["title"],
                state_data["level"],
                state_data["age_group"],
                state_data["price"],
                state_data["capacity"],
                state_data["category"],
                state_data["trainer"]
            )

            clear_state(user_id)

            send_message(
                user_id,
                "✅ Тренировка создана!\n\n"
                f"ID: #{training_id}",
                admin_keyboard()
            )

            return "ok"


    # =====================================================
    # АДМИН: РЕДАКТИРОВАНИЕ
    # =====================================================

    if (
        is_admin(user_id)
        and
        state == "admin_edit"
    ):

        training_id = state_data.get(
            "training_id"
        )

        field = state_data.get(
            "field"
        )

        if field:

            training = get_training_by_id(
                training_id
            )

            if not training:

                clear_state(user_id)

                send_message(
                    user_id,
                    "❌ Тренировка не найдена.",
                    admin_keyboard()
                )

                return "ok"

            value = text

            if field == "day_of_week":

                if text not in DAY_NAMES:

                    send_message(
                        user_id,
                        "Выберите день кнопкой.",
                        days_keyboard()
                    )

                    return "ok"

                value = DAY_NAMES[text]

            elif field == "price":

                if not text.isdigit():

                    send_message(
                        user_id,
                        "Введите цену числом."
                    )

                    return "ok"

                value = int(text)

            elif field == "capacity":

                if not text.isdigit():

                    send_message(
                        user_id,
                        "Введите количество мест числом."
                    )

                    return "ok"

                value = int(text)

            elif field == "category":

                if text == "👶 Дети":

                    value = "child"

                elif text == "👨 Взрослые":

                    value = "adult"

                else:

                    send_message(
                        user_id,
                        "Выберите тип кнопкой."
                    )

                    return "ok"

            elif field in {
                "level",
                "age_group"
            }:

                if text.lower() == "нет":
                    value = ""

            update_training(
                training_id,
                field,
                value
            )

            clear_state(user_id)

            updated_training = get_training_by_id(
                training_id
            )

            send_message(
                user_id,
                "✅ Изменение сохранено.\n\n"
                +
                admin_training_text(
                    updated_training
                ),
                admin_training_keyboard()
            )

            return "ok"


    # =====================================================
    # ПРИВЕТ
    # =====================================================

    if text.lower() == "привет":

        clear_state(user_id)

        send_message(
            user_id,

            "Привет! 👋\n\n"
            "Добро пожаловать в VOLLEY WAVE 🏐\n"
            "Выберите нужный раздел:",

            main_keyboard()
        )

        return "ok"


    # =====================================================
    # АДМИН-ПАНЕЛЬ
    # =====================================================

    if text == "⚙️ Админ-панель":

        if not is_admin(user_id):

            send_message(
                user_id,
                "❌ Доступ запрещён.",
                main_keyboard()
            )

            return "ok"

        clear_state(user_id)

        send_message(
            user_id,
            "⚙️ АДМИН-ПАНЕЛЬ\n\n"
            "Выберите действие:",
            admin_keyboard()
        )

        return "ok"


    # =====================================================
    # АДМИН: УПРАВЛЕНИЕ РАСПИСАНИЕМ
    # =====================================================

    if text == "📅 Управление расписанием":

        if not is_admin(user_id):

            send_message(
                user_id,
                "❌ Доступ запрещён.",
                main_keyboard()
            )

            return "ok"

        clear_state(user_id)

        send_admin_schedule(
            user_id
        )

        return "ok"


    # =====================================================
    # АДМИН: ДОБАВИТЬ ТРЕНИРОВКУ
    # =====================================================

    if text == "➕ Добавить тренировку":

        if not is_admin(user_id):

            send_message(
                user_id,
                "❌ Доступ запрещён.",
                main_keyboard()
            )

            return "ok"

        set_state(
            user_id,
            "admin_add",
            {
                "step": "day"
            }
        )

        send_message(
            user_id,
            "➕ ДОБАВЛЕНИЕ ТРЕНИРОВКИ\n\n"
            "Выберите день:",
            days_keyboard()
        )

        return "ok"


    # =====================================================
    # АДМИН: СТАТИСТИКА
    # =====================================================

    if text == "📊 Общая информация":

        if not is_admin(user_id):

            send_message(
                user_id,
                "❌ Доступ запрещён.",
                main_keyboard()
            )

            return "ok"

        send_message(
            user_id,
            admin_statistics(),
            admin_keyboard()
        )

        return "ok"


    # =====================================================
    # АДМИН: ЗАПИСИ
    # =====================================================

    if text == "👥 Записи на тренировки":

        if not is_admin(user_id):

            send_message(
                user_id,
                "❌ Доступ запрещён.",
                main_keyboard()
            )

            return "ok"

        clear_state(user_id)

        trainings = get_trainings()

        buttons = []

        for training in trainings:

            registered = get_registration_count(
                training["id"]
            )

            buttons.append(
                [
                    button(
                        f"#{training['id']} "
                        f"{training['time']} "
                        f"({registered})"
                    )
                ]
            )

        buttons.append(
            [
                button("⬅️ Админ-панель")
            ]
        )

        send_message(
            user_id,
            "👥 ЗАПИСИ НА ТРЕНИРОВКИ\n\n"
            "Выберите тренировку:",
            make_keyboard(buttons)
        )

        return "ok"


    # =====================================================
    # АДМИН: ВЫБОР ТРЕНИРОВКИ
    # =====================================================

    if is_admin(user_id):

        match = re.match(
            r"^(?:👨|👶)?\s*#(\d+)",
            text
        )

        if match:

            training_id = int(
                match.group(1)
            )

            training = get_training_by_id(
                training_id
            )

            if training:

                set_state(
                    user_id,
                    None,
                    {
                        "training_id":
                            training_id
                    }
                )

                send_message(
                    user_id,
                    admin_training_text(
                        training
                    ),
                    admin_training_keyboard()
                )

                return "ok"


    # =====================================================
    # АДМИН: ИЗМЕНИТЬ
    # =====================================================

    if text == "✏️ Изменить тренировку":

        if not is_admin(user_id):

            send_message(
                user_id,
                "❌ Доступ запрещён.",
                main_keyboard()
            )

            return "ok"

        previous = get_state(
            user_id
        )

        training_id = previous[
            "data"
        ].get(
            "training_id"
        )

        if not training_id:

            send_message(
                user_id,
                "Сначала выберите тренировку.",
                admin_keyboard()
            )

            return "ok"

        send_message(
            user_id,
            "✏️ Что изменить?",
            admin_edit_keyboard()
        )

        return "ok"


    # =====================================================
    # АДМИН: ПОЛЯ РЕДАКТИРОВАНИЯ
    # =====================================================

    if is_admin(user_id):

        previous = get_state(
            user_id
        )

        training_id = previous[
            "data"
        ].get(
            "training_id"
        )

        edit_fields = {

            "🗓 День":
                "day_of_week",

            "🕐 Время":
                "time",

            "🏐 Название":
                "title",

            "👨‍🏫 Тренер":
                "trainer",

            "💰 Цена":
                "price",

            "👥 Места":
                "capacity",

            "🎯 Уровень":
                "level",

            "👶 Возраст":
                "age_group",

            "👤 Тип":
                "category"
        }

        if (
            text in edit_fields
            and
            training_id
        ):

            field = edit_fields[text]

            if field == "day_of_week":

                set_state(
                    user_id,
                    "admin_edit",
                    {
                        "training_id":
                            training_id,
                        "field":
                            field
                    }
                )

                send_message(
                    user_id,
                    "🗓 Выберите новый день:",
                    days_keyboard()
                )

                return "ok"

            if field == "category":

                set_state(
                    user_id,
                    "admin_edit",
                    {
                        "training_id":
                            training_id,
                        "field":
                            field
                    }
                )

                send_message(
                    user_id,
                    "👤 Выберите тип:",
                    make_keyboard([
                        [
                            button("👨 Взрослые"),
                            button("👶 Дети")
                        ]
                    ])
                )

                return "ok"

            set_state(
                user_id,
                "admin_edit",
                {
                    "training_id":
                        training_id,
                    "field":
                        field
                }
            )

            prompts = {

                "time":
                    "🕐 Введите новое время.\n"
                    "Например: 19:00-20:30",

                "title":
                    "🏐 Введите новое название.",

                "trainer":
                    "👨‍🏫 Введите имя тренера.",

                "price":
                    "💰 Введите новую стоимость числом.",

                "capacity":
                    "👥 Введите новое количество мест.",

                "level":
                    "🎯 Введите уровень.\n"
                    "Если не нужен — напишите «нет».",

                "age_group":
                    "👶 Введите возрастную группу.\n"
                    "Если не нужна — напишите «нет»."
            }

            send_message(
                user_id,
                prompts.get(
                    field,
                    "Введите новое значение."
                )
            )

            return "ok"


    # =====================================================
    # АДМИН: УДАЛИТЬ
    # =====================================================

    if text == "🗑 Удалить тренировку":

        if not is_admin(user_id):

            send_message(
                user_id,
                "❌ Доступ запрещён.",
                main_keyboard()
            )

            return "ok"

        previous = get_state(
            user_id
        )

        training_id = previous[
            "data"
        ].get(
            "training_id"
        )

        if not training_id:

            send_message(
                user_id,
                "Сначала выберите тренировку.",
                admin_keyboard()
            )

            return "ok"

        training = get_training_by_id(
            training_id
        )

        if training:

            delete_training(
                training_id
            )

            clear_state(user_id)

            send_message(
                user_id,
                "🗑 Тренировка удалена.",
                admin_keyboard()
            )

        return "ok"


    # =====================================================
    # АДМИН: НАЗАД
    # =====================================================

    if text == "⬅️ Админ-панель":

        if is_admin(user_id):

            clear_state(user_id)

            send_message(
                user_id,
                "⚙️ Админ-панель:",
                admin_keyboard()
            )

        return "ok"


    # =====================================================
    # ЗАПИСАТЬСЯ
    # =====================================================

    if text == "🏐 Записаться":

        clear_state(user_id)

        send_message(
            user_id,
            "🏐 Запись на тренировку\n\n"
            "Выберите категорию:",
            schedule_type_keyboard()
        )

        return "ok"


    # =====================================================
    # РАСПИСАНИЕ
    # =====================================================

    if text == "📅 Расписание":

        clear_state(user_id)

        send_message(
            user_id,
            "📅 Какое расписание показать?",
            schedule_type_keyboard()
        )

        return "ok"


    # =====================================================
    # ВЗРОСЛЫЕ
    # =====================================================

    if text == "👨 Взрослые":

        clear_state(user_id)

        set_state(
            user_id,
            "select_day",
            {
                "category": "adult"
            }
        )

        send_message(
            user_id,
            "👨 ВЗРОСЛЫЕ\n\n"
            "Выберите день:",
            days_keyboard()
        )

        return "ok"


    # =====================================================
    # ДЕТИ
    # =====================================================

    if text == "👶 Дети":

        clear_state(user_id)

        set_state(
            user_id,
            "select_day",
            {
                "category": "child"
            }
        )

        send_message(
            user_id,
            "👶 ДЕТИ\n\n"
            "Выберите день:",
            days_keyboard()
        )

        return "ok"


    # =====================================================
    # ВЫБОР ДНЯ
    # =====================================================

    if text in DAY_NAMES:

        day_number = DAY_NAMES[text]

        current = get_state(
            user_id
        )

        # -------------------------------------------------
        # АДМИН: ДОБАВЛЕНИЕ
        # -------------------------------------------------

        if (
            is_admin(user_id)
            and
            current["state"] == "admin_add"
            and
            current["data"].get("step")
            == "day"
        ):

            current["data"]["day"] = (
                day_number
            )

            current["data"]["step"] = (
                "time"
            )

            set_state(
                user_id,
                "admin_add",
                current["data"]
            )

            send_message(
                user_id,
                "🕐 Введите время.\n\n"
                "Например:\n"
                "19:00-20:30"
            )

            return "ok"

        # -------------------------------------------------
        # АДМИН: РЕДАКТИРОВАНИЕ
        # -------------------------------------------------

        if (
            is_admin(user_id)
            and
            current["state"] == "admin_edit"
            and
            current["data"].get("field")
            == "day_of_week"
        ):

            training_id = current[
                "data"
            ].get(
                "training_id"
            )

            update_training(
                training_id,
                "day_of_week",
                day_number
            )

            clear_state(user_id)

            training = get_training_by_id(
                training_id
            )

            send_message(
                user_id,
                "✅ День изменён.\n\n"
                +
                admin_training_text(
                    training
                ),
                admin_training_keyboard()
            )

            return "ok"

        # -------------------------------------------------
        # ОБЫЧНЫЙ ПОЛЬЗОВАТЕЛЬ
        # -------------------------------------------------

        category = current[
            "data"
        ].get(
            "category"
        )

        if not category:

            category = "adult"

        trainings = get_trainings_by_day(
            day_number,
            category
        )

        if not trainings:

            send_message(
                user_id,
                "На этот день тренировок нет.",
                days_keyboard()
            )

            return "ok"

        set_state(
            user_id,
            "select_training",
            {
                "category": category,
                "day": day_number
            }
        )

        send_message(
            user_id,
            f"🏐 {text}\n\n"
            "Выберите тренировку:",
            training_list_keyboard(
                trainings
            )
        )

        return "ok"


    # =====================================================
    # ВЫБОР ТРЕНИРОВКИ ПО ID
    # =====================================================

    match = re.match(
        r"^(?:#)?(\d+)",
        text
    )

    if match:

        training_id = int(
            match.group(1)
        )

        training = get_training_by_id(
            training_id
        )

        if training:

            if is_admin(user_id):

                set_state(
                    user_id,
                    None,
                    {
                        "training_id":
                            training_id
                    }
                )

                send_message(
                    user_id,
                    admin_training_text(
                        training
                    ),
                    admin_training_keyboard()
                )

                return "ok"

            registered_by_user = (
                user_is_registered(
                    training_id,
                    user_id
                )
            )

            registered = get_registration_count(
                training_id
            )

            available = max(
                training["capacity"] -
                registered,
                0
            )

            send_message(
                user_id,
                format_training_info(
                    training
                ),
                training_keyboard(
                    training_id,
                    available,
                    registered_by_user
                )
            )

            return "ok"


    # =====================================================
    # ЗАПИСЬ
    # =====================================================

    if text.startswith(
        "✅ Записаться #"
    ):

        try:

            training_id = int(
                text.split("#")[1]
            )

            training = get_training_by_id(
                training_id
            )

            if not training:

                send_message(
                    user_id,
                    "❌ Тренировка не найдена.",
                    main_keyboard()
                )

                return "ok"

            if user_is_registered(
                training_id,
                user_id
            ):

                send_message(
                    user_id,
                    "ℹ️ Вы уже записаны "
                    "на эту тренировку.",
                    main_keyboard()
                )

                return "ok"

            registered = get_registration_count(
                training_id
            )

            if registered >= training[
                "capacity"
            ]:

                send_message(
                    user_id,
                    "❌ Свободных мест уже нет.",
                    main_keyboard()
                )

                return "ok"

            phone = get_user_phone(
                user_id
            )

            if not phone:

                set_state(
                    user_id,
                    "registration_phone",
                    {
                        "training_id":
                            training_id
                    }
                )

                send_message(
                    user_id,
                    "📱 Для записи нужен номер телефона.\n\n"
                    "Напишите номер в формате:\n"
                    "+79991234567"
                )

                return "ok"

            user_name = get_vk_user_name(
                user_id
            )

            success = add_registration(
                training_id,
                user_id,
                user_name,
                phone
            )

            if success:

                available = max(
                    training["capacity"] -
                    get_registration_count(
                        training_id
                    ),
                    0
                )

                send_message(
                    user_id,

                    "✅ Вы записаны!\n\n"
                    f"🏐 "
                    f"{format_training_title(training)}\n"
                    f"📅 "
                    f"{DAY_NAMES_REVERSE.get(training['day_of_week'], '')}\n"
                    f"🕐 {training['time']}\n"
                    f"👨‍🏫 {training['trainer']}\n"
                    f"💰 {training['price']} ₽\n\n"
                    f"👥 Свободных мест: "
                    f"{available}",

                    main_keyboard()
                )

            else:

                send_message(
                    user_id,
                    "ℹ️ Вы уже записаны "
                    "на эту тренировку.",
                    main_keyboard()
                )

        except Exception as error:

            print(
                "REGISTRATION ERROR:",
                error
            )

            send_message(
                user_id,
                "❌ Не удалось записать вас.",
                main_keyboard()
            )

        return "ok"


    # =====================================================
    # МОИ ТРЕНИРОВКИ
    # =====================================================

    if text == "👤 Мои тренировки":

        clear_state(user_id)

        info, registrations = (
            format_my_trainings(
                user_id
            )
        )

        if registrations:

            send_message(
                user_id,
                info,
                my_trainings_keyboard(
                    registrations
                )
            )

        else:

            send_message(
                user_id,
                info,
                main_keyboard()
            )

        return "ok"


    # =====================================================
    # ОТМЕНА ЗАПИСИ
    # =====================================================

    if text.startswith(
        "❌ Отменить #"
    ):

        try:

            training_id = int(
                text.split("#")[1]
            )

            training = get_training_by_id(
                training_id
            )

            if not training:

                send_message(
                    user_id,
                    "❌ Тренировка не найдена.",
                    main_keyboard()
                )

                return "ok"

            if not user_is_registered(
                training_id,
                user_id
            ):

                send_message(
                    user_id,
                    "ℹ️ Вы не записаны "
                    "на эту тренировку.",
                    main_keyboard()
                )

                return "ok"

            if not cancellation_allowed(
                training
            ):

                hours = hours_until_training(
                    training
                )

                send_message(
                    user_id,

                    "❌ Отмена записи невозможна.\n\n"
                    "Отменить тренировку можно "
                    "не позднее чем за 24 часа "
                    "до её начала.\n\n"
                    f"До тренировки осталось "
                    f"примерно {hours} ч.",

                    main_keyboard()
                )

                return "ok"

            deleted = delete_registration(
                training_id,
                user_id
            )

            if deleted:

                send_message(
                    user_id,

                    "✅ Запись отменена.\n\n"
                    f"🏐 "
                    f"{format_training_title(training)}\n"
                    f"📅 "
                    f"{DAY_NAMES_REVERSE.get(training['day_of_week'], '')}\n"
                    f"🕐 {training['time']}\n\n"
                    "Место снова доступно.",

                    main_keyboard()
                )

            else:

                send_message(
                    user_id,
                    "ℹ️ Запись уже отменена.",
                    main_keyboard()
                )

        except Exception as error:

            print(
                "CANCEL ERROR:",
                error
            )

            send_message(
                user_id,
                "❌ Не удалось отменить запись.",
                main_keyboard()
            )

        return "ok"


    # =====================================================
    # ЦЕНЫ
    # =====================================================

    if text == "💰 Цены":

        clear_state(user_id)

        send_message(
            user_id,

            "💰 ЦЕНЫ VOLLEY WAVE\n\n"
            "Стоимость каждой тренировки "
            "указана непосредственно "
            "в расписании.\n\n"
            "👶 Детские группы — от 600 ₽\n"
            "👨 Взрослые тренировки — от 1200 ₽",

            main_keyboard()
        )

        return "ok"


    # =====================================================
    # ДЕТСКИЕ ГРУППЫ
    # =====================================================

    if text == "👶 Детские группы":

        clear_state(user_id)

        send_message(
            user_id,

            "👶 ДЕТСКИЕ ГРУППЫ VOLLEY WAVE\n\n"
            "🏐 Тренировки проходят "
            "на песке круглый год.\n\n"
            "Возрастные направления:\n"
            "• 5–9 лет\n"
            "• 5–10 лет\n"
            "• 9–13 лет\n"
            "• 9–14 лет\n"
            "• 11–14 лет\n\n"
            "Актуальное расписание и "
            "свободные места доступны "
            "в разделе «🏐 Записаться».",

            main_keyboard()
        )

        return "ok"


    # =====================================================
    # ГДЕ ТРЕНИРУЕМСЯ
    # =====================================================

    if text == "📍 Где тренируемся":

        clear_state(user_id)

        send_message(
            user_id,

            "📍 ГДЕ ТРЕНИРУЕМСЯ\n\n"
            "🏐 VOLLEY WAVE\n\n"
            "Тренировки проходят "
            "на песке круглый год.\n\n"
            "Актуальный адрес конкретной "
            "тренировки сообщается "
            "при записи.",

            main_keyboard()
        )

        return "ok"


    # =====================================================
    # ЗАДАТЬ ВОПРОС
    # =====================================================

    if text == "❓ Задать вопрос":

        set_state(
            user_id,
            "question"
        )

        send_message(
            user_id,

            "❓ ЗАДАТЬ ВОПРОС\n\n"
            "Напишите вопрос следующим "
            "сообщением.\n\n"
            "Он будет передан "
            "администраторам VOLLEY WAVE."
        )

        return "ok"


    # =====================================================
    # ГЛАВНОЕ МЕНЮ
    # =====================================================

    if text == "🏠 Главное меню":

        clear_state(user_id)

        send_message(
            user_id,
            "🏠 Главное меню:",
            main_keyboard()
        )

        return "ok"


    # =====================================================
    # АДМИНСКИЙ ДОСТУП ИЗ ГЛАВНОГО МЕНЮ
    # =====================================================

    if (
        is_admin(user_id)
        and
        text == "⚙️ Админ-панель"
    ):

        clear_state(user_id)

        send_message(
            user_id,
            "⚙️ АДМИН-ПАНЕЛЬ:",
            admin_keyboard()
        )

        return "ok"


    # =====================================================
    # НАЗАД
    # =====================================================

    if text == "⬅️ Назад":

        clear_state(user_id)

        send_message(
            user_id,
            "🏠 Главное меню:",
            main_keyboard()
        )

        return "ok"


    # =====================================================
    # НЕИЗВЕСТНОЕ СООБЩЕНИЕ
    # =====================================================

    send_message(
        user_id,

        "Я пока не понял сообщение 🤔\n\n"
        "Выберите раздел из меню:",

        main_keyboard()
    )

    return "ok"


# =========================================================
# HOME
# =========================================================

@app.route(
    "/",
    methods=["GET"]
)
def home():

    return (
        "VOLLEY WAVE VK BOT IS RUNNING"
    )


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    port = int(
        os.getenv(
            "PORT",
            10000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
