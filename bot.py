import os
import json
import random
import requests

from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

from flask import Flask, request

from database import (
    init_db,

    create_or_update_user,
    get_user,
    is_user_blocked,

    create_training_template,
    get_training_templates,

    create_training,
    get_training,
    get_upcoming_trainings,
    get_trainings_by_date,

    get_registration,
    get_registration_count,
    get_registrations,
    add_registration,
    cancel_registration,
    get_user_registrations,

    get_waitlist,
    get_waitlist_entry,
    add_to_waitlist,
    remove_from_waitlist,

    mark_attendance,
    get_training_attendance,

    create_notification,

    add_admin_log,
)


# ============================================================
# НАСТРОЙКИ
# ============================================================

VK_TOKEN = os.getenv("VK_TOKEN")
VK_SECRET_KEY = os.getenv("VK_SECRET_KEY")
VK_CONFIRMATION_TOKEN = os.getenv("VK_CONFIRMATION_TOKEN")

VK_API_VERSION = "5.199"

TIMEZONE = "Asia/Yekaterinburg"

ADMIN_IDS = {
    87984447,
    172892670,
    148372158,
}

app = Flask(__name__)

user_states = {}


# ============================================================
# ИНИЦИАЛИЗАЦИЯ
# ============================================================

init_db()


# ============================================================
# ВРЕМЯ
# ============================================================

def now_local():
    return datetime.now(
        ZoneInfo(TIMEZONE)
    )


def today_local():
    return now_local().date()


# ============================================================
# VK API
# ============================================================

def vk_api(method, params=None):
    if params is None:
        params = {}

    params["access_token"] = VK_TOKEN
    params["v"] = VK_API_VERSION

    try:
        response = requests.post(
            f"https://api.vk.com/method/{method}",
            data=params,
            timeout=15,
        )

        return response.json()

    except Exception as error:
        print(
            f"VK API ERROR: {error}"
        )

        return {}


def send_message(
    user_id,
    message,
    keyboard_data=None,
):
    params = {
        "user_id": user_id,
        "message": message,
        "random_id": random.randint(
            -2147483648,
            2147483647,
        ),
    }

    if keyboard_data is not None:
        params["keyboard"] = json.dumps(
            keyboard_data,
            ensure_ascii=False,
        )

    result = vk_api(
        "messages.send",
        params,
    )

    print(
        f"SEND MESSAGE: user_id={user_id}, result={result}"
    )

    return result


def get_vk_user(user_id):
    result = vk_api(
        "users.get",
        {
            "user_ids": user_id,
        },
    )

    try:
        users = result.get(
            "response",
            [],
        )

        if users:
            return users[0]

    except Exception:
        pass

    return None


# ============================================================
# КЛАВИАТУРЫ
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


def make_keyboard(
    rows,
    one_time=False,
):
    return {
        "one_time": one_time,
        "buttons": rows,
    }


def back_button():
    return button(
        "⬅️ Назад",
        "secondary",
    )


def admin_back_button():
    return button(
        "⚙️ В админ-панель",
        "primary",
    )


# ============================================================
# ГЛАВНОЕ МЕНЮ
# ============================================================

