import os
import json
import sqlite3
import random
from datetime import datetime, timedelta

import requests
from flask import Flask, request


# ============================================================
# CONFIG
# ============================================================

VK_TOKEN = os.getenv("VK_TOKEN", "")
VK_SECRET_KEY = os.getenv("VK_SECRET_KEY", "")
VK_CONFIRMATION_TOKEN = os.getenv("VK_CONFIRMATION_TOKEN", "")

VK_API_VERSION = "5.199"

ADMINS = {
    87984447,
    172892670,
    148372158,
}

DB_FILE = "volley_wave.db"

app = Flask(__name__)

USER_STATE = {}


# ============================================================
# DATABASE
# ============================================================

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vk_id INTEGER UNIQUE,
            first_name TEXT,
            last_name TEXT,
            created_at TEXT
        )
    """)

    conn.execute("""
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
            capacity INTEGER DEFAULT 20,
            price INTEGER DEFAULT 0,
            location TEXT,
            status TEXT DEFAULT 'active',
            template_id INTEGER,
            created_at TEXT,
            updated_at TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            training_id INTEGER,
            user_id INTEGER,
            created_at TEXT,
            UNIQUE(training_id, user_id)
        )
    """)

    conn.commit()
    conn.close()


init_database()


# ============================================================
# VK API
# ============================================================

def vk_api(method, **params):
    params["access_token"] = VK_TOKEN
    params["v"] = VK_API_VERSION

    try:
        response = requests.post(
            f"https://api.vk.com/method/{method}",
            data=params,
            timeout=15
        )

        data = response.json()

        if "error" in data:
            print("VK API ERROR:", data["error"], flush=True)

        return data

    except Exception as error:
        print("VK API REQUEST ERROR:", repr(error), flush=True)
        return None


def send_message(user_id, message, keyboard=None):
    params = {
        "user_id": user_id,
        "random_id": random.randint(1, 2_000_000_000),
        "message": message,
    }

    if keyboard is not None:
        params["keyboard"] = json.dumps(
            keyboard,
            ensure_ascii=False,
            separators=(",", ":")
        )

    return vk_api("messages.send", **params)


# ============================================================
# KEYBOARDS
# ============================================================

def button(text, color="secondary"):
    return {
        "action": {
            "type": "text",
            "label": text,
        },
        "color": color,
    }


def main_keyboard(user_id):
    rows = [
        [
            button("📅 Расписание на неделю", "primary")
        ],
        [
            button("📝 Записаться", "positive")
        ],
        [
            button("📋 Мои тренировки", "secondary")
        ],
        [
            button("❌ Отмена тренировки", "negative")
        ],
    ]

    if user_id in ADMINS:
        rows.append([
            button("⚙️ Админ-панель", "secondary")
        ])

    return {
        "one_time": False,
        "inline": False,
        "buttons": rows,
    }


def admin_keyboard():
    return {
        "one_time": False,
        "inline": False,
        "buttons": [
            [
                button("📋 Расписание с учениками", "primary")
            ],
            [
                button("➕ Создать тренировку", "positive")
            ],
            [
                button("🗑 Удалить тренировку", "negative")
            ],
            [
                button("⬅️ Главное меню", "secondary")
            ],
        ],
    }


def back_keyboard():
    return {
        "one_time": False,
        "inline": False,
        "buttons": [
            [
                button("⬅️ Назад", "secondary")
            ]
        ],
    }


# ============================================================
# STATE
# ============================================================

def set_state(user_id, state):
    USER_STATE[user_id] = state


def get_state(user_id):
    return USER_STATE.get(user_id, "main")


def clear_state(user_id):
    USER_STATE.pop(user_id, None)


# ============================================================
# USERS
# ============================================================

def ensure_user(user_id):
    conn = get_db()

    row = conn.execute(
        "SELECT id FROM users WHERE vk_id=?",
        (user_id,)
    ).fetchone()

    if row is None:
        conn.execute("""
            INSERT INTO users (
                vk_id,
                created_at
            )
            VALUES (?, ?)
        """, (
            user_id,
            datetime.now().isoformat()
        ))

        conn.commit()

    conn.close()


def get_internal_user_id(user_id):
    ensure_user(user_id)

    conn = get_db()

    row = conn.execute(
        "SELECT id FROM users WHERE vk_id=?",
        (user_id,)
    ).fetchone()

    conn.close()

    if row:
        return row["id"]

    return None


# ============================================================
# DATES
# ============================================================

WEEKDAYS = [
    "Пн",
    "Вт",
    "Ср",
    "Чт",
    "Пт",
    "Сб",
    "Вс",
]


def parse_date(value):
    if not value:
        return None

    value = str(value).strip()

    formats = [
        "%d.%m.%Y",
        "%Y-%m-%d",
        "%d.%m.%y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass

    return None


def format_date(value):
    parsed = parse_date(value)

    if not parsed:
        return str(value)

    return (
        f"{WEEKDAYS[parsed.weekday()]} "
        f"{parsed.strftime('%d.%m')}"
    )


# ============================================================
# TRAININGS
# ============================================================

def get_week_trainings():
    today = datetime.now().date()
    end_date = today + timedelta(days=6)

    conn = get_db()

    rows = conn.execute("""
        SELECT *
        FROM trainings
        WHERE status='active'
          AND category='adults'
    """).fetchall()

    conn.close()

    result = []

    for row in rows:
        parsed = parse_date(row["training_date"])

        if not parsed:
            continue

        if today <= parsed <= end_date:
            result.append(row)

    result.sort(
        key=lambda row: (
            parse_date(row["training_date"]),
            row["start_time"] or ""
        )
    )

    return result


def get_future_trainings():
    today = datetime.now().date()

    conn = get_db()

    rows = conn.execute("""
        SELECT *
        FROM trainings
        WHERE status='active'
          AND category='adults'
    """).fetchall()

    conn.close()

    result = []

    for row in rows:
        parsed = parse_date(row["training_date"])

        if parsed and parsed >= today:
            result.append(row)

    result.sort(
        key=lambda row: (
            parse_date(row["training_date"]),
            row["start_time"] or ""
        )
    )

    return result


def get_training(training_id):
    conn = get_db()

    row = conn.execute("""
        SELECT *
        FROM trainings
        WHERE id=?
          AND status='active'
    """, (training_id,)).fetchone()

    conn.close()

    return row


def training_text(row):
    time_text = row["start_time"] or ""

    if row["end_time"]:
        time_text += f"-{row['end_time']}"

    return (
        f"#{row['id']}  "
        f"{format_date(row['training_date'])} "
        f"{time_text}\n"
        f"Формат: {row['format'] or '—'}\n"
        f"Уровень: {row['level'] or '—'}\n"
        f"Цена: {row['price'] or 0} ₽\n"
        f"Тренер: {row['coach'] or '—'}"
    )


def training_short_text(row):
    time_text = row["start_time"] or ""

    if row["end_time"]:
        time_text += f"-{row['end_time']}"

    return (
        f"#{row['id']} — "
        f"{format_date(row['training_date'])} "
        f"{time_text}\n"
        f"{row['format'] or '—'}, "
        f"{row['level'] or '—'}"
    )


# ============================================================
# REGISTRATIONS
# ============================================================

def is_registered(user_id, training_id):
    internal_id = get_internal_user_id(user_id)

    conn = get_db()

    row = conn.execute("""
        SELECT id
        FROM registrations
        WHERE training_id=?
          AND user_id=?
    """, (
        training_id,
        internal_id
    )).fetchone()

    conn.close()

    return row is not None


def register_user(user_id, training_id):
    internal_id = get_internal_user_id(user_id)

    conn = get_db()

    training = conn.execute("""
        SELECT *
        FROM trainings
        WHERE id=?
          AND status='active'
    """, (training_id,)).fetchone()

    if not training:
        conn.close()
        return "not_found"

    existing = conn.execute("""
        SELECT id
        FROM registrations
        WHERE training_id=?
          AND user_id=?
    """, (
        training_id,
        internal_id
    )).fetchone()

    if existing:
        conn.close()
        return "already"

    capacity = training["capacity"] or 20

    count = conn.execute("""
        SELECT COUNT(*)
        FROM registrations
        WHERE training_id=?
    """, (training_id,)).fetchone()[0]

    if count >= capacity:
        conn.close()
        return "full"

    try:
        conn.execute("""
            INSERT INTO registrations (
                training_id,
                user_id,
                created_at
            )
            VALUES (?, ?, ?)
        """, (
            training_id,
            internal_id,
            datetime.now().isoformat()
        ))

        conn.commit()
        conn.close()

        return "ok"

    except sqlite3.IntegrityError:
        conn.close()
        return "already"


def cancel_registration(user_id, training_id):
    internal_id = get_internal_user_id(user_id)

    conn = get_db()

    result = conn.execute("""
        DELETE FROM registrations
        WHERE training_id=?
          AND user_id=?
    """, (
        training_id,
        internal_id
    ))

    conn.commit()
    conn.close()

    return result.rowcount > 0


def get_user_trainings(user_id):
    internal_id = get_internal_user_id(user_id)

    conn = get_db()

    rows = conn.execute("""
        SELECT t.*
        FROM trainings t
        JOIN registrations r
          ON r.training_id=t.id
        WHERE r.user_id=?
          AND t.status='active'
        ORDER BY t.training_date, t.start_time
    """, (internal_id,)).fetchall()

    conn.close()

    return rows


# ============================================================
# USER MENU
# ============================================================

def show_main(user_id):
    clear_state(user_id)

    send_message(
        user_id,
        "Главное меню:",
        main_keyboard(user_id)
    )


def show_schedule(user_id):
    rows = get_week_trainings()

    if not rows:
        text = "📅 На ближайшие 7 дней тренировок пока нет."
    else:
        parts = ["📅 Расписание на неделю:\n"]

        for row in rows:
            parts.append(training_text(row))

        text = "\n\n".join(parts)

    send_message(
        user_id,
        text,
        main_keyboard(user_id)
    )


def start_booking(user_id):
    rows = get_week_trainings()

    if not rows:
        send_message(
            user_id,
            "На ближайшие 7 дней тренировок нет.",
            main_keyboard(user_id)
        )
        return

    parts = ["📝 Выбери тренировку:\n"]

    for row in rows:
        parts.append(training_short_text(row))

    parts.append("\nНапиши номер тренировки.")

    set_state(user_id, "booking")

    send_message(
        user_id,
        "\n\n".join(parts),
        back_keyboard()
    )


def booking(user_id, text):
    try:
        training_id = int(text.strip())
    except ValueError:
        send_message(
            user_id,
            "Напиши только номер тренировки."
        )
        return

    training = get_training(training_id)

    if not training:
        send_message(
            user_id,
            "Такой тренировки нет."
        )
        return

    result = register_user(user_id, training_id)

    if result == "already":
        send_message(
            user_id,
            "Ты уже записан на эту тренировку.",
            main_keyboard(user_id)
        )
        clear_state(user_id)
        return

    if result == "full":
        send_message(
            user_id,
            "На тренировке уже нет свободных мест.",
            main_keyboard(user_id)
        )
        clear_state(user_id)
        return

    if result != "ok":
        send_message(
            user_id,
            "Не удалось записаться. Попробуй ещё раз.",
            main_keyboard(user_id)
        )
        clear_state(user_id)
        return

    clear_state(user_id)

    send_message(
        user_id,
        "✅ Ты записан:\n\n" + training_text(training),
        main_keyboard(user_id)
    )


def show_my_trainings(user_id):
    rows = get_user_trainings(user_id)

    if not rows:
        send_message(
            user_id,
            "📋 У тебя пока нет записей.",
            main_keyboard(user_id)
        )
        return

    parts = ["📋 Мои тренировки:\n"]

    for row in rows:
        parts.append(training_text(row))

    send_message(
        user_id,
        "\n\n".join(parts),
        main_keyboard(user_id)
    )


def start_cancel(user_id):
    rows = get_user_trainings(user_id)

    if not rows:
        send_message(
            user_id,
            "У тебя нет тренировок для отмены.",
            main_keyboard(user_id)
        )
        return

    parts = [
        "❌ Напиши номер тренировки, "
        "которую хочешь отменить:\n"
    ]

    for row in rows:
        parts.append(training_short_text(row))

    set_state(user_id, "cancel")

    send_message(
        user_id,
        "\n\n".join(parts),
        back_keyboard()
    )


def cancel_training(user_id, text):
    try:
        training_id = int(text.strip())
    except ValueError:
        send_message(
            user_id,
            "Напиши только номер тренировки."
        )
        return

    if cancel_registration(user_id, training_id):
        text = "✅ Запись отменена."
    else:
        text = "Не удалось найти эту запись."

    clear_state(user_id)

    send_message(
        user_id,
        text,
        main_keyboard(user_id)
    )


# ============================================================
# ADMIN
# ============================================================

def show_admin(user_id):
    set_state(user_id, "admin")

    send_message(
        user_id,
        "⚙️ Админ-панель:",
        admin_keyboard()
    )


def admin_schedule(user_id):
    rows = get_week_trainings()

    if not rows:
        send_message(
            user_id,
            "На ближайшие 7 дней тренировок нет.",
            admin_keyboard()
        )
        return

    conn = get_db()

    parts = ["📋 Расписание с учениками:\n"]

    for row in rows:
        students = conn.execute("""
            SELECT u.vk_id, u.first_name, u.last_name
            FROM registrations r
            JOIN users u
              ON u.id=r.user_id
            WHERE r.training_id=?
        """, (row["id"],)).fetchall()

        parts.append(training_text(row))

        if not students:
            parts.append("Ученики: пока нет")
        else:
            parts.append("Ученики:")

            for student in students:
                name = (
                    f"{student['first_name'] or ''} "
                    f"{student['last_name'] or ''}"
                ).strip()

                if not name:
                    name = f"id{student['vk_id']}"

                parts.append(
                    f"• {name} — vk.com/id{student['vk_id']}"
                )

    conn.close()

    send_message(
        user_id,
        "\n\n".join(parts),
        admin_keyboard()
    )


def start_create_training(user_id):
    set_state(user_id, "create")

    send_message(
        user_id,
        "➕ Создание тренировки\n\n"
        "Отправь ВСЕ данные одним сообщением.\n"
        "Каждый пункт с новой строки:\n\n"
        "1. Дата\n"
        "2. Время\n"
        "3. Формат\n"
        "4. Уровень\n"
        "5. Цена\n"
        "6. Тренер\n\n"
        "Пример:\n\n"
        "06.10.2026\n"
        "19:00-20:30\n"
        "Техничка\n"
        "Общий\n"
        "1200\n"
        "Алексей",
        back_keyboard()
    )


def create_training(user_id, text):
    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    if len(lines) != 6:
        send_message(
            user_id,
            "❌ Нужно ровно 6 строк:\n\n"
            "Дата\n"
            "Время\n"
            "Формат\n"
            "Уровень\n"
            "Цена\n"
            "Тренер"
        )
        return

    training_date = lines[0]
    time_value = lines[1]
    format_value = lines[2]
    level_value = lines[3]
    price_value = lines[4]
    coach_value = lines[5]

    parsed_date = parse_date(training_date)

    if not parsed_date:
        send_message(
            user_id,
            "❌ Неверная дата.\n"
            "Используй формат ДД.ММ.ГГГГ."
        )
        return

    if not price_value.isdigit():
        send_message(
            user_id,
            "❌ Цена должна быть числом."
        )
        return

    if "-" in time_value:
        time_parts = time_value.split("-", 1)
        start_time = time_parts[0].strip()
        end_time = time_parts[1].strip()
    else:
        start_time = time_value
        end_time = ""

    conn = get_db()

    now = datetime.now().isoformat()

    conn.execute("""
        INSERT INTO trainings (
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
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        parsed_date.strftime("%Y-%m-%d"),
        WEEKDAYS[parsed_date.weekday()],
        start_time,
        end_time,
        format_value,
        "adults",
        "adults",
        level_value,
        format_value,
        coach_value,
        20,
        int(price_value),
        "",
        "active",
        now,
        now
    ))

    conn.commit()

    training_id = conn.execute(
        "SELECT last_insert_rowid()"
    ).fetchone()[0]

    conn.close()

    clear_state(user_id)

    send_message(
        user_id,
        f"✅ Тренировка создана #{training_id}\n\n"
        f"{format_date(parsed_date.strftime('%Y-%m-%d'))} "
        f"{time_value}\n"
        f"Формат: {format_value}\n"
        f"Уровень: {level_value}\n"
        f"Цена: {price_value} ₽\n"
        f"Тренер: {coach_value}",
        admin_keyboard()
    )


