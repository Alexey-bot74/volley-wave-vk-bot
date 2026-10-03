import os
import json
import sqlite3
import logging
from datetime import datetime, date, timedelta

import requests
from flask import Flask, request

VK_TOKEN = os.getenv("VK_TOKEN")
VK_SECRET_KEY = os.getenv("VK_SECRET_KEY")
VK_CONFIRMATION_TOKEN = os.getenv("VK_CONFIRMATION_TOKEN")
VK_API_VERSION = "5.199"
GROUP_ID = 221776135
ADMINS = {87984447, 172892670, 148372158}
DB_FILE = "volley_wave.db"

CHILDREN_PRICE = 600
ADULT_PRICE_UP_TO_7 = 1200
ADULT_PRICE_FROM_8 = 1000
MIN_ADULTS = 4

WINTER_LOCATION = "СК «Арена», ул. Молодогвардейцев, 7"
SUMMER_LOCATION = "Парк Гагарина"

LEVELS = ["Начальный", "Средний", "Продвинутый"]
FORMATS = ["Техничка", "MIXED", "Женская", "Мужская", "Общая"]
CATEGORIES = ["Детская", "Взрослая"]

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

app = Flask(__name__)
USER_STATE = {}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def button(label, color="secondary"):
    return {
        "action": {
            "type": "text",
            "label": str(label),
        },
        "color": color,
    }


def get_db():
    conn = sqlite3.connect(DB_FILE, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_database():
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vk_id INTEGER UNIQUE NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS trainings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            training_number INTEGER UNIQUE NOT NULL,
            training_date TEXT NOT NULL,
            weekday TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            title TEXT NOT NULL DEFAULT '',
            category TEXT NOT NULL,
            age_group TEXT NOT NULL DEFAULT '',
            level TEXT NOT NULL,
            format TEXT NOT NULL,
            coach TEXT NOT NULL DEFAULT '',
            capacity INTEGER NOT NULL,
            price INTEGER NOT NULL,
            location TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            template_id INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            training_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(user_id, training_id),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(training_id) REFERENCES trainings(id) ON DELETE CASCADE
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS admin_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_vk_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            details TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        )
        """
    )

    conn.commit()
    conn.close()


def ensure_user(vk_id):
    vk_id = int(vk_id)

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT id FROM users WHERE vk_id = ?",
        (vk_id,),
    )
    row = cur.fetchone()

    if row is None:
        cur.execute(
            """
            INSERT INTO users (vk_id, created_at)
            VALUES (?, ?)
            """,
            (
                vk_id,
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
        user_id = cur.lastrowid
    else:
        user_id = row["id"]

    conn.close()

    return user_id


def get_internal_user_id(vk_id):
    return ensure_user(vk_id)


def vk_api(method, **params):
    if not VK_TOKEN:
        logger.error("VK_TOKEN не задан")
        return {
            "error": {
                "error_code": -1,
                "error_msg": "VK_TOKEN не задан",
            }
        }

    params["access_token"] = VK_TOKEN
    params["v"] = VK_API_VERSION

    try:
        response = requests.post(
            f"https://api.vk.com/method/{method}",
            data=params,
            timeout=15,
        )

        response.raise_for_status()

        data = response.json()

        if "error" in data:
            logger.error("VK API error: %s", data["error"])

        return data

    except requests.RequestException as exc:
        logger.exception("VK API request failed: %s", exc)

        return {
            "error": {
                "error_code": -1,
                "error_msg": str(exc),
            }
        }

    except ValueError:
        logger.exception("VK API вернул некорректный JSON")

        return {
            "error": {
                "error_code": -1,
                "error_msg": "Некорректный ответ VK API",
            }
        }


def send_message(user_id, message, keyboard=None):
    params = {
        "user_id": int(user_id),
        "random_id": 0,
        "message": str(message),
    }

    if keyboard is not None:
        params["keyboard"] = json.dumps(
            keyboard,
            ensure_ascii=False,
            separators=(",", ":"),
        )

    return vk_api(
        "messages.send",
        **params,
    )


def set_state(user_id, state, **data):
    USER_STATE[int(user_id)] = {
        "state": state,
        **data,
    }


def get_state(user_id):
    return USER_STATE.get(
        int(user_id),
        {
            "state": "main",
        },
    )


def clear_state(user_id):
    USER_STATE.pop(int(user_id), None)


def log_admin(admin_id, action, details=""):
    conn = get_db()

    conn.execute(
        """
        INSERT INTO admin_logs (
            admin_vk_id,
            action,
            details,
            created_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            int(admin_id),
            action,
            str(details),
            datetime.now().isoformat(),
        ),
    )

    conn.commit()
    conn.close()


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

    if int(user_id) in ADMINS:
        rows.append(
            [
                button("⚙️ Админ-панель", "positive"),
            ]
        )

    return {
        "one_time": False,
        "inline": False,
        "buttons": rows,
    }


def back_keyboard(label="⬅️ Назад"):
    return {
        "one_time": False,
        "inline": False,
        "buttons": [
            [
                button(label, "secondary"),
            ]
        ],
    }


def category_keyboard():
    return {
        "one_time": False,
        "inline": False,
        "buttons": [
            [
                button("👧 Детская", "primary"),
            ],
            [
                button("🏐 Взрослая", "primary"),
            ],
            [
                button("⬅️ Назад", "secondary"),
            ],
        ],
    }