def main_menu(user_id):
    rows = [
        [
            button(
                "🏐 Записаться",
                "positive",
            ),
            button(
                "📅 Расписание",
                "primary",
            ),
        ],
        [
            button(
                "👤 Мои тренировки",
                "secondary",
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
                "🎯 Индивидуальная тренировка",
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

    if user_id in ADMIN_IDS:
        rows.append([
            button(
                "⚙️ Админ-панель",
                "primary",
            )
        ])

    return make_keyboard(rows)


def admin_menu():
    return make_keyboard([
        [
            button(
                "📅 Расписание",
                "primary",
            ),
        ],
        [
            button(
                "👥 Участники тренировок",
                "primary",
            ),
        ],
        [
            button(
                "➕ Добавить тренировку",
                "positive",
            ),
        ],
        [
            button(
                "📋 Шаблоны расписания",
                "secondary",
            ),
        ],
        [
            button(
                "👤 Пользовательский режим",
                "secondary",
            ),
        ],
    ])


# ============================================================
# СОСТОЯНИЯ
# ============================================================

def set_state(
    user_id,
    state,
    data=None,
):
    user_states[user_id] = {
        "state": state,
        "data": data or {},
    }


def get_state(user_id):
    return user_states.get(
        user_id,
        {
            "state": None,
            "data": {},
        },
    )


def clear_state(user_id):
    user_states.pop(
        user_id,
        None,
    )


# ============================================================
# ПОЛЬЗОВАТЕЛИ
# ============================================================

def register_user(user_id):
    vk_user = get_vk_user(
        user_id
    )

    first_name = None
    last_name = None

    if vk_user:
        first_name = vk_user.get(
            "first_name"
        )
        last_name = vk_user.get(
            "last_name"
        )

    create_or_update_user(
        user_id,
        first_name,
        last_name,
    )


# ============================================================
# ФОРМАТИРОВАНИЕ
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


def category_text(category):
    if category == "children":
        return "👶 Дети"

    if category == "adults":
        return "🧑 Взрослые"

    return category or "—"


def full_date_text(date_value):
    if isinstance(
        date_value,
        str,
    ):
        date_value = date.fromisoformat(
            date_value
        )

    return (
        f"{WEEKDAYS[date_value.weekday()]}, "
        f"{date_value.day:02d}."
        f"{date_value.month:02d}."
        f"{date_value.year}"
    )


def training_date_text(training):
    return full_date_text(
        training["training_date"]
    )


def training_short_date(training):
    date_value = date.fromisoformat(
        training["training_date"]
    )

    return (
        f"{WEEKDAYS_SHORT[date_value.weekday()]}, "
        f"{date_value.strftime('%d.%m')}"
    )


# ============================================================
# ДАТА / ВРЕМЯ ТРЕНИРОВКИ
# ============================================================

def training_datetime(training):
    training_date = date.fromisoformat(
        training["training_date"]
    )

    time_value = datetime.strptime(
        training["start_time"],
        "%H:%M",
    ).time()

    return datetime.combine(
        training_date,
        time_value,
    ).replace(
        tzinfo=ZoneInfo(TIMEZONE)
    )


def can_cancel_training(training):
    start = training_datetime(
        training
    )

    return (
        start - now_local()
        >= timedelta(hours=24)
    )


def is_training_in_future(training):
    return (
        training_datetime(training)
        > now_local()
    )


# ============================================================
# ЦЕНЫ
# ============================================================

def show_prices(user_id):
    text = (
        "💰 Цены\n\n"
        "👶 Дети — 600 ₽ за тренировку\n\n"
        "🧑 Взрослые:\n"
        "• 1–6 человек — 1200 ₽/чел.\n"
        "• 7 и более — 1000 ₽/чел.\n\n"
        "Минимальная группа для взрослой "
        "тренировки — 4 человека."
    )

    send_message(
        user_id,
        text,
        make_keyboard([
            [back_button()],
        ]),
    )


# ============================================================
# ЛОКАЦИИ
# ============================================================

def show_locations(user_id):
    text = (
        "📍 Где тренируемся\n\n"
        "☀️ Летом\n"
        "Парк Гагарина, Челябинск.\n\n"
        "❄️ Зимой\n"
        "СК «Арена»\n"
        "ул. Молодогвардейцев, 7\n\n"
        "🏐 Тренировки проходят на песке."
    )

    send_message(
        user_id,
        text,
        make_keyboard([
            [back_button()],
        ]),
    )


# ============================================================
# ШАБЛОНЫ РАСПИСАНИЯ
# ============================================================

INITIAL_TEMPLATES = [
    (
        0,
        "09:00",
        "11:00",
        "Дети 9–13",
        "children",
        "9–13",
        "Начальный / средний",
        "Группа",
        "Алексей",
        10,
        600,
        "СК «Арена»",
    ),
    (
        0,
        "17:00",
        "19:00",
        "Дети 11–14",
        "children",
        "11–14",
        "Средний",
        "Группа",
        "Алексей",
        10,
        600,
        "СК «Арена»",
    ),
    (
        0,
        "19:00",
        "20:30",
        "Техничка",
        "adults",
        "18+",
        "Техническая",
        "Группа",
        "Алексей",
        10,
        1200,
        "СК «Арена»",
    ),
    (
        1,
        "09:00",
        "11:00",
        "Общая группа",
        "adults",
        "18+",
        "Общий",
        "Группа",
        "Алексей",
        8,
        1200,
        "СК «Арена»",
    ),
    (
        1,
        "17:00",
        "18:30",
        "Дети 11–14",
        "children",
        "11–14",
        "Средний",
        "Группа",
        "Алексей",
        10,
        600,
        "СК «Арена»",
    ),
    (
        1,
        "19:30",
        "21:00",
        "Женская группа",
        "adults",
        "18+",
        "Средний+",
        "Группа",
        "Алексей",
        8,
        1200,
        "СК «Арена»",
    ),
    (
        2,
        "09:00",
        "11:00",
        "Дети 9–14",
        "children",
        "9–14",
        "Начальный / средний",
        "Группа",
        "Алексей",
        10,
        600,
        "СК «Арена»",
    ),
    (
        2,
        "17:00",
        "18:00",
        "Дети 5–9",
        "children",
        "5–9",
        "Начальный",
        "Группа",
        "Ксения",
        10,
        600,
        "СК «Арена»",
    ),
    (
        2,
        "18:00",
        "19:30",
        "Продвинутая группа",
        "adults",
        "18+",
        "Продвинутый",
        "Группа",
        "Алексей",
        8,
        1200,
        "СК «Арена»",
    ),
    (
        2,
        "19:30",
        "21:00",
        "MIXED",
        "adults",
        "18+",
        "Средний+",
        "MIXED",
        "Алексей",
        8,
        1200,
        "СК «Арена»",
    ),
    (
        3,
        "09:00",
        "11:00",
        "Общая группа",
        "adults",
        "18+",
        "Общий",
        "Группа",
        "Алексей",
        8,
        1200,
        "СК «Арена»",
    ),
    (
        3,
        "17:00",
        "19:00",
        "Дети 11–14",
        "children",
        "11–14",
        "Средний",
        "Группа",
        "Алексей",
        10,
        600,
        "СК «Арена»",
    ),
    (
        3,
        "19:00",
        "20:30",
        "Средняя группа",
        "adults",
        "18+",
        "Средний",
        "Группа",
        "Алексей",
        8,
        1200,
        "СК «Арена»",
    ),
    (
        4,
        "09:00",
        "11:00",
        "Дети 9–14",
        "children",
        "9–14",
        "Начальный / средний",
        "Группа",
        "Алексей",
        10,
        600,
        "СК «Арена»",
    ),
    (
        4,
        "17:00",
        "18:00",
        "Дети 5–10",
        "children",
        "5–10",
        "Начальный",
        "Группа",
        "Ксения",
        10,
        600,
        "СК «Арена»",
    ),
    (
        4,
        "17:00",
        "19:00",
        "Дети 11–14",
        "children",
        "11–14",
        "Средний",
        "Группа",
        "Алексей",
        10,
        600,
        "СК «Арена»",
    ),
    (
        4,
        "19:00",
        "20:30",
        "Техничка",
        "adults",
        "18+",
        "Техническая",
        "Группа",
        "Алексей",
        10,
        1200,
        "СК «Арена»",
    ),
]


def ensure_templates():
    templates = get_training_templates(
        active_only=False
    )

    if templates:
        return

    print(
        "Creating initial training templates..."
    )

    for item in INITIAL_TEMPLATES:
        create_training_template(
            weekday=item[0],
            start_time=item[1],
            end_time=item[2],
            title=item[3],
            category=item[4],
            age_group=item[5],
            level=item[6],
            format=item[7],
            coach=item[8],
            capacity=item[9],
            price=item[10],
            location=item[11],
        )


def generate_trainings_for_period(
    weeks=6,
):
    ensure_templates()

    templates = get_training_templates(
        active_only=True
    )

    start_date = today_local()

    end_date = (
        start_date
        + timedelta(weeks=weeks)
    )

    existing = get_upcoming_trainings()

    existing_keys = set()

    for training in existing:
        existing_keys.add(
            (
                training["training_date"],
                training["start_time"],
                training["title"],
            )
        )

    current = start_date

    while current <= end_date:

        for template in templates:

            if current.weekday() != template["weekday"]:
                continue

            key = (
                current.isoformat(),
                template["start_time"],
                template["title"],
            )

            if key in existing_keys:
                continue

            create_training(
                training_date=current.isoformat(),
                weekday=current.weekday(),
                start_time=template["start_time"],
                end_time=template["end_time"],
                title=template["title"],
                category=template["category"],
                age_group=template["age_group"],
                level=template["level"],
                format=template["format"],
                coach=template["coach"],
                capacity=template["capacity"],
                price=template["price"],
                location=template["location"],
                template_id=template["id"],
            )

            existing_keys.add(key)

        current += timedelta(days=1)


# ============================================================
# РАСПИСАНИЕ
# ============================================================

def show_schedule_categories(user_id):
    clear_state(user_id)

    send_message(
        user_id,
        "📅 Выберите категорию:",
        make_keyboard([
            [
                button(
                    "👶 Дети",
                    "positive",
                ),
                button(
                    "🧑 Взрослые",
                    "primary",
                ),
            ],
            [
                back_button(),
            ],
        ]),
    )


def show_schedule_week(
    user_id,
    category,
):
    start = today_local()

    end = (
        start
        + timedelta(days=6)
    )

    trainings = get_upcoming_trainings(
        from_date=start.isoformat(),
        to_date=end.isoformat(),
        category=category,
    )

    if not trainings:
        send_message(
            user_id,
            "📅 В ближайшие 7 дней тренировок нет.",
            make_keyboard([
                [back_button()],
            ]),
        )
        return

    lines = [
        f"📅 Расписание — {category_text(category)}",
        "",
    ]

    current_day = None

    for training in trainings:

        training_day = training["training_date"]

        if training_day != current_day:
            current_day = training_day

            lines.append(
                f"🔹 {training_date_text(training)}"
            )

        count = get_registration_count(
            training["id"]
        )

        lines.append(
            f"№{training['training_number']} "
            f"• {training['start_time']}–"
            f"{training['end_time']} "
            f"• {training['title']} "
            f"• {count}/{training['capacity']}"
        )

    send_message(
        user_id,
        "\n".join(lines),
        make_keyboard([
            [back_button()],
        ]),
    )


# ============================================================
# ЗАПИСЬ
# ============================================================

def start_booking(user_id):
    set_state(
        user_id,
        "booking_category",
    )

    send_message(
        user_id,
        "🏐 На какую тренировку хотите записаться?",
        make_keyboard([
            [
                button(
                    "👶 Дети",
                    "positive",
                ),
                button(
                    "🧑 Взрослые",
                    "primary",
                ),
            ],
            [
                back_button(),
            ],
        ]),
    )


def show_booking_dates(
    user_id,
    category,
):
    start = today_local()

    end = (
        start
        + timedelta(days=6)
    )

    trainings = get_upcoming_trainings(
        from_date=start.isoformat(),
        to_date=end.isoformat(),
        category=category,
    )

    if not trainings:
        send_message(
            user_id,
            "На ближайшие дни тренировок нет.",
            make_keyboard([
                [back_button()],
            ]),
        )
        return

    dates = []

    for training in trainings:
        if training["training_date"] not in dates:
            dates.append(
                training["training_date"]
            )

    rows = []

    for date_text in dates:

        date_value = date.fromisoformat(
            date_text
        )

        label = (
            f"{WEEKDAYS_SHORT[date_value.weekday()]}, "
            f"{date_value.strftime('%d.%m')}"
        )

        rows.append([
            button(
                label,
                "primary",
            )
        ])

    rows.append([
        back_button(),
    ])

    set_state(
        user_id,
        "booking_date",
        {
            "category": category,
        },
    )

    send_message(
        user_id,
        "📅 Выберите день:",
        make_keyboard(rows),
    )


def show_booking_trainings(
    user_id,
    category,
    training_date,
):
    trainings = get_trainings_by_date(
        training_date,
        category,
    )

    if not trainings:
        send_message(
            user_id,
            "На этот день тренировок нет.",
            make_keyboard([
                [back_button()],
            ]),
        )
        return

    rows = []

    for training in trainings:

        count = get_registration_count(
            training["id"]
        )

        if count >= training["capacity"]:
            color = "secondary"
            suffix = " — НЕТ МЕСТ"
        else:
            color = "primary"
            suffix = (
                f" — {count}/{training['capacity']}"
            )

        label = (
            f"№{training['training_number']} "
            f"{training['start_time']} "
            f"{training['title']}"
            f"{suffix}"
        )

        rows.append([
            button(
                label,
                color,
            )
        ])

    rows.append([
        back_button(),
    ])

    set_state(
        user_id,
        "booking_training",
        {
            "category": category,
            "training_date": training_date,
        },
    )

    date_value = date.fromisoformat(
        training_date
    )

    send_message(
        user_id,
        (
            f"🏐 Тренировки на "
            f"{WEEKDAYS[date_value.weekday()]}, "
            f"{date_value.strftime('%d.%m.%Y')}"
        ),
        make_keyboard(rows),
    )


def find_booking_training(
    user_id,
    text,
):
    state = get_state(
        user_id
    )

    data = state["data"]

    category = data.get(
        "category"
    )

    training_date = data.get(
        "training_date"
    )

    if not category or not training_date:
        return None

    trainings = get_trainings_by_date(
        training_date,
        category,
    )

    for training in trainings:

        prefix = (
            f"№{training['training_number']} "
            f"{training['start_time']} "
            f"{training['title']}"
        )

        if text.startswith(prefix):
            return training

    return None


def show_training_details(
    user_id,
    training,
):
    count = get_registration_count(
        training["id"]
    )

    registrations = get_registrations(
        training["id"]
    )

    lines = [
        f"🏐 Тренировка №{training['training_number']}",
        "",
        f"📅 {training_date_text(training)}",
        f"⏰ {training['start_time']}–{training['end_time']}",
        "",
        f"🏷 {training['title']}",
        f"👥 Формат: {training['format']}",
        f"🎯 Уровень: {training['level']}",
        f"👶 Возраст: {training['age_group']}",
        f"👨‍🏫 Тренер: {training['coach']}",
        f"📍 {training['location']}",
        f"💰 {training['price']} ₽",
        "",
        f"👥 Мест занято: {count}/{training['capacity']}",
    ]

    if registrations:
        lines.append("")
        lines.append(
            "Уже записались:"
        )

        for index, registration in enumerate(
            registrations,
            start=1,
        ):
            name = " ".join(
                part
                for part in [
                    registration["first_name"],
                    registration["last_name"],
                ]
                if part
            )

            if not name:
                name = f"Участник {index}"

            lines.append(
                f"{index}. {name}"
            )

    rows = []

    existing = get_registration(
        training["id"],
        user_id,
    )

    if existing:
        rows.append([
            button(
                "❌ Отменить запись",
                "negative",
            )
        ])

    elif count < training["capacity"]:
        rows.append([
            button(
                "✅ Записаться",
                "positive",
            )
        ])

    else:
        wait = get_waitlist_entry(
            training["id"],
            user_id,
        )

        if wait:
            rows.append([
                button(
                    "❌ Выйти из листа ожидания",
                    "negative",
                )
            ])
        else:
            rows.append([
                button(
                    "➕ В лист ожидания",
                    "primary",
                )
            ])

    rows.append([
        back_button(),
    ])

    set_state(
        user_id,
        "training_details",
        {
            "training_id": training["id"],
        },
    )

    send_message(
        user_id,
        "\n".join(lines),
        make_keyboard(rows),
    )


# ============================================================
# ЗАПИСЬ НА ТРЕНИРОВКУ
# ============================================================

def register_for_training(
    user_id,
    training,
):
    if training["status"] != "scheduled":
        send_message(
            user_id,
            "Эта тренировка недоступна для записи.",
            make_keyboard([
                [back_button()],
            ]),
        )
        return

    if not is_training_in_future(
        training
    ):
        send_message(
            user_id,
            "Эта тренировка уже началась или закончилась.",
            make_keyboard([
                [back_button()],
            ]),
        )
        return

    existing = get_registration(
        training["id"],
        user_id,
    )

    if existing:
        send_message(
            user_id,
            "Вы уже записаны на эту тренировку.",
            make_keyboard([
                [back_button()],
            ]),
        )
        return

    count = get_registration_count(
        training["id"]
    )

    if count >= training["capacity"]:
        send_message(
            user_id,
            (
                "❌ Свободных мест больше нет.\n\n"
                "Можно встать в лист ожидания."
            ),
            make_keyboard([
                [
                    button(
                        "➕ В лист ожидания",
                        "primary",
                    )
                ],
                [back_button()],
            ]),
        )
        return

    try:
        add_registration(
            training["id"],
            user_id,
        )

        start = training_datetime(
            training
        )

        create_notification(
            user_id,
            training["id"],
            "24h",
            (
                start
                - timedelta(hours=24)
            ).isoformat(),
        )

        create_notification(
            user_id,
            training["id"],
            "2h",
            (
                start
                - timedelta(hours=2)
            ).isoformat(),
        )

        send_message(
            user_id,
            (
                "✅ Вы записаны!\n\n"
                f"🏐 Тренировка №"
                f"{training['training_number']}\n"
                f"📅 {training_date_text(training)}\n"
                f"⏰ {training['start_time']}–"
                f"{training['end_time']}\n"
                f"👨‍🏫 {training['coach']}\n"
                f"📍 {training['location']}"
            ),
            main_menu(user_id),
        )

        clear_state(user_id)

    except Exception as error:
        print(
            f"REGISTER ERROR: {error}"
        )

        send_message(
            user_id,
            f"❌ Не удалось записать вас: {error}",
            main_menu(user_id),
        )

        clear_state(user_id)


# ============================================================
# МОИ ТРЕНИРОВКИ
# ============================================================

def show_my_trainings(user_id):
    try:
        registrations = get_user_registrations(
            user_id
        )

    except Exception as error:
        print(
            f"MY TRAININGS ERROR: {error}"
        )

        send_message(
            user_id,
            "Не удалось получить ваши тренировки.",
            make_keyboard([
                [back_button()],
            ]),
        )
        return

    future_trainings = []

    for registration in registrations:

        training = get_training(
            registration["training_id"]
        )

        if not training:
            continue

        if training["status"] != "scheduled":
            continue

        if not is_training_in_future(
            training
        ):
            continue

        future_trainings.append(
            training
        )

    if not future_trainings:
        send_message(
            user_id,
            (
                "👤 Мои тренировки\n\n"
                "У вас пока нет предстоящих записей."
            ),
            make_keyboard([
                [back_button()],
            ]),
        )
        return

    lines = [
        "👤 Мои тренировки",
        "",
    ]

    rows = []

    for training in future_trainings:

        lines.append(
            f"🏐 Тренировка №"
            f"{training['training_number']}"
        )

        lines.append(
            f"📅 {training_date_text(training)}"
        )

        lines.append(
            f"⏰ {training['start_time']}–"
            f"{training['end_time']}"
        )

        lines.append(
            f"👨‍🏫 {training['coach']}"
        )

        lines.append("")

        rows.append([
            button(
                (
                    f"❌ №"
                    f"{training['training_number']} "
                    f"{training['start_time']}"
                ),
                "negative",
            )
        ])

    rows.append([
        back_button(),
    ])

    send_message(
        user_id,
        "\n".join(lines),
        make_keyboard(rows),
    )


def find_my_training_button(
    user_id,
    text,
):
    registrations = get_user_registrations(
        user_id
    )

    for registration in registrations:

        training = get_training(
            registration["training_id"]
        )

        if not training:
            continue

        expected = (
            f"❌ №"
            f"{training['training_number']} "
            f"{training['start_time']}"
        )

        if text == expected:
            return training

    return None


def cancel_my_training(
    user_id,
    training,
):
    if not can_cancel_training(
        training
    ):
        send_message(
            user_id,
            (
                "❌ Отмена невозможна.\n\n"
                "До тренировки осталось меньше 24 часов."
            ),
            make_keyboard([
                [back_button()],
            ]),
        )
        return

    existing = get_registration(
        training["id"],
        user_id,
    )

    if not existing:
        send_message(
            user_id,
            "Вы не записаны на эту тренировку.",
            main_menu(user_id),
        )
        return

    success = cancel_registration(
        training["id"],
        user_id,
        "Отмена пользователем",
    )

    if success:
        send_message(
            user_id,
            (
                "✅ Запись отменена.\n\n"
                f"Тренировка №"
                f"{training['training_number']}\n"
                f"📅 {training_date_text(training)}"
            ),
            main_menu(user_id),
        )

    else:
        send_message(
            user_id,
            "Не удалось отменить запись.",
            main_menu(user_id),
        )


# ============================================================
# ЛИСТ ОЖИДАНИЯ
# ============================================================

def join_waitlist(
    user_id,
    training,
):
    count = get_registration_count(
        training["id"]
    )

    if count < training["capacity"]:
        send_message(
            user_id,
            "Свободное место уже появилось. Можно сразу записаться.",
            make_keyboard([
                [
                    button(
                        "✅ Записаться",
                        "positive",
                    )
                ],
                [back_button()],
            ]),
        )
        return

    existing = get_waitlist_entry(
        training["id"],
        user_id,
    )

    if existing:
        send_message(
            user_id,
            (
                "Вы уже в листе ожидания.\n"
                f"Ваша позиция: {existing['position']}"
            ),
            make_keyboard([
                [back_button()],
            ]),
        )
        return

    try:
        add_to_waitlist(
            training["id"],
            user_id,
        )

        waitlist = get_waitlist(
            training["id"]
        )

        position = None

        for item in waitlist:
            if item["vk_id"] == user_id:
                position = item["position"]
                break

        send_message(
            user_id,
            (
                "➕ Вы добавлены в лист ожидания.\n\n"
                f"Тренировка №"
                f"{training['training_number']}\n"
                f"📅 {training_date_text(training)}\n"
                f"Ваша позиция: {position}"
            ),
            main_menu(user_id),
        )

        clear_state(user_id)

    except Exception as error:
        print(
            f"WAITLIST ERROR: {error}"
        )

        send_message(
            user_id,
            "Не удалось добавить вас в лист ожидания.",
            main_menu(user_id),
        )


def leave_waitlist(
    user_id,
    training,
):
    success = remove_from_waitlist(
        training["id"],
        user_id,
    )

    if success:
        send_message(
            user_id,
            "Вы вышли из листа ожидания.",
            main_menu(user_id),
        )

    else:
        send_message(
            user_id,
            "Вы не находились в листе ожидания.",
            main_menu(user_id),
        )

    clear_state(user_id)


# ============================================================
# АДМИН-ПАНЕЛЬ
# ============================================================

def show_admin_panel(user_id):
    if user_id not in ADMIN_IDS:
        send_message(
            user_id,
            "Нет доступа.",
            main_menu(user_id),
        )
        return

    clear_state(user_id)

    send_message(
        user_id,
        (
            "⚙️ Админ-панель\n\n"
            "Выберите действие:"
        ),
        admin_menu(),
    )


# ============================================================
# АДМИН — ТРЕНИРОВКИ
# ============================================================

def show_admin_trainings(
    user_id,
    mode="participants",
):
    if user_id not in ADMIN_IDS:
        return

    start = today_local()

    end = (
        start
        + timedelta(days=13)
    )

    trainings = get_upcoming_trainings(
        from_date=start.isoformat(),
        to_date=end.isoformat(),
    )

    if not trainings:
        send_message(
            user_id,
            "Предстоящих тренировок нет.",
            make_keyboard([
                [admin_back_button()],
            ]),
        )
        return

    rows = []

    for training in trainings:

        count = get_registration_count(
            training["id"]
        )

        label = (
            f"№{training['training_number']} "
            f"{training_short_date(training)} "
            f"{training['start_time']} "
            f"({count}/{training['capacity']})"
        )

        rows.append([
            button(
                label,
                "primary",
            )
        ])

    rows.append([
        admin_back_button(),
    ])

    set_state(
        user_id,
        "admin_training_select",
        {
            "mode": mode,
        },
    )

    send_message(
        user_id,
        "📅 Выберите тренировку:",
        make_keyboard(rows),
    )


def find_admin_training(text):
    trainings = get_upcoming_trainings()

    for training in trainings:

        prefix = (
            f"№{training['training_number']} "
            f"{training_short_date(training)} "
            f"{training['start_time']}"
        )

        if text.startswith(prefix):
            return training

    return None


# ============================================================
# АДМИН — УЧАСТНИКИ
# ============================================================

def show_training_participants(
    user_id,
    training,
):
    if user_id not in ADMIN_IDS:
        return

    registrations = get_registrations(
        training["id"]
    )

    count = len(registrations)

    lines = [
        f"👥 Тренировка №"
        f"{training['training_number']}",
        "",
        f"📅 {training_date_text(training)}",
        f"⏰ {training['start_time']}–"
        f"{training['end_time']}",
        f"🏷 {training['title']}",
        f"👨‍🏫 {training['coach']}",
        f"📍 {training['location']}",
        "",
        f"📊 Участники: "
        f"{count}/{training['capacity']}",
        "",
    ]

    if not registrations:
        lines.append(
            "Пока никто не записался."
        )

    else:

        for index, registration in enumerate(
            registrations,
            start=1,
        ):
            name = " ".join(
                part
                for part in [
                    registration["first_name"],
                    registration["last_name"],
                ]
                if part
            )

            if not name:
                name = (
                    f"VK ID "
                    f"{registration['vk_id']}"
                )

            lines.append(
                f"{index}. {name}"
            )

    waitlist = get_waitlist(
        training["id"]
    )

    if waitlist:
        lines.append("")
        lines.append(
            "⏳ Лист ожидания:"
        )

        for item in waitlist:
            name = " ".join(
                part
                for part in [
                    item["first_name"],
                    item["last_name"],
                ]
                if part
            )

            if not name:
                name = (
                    f"VK ID {item['vk_id']}"
                )

            lines.append(
                f"{item['position']}. {name}"
            )

    rows = [
        [
            button(
                "📋 Посещаемость",
                "primary",
            )
        ],
        [
            button(
                "⬅️ К тренировкам",
                "secondary",
            )
        ],
        [
            admin_back_button(),
        ],
    ]

    set_state(
        user_id,
        "admin_participants",
        {
            "training_id": training["id"],
        },
    )

    send_message(
        user_id,
        "\n".join(lines),
        make_keyboard(rows),
    )


# ============================================================
# АДМИН — ПОСЕЩАЕМОСТЬ
# ============================================================

def show_attendance(
    user_id,
    training,
):
    if user_id not in ADMIN_IDS:
        return

    registrations = get_registrations(
        training["id"]
    )

    lines = [
        f"📋 Посещаемость №"
        f"{training['training_number']}",
        "",
    ]

    rows = []

    attendance = get_training_attendance(
        training["id"]
    )

    attendance_by_vk = {}

    for item in attendance:
        attendance_by_vk[
            item["vk_id"]
        ] = item["status"]

    for index, registration in enumerate(
        registrations,
        start=1,
    ):
        vk_id = registration["vk_id"]

        name = " ".join(
            part
            for part in [
                registration["first_name"],
                registration["last_name"],
            ]
            if part
        )

        if not name:
            name = f"VK ID {vk_id}"

        status = attendance_by_vk.get(
            vk_id,
            "unknown",
        )

        if status == "present":
            marker = "✅"
        elif status == "absent":
            marker = "❌"
        else:
            marker = "⬜"

        lines.append(
            f"{marker} {index}. {name}"
        )

        rows.append([
            button(
                f"№{index} {marker}",
                "secondary",
            )
        ])

    rows.append([
        button(
            "⬅️ К участникам",
            "secondary",
        )
    ])

    rows.append([
        admin_back_button(),
    ])

    set_state(
        user_id,
        "admin_attendance",
        {
            "training_id": training["id"],
        },
    )

    send_message(
        user_id,
        "\n".join(lines),
        make_keyboard(rows),
    )


# ============================================================
# АДМИН — ДОБАВЛЕНИЕ ТРЕНИРОВКИ
# ============================================================

def start_add_training(user_id):
    if user_id not in ADMIN_IDS:
        return

    set_state(
        user_id,
        "add_training_date",
    )

    send_message(
        user_id,
        (
            "➕ Добавление тренировки\n\n"
            "Введите дату:\n"
            "05.10.2026"
        ),
        make_keyboard([
            [admin_back_button()],
        ]),
    )


def save_admin_training(
    user_id,
    data,
):
    try:
        training_date = date.fromisoformat(
            data["training_date"]
        )

        training = create_training(
            training_date=training_date.isoformat(),
            weekday=training_date.weekday(),
            start_time=data["start_time"],
            end_time=data["end_time"],
            title=data["title"],
            category=data["category"],
            age_group=data["age_group"],
            level=data["level"],
            format=data["format"],
            coach=data["coach"],
            capacity=data["capacity"],
            price=data["price"],
            location=data["location"],
        )

        add_admin_log(
            user_id,
            "create_training",
            "training",
            str(
                training["id"]
                if training
                else ""
            ),
            (
                f"Создана тренировка "
                f"{data['title']} "
                f"{training_date}"
            ),
        )

        send_message(
            user_id,
            "✅ Тренировка создана.",
            admin_menu(),
        )

        clear_state(user_id)

    except Exception as error:
        print(
            f"SAVE ADMIN TRAINING ERROR: {error}"
        )

        send_message(
            user_id,
            (
                "❌ Не удалось создать тренировку.\n\n"
                f"Ошибка: {error}"
            ),
            admin_menu(),
        )

        clear_state(user_id)


# ============================================================
# ШАБЛОНЫ
# ============================================================

def show_templates(user_id):
    templates = get_training_templates(
        active_only=True
    )

    if not templates:
        send_message(
            user_id,
            "Шаблонов расписания пока нет.",
            make_keyboard([
                [admin_back_button()],
            ]),
        )
        return

    lines = [
        "📋 Шаблоны расписания",
        "",
    ]

    for template in templates:

        lines.append(
            f"#{template['id']} — "
            f"{WEEKDAYS[template['weekday']]}"
        )

        lines.append(
            f"{template['start_time']}–"
            f"{template['end_time']} "
            f"— {template['title']}"
        )

        lines.append(
            f"{category_text(template['category'])} "
            f"• {template['capacity']} мест "
            f"• {template['price']} ₽"
        )

        lines.append("")

    send_message(
        user_id,
        "\n".join(lines),
        make_keyboard([
            [admin_back_button()],
        ]),
    )


# ============================================================
# ИНДИВИДУАЛЬНАЯ ТРЕНИРОВКА
# ============================================================

def start_individual(user_id):
    set_state(
        user_id,
        "individual",
    )

    send_message(
        user_id,
        (
            "🎯 Индивидуальная тренировка\n\n"
            "Напишите одним сообщением:\n"
            "• желаемый день;\n"
            "• удобное время;\n"
            "• ваш уровень;\n"
            "• дополнительные пожелания."
        ),
        make_keyboard([
            [back_button()],
        ]),
    )


def send_request_to_admins(
    user_id,
    text,
    request_type,
):
    user = get_user(
        user_id
    )

    if user:
        name = " ".join(
            part
            for part in [
                user["first_name"],
                user["last_name"],
            ]
            if part
        )
    else:
        name = ""

    if not name:
        name = f"VK ID {user_id}"

    if request_type == "individual":
        title = (
            "🎯 Новая заявка "
            "на индивидуальную тренировку"
        )
    else:
        title = "❓ Новый вопрос"

    message = (
        f"{title}\n\n"
        f"👤 {name}\n"
        f"VK ID: {user_id}\n\n"
        f"Сообщение:\n{text}"
    )

    for admin_id in ADMIN_IDS:
        send_message(
            admin_id,
            message,
            make_keyboard([
                [
                    admin_back_button(),
                ]
            ]),
        )


def start_question(user_id):
    set_state(
        user_id,
        "question",
    )

    send_message(
        user_id,
        (
            "❓ Задать вопрос\n\n"
            "Напишите ваш вопрос одним сообщением."
        ),
        make_keyboard([
            [back_button()],
        ]),
    )


# ============================================================
# ОСНОВНОЙ ОБРАБОТЧИК
# ============================================================

def handle_message(
    user_id,
    text,
):
    text = (
        text or ""
    ).strip()

    print(
        f"HANDLE MESSAGE: user_id={user_id}, text={text}"
    )

    if is_user_blocked(
        user_id
    ):
        send_message(
            user_id,
            "Доступ к боту ограничен.",
        )
        return

    register_user(
        user_id
    )

    state = get_state(
        user_id
    )

    state_name = state["state"]

    # --------------------------------------------------------
    # ОБЩИЕ
    # --------------------------------------------------------

    if text == "⬅️ Назад":
        clear_state(
            user_id
        )

        send_message(
            user_id,
            "Главное меню:",
            main_menu(user_id),
        )
        return

    if text == "⚙️ В админ-панель":
        clear_state(
            user_id
        )

        show_admin_panel(
            user_id
        )
        return

    if text == "⬅️ К тренировкам":
        if user_id in ADMIN_IDS:
            show_admin_trainings(
                user_id,
                "participants",
            )
        else:
            send_message(
                user_id,
                "Главное меню:",
                main_menu(user_id),
            )
        return

    # --------------------------------------------------------
    # ГЛАВНОЕ МЕНЮ
    # --------------------------------------------------------

    if text == "🏐 Записаться":
        start_booking(
            user_id
        )
        return

    if text == "📅 Расписание":
        show_schedule_categories(
            user_id
        )
        return

    if text == "👤 Мои тренировки":
        clear_state(
            user_id
        )

        show_my_trainings(
            user_id
        )
        return

    if text == "💰 Цены":
        clear_state(
            user_id
        )

        show_prices(
            user_id
        )
        return

    if text == "📍 Где тренируемся":
        clear_state(
            user_id
        )

        show_locations(
            user_id
        )
        return

    if text == "🎯 Индивидуальная тренировка":
        start_individual(
            user_id
        )
        return

    if text == "❓ Задать вопрос":
        start_question(
            user_id
        )
        return

    # --------------------------------------------------------
    # АДМИН
    # --------------------------------------------------------

    if text == "⚙️ Админ-панель":
        show_admin_panel(
            user_id
        )
        return

    if (
        user_id in ADMIN_IDS
        and text == "👤 Пользовательский режим"
    ):
        clear_state(
            user_id
        )

        send_message(
            user_id,
            (
                "👤 Пользовательский режим\n\n"
                "Вы можете пользоваться ботом "
                "как обычный пользователь.\n\n"
                "Права администратора сохраняются."
            ),
            main_menu(user_id),
        )
        return

    if (
        user_id in ADMIN_IDS
        and text == "👥 Участники тренировок"
    ):
        show_admin_trainings(
            user_id,
            "participants",
        )
        return

    if (
        user_id in ADMIN_IDS
        and text == "➕ Добавить тренировку"
    ):
        start_add_training(
            user_id
        )
        return

    if (
        user_id in ADMIN_IDS
        and text == "📋 Шаблоны расписания"
    ):
        show_templates(
            user_id
        )
        return

    # --------------------------------------------------------
    # КАТЕГОРИЯ РАСПИСАНИЯ
    # --------------------------------------------------------

    if (
        state_name is None
        and text == "👶 Дети"
    ):
        show_schedule_week(
            user_id,
            "children",
        )
        return

    if (
        state_name is None
        and text == "🧑 Взрослые"
    ):
        show_schedule_week(
            user_id,
            "adults",
        )
        return

    # --------------------------------------------------------
    # ЗАПИСЬ — КАТЕГОРИЯ
    # --------------------------------------------------------

    if state_name == "booking_category":

        if text == "👶 Дети":
            show_booking_dates(
                user_id,
                "children",
            )
            return

        if text == "🧑 Взрослые":
            show_booking_dates(
                user_id,
                "adults",
            )
            return

    # --------------------------------------------------------
    # ЗАПИСЬ — ДАТА
    # --------------------------------------------------------

    if state_name == "booking_date":

        category = state["data"].get(
            "category"
        )

        trainings = get_upcoming_trainings(
            from_date=today_local().isoformat(),
            to_date=(
                today_local()
                + timedelta(days=6)
            ).isoformat(),
            category=category,
        )

        for training in trainings:

            training_date_value = date.fromisoformat(
                training["training_date"]
            )

            expected_label = (
                f"{WEEKDAYS_SHORT[training_date_value.weekday()]}, "
                f"{training_date_value.strftime('%d.%m')}"
            )

            if text == expected_label:
                show_booking_trainings(
                    user_id,
                    category,
                    training["training_date"],
                )
                return

    # --------------------------------------------------------
    # ЗАПИСЬ — ТРЕНИРОВКА
    # --------------------------------------------------------

    if state_name == "booking_training":

        training = find_booking_training(
            user_id,
            text,
        )

        if training:
            show_training_details(
                user_id,
                training,
            )
            return

    # --------------------------------------------------------
    # ДЕТАЛИ ТРЕНИРОВКИ
    # --------------------------------------------------------

    if state_name == "training_details":

        training_id = state["data"].get(
            "training_id"
        )

        training = get_training(
            training_id
        )

        if not training:
            send_message(
                user_id,
                "Тренировка не найдена.",
                main_menu(user_id),
            )
            clear_state(
                user_id
            )
            return

        if text == "✅ Записаться":
            register_for_training(
                user_id,
                training,
            )
            return

        if text == "➕ В лист ожидания":
            join_waitlist(
                user_id,
                training,
            )
            return

        if text == "❌ Выйти из листа ожидания":
            leave_waitlist(
                user_id,
                training,
            )
            return

        if text == "❌ Отменить запись":
            cancel_my_training(
                user_id,
                training,
            )
            return

    # --------------------------------------------------------
    # МОИ ТРЕНИРОВКИ
    # --------------------------------------------------------

    training = find_my_training_button(
        user_id,
        text,
    )

    if training:
        cancel_my_training(
            user_id,
            training,
        )
        return

    # --------------------------------------------------------
    # АДМИН — ВЫБОР ТРЕНИРОВКИ
    # --------------------------------------------------------

    if (
        user_id in ADMIN_IDS
        and state_name == "admin_training_select"
    ):
        training = find_admin_training(
            text
        )

        if training:
            show_training_participants(
                user_id,
                training,
            )
            return

    # --------------------------------------------------------
    # АДМИН — УЧАСТНИКИ
    # --------------------------------------------------------

    if (
        user_id in ADMIN_IDS
        and state_name == "admin_participants"
    ):
        training_id = state["data"].get(
            "training_id"
        )

        training = get_training(
            training_id
        )

        if text == "📋 Посещаемость":
            show_attendance(
                user_id,
                training,
            )
            return

    # --------------------------------------------------------
    # АДМИН — ПОСЕЩАЕМОСТЬ
    # --------------------------------------------------------

    if (
        user_id in ADMIN_IDS
        and state_name == "admin_attendance"
    ):
        training_id = state["data"].get(
            "training_id"
        )

        training = get_training(
            training_id
        )

        registrations = get_registrations(
            training_id
        )

        if text.startswith("№"):

            try:
                number = int(
                    text.split()[0][1:]
                )

                registration = registrations[
                    number - 1
                ]

                attendance = get_training_attendance(
                    training_id
                )

                current_status = "unknown"

                for item in attendance:
                    if (
                        item["vk_id"]
                        == registration["vk_id"]
                    ):
                        current_status = item["status"]
                        break

                if current_status == "present":
                    new_status = "absent"
                else:
                    new_status = "present"

                mark_attendance(
                    registration["id"],
                    new_status,
                    user_id,
                )

                show_attendance(
                    user_id,
                    training,
                )

                return

            except Exception as error:
                print(
                    f"ATTENDANCE ERROR: {error}"
                )

    # --------------------------------------------------------
    # ДОБАВЛЕНИЕ ТРЕНИРОВКИ — ДАТА
    # --------------------------------------------------------

    if (
        user_id in ADMIN_IDS
        and state_name == "add_training_date"
    ):
        try:
            training_date = datetime.strptime(
                text,
                "%d.%m.%Y",
            ).date()

            set_state(
                user_id,
                "add_training_time",
                {
                    "training_date":
                        training_date.isoformat()
                },
            )

            send_message(
                user_id,
                (
                    "Введите время:\n\n"
                    "Например:\n"
                    "17:00-19:00"
                ),
                make_keyboard([
                    [admin_back_button()],
                ]),
            )

            return

        except ValueError:
            send_message(
                user_id,
                (
                    "❌ Неверный формат даты.\n\n"
                    "Введите, например:\n"
                    "05.10.2026"
                ),
                make_keyboard([
                    [admin_back_button()],
                ]),
            )
            return

    # --------------------------------------------------------
    # ДОБАВЛЕНИЕ — ВРЕМЯ
    # --------------------------------------------------------

    if (
        user_id in ADMIN_IDS
        and state_name == "add_training_time"
    ):
        try:
            parts = text.split("-")

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

            set_state(
                user_id,
                "add_training_title",
                {
                    **state["data"],
                    "start_time": start_time,
                    "end_time": end_time,
                },
            )

            send_message(
                user_id,
                "Введите название тренировки:",
                make_keyboard([
                    [admin_back_button()],
                ]),
            )

            return

        except ValueError:
            send_message(
                user_id,
                (
                    "❌ Неверный формат.\n\n"
                    "Например:\n"
                    "17:00-19:00"
                ),
                make_keyboard([
                    [admin_back_button()],
                ]),
            )
            return

    # --------------------------------------------------------
    # ДОБАВЛЕНИЕ — НАЗВАНИЕ
    # --------------------------------------------------------

    if (
        user_id in ADMIN_IDS
        and state_name == "add_training_title"
    ):
        set_state(
            user_id,
            "add_training_category",
            {
                **state["data"],
                "title": text,
            },
        )

        send_message(
            user_id,
            "Выберите категорию:",
            make_keyboard([
                [
                    button(
                        "👶 Дети",
                        "positive",
                    ),
                    button(
                        "🧑 Взрослые",
                        "primary",
                    ),
                ],
                [
                    admin_back_button(),
                ],
            ]),
        )

        return

    # --------------------------------------------------------
    # ДОБАВЛЕНИЕ — КАТЕГОРИЯ
    # --------------------------------------------------------

    if (
        user_id in ADMIN_IDS
        and state_name == "add_training_category"
    ):
        if text == "👶 Дети":
            category = "children"

        elif text == "🧑 Взрослые":
            category = "adults"

        else:
            return

        set_state(
            user_id,
            "add_training_age",
            {
                **state["data"],
                "category": category,
            },
        )

        send_message(
            user_id,
            (
                "Введите возрастную группу.\n\n"
                "Например:\n"
                "11–14\n"
                "18+"
            ),
            make_keyboard([
                [admin_back_button()],
            ]),
        )

        return

    # --------------------------------------------------------
    # ДОБАВЛЕНИЕ — ВОЗРАСТ
    # --------------------------------------------------------

    if (
        user_id in ADMIN_IDS
        and state_name == "add_training_age"
    ):
        set_state(
            user_id,
            "add_training_level",
            {
                **state["data"],
                "age_group": text,
            },
        )

        send_message(
            user_id,
            "Введите уровень:",
            make_keyboard([
                [
                    button(
                        "Начальный",
                        "secondary",
                    )
                ],
                [
                    button(
                        "Начальный / средний",
                        "secondary",
                    )
                ],
                [
                    button(
                        "Средний",
                        "secondary",
                    )
                ],
                [
                    button(
                        "Средний+",
                        "secondary",
                    )
                ],
                [
                    button(
                        "Продвинутый",
                        "secondary",
                    )
                ],
                [
                    button(
                        "Техническая",
                        "secondary",
                    )
                ],
                [
                    admin_back_button(),
                ],
            ]),
        )

        return

    # --------------------------------------------------------
    # ДОБАВЛЕНИЕ — УРОВЕНЬ
    # --------------------------------------------------------

    if (
        user_id in ADMIN_IDS
        and state_name == "add_training_level"
    ):
        set_state(
            user_id,
            "add_training_coach",
            {
                **state["data"],
                "level": text,
            },
        )

        send_message(
            user_id,
            "Введите имя тренера:",
            make_keyboard([
                [
                    button(
                        "Алексей",
                        "primary",
                    )
                ],
                [
                    button(
                        "Ксения",
                        "primary",
                    )
                ],
                [
                    admin_back_button(),
                ],
            ]),
        )

        return

    # --------------------------------------------------------
    # ДОБАВЛЕНИЕ — ТРЕНЕР
    # --------------------------------------------------------

    if (
        user_id in ADMIN_IDS
        and state_name == "add_training_coach"
    ):
        set_state(
            user_id,
            "add_training_capacity",
            {
                **state["data"],
                "coach": text,
            },
        )

        send_message(
            user_id,
            (
                "Введите количество мест:\n\n"
                "Например: 10"
            ),
            make_keyboard([
                [admin_back_button()],
            ]),
        )

        return

    # --------------------------------------------------------
    # ДОБАВЛЕНИЕ — ВМЕСТИМОСТЬ
    # --------------------------------------------------------

    if (
        user_id in ADMIN_IDS
        and state_name == "add_training_capacity"
    ):
        try:
            capacity = int(text)

            if capacity < 1:
                raise ValueError

            set_state(
                user_id,
                "add_training_price",
                {
                    **state["data"],
                    "capacity": capacity,
                },
            )

            send_message(
                user_id,
                (
                    "Введите цену в рублях:\n\n"
                    "Например: 600"
                ),
                make_keyboard([
                    [admin_back_button()],
                ]),
            )

            return

        except ValueError:
            send_message(
                user_id,
                "Введите целое число, например 10.",
                make_keyboard([
                    [admin_back_button()],
                ]),
            )
            return

    # --------------------------------------------------------
    # ДОБАВЛЕНИЕ — ЦЕНА
    # --------------------------------------------------------

    if (
        user_id in ADMIN_IDS
        and state_name == "add_training_price"
    ):
        try:
            price = int(text)

            if price < 0:
                raise ValueError

            data = {
                **state["data"],
                "price": price,
                "format": "Группа",
                "location": "СК «Арена»",
            }

            save_admin_training(
                user_id,
                data,
            )

            return

        except ValueError:
            send_message(
                user_id,
                "Введите цену числом, например 600.",
                make_keyboard([
                    [admin_back_button()],
                ]),
            )
            return

    # --------------------------------------------------------
    # ИНДИВИДУАЛЬНАЯ
    # --------------------------------------------------------

    if state_name == "individual":

        send_request_to_admins(
            user_id,
            text,
            "individual",
        )

        clear_state(
            user_id
        )

        send_message(
            user_id,
            (
                "✅ Заявка отправлена тренеру.\n\n"
                "С вами свяжутся для согласования "
                "времени и деталей."
            ),
            main_menu(user_id),
        )

        return

    # --------------------------------------------------------
    # ВОПРОС
    # --------------------------------------------------------

    if state_name == "question":

        send_request_to_admins(
            user_id,
            text,
            "question",
        )

        clear_state(
            user_id
        )

        send_message(
            user_id,
            (
                "✅ Вопрос отправлен.\n\n"
                "Мы постараемся ответить как можно скорее."
            ),
            main_menu(user_id),
        )

        return

    # --------------------------------------------------------
    # НЕИЗВЕСТНАЯ КОМАНДА
    # --------------------------------------------------------

    print(
        f"UNHANDLED MESSAGE: "
        f"user_id={user_id}, "
        f"text={text}, "
        f"state={state_name}"
    )

    send_message(
        user_id,
        "Выберите действие из меню:",
        main_menu(user_id),
    )


# ============================================================
# CALLBACK API
# ============================================================

@app.route(
    "/callback",
    methods=["POST"],
)
def callback():
    data = request.get_json(
        silent=True
    ) or {}

    print(
        f"CALLBACK: {data}"
    )

    # CONFIRMATION
    if data.get("type") == "confirmation":
        return VK_CONFIRMATION_TOKEN

    # SECRET
    if (
        VK_SECRET_KEY
        and data.get("secret")
        != VK_SECRET_KEY
    ):
        print(
            "INVALID SECRET"
        )

        return (
            "invalid secret",
            403,
        )

    obj = data.get(
        "object",
        {},
    )

    # VK Callback API 5.199
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

        print(
            f"VK MESSAGE: "
            f"user_id={user_id}, "
            f"text={text}"
        )

        try:
            handle_message(
                int(user_id),
                text,
            )

        except Exception as error:

            print(
                "================================"
            )
            print(
                "HANDLER ERROR:"
            )
            print(
                repr(error)
            )
            print(
                "================================"
            )

    return "ok"


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route(
    "/",
    methods=["GET"],
)
def health():
    return "Volley Wave VK Bot is running"


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    try:
        generate_trainings_for_period(
            weeks=6
        )

    except Exception as error:
        print(
            "SCHEDULE GENERATION ERROR:"
        )
        print(
            repr(error)
        )

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