def start_delete_training(user_id):
    rows = get_future_trainings()

    if not rows:
        send_message(
            user_id,
            "Тренировок для удаления нет.",
            admin_keyboard()
        )
        return

    parts = [
        "🗑 Напиши номер тренировки, "
        "которую нужно удалить:\n"
    ]

    for row in rows:
        parts.append(training_short_text(row))

    set_state(user_id, "delete")

    send_message(
        user_id,
        "\n\n".join(parts),
        back_keyboard()
    )


def delete_training(user_id, text):
    try:
        training_id = int(text.strip())
    except ValueError:
        send_message(
            user_id,
            "Напиши только номер тренировки."
        )
        return

    conn = get_db()

    row = conn.execute("""
        SELECT id
        FROM trainings
        WHERE id=?
          AND status='active'
    """, (training_id,)).fetchone()

    if not row:
        conn.close()

        send_message(
            user_id,
            "Такой тренировки нет."
        )
        return

    conn.execute("""
        UPDATE trainings
        SET status='deleted',
            updated_at=?
        WHERE id=?
    """, (
        datetime.now().isoformat(),
        training_id
    ))

    conn.commit()
    conn.close()

    clear_state(user_id)

    send_message(
        user_id,
        "✅ Тренировка удалена.",
        admin_keyboard()
    )