def level_keyboard():
    return {
        "one_time": False,
        "inline": False,
        "buttons": [
            [
                button("Начальный", "secondary"),
                button("Средний", "secondary"),
            ],
            [
                button("Продвинутый", "secondary"),
            ],
            [
                button("⬅️ Назад", "secondary"),
            ],
        ],
    }


def format_keyboard():
    return {
        "one_time": False,
        "inline": False,
        "buttons": [
            [
                button("Техничка", "secondary"),
                button("MIXED", "secondary"),
            ],
            [
                button("Женская", "secondary"),
                button("Мужская", "secondary"),
            ],
            [
                button("Общая", "secondary"),
            ],
            [
                button("⬅️ Назад", "secondary"),
            ],
        ],
    }


def admin_keyboard():
    return {
        "one_time": False,
        "inline": False,
        "buttons": [
            [
                button("➕ Создать тренировку", "positive"),
            ],
            [
                button("📅 Управление расписанием", "primary"),
            ],
            [
                button("👥 Участники", "primary"),
            ],
            [
                button("⬅️ В главное меню", "secondary"),
            ],
        ],
    }


def normalize_category(value):
    text = str(value).strip().lower()

    if "дет" in text:
        return "Детская"

    if "взрос" in text:
        return "Взрослая"

    return str(value).strip()


def category_label(category):
    return normalize_category(category)


def category_from_text(text):
    return normalize_category(text)


def parse_date(value):
    value = str(value).strip()

    for fmt in (
        "%d.%m.%Y",
        "%Y-%m-%d",
        "%d/%m/%Y",
    ):
        try:
            return datetime.strptime(
                value,
                fmt,
            ).date()
        except ValueError:
            continue

    return None


def format_date_long(value):
    parsed = value if isinstance(value, date) else parse_date(value)

    if parsed is None:
        return str(value)

    weekday_names = [
        "Понедельник",
        "Вторник",
        "Среда",
        "Четверг",
        "Пятница",
        "Суббота",
        "Воскресенье",
    ]

    return (
        f"{weekday_names[parsed.weekday()]}, "
        f"{parsed.day} {MONTHS[parsed.month]} {parsed.year}"
    )


def format_date_short(value):
    parsed = value if isinstance(value, date) else parse_date(value)

    if parsed is None:
        return str(value)

    return parsed.strftime("%d.%m.%Y")


def valid_time(value):
    try:
        datetime.strptime(
            str(value).strip(),
            "%H:%M",
        )
        return True
    except ValueError:
        return False


def get_next_training_number():
    conn = get_db()

    row = conn.execute(
        """
        SELECT COALESCE(MAX(training_number), 0) + 1 AS next_number
        FROM trainings
        """
    ).fetchone()

    conn.close()

    return int(row["next_number"])


def get_training(training_id):
    conn = get_db()

    row = conn.execute(
        """
        SELECT *
        FROM trainings
        WHERE id = ?
        """,
        (int(training_id),),
    ).fetchone()

    conn.close()

    if row is None:
        return None

    return dict(row)


def get_training_by_number(number):
    conn = get_db()

    row = conn.execute(
        """
        SELECT *
        FROM trainings
        WHERE training_number = ?
        """,
        (int(number),),
    ).fetchone()

    conn.close()

    if row is None:
        return None

    return dict(row)


def create_training(
    training_date,
    start_time,
    end_time,
    category,
    level,
    training_format,
    capacity,
    price,
    location,
    title="",
    age_group="",
    coach="",
):
    parsed_date = parse_date(training_date)

    if parsed_date is None:
        raise ValueError("Неверная дата")

    if not valid_time(start_time):
        raise ValueError("Неверное время начала")

    if not valid_time(end_time):
        raise ValueError("Неверное время окончания")

    category = normalize_category(category)

    if category not in CATEGORIES:
        raise ValueError("Неверная категория")

    if level not in LEVELS:
        raise ValueError("Неверный уровень")

    if training_format not in FORMATS:
        raise ValueError("Неверный формат")

    try:
        capacity = int(capacity)
        price = int(price)
    except (TypeError, ValueError):
        raise ValueError(
            "Количество мест и стоимость должны быть числами"
        )

    if capacity < 1:
        raise ValueError(
            "Количество мест должно быть больше нуля"
        )

    if category == "Детская":
        price = CHILDREN_PRICE

    if category == "Взрослая" and capacity < MIN_ADULTS:
        raise ValueError(
            "Для взрослой тренировки минимальный набор — 4 человека"
        )

    if category == "Взрослая":
        if capacity <= 7:
            price = ADULT_PRICE_UP_TO_7
        else:
            price = ADULT_PRICE_FROM_8

    if price < 0:
        raise ValueError(
            "Стоимость не может быть отрицательной"
        )

    conn = get_db()

    training_number = get_next_training_number()
    now = datetime.now().isoformat()

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
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?
        )
        """,
        (
            training_number,
            parsed_date.isoformat(),
            parsed_date.strftime("%A"),
            str(start_time).strip(),
            str(end_time).strip(),
            str(title).strip(),
            category,
            str(age_group).strip(),
            level,
            training_format,
            str(coach).strip(),
            capacity,
            price,
            str(location).strip(),
            now,
            now,
        ),
    )

    conn.commit()
    conn.close()

    return get_training_by_number(training_number)


def get_future_trainings(category=None, days=90):
    today = date.today().isoformat()
    end_date = (
        date.today() + timedelta(days=days)
    ).isoformat()

    conn = get_db()

    if category:
        rows = conn.execute(
            """
            SELECT *
            FROM trainings
            WHERE status = 'active'
              AND training_date >= ?
              AND training_date <= ?
              AND category = ?
            ORDER BY training_date, start_time, id
            """,
            (
                today,
                end_date,
                normalize_category(category),
            ),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT *
            FROM trainings
            WHERE status = 'active'
              AND training_date >= ?
              AND training_date <= ?
            ORDER BY training_date, start_time, id
            """,
            (
                today,
                end_date,
            ),
        ).fetchall()

    conn.close()

    return [dict(row) for row in rows]


