import os
import sqlite3
import logging
import random
from datetime import datetime, date, timedelta

import requests
from flask import Flask, request

VERSION = "№5"

VK_TOKEN = os.getenv("VK_TOKEN", "")
VK_CONFIRMATION_TOKEN = os.getenv("VK_CONFIRMATION_TOKEN", "")
VK_SECRET_KEY = os.getenv("VK_SECRET_KEY", "")
VK_API_VERSION = "5.199"

GROUP_ID = 221776135
DB_NAME = "volley_wave.db"

ADMINS = {87984447, 172892670, 148372158}
ADMIN_CONTACT_ID = int(os.getenv("ADMIN_CONTACT_ID", "87984447"))

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

USER_STATES = {}

WEEKDAYS_RU = [
    "Понедельник",
    "Вторник",
    "Среда",
    "Четверг",
    "Пятница",
    "Суббота",
    "Воскресенье",
]

BACK = "⬅️ Назад"
MAIN = "🏠 Главное меню"


def db():
    conn = sqlite3.connect(DB_NAME, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            state TEXT DEFAULT 'main',
            category TEXT,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS trainings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            training_number INTEGER,
            training_date TEXT NOT NULL,
            weekday TEXT,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            category TEXT NOT NULL,
            format TEXT NOT NULL,
            level TEXT NOT NULL,
            capacity INTEGER NOT NULL,
            price INTEGER NOT NULL,
            location TEXT NOT NULL,
            active INTEGER DEFAULT 1,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            training_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            created_at TEXT,
            UNIQUE(training_id, user_id)
        )
    """)

    conn.commit()
    conn.close()

    migrate_db()


def migrate_db():
    conn = db()
    cur = conn.cursor()

    existing = {
        row["name"]
        for row in cur.execute("PRAGMA table_info(trainings)").fetchall()
    }

    additions = {
        "training_number": "INTEGER",
        "weekday": "TEXT",
        "active": "INTEGER DEFAULT 1",
        "created_at": "TEXT",
    }

    for name, definition in additions.items():
        if name not in existing:
            cur.execute(
                f"ALTER TABLE trainings ADD COLUMN {name} {definition}"
            )

    conn.commit()

    rows = cur.execute("""
        SELECT id, training_date, category, weekday
        FROM trainings
    """).fetchall()

    for row in rows:
        parsed = parse_date(row["training_date"])

        new_date = (
            parsed.isoformat()
            if parsed
            else row["training_date"]
        )

        new_weekday = (
            WEEKDAYS_RU[parsed.weekday()]
            if parsed
            else row["weekday"]
        )

        new_category = normalize_category(row["category"])

        cur.execute("""
            UPDATE trainings
            SET training_date = ?,
                weekday = ?,
                category = ?,
                active = COALESCE(active, 1)
            WHERE id = ?
        """, (
            new_date,
            new_weekday,
            new_category,
            row["id"],
        ))

    rows = cur.execute("""
        SELECT id, training_number
        FROM trainings
        ORDER BY id
    """).fetchall()

    number = 1

    for row in rows:
        if not row["training_number"]:
            cur.execute("""
                UPDATE trainings
                SET training_number = ?
                WHERE id = ?
            """, (
                number,
                row["id"],
            ))

        number += 1

    conn.commit()
    conn.close()


def parse_date(value):
    if value is None:
        return None

    if isinstance(value, date):
        return value

    value = str(value).strip()

    if not value:
        return None

    candidates = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d.%m.%Y",
        "%d/%m/%Y",
        "%d-%m-%Y",
    ]

    for fmt in candidates:
        try:
            return datetime.strptime(
                value[:10],
                fmt,
            ).date()
        except ValueError:
            pass

    try:
        return datetime.fromisoformat(
            value.replace("Z", "+00:00")
        ).date()
    except ValueError:
        return None


def normalize_category(value):
    text = str(value or "").strip().lower()

    if "дет" in text:
        return "Детская"

    if "взрос" in text:
        return "Взрослая"

    return str(value or "").strip()


def get_next_training_number(conn):
    row = conn.execute("""
        SELECT COALESCE(MAX(training_number), 0) + 1 AS n
        FROM trainings
    """).fetchone()

    return int(row["n"])


def button(label, color="secondary"):
    return {
        "action": {
            "type": "text",
            "label": str(label),
        },
        "color": color,
    }


def link_button(label, link, color="primary"):
    return {
        "action": {
            "type": "open_link",
            "link": link,
            "label": str(label),
        },
        "color": color,
    }


def keyboard(rows, inline=False):
    return {
        "one_time": False,
        "inline": inline,
        "buttons": rows,
    }


def main_keyboard(user_id=None):
    rows = [
        [
            button(
                "📅 Расписание",
                "primary",
            )
        ],
        [
            button(
                "📝 Записаться",
                "primary",
            )
        ],
        [
            button(
                "💰 Цены",
                "secondary",
            )
        ],
        [
            button(
                "🏐 Индивидуальная тренировка",
                "secondary",
            )
        ],
    ]

    if user_id in ADMINS:
        rows.append([
            button(
                "⚙️ Админ-панель",
                "secondary",
            )
        ])

    return keyboard(rows)


def category_keyboard():
    return keyboard([
        [
            button("👧 Детские")
        ],
        [
            button("🧑 Взрослые")
        ],
        [
            button(BACK)
        ],
    ])


def admin_keyboard():
    return keyboard([
        [
            button(
                "➕ Создать тренировку",
                "primary",
            )
        ],
        [
            button("📋 Все тренировки")
        ],
        [
            button("👥 Записи")
        ],
        [
            button(BACK)
        ],
    ])


def create_category_keyboard():
    return keyboard([
        [
            button("👧 Детская")
        ],
        [
            button("🧑 Взрослая")
        ],
        [
            button(BACK)
        ],
    ])


def format_keyboard():
    return keyboard([
        [
            button("Техничка")
        ],
        [
            button("MIXED")
        ],
        [
            button("Женская")
        ],
        [
            button("Мужская")
        ],
        [
            button("Общая")
        ],
        [
            button(BACK)
        ],
    ])


def level_keyboard():
    return keyboard([
        [
            button("Начинающие")
        ],
        [
            button("Средний")
        ],
        [
            button("Продвинутый")
        ],
        [
            button("Любой уровень")
        ],
        [
            button(BACK)
        ],
    ])


def send_vk(user_id, message, kb=None):
    if not VK_TOKEN:
        logging.error("VK_TOKEN is empty")
        return False

    payload = {
        "access_token": VK_TOKEN,
        "v": VK_API_VERSION,
        "user_id": int(user_id),
        "random_id": random.randint(
            1,
            2147483646,
        ),
        "message": str(message),
    }

    if kb is not None:
        payload["keyboard"] = kb

    try:
        response = requests.post(
            "https://api.vk.com/method/messages.send",
            data=payload,
            timeout=15,
        )

        data = response.json()

        if "error" in data:
            logging.error(
                "VK send error: %s",
                data,
            )
            return False

        return True

    except Exception:
        logging.exception(
            "VK send exception"
        )
        return False


def set_state(user_id, state, **data):
    USER_STATES[user_id] = {
        "state": state,
        **data,
    }

    conn = db()

    conn.execute("""
        INSERT INTO users(
            user_id,
            state,
            created_at
        )
        VALUES (?, ?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET
            state = excluded.state
    """, (
        user_id,
        state,
        datetime.now().isoformat(),
    ))

    conn.commit()
    conn.close()


def clear_state(user_id):
    USER_STATES.pop(
        user_id,
        None,
    )

    conn = db()

    conn.execute("""
        INSERT INTO users(
            user_id,
            state,
            created_at
        )
        VALUES (?, 'main', ?)
        ON CONFLICT(user_id)
        DO UPDATE SET
            state = 'main'
    """, (
        user_id,
        datetime.now().isoformat(),
    ))

    conn.commit()
    conn.close()


def get_state(user_id):
    if user_id in USER_STATES:
        return USER_STATES[user_id]

    conn = db()

    row = conn.execute("""
        SELECT state, category
        FROM users
        WHERE user_id = ?
    """, (
        user_id,
    )).fetchone()

    conn.close()

    if not row:
        state = {
            "state": "main"
        }
    else:
        state = {
            "state": row["state"] or "main",
            "category": row["category"],
        }

    USER_STATES[user_id] = state

    return state


def save_user_category(user_id, category):
    conn = db()

    conn.execute("""
        INSERT INTO users(
            user_id,
            category,
            state,
            created_at
        )
        VALUES (?, ?, 'main', ?)
        ON CONFLICT(user_id)
        DO UPDATE SET
            category = excluded.category
    """, (
        user_id,
        category,
        datetime.now().isoformat(),
    ))

    conn.commit()
    conn.close()


def parse_time(value):
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

    if not 0 <= hour <= 23:
        return None

    if not 0 <= minute <= 59:
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


def price_for(category, capacity):
    category = normalize_category(category)
    capacity = int(capacity)

    if category == "Детская":
        return 600

    if capacity < 4:
        return None

    if capacity >= 6:
        return 1000

    return 1200


def get_future_trainings(category=None, days=365):
    today = date.today()
    last_day = today + timedelta(days=days)

    conn = db()

    rows = conn.execute("""
        SELECT *
        FROM trainings
        WHERE COALESCE(active, 1) = 1
    """).fetchall()

    conn.close()

    result = []

    for row in rows:
        training_date = parse_date(
            row["training_date"]
        )

        if not training_date:
            logging.warning(
                "Invalid training date: id=%s value=%r",
                row["id"],
                row["training_date"],
            )
            continue

        if training_date < today:
            continue

        if training_date > last_day:
            continue

        row_category = normalize_category(
            row["category"]
        )

        if category:
            if row_category != normalize_category(category):
                continue

        result.append({
            "id": row["id"],
            "training_number": (
                row["training_number"]
                or row["id"]
            ),
            "training_date": training_date,
            "weekday": WEEKDAYS_RU[
                training_date.weekday()
            ],
            "start_time": (
                parse_time(row["start_time"])
                or str(row["start_time"])
            ),
            "end_time": (
                parse_time(row["end_time"])
                or str(row["end_time"])
            ),
            "category": row_category,
            "format": row["format"],
            "level": row["level"],
            "capacity": int(row["capacity"]),
            "price": int(row["price"]),
            "location": row["location"],
            "active": row["active"],
        })

    result.sort(
        key=lambda x: (
            x["training_date"],
            time_to_minutes(
                x["start_time"]
            ),
            x["id"],
        )
    )

    return result


def get_training(training_id):
    if not training_id:
        return None

    conn = db()

    row = conn.execute("""
        SELECT *
        FROM trainings
        WHERE id = ?
    """, (
        training_id,
    )).fetchone()

    conn.close()

    return row


def registered_count(training_id):
    conn = db()

    row = conn.execute("""
        SELECT COUNT(*) AS count
        FROM registrations
        WHERE training_id = ?
    """, (
        training_id,
    )).fetchone()

    conn.close()

    return int(row["count"])


def free_places(training_id):
    row = get_training(training_id)

    if not row:
        return 0

    return max(
        int(row["capacity"])
        - registered_count(training_id),
        0,
    )


def training_text(training):
    if isinstance(training, sqlite3.Row):
        training_date = parse_date(
            training["training_date"]
        )

        number = (
            training["training_number"]
            or training["id"]
        )

        start = (
            parse_time(training["start_time"])
            or str(training["start_time"])
        )

        end = (
            parse_time(training["end_time"])
            or str(training["end_time"])
        )

        fmt = training["format"]
        level = training["level"]
        capacity = int(training["capacity"])
        price = int(training["price"])
        location = training["location"]

    else:
        training_date = training["training_date"]
        number = training["training_number"]
        start = training["start_time"]
        end = training["end_time"]
        fmt = training["format"]
        level = training["level"]
        capacity = int(training["capacity"])
        price = int(training["price"])
        location = training["location"]

    weekday = (
        WEEKDAYS_RU[
            training_date.weekday()
        ]
        if training_date
        else ""
    )

    free = free_places(
        training["id"]
    )

    date_text = (
        training_date.strftime(
            "%d.%m.%Y"
        )
        if training_date
        else "—"
    )

    return (
        f"🏐 Тренировка №{number}\n\n"
        f"📅 Дата: {date_text}\n"
        f"🗓 {weekday}\n"
        f"🕐 Время: {start}–{end}\n"
        f"🏐 Формат: {fmt}\n"
        f"📊 Уровень: {level}\n"
        f"👥 Мест: {capacity}\n"
        f"💳 Стоимость: {price} ₽\n"
        f"📍 Место: {location}\n"
        f"Свободно мест: {free}"
    )


def show_main(user_id):
    clear_state(user_id)

    send_vk(
        user_id,
        "🏐 VOLLEY WAVE\n\n"
        "Выберите действие:",
        main_keyboard(user_id),
    )


def show_prices(user_id):
    set_state(
        user_id,
        "prices",
    )

    send_vk(
        user_id,
        "💰 Стоимость тренировок\n\n"
        "👧 Детские — 600 ₽ за тренировку.\n\n"
        "🧑 Взрослые:\n"
        "• минимум 4 человека;\n"
        "• 4–5 человек — 1200 ₽ с человека;\n"
        "• от 6 человек — 1000 ₽ с человека.",
        keyboard([
            [
                button(BACK)
            ]
        ])
    )


def show_individual(user_id):
    set_state(
        user_id,
        "individual",
    )

    link = (
        f"https://vk.com/id{ADMIN_CONTACT_ID}"
    )

    send_vk(
        user_id,
        "🏐 Индивидуальная тренировка\n\n"
        "По индивидуальной тренировке "
        "напишите администратору. "
        "Мы согласуем дату, время и формат занятия.",
        keyboard([
            [
                link_button(
                    "✉️ Написать администратору",
                    link,
                    "primary",
                )
            ],
            [
                button(BACK)
            ],
        ])
    )

    for admin in ADMINS:
        if admin != user_id:
            send_vk(
                admin,
                "🏐 Пользователь "
                f"id{user_id} интересуется "
                "индивидуальной тренировкой."
            )


def show_schedule_category(user_id):
    set_state(
        user_id,
        "schedule_category",
    )

    send_vk(
        user_id,
        "📅 Расписание\n\n"
        "Выберите направление:",
        category_keyboard(),
    )


def show_schedule(user_id, category):
    trainings = get_future_trainings(
        category
    )

    logging.info(
        "SCHEDULE user=%s category=%r found=%s",
        user_id,
        category,
        len(trainings),
    )

    if not trainings:
        send_vk(
            user_id,
            "📅 Расписание — "
            f"{normalize_category(category)}\n\n"
            "Пока подходящих тренировок нет.",
            keyboard([
                [
                    button(BACK)
                ]
            ])
        )
        return

    text = (
        "📅 Расписание — "
        f"{normalize_category(category)}\n\n"
        "Ближайшие тренировки:\n\n"
    )

    for training in trainings:
        text += (
            training_text(training)
            + "\n\n"
        )

    send_vk(
        user_id,
        text.strip(),
        keyboard([
            [
                button(BACK)
            ]
        ])
    )


def show_booking_category(user_id):
    set_state(
        user_id,
        "booking_category",
    )

    send_vk(
        user_id,
        "📝 Запись на тренировку\n\n"
        "Выберите направление:",
        category_keyboard(),
    )


def show_booking_dates(user_id, category):
    trainings = get_future_trainings(
        category
    )

    if not trainings:
        send_vk(
            user_id,
            "📝 Ближайших тренировок "
            "для записи пока нет.",
            keyboard([
                [
                    button(BACK)
                ]
            ])
        )
        return

    dates = []
    seen = set()

    for training in trainings:
        key = training[
            "training_date"
        ].isoformat()

        if key not in seen:
            seen.add(key)
            dates.append(
                training["training_date"]
            )

    rows = []

    for d in dates:
        rows.append([
            button(
                d.strftime("%d.%m.%Y")
                + " — "
                + WEEKDAYS_RU[d.weekday()]
            )
        ])

    rows.append([
        button(BACK)
    ])

    set_state(
        user_id,
        "booking_date",
        category=normalize_category(
            category
        ),
    )

    send_vk(
        user_id,
        "📅 Выберите дату:",
        keyboard(rows),
    )


def show_booking_trainings(
    user_id,
    category,
    selected_date,
):
    parsed = parse_date(
        selected_date
    )

    if not parsed:
        show_booking_dates(
            user_id,
            category,
        )
        return

    trainings = [
        x
        for x in get_future_trainings(category)
        if x["training_date"] == parsed
    ]

    if not trainings:
        send_vk(
            user_id,
            "На эту дату тренировок нет.",
            keyboard([
                [
                    button(BACK)
                ]
            ])
        )
        return

    rows = []

    for training in trainings:
        free = free_places(
            training["id"]
        )

        if free <= 0:
            label = (
                f"№{training['training_number']} "
                f"{training['start_time']}–"
                f"{training['end_time']} — НЕТ МЕСТ"
            )
        else:
            label = (
                f"№{training['training_number']} "
                f"{training['start_time']}–"
                f"{training['end_time']} — "
                f"{free} мест"
            )

        rows.append([
            button(label)
        ])

    rows.append([
        button(BACK)
    ])

    set_state(
        user_id,
        "booking_training",
        category=normalize_category(
            category
        ),
        selected_date=parsed.isoformat(),
    )

    send_vk(
        user_id,
        f"📅 {parsed.strftime('%d.%m.%Y')} — "
        f"{WEEKDAYS_RU[parsed.weekday()]}\n\n"
        "Выберите тренировку:",
        keyboard(rows),
    )


def find_training_by_label(
    category,
    selected_date,
    text,
):
    parsed = parse_date(
        selected_date
    )

    if not parsed:
        return None

    trainings = [
        x
        for x in get_future_trainings(category)
        if x["training_date"] == parsed
    ]

    for training in trainings:
        prefix = (
            f"№{training['training_number']} "
        )

        if text.startswith(prefix):
            return training

    return None


def show_booking_confirm(
    user_id,
    training,
):
    set_state(
        user_id,
        "booking_confirm",
        training_id=training["id"],
    )

    free = free_places(
        training["id"]
    )

    if free <= 0:
        send_vk(
            user_id,
            "❌ В этой тренировке "
            "уже нет свободных мест.",
            keyboard([
                [
                    button(BACK)
                ]
            ])
        )
        return

    send_vk(
        user_id,
        training_text(training)
        + "\n\nЗаписать вас?",
        keyboard([
            [
                button(
                    "✅ Записаться",
                    "primary",
                )
            ],
            [
                button(BACK)
            ],
        ])
    )


def register_user(
    user_id,
    training_id,
):
    row = get_training(
        training_id
    )

    if not row:
        return False, "Тренировка не найдена."

    if not row["active"]:
        return False, "Эта тренировка уже закрыта."

    if free_places(training_id) <= 0:
        return False, "Свободных мест больше нет."

    conn = db()

    try:
        conn.execute("""
            INSERT INTO registrations(
                training_id,
                user_id,
                created_at
            )
            VALUES (?, ?, ?)
        """, (
            training_id,
            user_id,
            datetime.now().isoformat(),
        ))

        conn.commit()

    except sqlite3.IntegrityError:
        conn.close()

        return (
            False,
            "Вы уже записаны "
            "на эту тренировку."
        )

    finally:
        conn.close()

    return True, "ok"


def notify_admin_registration(
    user_id,
    training_id,
):
    row = get_training(
        training_id
    )

    if not row:
        return

    count = registered_count(
        training_id
    )

    training_date = parse_date(
        row["training_date"]
    )

    date_text = (
        training_date.strftime(
            "%d.%m.%Y"
        )
        if training_date
        else str(row["training_date"])
    )

    message = (
        "📝 Новая запись\n\n"
        f"Пользователь: id{user_id}\n"
        f"Тренировка №"
        f"{row['training_number'] or row['id']}\n"
        f"Дата: {date_text}\n"
        f"Время: {row['start_time']}–"
        f"{row['end_time']}\n"
        f"Участников: "
        f"{count}/{row['capacity']}"
    )

    for admin in ADMINS:
        send_vk(
            admin,
            message,
        )


def show_admin(user_id):
    if user_id not in ADMINS:
        show_main(user_id)
        return

    set_state(
        user_id,
        "admin",
    )

    send_vk(
        user_id,
        "⚙️ Админ-панель",
        admin_keyboard(),
    )


def start_create_training(user_id):
    if user_id not in ADMINS:
        show_main(user_id)
        return

    set_state(
        user_id,
        "create_category",
    )

    send_vk(
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

    send_vk(
        user_id,
        "📅 Дата\n\n"
        "Введите дату в формате "
        "ДД.ММ.ГГГГ.",
        keyboard([
            [
                button(BACK)
            ]
        ])
    )


def create_ask_time(
    user_id,
    category,
    training_date,
):
    set_state(
        user_id,
        "create_time",
        category=category,
        training_date=training_date,
    )

    send_vk(
        user_id,
        "🕐 Время\n\n"
        "Введите время начала и окончания "
        "через дефис.\n\n"
        "Например: 19:00-20:30",
        keyboard([
            [
                button(BACK)
            ]
        ])
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

    send_vk(
        user_id,
        "🏐 Формат",
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

    send_vk(
        user_id,
        "📊 Уровень",
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
            "Минимум 4 человека."
        )
    else:
        message = (
            "👥 Сколько мест?\n\n"
            "Введите количество мест."
        )

    send_vk(
        user_id,
        message,
        keyboard([
            [
                button(BACK)
            ]
        ])
    )


def create_ask_location(
    user_id,
    data,
):
    price = price_for(
        data["category"],
        data["capacity"],
    )

    if price is None:
        send_vk(
            user_id,
            "❌ Для взрослой тренировки "
            "нужно минимум 4 места.",
            keyboard([
                [
                    button(BACK)
                ]
            ])
        )
        return

    data["price"] = price

    set_state(
        user_id,
        "create_location",
        **data,
    )

    send_vk(
        user_id,
        f"💳 Стоимость: {price} ₽\n\n"
        "📍 Место\n\n"
        "Введите место проведения.",
        keyboard([
            [
                button(BACK)
            ]
        ])
    )


def save_training(
    user_id,
    data,
):
    conn = db()

    number = get_next_training_number(
        conn
    )

    training_date = parse_date(
        data["training_date"]
    )

    if not training_date:
        conn.close()
        return None

    start_time = parse_time(
        data["start_time"]
    )

    end_time = parse_time(
        data["end_time"]
    )

    if not start_time or not end_time:
        conn.close()
        return None

    conn.execute("""
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
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?
        )
    """, (
        number,
        training_date.isoformat(),
        WEEKDAYS_RU[
            training_date.weekday()
        ],
        start_time,
        end_time,
        data["category"],
        data["format"],
        data["level"],
        int(data["capacity"]),
        int(data["price"]),
        data["location"],
        datetime.now().isoformat(),
    ))

    training_id = conn.execute(
        "SELECT last_insert_rowid()"
    ).fetchone()[0]

    conn.commit()
    conn.close()

    return training_id


def finish_create_training(
    user_id,
    data,
):
    training_id = save_training(
        user_id,
        data,
    )

    if not training_id:
        send_vk(
            user_id,
            "❌ Не удалось создать "
            "тренировку. Проверьте дату "
            "и время.",
            keyboard([
                [
                    button(BACK)
                ]
            ])
        )
        return

    row = get_training(
        training_id
    )

    clear_state(user_id)

    send_vk(
        user_id,
        "✅ Тренировка создана!\n\n"
        + training_text(row),
        main_keyboard(user_id),
    )


def show_all_trainings(user_id):
    trainings = get_future_trainings(
        None
    )

    if not trainings:
        send_vk(
            user_id,
            "📋 В базе нет будущих "
            "активных тренировок.",
            admin_keyboard(),
        )
        return

    text = (
        "📋 Все будущие тренировки\n\n"
    )

    for training in trainings:
        text += (
            training_text(training)
            + "\n\n"
        )

    send_vk(
        user_id,
        text.strip(),
        admin_keyboard(),
    )


def show_registration_list(user_id):
    trainings = get_future_trainings(
        None
    )

    if not trainings:
        send_vk(
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

        rows.append([
            button(
                f"№{training['training_number']} "
                f"{training['training_date'].strftime('%d.%m')} "
                f"{training['start_time']} — "
                f"{count}/{training['capacity']}"
            )
        ])

    rows.append([
        button(BACK)
    ])

    set_state(
        user_id,
        "admin_registration_training",
    )

    send_vk(
        user_id,
        "👥 Выберите тренировку:",
        keyboard(rows),
    )


def show_participants(
    user_id,
    text,
):
    trainings = get_future_trainings(
        None
    )

    selected = None

    for training in trainings:
        if text.startswith(
            f"№{training['training_number']} "
        ):
            selected = training
            break

    if not selected:
        send_vk(
            user_id,
            "Тренировка не найдена.",
            keyboard([
                [
                    button(BACK)
                ]
            ])
        )
        return

    conn = db()

    rows = conn.execute("""
        SELECT user_id, created_at
        FROM registrations
        WHERE training_id = ?
        ORDER BY id
    """, (
        selected["id"],
    )).fetchall()

    conn.close()

    if not rows:
        text_out = (
            training_text(selected)
            + "\n\n"
            "👥 Записей пока нет."
        )
    else:
        lines = [
            training_text(selected),
            "",
            f"👥 Записано: "
            f"{len(rows)}/"
            f"{selected['capacity']}",
            "",
        ]

        for index, row in enumerate(
            rows,
            1,
        ):
            lines.append(
                f"{index}. id{row['user_id']}"
            )

        text_out = "\n".join(lines)

    set_state(
        user_id,
        "admin_registration_training",
    )

    send_vk(
        user_id,
        text_out,
        keyboard([
            [
                button(BACK)
            ]
        ])
    )


def handle_create_state(
    user_id,
    state,
    text,
):
    data = get_state(user_id)

    if text == BACK:
        show_admin(user_id)
        return

    if state == "create_category":
        if text not in (
            "👧 Детская",
            "🧑 Взрослая",
        ):
            send_vk(
                user_id,
                "Выберите направление "
                "кнопкой.",
                create_category_keyboard(),
            )
            return

        category = (
            "Детская"
            if text.startswith("👧")
            else "Взрослая"
        )

        create_ask_date(
            user_id,
            category,
        )
        return

    if state == "create_date":
        parsed = parse_date(text)

        if not parsed:
            send_vk(
                user_id,
                "❌ Неверная дата.\n\n"
                "Например: 05.10.2026"
            )
            return

        create_ask_time(
            user_id,
            data["category"],
            parsed.isoformat(),
        )
        return

    if state == "create_time":
        value = (
            text
            .replace(" ", "")
            .replace("–", "-")
            .replace("—", "-")
        )

        parts = value.split("-")

        if len(parts) != 2:
            send_vk(
                user_id,
                "❌ Формат времени:\n"
                "19:00-20:30"
            )
            return

        start = parse_time(parts[0])
        end = parse_time(parts[1])

        if not start or not end:
            send_vk(
                user_id,
                "❌ Проверьте время.\n\n"
                "Например: 19:00-20:30"
            )
            return

        create_ask_format(
            user_id,
            {
                "category": data["category"],
                "training_date": data[
                    "training_date"
                ],
                "start_time": start,
                "end_time": end,
            }
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
            send_vk(
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
            send_vk(
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
            capacity = int(text)
        except ValueError:
            send_vk(
                user_id,
                "❌ Введите количество "
                "мест числом."
            )
            return

        if capacity <= 0:
            send_vk(
                user_id,
                "❌ Количество мест "
                "должно быть больше нуля."
            )
            return

        if (
            data["category"] == "Взрослая"
            and capacity < 4
        ):
            send_vk(
                user_id,
                "❌ Для взрослой тренировки "
                "минимум 4 места."
            )
            return

        new_data = dict(data)
        new_data["capacity"] = capacity

        create_ask_location(
            user_id,
            new_data,
        )
        return

    if state == "create_location":
        location = text.strip()

        if not location:
            send_vk(
                user_id,
                "❌ Укажите место "
                "проведения."
            )
            return

        new_data = dict(data)
        new_data["location"] = location

        finish_create_training(
            user_id,
            new_data,
        )
        return


def handle_message(
    user_id,
    text,
):
    state_data = get_state(
        user_id
    )

    state = state_data.get(
        "state",
        "main",
    )

    logging.info(
        "VK %s | state=%s | text=%r",
        user_id,
        state,
        text,
    )

    if text == MAIN:
        show_main(user_id)
        return

    if state.startswith("create_"):
        handle_create_state(
            user_id,
            state,
            text,
        )
        return

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
            show_booking_category(
                user_id
            )
            return

        if state == "booking_training":
            data = get_state(
                user_id
            )

            show_booking_dates(
                user_id,
                data.get("category"),
            )
            return

        if state == "booking_confirm":
            data = get_state(
                user_id
            )

            row = get_training(
                data.get("training_id")
            )

            if row:
                parsed = parse_date(
                    row["training_date"]
                )

                show_booking_trainings(
                    user_id,
                    normalize_category(
                        row["category"]
                    ),
                    (
                        parsed.isoformat()
                        if parsed
                        else row["training_date"]
                    ),
                )
            else:
                show_booking_category(
                    user_id
                )

            return

        if state == "admin_registration_training":
            show_admin(user_id)
            return

        show_main(user_id)
        return

    if text == "📅 Расписание":
        show_schedule_category(
            user_id
        )
        return

    if text == "📝 Записаться":
        show_booking_category(
            user_id
        )
        return

    if text == "💰 Цены":
        show_prices(user_id)
        return

    if text == "🏐 Индивидуальная тренировка":
        show_individual(user_id)
        return

    if text == "⚙️ Админ-панель":
        show_admin(user_id)
        return

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
        show_registration_list(
            user_id
        )
        return

    if state == "schedule_category":
        if text in (
            "👧 Детские",
            "🧑 Взрослые",
        ):
            category = (
                "Детская"
                if text.startswith("👧")
                else "Взрослая"
            )

            save_user_category(
                user_id,
                category,
            )

            show_schedule(
                user_id,
                category,
            )
        else:
            send_vk(
                user_id,
                "Выберите направление "
                "кнопкой.",
                category_keyboard(),
            )

        return

    if state == "booking_category":
        if text in (
            "👧 Детские",
            "🧑 Взрослые",
        ):
            category = (
                "Детская"
                if text.startswith("👧")
                else "Взрослая"
            )

            save_user_category(
                user_id,
                category,
            )

            show_booking_dates(
                user_id,
                category,
            )
        else:
            send_vk(
                user_id,
                "Выберите направление "
                "кнопкой.",
                category_keyboard(),
            )

        return

    if state == "booking_date":
        data = get_state(
            user_id
        )

        parsed = parse_date(
            text[:10]
        )

        if not parsed:
            send_vk(
                user_id,
                "Выберите дату "
                "кнопкой.",
            )
            return

        show_booking_trainings(
            user_id,
            data.get("category"),
            parsed.isoformat(),
        )
        return

    if state == "booking_training":
        data = get_state(
            user_id
        )

        training = find_training_by_label(
            data.get("category"),
            data.get("selected_date"),
            text,
        )

        if not training:
            send_vk(
                user_id,
                "Выберите тренировку "
                "кнопкой.",
            )
            return

        show_booking_confirm(
            user_id,
            training,
        )
        return

    if state == "booking_confirm":
        if text == "✅ Записаться":
            data = get_state(
                user_id
            )

            ok, message = register_user(
                user_id,
                data.get("training_id"),
            )

            if ok:
                notify_admin_registration(
                    user_id,
                    data.get("training_id"),
                )

                clear_state(
                    user_id
                )

                send_vk(
                    user_id,
                    "✅ Вы записаны "
                    "на тренировку!",
                    main_keyboard(user_id),
                )
            else:
                send_vk(
                    user_id,
                    f"❌ {message}",
                    keyboard([
                        [
                            button(BACK)
                        ]
                    ])
                )

            return

    if state == "admin_registration_training":
        if user_id in ADMINS:
            show_participants(
                user_id,
                text,
            )
        return

    send_vk(
        user_id,
        "Не понял команду.\n\n"
        "Откройте главное меню:",
        main_keyboard(user_id),
    )


def handle_callback(data):
    if not isinstance(data, dict):
        return "ok"

    if data.get("type") == "confirmation":
        return VK_CONFIRMATION_TOKEN

    if data.get("secret") != VK_SECRET_KEY:
        logging.warning(
            "Invalid VK secret"
        )
        return "ok"

    if data.get("type") != "message_new":
        return "ok"

    obj = data.get("object") or {}
    message = obj.get("message") or {}

    user_id = message.get(
        "from_id"
    )

    text = message.get(
        "text",
        "",
    )

    if not user_id:
        logging.warning(
            "VK message without from_id: %s",
            data,
        )
        return "ok"

    logging.info(
        "VK MESSAGE: user_id=%s text=%r",
        user_id,
        text,
    )

    handle_message(
        int(user_id),
        str(text).strip(),
    )

    return "ok"


@app.route(
    "/callback",
    methods=["POST"],
)
def callback():
    try:
        data = request.get_json(
            silent=True
        ) or {}

        logging.info(
            "CALLBACK: %s",
            data,
        )

        return handle_callback(
            data
        )

    except Exception:
        logging.exception(
            "Callback error"
        )
        return "ok"


@app.route(
    "/",
    methods=["GET"],
)
def index():
    return (
        f"VOLLEY WAVE VK BOT "
        f"{VERSION} OK",
        200,
    )


@app.route(
    "/health",
    methods=["GET"],
)
def health():
    return "OK", 200


if __name__ == "__main__":
    init_db()

    port = int(
        os.getenv(
            "PORT",
            "10000",
        )
    )

    logging.info(
        "Starting VOLLEY WAVE VK BOT %s",
        VERSION,
    )

    app.run(
        host="0.0.0.0",
        port=port,
    )