# ============================================================
# MESSAGE HANDLER
# ============================================================

def handle_message(user_id, text):
    ensure_user(user_id)

    text = (text or "").strip()
    state = get_state(user_id)

    print(
        f"VK MESSAGE: user_id={user_id}, "
        f"state={state}, text={text!r}",
        flush=True
    )

    # Назад
    if text == "⬅️ Назад":
        show_main(user_id)
        return

    # Главное меню
    if text in (
        "Привет",
        "привет",
        "Начать",
        "начать",
        "/start"
    ):
        show_main(user_id)
        return

    # --------------------------------------------------------
    # ADMIN
    # --------------------------------------------------------

    if user_id in ADMINS:

        if text == "⚙️ Админ-панель":
            show_admin(user_id)
            return

        if text == "📋 Расписание с учениками":
            admin_schedule(user_id)
            return

        if text == "➕ Создать тренировку":
            start_create_training(user_id)
            return

        if text == "🗑 Удалить тренировку":
            start_delete_training(user_id)
            return

        if state == "create":
            create_training(user_id, text)
            return

        if state == "delete":
            delete_training(user_id, text)
            return

        if state == "admin":
            show_admin(user_id)
            return

    # --------------------------------------------------------
    # USER
    # --------------------------------------------------------

    if text == "📅 Расписание на неделю":
        show_schedule(user_id)
        return

    if text == "📝 Записаться":
        start_booking(user_id)
        return

    if text == "📋 Мои тренировки":
        show_my_trainings(user_id)
        return

    if text == "❌ Отмена тренировки":
        start_cancel(user_id)
        return

    if state == "booking":
        booking(user_id, text)
        return

    if state == "cancel":
        cancel_training(user_id, text)
        return

    show_main(user_id)