def registration_count(training_id):
    conn = get_db()

    row = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM registrations
        WHERE training_id = ?
        """,
        (int(training_id),),
    ).fetchone()

    conn.close()

    return int(row["count"])


def is_registered(vk_id, training_id):
    internal_id = get_internal_user_id(vk_id)

    conn = get_db()

    row = conn.execute(
        """
        SELECT id
        FROM registrations
        WHERE user_id = ?
          AND training_id = ?
        """,
        (
            internal_id,
            int(training_id),
        ),
    ).fetchone()

    conn.close()

    return row is not None


def register_user(vk_id, training_id):
    internal_id = get_internal_user_id(vk_id)

    conn = get_db()

    training = conn.execute(
        """
        SELECT *
        FROM trainings
        WHERE id = ?
          AND status = 'active'
        """,
        (int(training_id),),
    ).fetchone()

    if training is None:
        conn.close()
        return False, "Тренировка не найдена или уже недоступна."

    existing = conn.execute(
        """
        SELECT id
        FROM registrations
        WHERE user_id = ?
          AND training_id = ?
        """,
        (
            internal_id,
            int(training_id),
        ),
    ).fetchone()

    if existing:
        conn.close()
        return False, "Вы уже записаны на эту тренировку."

    count_row = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM registrations
        WHERE training_id = ?
        """,
        (int(training_id),),
    ).fetchone()

    if int(count_row["count"]) >= int(training["capacity"]):
        conn.close()
        return False, "К сожалению, свободных мест уже нет."

    conn.execute(
        """
        INSERT INTO registrations (
            user_id,
            training_id,
            created_at
        )
        VALUES (?, ?, ?)
        """,
        (
            internal_id,
            int(training_id),
            datetime.now().isoformat(),
        ),
    )

    conn.commit()
    conn.close()

    return True, "Вы успешно записались на тренировку."


def get_user_trainings(vk_id):
    internal_id = get_internal_user_id(vk_id)

    conn = get_db()

    rows = conn.execute(
        """
        SELECT
            t.*,
            r.created_at AS registration_created_at
        FROM registrations r
        JOIN trainings t
          ON t.id = r.training_id
        WHERE r.user_id = ?
        ORDER BY t.training_date, t.start_time, t.id
        """,
        (internal_id,),
    ).fetchall()

    conn.close()

    return [dict(row) for row in rows]


def get_participants(training_id):
    conn = get_db()

    rows = conn.execute(
        """
        SELECT
            u.vk_id,
            r.created_at
        FROM registrations r
        JOIN users u
          ON u.id = r.user_id
        WHERE r.training_id = ?
        ORDER BY r.created_at, r.id
        """,
        (int(training_id),),
    ).fetchall()

    conn.close()

    return [dict(row) for row in rows]


def training_details_text(training):
    count = registration_count(training["id"])
    capacity = int(training["capacity"] or 0)
    free = max(
        capacity - count,
        0,
    )

    lines = [
        f"🏐 Тренировка №{training['training_number']}",
        "",
        f"📅 Дата: {format_date_long(training['training_date'])}",
        f"🕐 Время: {training['start_time']}–{training['end_time']}",
        f"🏐 Формат: {training['format']}",
        f"📊 Уровень: {training['level']}",
        f"👥 Мест: {capacity}",
        f"💳 Стоимость: {int(training['price'])}₽",
        f"📍 Место: {training['location']}",
        f"👤 Записано: {count}",
        f"🪑 Свободно: {free}",
    ]

    if training.get("title"):
        lines.insert(
            1,
            f"🎯 {training['title']}",
        )

    if training.get("age_group"):
        lines.append(
            f"🎂 Возраст: {training['age_group']}"
        )

    if training.get("coach"):
        lines.append(
            f"🏐 Тренер: {training['coach']}"
        )

    return "\n".join(lines)


def show_main_menu(user_id):
    clear_state(user_id)

    send_message(
        user_id,
        "🏐 VOLLEY WAVE\n\nВыберите нужный раздел:",
        main_keyboard(user_id),
    )


def start_booking(user_id):
    set_state(
        user_id,
        "booking_category",
    )

    send_message(
        user_id,
        "Выберите направление:",
        category_keyboard(),
    )


def show_booking_dates(user_id, category):
    trainings = get_future_trainings(
        category=category,
    )

    if not trainings:
        send_message(
            user_id,
            "Пока нет доступных тренировок для записи.",
            category_keyboard(),
        )
        return

    dates = []
    seen = set()

    for training in trainings:
        training_date = training["training_date"]

        if training_date not in seen:
            seen.add(training_date)
            dates.append(training_date)

    rows = []

    for item in dates[:20]:
        parsed = parse_date(item)

        if parsed:
            label = parsed.strftime("%d.%m.%Y")
        else:
            label = item

        rows.append(
            [
                button(
                    label,
                    "primary",
                )
            ]
        )

    rows.append(
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
        category=normalize_category(category),
    )

    send_message(
        user_id,
        "Выберите дату:",
        {
            "one_time": False,
            "inline": False,
            "buttons": rows,
        },
    )