# ============================================================
# VK CALLBACK
# ============================================================

def process_event(data):
    if not isinstance(data, dict):
        return "ok"

    event_type = data.get("type")

    # Подтверждение Callback API
    if event_type == "confirmation":
        return VK_CONFIRMATION_TOKEN

    # Нас интересуют только новые сообщения
    if event_type != "message_new":
        return "ok"

    # Проверка секретного ключа
    if VK_SECRET_KEY:
        if data.get("secret") != VK_SECRET_KEY:
            print("VK SECRET MISMATCH", flush=True)
            return "ok"

    obj = data.get("object")

    user_id = None
    text = ""

    if isinstance(obj, dict):

        # Новый формат VK
        message = obj.get("message")

        if isinstance(message, dict):
            user_id = message.get("from_id")
            text = message.get("text", "")

        # Старый формат VK
        else:
            user_id = obj.get("from_id")
            text = obj.get("text", "")

    if user_id is None:
        print(
            "VK EVENT WITHOUT USER:",
            json.dumps(data, ensure_ascii=False),
            flush=True
        )
        return "ok"

    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return "ok"

    handle_message(user_id, text)

    return "ok"


@app.route("/callback", methods=["POST"])
def callback():
    try:
        data = request.get_json(silent=True)

        if not data:
            print("EMPTY VK EVENT", flush=True)
            return "ok"

        print(
            "VK EVENT:",
            json.dumps(data, ensure_ascii=False),
            flush=True
        )

        return process_event(data)

    except Exception as error:
        print(
            "CALLBACK ERROR:",
            repr(error),
            flush=True
        )
        return "ok"


@app.route("/", methods=["GET"])
def index():
    return "VOLLEY WAVE BOT OK"


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))

    app.run(
        host="0.0.0.0",
        port=port
    )