def show_booking_trainings(user_id, training_date):
    state = get_state(user_id)
    category = state.get("category")

    parsed = parse_date(training_date)

    if parsed is None:
        send_message(
            user_id,
            "Не удалось определить дату.",
            back_keyboard(),
        )
        return

    conn = get_db()

    rows = conn.execute(
        """
        SELECT *
        FROM trainings
        WHERE status = 'active'
          AND training_date = ?
          AND category = ?
        ORDER BY start_time, id
        """,
        (
            parsed.isoformat(),
            normalize_category(category),
        ),
    ).fetchall()

    conn.close()

    trainings = [dict(row) for row in rows]

    if not trainings:
        send_message(
            user_id,
            "На эту дату подходящих тренировок нет.",
            back_keyboard(),
        )
        return

    buttons = []

    for training in trainings:
        count = registration_count(
            training["id"]
        )

        free = max(
            int(training["capacity"]) - count,
            0,
        )

        label = (
            f"{training['start_time']} "
            f"{training['format']} — "
            f"{free} мест"
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
        category=normalize_category(category),
        training_date=parsed.isoformat(),
        training_ids=[
            training["id"]
            for training in trainings
        ],
    )

    send_message(
        user_id,
        f"Тренировки на {parsed.strftime('%d.%m.%Y')}:",
        {
            "one_time": False,
            "inline": False,
            "buttons": buttons,
        },
    )


def show_booking_details(user_id, training_id):
    training = get_training(training_id)

    if (
        training is None
        or training["status"] != "active"
    ):
        send_message(
            user_id,
            "Тренировка не найдена.",
            back_keyboard(),
        )
        return

    count = registration_count(
        training["id"]
    )

    free = max(
        int(training["capacity"]) - count,
        0,
    )

    if is_registered(
        user_id,
        training["id"],
    ):
        send_message(
            user_id,
            training_details_text(training)
            + "\n\n✅ Вы уже записаны.",
            back_keyboard(),
        )
        return

    if free <= 0:
        send_message(
            user_id,
            training_details_text(training)
            + "\n\n❌ Свободных мест нет.",
            back_keyboard(),
        )
        return

    set_state(
        user_id,
        "booking_confirm",
        training_id=training["id"],
    )

    send_message(
        user_id,
        training_details_text(training)
        + "\n\nЗаписаться на эту тренировку?",
        {
            "one_time": False,
            "inline": False,
            "buttons": [
                [
                    button(
                        "✅ Записаться",
                        "positive",
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


def show_schedule_categories(user_id):
    set_state(
        user_id,
        "schedule_category",
    )

    send_message(
        user_id,
        "📅 Расписание\n\nВыберите направление:",
        category_keyboard(),
    )


def show_week_schedule(user_id, category):
    trainings = get_future_trainings(
        category=category,
        days=365,
    )

    if not trainings:
        send_message(
            user_id,
            "📅 В расписании пока нет тренировок.\n\n"
            "Расписание появится здесь после добавления "
            "тренировок администратором.",
            category_keyboard(),
        )
        return

    lines = [
        f"📅 Расписание — {category_label(category)}",
        "",
    ]

    current_date = None

    for training in trainings:
        if training["training_date"] != current_date:
            current_date = training["training_date"]

            lines.append(
                f"📌 {format_date_long(current_date)}"
            )

        count = registration_count(
            training["id"]
        )

        capacity = int(
            training["capacity"]
        )

        free = max(
            capacity - count,
            0,
        )

        lines.append(
            f"• {training['start_time']}–"
            f"{training['end_time']} | "
            f"{training['format']} | "
            f"{training['level']}"
        )

        lines.append(
            f"  Мест: {free}/{capacity} | "
            f"{training['price']}₽"
        )

        lines.append(
            f"  📍 {training['location']}"
        )

        lines.append("")

    lines.append(
        "Нажмите «Записаться», чтобы выбрать "
        "конкретную тренировку."
    )

    send_message(
        user_id,
        "\n".join(lines),
        {
            "one_time": False,
            "inline": False,
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


def show_my_trainings(user_id):
    trainings = get_user_trainings(user_id)

    if not trainings:
        send_message(
            user_id,
            "👤 У вас пока нет записей на тренировки.",
            back_keyboard(),
        )
        return

    lines = [
        "👤 Мои тренировки",
        "",
    ]

    for training in trainings:
        lines.append(
            f"🏐 №{training['training_number']} — "
            f"{format_date_short(training['training_date'])} "
            f"{training['start_time']}"
        )

        lines.append(
            f"{training['format']} | "
            f"{training['level']} | "
            f"{training['price']}₽"
        )

        lines.append(
            f"📍 {training['location']}"
        )

        lines.append("")

    send_message(
        user_id,
        "\n".join(lines),
        back_keyboard(),
    )


def show_prices(user_id):
    send_message(
        user_id,
        "💰 Цены\n\n"
        "👧 Дети — 600₽ за тренировку.\n\n"
        "🏐 Взрослые:\n"
        "• минимальный набор — 4 человека;\n"
        "• до 7 человек — 1200₽ с человека;\n"
        "• от 8 человек — 1000₽ с человека.",
        back_keyboard(),
    )


def show_location(user_id):
    send_message(
        user_id,
        "📍 Где тренируемся\n\n"
        f"❄️ Зимой: {WINTER_LOCATION}\n"
        f"☀️ В тёплый сезон: {SUMMER_LOCATION}",
        back_keyboard(),
    )


def show_individual(user_id):
    set_state(
        user_id,
        "individual",
    )

    send_message(
        user_id,
        "🎯 Индивидуальная тренировка\n\n"
        "Если хотите индивидуальную тренировку, "
        "напишите администратору. Он уточнит задачу, "
        "подберёт время и расскажет о стоимости.",
        {
            "one_time": False,
            "inline": False,
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


def send_admin_contact(user_id):
    for admin_id in ADMINS:
        send_message(
            admin_id,
            "🎯 Запрос на индивидуальную тренировку "
            f"от пользователя VK ID {user_id}.\n\n"
            "Свяжитесь с ним через сообщения сообщества.",
        )

    clear_state(user_id)

    send_message(
        user_id,
        "✅ Запрос отправлен администратору.\n\n"
        "Ожидайте ответа в сообщениях сообщества.",
        main_keyboard(user_id),
    )


def start_question(user_id):
    set_state(
        user_id,
        "question",
    )

    send_message(
        user_id,
        "❓ Напишите свой вопрос одним сообщением. "
        "Я передам его администратору.",
        back_keyboard(),
    )


def forward_question(user_id, text):
    for admin_id in ADMINS:
        send_message(
            admin_id,
            f"❓ Вопрос от пользователя VK ID {user_id}:\n\n"
            f"{text}",
        )

    clear_state(user_id)

    send_message(
        user_id,
        "✅ Вопрос отправлен администратору.",
        main_keyboard(user_id),
    )


def show_admin(user_id):
    if int(user_id) not in ADMINS:
        show_main_menu(user_id)
        return

    clear_state(user_id)

    send_message(
        user_id,
        "⚙️ Админ-панель\n\nВыберите действие:",
        admin_keyboard(),
    )


def show_admin_schedule(user_id):
    if int(user_id) not in ADMINS:
        show_main_menu(user_id)
        return

    trainings = get_future_trainings(
        days=365,
    )

    if not trainings:
        send_message(
            user_id,
            "📅 Будущих тренировок пока нет.",
            admin_keyboard(),
        )
        return

    lines = [
        "📅 Ближайшие тренировки",
        "",
    ]

    for training in trainings:
        count = registration_count(
            training["id"]
        )

        capacity = int(
            training["capacity"]
        )

        lines.append(
            f"№{training['training_number']} | "
            f"{format_date_short(training['training_date'])} | "
            f"{training['start_time']}–"
            f"{training['end_time']}"
        )

        lines.append(
            f"{training['format']} | "
            f"{training['level']} | "
            f"{count}/{capacity} | "
            f"{training['price']}₽"
        )

        lines.append(
            f"📍 {training['location']}"
        )

        lines.append("")

    send_message(
        user_id,
        "\n".join(lines),
        admin_keyboard(),
    )


def show_admin_participants(user_id):
    if int(user_id) not in ADMINS:
        show_main_menu(user_id)
        return

    trainings = get_future_trainings(
        days=365,
    )

    if not trainings:
        send_message(
            user_id,
            "Нет будущих тренировок.",
            admin_keyboard(),
        )
        return

    buttons = []

    for training in trainings[:30]:
        label = (
            f"№{training['training_number']} "
            f"{format_date_short(training['training_date'])} "
            f"{training['start_time']}"
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
        "admin_participants_select",
        training_ids=[
            training["id"]
            for training in trainings[:30]
        ],
    )

    send_message(
        user_id,
        "Выберите тренировку:",
        {
            "one_time": False,
            "inline": False,
            "buttons": buttons,
        },
    )


def show_participants(user_id, training_id):
    if int(user_id) not in ADMINS:
        show_main_menu(user_id)
        return

    training = get_training(
        training_id
    )

    if training is None:
        send_message(
            user_id,
            "Тренировка не найдена.",
            admin_keyboard(),
        )
        return

    participants = get_participants(
        training_id
    )

    lines = [
        f"👥 Участники тренировки "
        f"№{training['training_number']}",
        "",
        training_details_text(training),
        "",
    ]

    if not participants:
        lines.append(
            "Пока никто не записался."
        )
    else:
        for index, participant in enumerate(
            participants,
            1,
        ):
            lines.append(
                f"{index}. VK ID {participant['vk_id']}"
            )

    send_message(
        user_id,
        "\n".join(lines),
        admin_keyboard(),
    )


def start_create_training(user_id):
    if int(user_id) not in ADMINS:
        show_main_menu(user_id)
        return

    set_state(
        user_id,
        "create_date",
    )

    send_message(
        user_id,
        "➕ Создание тренировки\n\n"
        "Введите дату в формате ДД.ММ.ГГГГ.",
        back_keyboard(),
    )


def ask_create_time(user_id):
    set_state(
        user_id,
        "create_time",
        **{
            key: value
            for key, value in get_state(user_id).items()
            if key != "state"
        },
    )

    send_message(
        user_id,
        "Введите время в формате ЧЧ:ММ–ЧЧ:ММ.\n"
        "Например: 19:00-20:30",
        back_keyboard(),
    )


def parse_time_range(text):
    normalized = (
        str(text)
        .strip()
        .replace("–", "-")
        .replace("—", "-")
    )

    parts = [
        part.strip()
        for part in normalized.split("-")
    ]

    if len(parts) != 2:
        return None, None

    start_time = parts[0]
    end_time = parts[1]

    if not valid_time(start_time):
        return None, None

    if not valid_time(end_time):
        return None, None

    return start_time, end_time


def ask_create_category(user_id):
    state = get_state(user_id)

    set_state(
        user_id,
        "create_category",
        **{
            key: value
            for key, value in state.items()
            if key != "state"
        },
    )

    send_message(
        user_id,
        "Выберите категорию:",
        category_keyboard(),
    )


def ask_create_level(user_id):
    state = get_state(user_id)

    set_state(
        user_id,
        "create_level",
        **{
            key: value
            for key, value in state.items()
            if key != "state"
        },
    )

    send_message(
        user_id,
        "Выберите уровень:",
        level_keyboard(),
    )


def ask_create_format(user_id):
    state = get_state(user_id)

    set_state(
        user_id,
        "create_format",
        **{
            key: value
            for key, value in state.items()
            if key != "state"
        },
    )

    send_message(
        user_id,
        "Выберите формат:",
        format_keyboard(),
    )


def ask_create_capacity(user_id):
    state = get_state(user_id)

    set_state(
        user_id,
        "create_capacity",
        **{
            key: value
            for key, value in state.items()
            if key != "state"
        },
    )

    send_message(
        user_id,
        "Введите количество мест числом.",
        back_keyboard(),
    )


def ask_create_price(user_id):
    state = get_state(user_id)
    category = normalize_category(
        state.get("category", "")
    )

    if category == "Детская":
        state["price"] = CHILDREN_PRICE

        set_state(
            user_id,
            "create_location",
            **{
                key: value
                for key, value in state.items()
                if key != "state"
            },
        )

        send_message(
            user_id,
            "Стоимость автоматически установлена: 600₽.\n\n"
            "Введите место проведения.",
            back_keyboard(),
        )
        return

    set_state(
        user_id,
        "create_price",
        **{
            key: value
            for key, value in state.items()
            if key != "state"
        },
    )

    send_message(
        user_id,
        "Введите стоимость с человека числом.\n\n"
        "Для взрослых автоматически применяется:\n"
        "• до 7 человек — 1200₽;\n"
        "• от 8 человек — 1000₽.\n"
        "Минимальный набор — 4 человека.",
        back_keyboard(),
    )


def ask_create_location(user_id):
    state = get_state(user_id)

    set_state(
        user_id,
        "create_location",
        **{
            key: value
            for key, value in state.items()
            if key != "state"
        },
    )

    send_message(
        user_id,
        "Введите место проведения.",
        back_keyboard(),
    )


def finish_create_training(user_id, location):
    state = get_state(user_id)

    try:
        training = create_training(
            training_date=state["training_date"],
            start_time=state["start_time"],
            end_time=state["end_time"],
            category=state["category"],
            level=state["level"],
            training_format=state["format"],
            capacity=state["capacity"],
            price=state.get("price", 0),
            location=location,
            title=state.get("title", ""),
            age_group=state.get("age_group", ""),
            coach=state.get("coach", ""),
        )

    except (
        KeyError,
        ValueError,
        sqlite3.Error,
    ) as exc:
        logger.exception(
            "Ошибка создания тренировки: %s",
            exc,
        )

        clear_state(user_id)

        send_message(
            user_id,
            "❌ Не удалось создать тренировку. "
            "Проверьте введённые данные.",
            admin_keyboard(),
        )
        return

    log_admin(
        user_id,
        "create_training",
        f"training_id={training['id']}",
    )

    clear_state(user_id)

    send_message(
        user_id,
        "✅ Тренировка создана.\n\n"
        + training_details_text(training),
        admin_keyboard(),
    )


def handle_create_state(user_id, text):
    state = get_state(user_id)
    current = state.get("state")

    if current == "create_date":
        parsed = parse_date(text)

        if parsed is None:
            send_message(
                user_id,
                "❌ Неверная дата. "
                "Введите дату в формате ДД.ММ.ГГГГ.",
                back_keyboard(),
            )
            return

        if parsed < date.today():
            send_message(
                user_id,
                "❌ Нельзя создать тренировку "
                "на прошедшую дату.",
                back_keyboard(),
            )
            return

        state["training_date"] = parsed.isoformat()

        set_state(
            user_id,
            "create_time",
            **{
                key: value
                for key, value in state.items()
                if key != "state"
            },
        )

        send_message(
            user_id,
            "Введите время в формате ЧЧ:ММ–ЧЧ:ММ.\n"
            "Например: 19:00-20:30",
            back_keyboard(),
        )
        return

    if current == "create_time":
        start_time, end_time = parse_time_range(text)

        if start_time is None:
            send_message(
                user_id,
                "❌ Неверный формат времени.\n"
                "Введите, например: 19:00-20:30",
                back_keyboard(),
            )
            return

        state["start_time"] = start_time
        state["end_time"] = end_time

        set_state(
            user_id,
            "create_category",
            **{
                key: value
                for key, value in state.items()
                if key != "state"
            },
        )

        send_message(
            user_id,
            "Выберите категорию:",
            category_keyboard(),
        )
        return

    if current == "create_category":
        category = category_from_text(text)

        if category not in CATEGORIES:
            send_message(
                user_id,
                "Выберите категорию кнопкой.",
                category_keyboard(),
            )
            return

        state["category"] = category

        set_state(
            user_id,
            "create_level",
            **{
                key: value
                for key, value in state.items()
                if key != "state"
            },
        )

        send_message(
            user_id,
            "Выберите уровень:",
            level_keyboard(),
        )
        return

    if current == "create_level":
        if text not in LEVELS:
            send_message(
                user_id,
                "Выберите уровень кнопкой.",
                level_keyboard(),
            )
            return

        state["level"] = text

        set_state(
            user_id,
            "create_format",
            **{
                key: value
                for key, value in state.items()
                if key != "state"
            },
        )

        send_message(
            user_id,
            "Выберите формат:",
            format_keyboard(),
        )
        return

    if current == "create_format":
        if text not in FORMATS:
            send_message(
                user_id,
                "Выберите формат кнопкой.",
                format_keyboard(),
            )
            return

        state["format"] = text

        set_state(
            user_id,
            "create_capacity",
            **{
                key: value
                for key, value in state.items()
                if key != "state"
            },
        )

        send_message(
            user_id,
            "Введите количество мест числом.",
            back_keyboard(),
        )
        return

    if current == "create_capacity":
        try:
            capacity = int(
                str(text).strip()
            )
        except ValueError:
            send_message(
                user_id,
                "❌ Введите количество мест "
                "целым числом.",
                back_keyboard(),
            )
            return

        if capacity < 1:
            send_message(
                user_id,
                "❌ Количество мест должно "
                "быть больше нуля.",
                back_keyboard(),
            )
            return

        if (
            state.get("category") == "Взрослая"
            and capacity < MIN_ADULTS
        ):
            send_message(
                user_id,
                "❌ Для взрослой тренировки "
                "минимальный набор — 4 человека.",
                back_keyboard(),
            )
            return

        state["capacity"] = capacity

        if state.get("category") == "Детская":
            state["price"] = CHILDREN_PRICE

            set_state(
                user_id,
                "create_location",
                **{
                    key: value
                    for key, value in state.items()
                    if key != "state"
                },
            )

            send_message(
                user_id,
                "Стоимость: 600₽.\n\n"
                "Введите место проведения.",
                back_keyboard(),
            )
            return

        if state.get("category") == "Взрослая":
            if capacity <= 7:
                state["price"] = ADULT_PRICE_UP_TO_7
            else:
                state["price"] = ADULT_PRICE_FROM_8

            set_state(
                user_id,
                "create_location",
                **{
                    key: value
                    for key, value in state.items()
                    if key != "state"
                },
            )

            send_message(
                user_id,
                f"Стоимость автоматически установлена: "
                f"{state['price']}₽ с человека.\n\n"
                "Введите место проведения.",
                back_keyboard(),
            )
            return

        ask_create_price(user_id)
        return

    if current == "create_price":
        try:
            price = int(
                str(text).strip()
            )
        except ValueError:
            send_message(
                user_id,
                "❌ Введите стоимость "
                "целым числом.",
                back_keyboard(),
            )
            return

        if price < 0:
            send_message(
                user_id,
                "❌ Стоимость не может "
                "быть отрицательной.",
                back_keyboard(),
            )
            return

        state["price"] = price

        set_state(
            user_id,
            "create_location",
            **{
                key: value
                for key, value in state.items()
                if key != "state"
            },
        )

        send_message(
            user_id,
            "Введите место проведения.",
            back_keyboard(),
        )
        return

    if current == "create_location":
        location = str(text).strip()

        if not location:
            send_message(
                user_id,
                "❌ Место не может быть пустым.",
                back_keyboard(),
            )
            return

        finish_create_training(
            user_id,
            location,
        )


def find_training_from_button(user_id, text):
    state = get_state(user_id)

    training_ids = state.get(
        "training_ids",
        [],
    )

    for training_id in training_ids:
        training = get_training(
            training_id
        )

        if training is None:
            continue

        count = registration_count(
            training_id
        )

        free = max(
            int(training["capacity"]) - count,
            0,
        )

        expected = (
            f"{training['start_time']} "
            f"{training['format']} — "
            f"{free} мест"
        )

        if text == expected:
            return training_id

    return None


def find_admin_training_from_button(user_id, text):
    state = get_state(user_id)

    training_ids = state.get(
        "training_ids",
        [],
    )

    for training_id in training_ids:
        training = get_training(
            training_id
        )

        if training is None:
            continue

        expected = (
            f"№{training['training_number']} "
            f"{format_date_short(training['training_date'])} "
            f"{training['start_time']}"
        )

        if text == expected:
            return training_id

    return None


def handle_message(user_id, text):
    ensure_user(user_id)

    text = str(text or "").strip()

    state = get_state(user_id)
    current_state = state.get(
        "state",
        "main",
    )

    logger.info(
        "VK %s | state=%s | text=%r",
        user_id,
        current_state,
        text,
    )

    if text in {
        "Начать",
        "/start",
        "🏠 Главное меню",
    }:
        show_main_menu(user_id)
        return

    if text in {
        "⬅️ Назад",
        "Назад",
        "⬅️ В главное меню",
    }:
        if current_state.startswith("create_"):
            show_admin(user_id)
            return

        if current_state in {
            "booking_category",
            "schedule_category",
            "individual",
            "question",
        }:
            show_main_menu(user_id)
            return

        if current_state in {
            "booking_date",
            "booking_training",
            "booking_confirm",
        }:
            category = state.get("category")

            if category:
                show_booking_dates(
                    user_id,
                    category,
                )
            else:
                start_booking(user_id)

            return

        if current_state == "admin_participants_select":
            show_admin(user_id)
            return

        show_main_menu(user_id)
        return

    if current_state == "question":
        forward_question(
            user_id,
            text,
        )
        return

    if current_state == "individual":
        if text == "✉️ Написать администратору":
            send_admin_contact(user_id)
        else:
            show_main_menu(user_id)
        return

    if current_state == "booking_category":
        category = category_from_text(text)

        if category in CATEGORIES:
            show_booking_dates(
                user_id,
                category,
            )
        else:
            send_message(
                user_id,
                "Выберите направление кнопкой.",
                category_keyboard(),
            )

        return

    if current_state == "booking_date":
        parsed = parse_date(text)

        if parsed is None:
            send_message(
                user_id,
                "Выберите дату кнопкой.",
                back_keyboard(),
            )
            return

        show_booking_trainings(
            user_id,
            parsed.isoformat(),
        )
        return

    if current_state == "booking_training":
        training_id = find_training_from_button(
            user_id,
            text,
        )

        if training_id is None:
            send_message(
                user_id,
                "Выберите тренировку кнопкой.",
                back_keyboard(),
            )
            return

        show_booking_details(
            user_id,
            training_id,
        )
        return

    if current_state == "booking_confirm":
        training_id = state.get(
            "training_id"
        )

        if (
            text == "✅ Записаться"
            and training_id
        ):
            success, message = register_user(
                user_id,
                training_id,
            )

            training = get_training(
                training_id
            )

            clear_state(user_id)

            if success and training:
                send_message(
                    user_id,
                    f"✅ {message}\n\n"
                    + training_details_text(
                        training
                    ),
                    main_keyboard(user_id),
                )
            else:
                send_message(
                    user_id,
                    f"❌ {message}",
                    main_keyboard(user_id),
                )

            return

    if current_state == "schedule_category":
        category = category_from_text(text)

        if category in CATEGORIES:
            show_week_schedule(
                user_id,
                category,
            )
        else:
            send_message(
                user_id,
                "Выберите направление кнопкой.",
                category_keyboard(),
            )

        return

    if current_state == "admin_participants_select":
        training_id = find_admin_training_from_button(
            user_id,
            text,
        )

        if training_id is None:
            send_message(
                user_id,
                "Выберите тренировку кнопкой.",
                back_keyboard(),
            )
            return

        show_participants(
            user_id,
            training_id,
        )
        return

    if current_state.startswith("create_"):
        if int(user_id) not in ADMINS:
            show_main_menu(user_id)
            return

        handle_create_state(
            user_id,
            text,
        )
        return

    if text == "🏐 Записаться":
        start_booking(user_id)
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

    if text == "🎯 Индивидуальная":
        show_individual(user_id)
        return

    if text == "❓ Задать вопрос":
        start_question(user_id)
        return

    if text == "⚙️ Админ-панель":
        show_admin(user_id)
        return

    if text == "➕ Создать тренировку":
        start_create_training(user_id)
        return

    if text == "📅 Управление расписанием":
        show_admin_schedule(user_id)
        return

    if text == "👥 Участники":
        show_admin_participants(user_id)
        return

    if text == "✉️ Написать администратору":
        send_admin_contact(user_id)
        return

    show_main_menu(user_id)


@app.route("/", methods=["GET"])
def index():
    return "VOLLEY WAVE VK BOT is running", 200


@app.route("/health", methods=["GET"])
def health():
    return "OK", 200


@app.route("/callback", methods=["POST"])
def callback():
    try:
        data = request.get_json(
            silent=True
        ) or {}

        event_type = data.get(
            "type"
        )

        logger.info(
            "VK EVENT: type=%r",
            event_type,
        )

        if event_type == "confirmation":
            return (
                VK_CONFIRMATION_TOKEN or "",
                200,
            )

        if event_type != "message_new":
            return "ok", 200

        object_data = data.get(
            "object"
        ) or {}

        message = object_data.get(
            "message"
        ) or {}

        user_id = message.get(
            "from_id"
        )

        text = message.get(
            "text",
            "",
        )

        if not user_id:
            logger.warning(
                "VK message_new без from_id: %s",
                data,
            )
            return "ok", 200

        logger.info(
            "VK MESSAGE: user_id=%s text=%r",
            user_id,
            text,
        )

        try:
            handle_message(
                int(user_id),
                text,
            )

        except Exception:
            logger.exception(
                "Ошибка обработки сообщения "
                "user_id=%s text=%r",
                user_id,
                text,
            )

            try:
                send_message(
                    int(user_id),
                    "Произошла техническая ошибка. "
                    "Попробуйте ещё раз.",
                    main_keyboard(
                        int(user_id)
                    ),
                )
            except Exception:
                logger.exception(
                    "Не удалось отправить сообщение "
                    "об ошибке"
                )

        return "ok", 200

    except Exception:
        logger.exception(
            "Критическая ошибка callback"
        )

        return "ok", 200


init_database()

logger.info(
    "VOLLEY WAVE VK BOT VERSION №4 started"
)


if __name__ == "__main__":
    port = int(
        os.getenv(
            "PORT",
            "10000",
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
    )
