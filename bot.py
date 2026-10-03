import os
import json
import random
import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from flask import Flask, request

from database import (
    init_db,
    create_or_update_user,
    get_user,
    get_trainings,
    get_training,
    get_trainings_by_day,
    get_trainings_by_category,
    get_registration_count,
    get_registrations,
    get_registration,
    add_registration,
    cancel_registration,
    get_user_registrations,
    add_admin_log,
)


# ============================================================
# SETTINGS
# ============================================================

VK_TOKEN = os.getenv("VK_TOKEN")
VK_SECRET_KEY = os.getenv("VK_SECRET_KEY")
VK_CONFIRMATION_TOKEN = os.getenv("VK_CONFIRMATION_TOKEN")

VK_API_VERSION = "5.199"

ADMIN_IDS = {
    87984447,
    172892670,
    148372158,
}

TIMEZONE = ZoneInfo("Asia/Yekaterinburg")

app = Flask(__name__)


# ============================================================
# USER STATES
# ============================================================

user_states = {}


# ============================================================
# INITIALIZE DATABASE
# ============================================================

init_db()


# ============================================================
# VK API
# ============================================================

def vk_api(method, params=None):
    if params is None:
        params = {}

    params["access_token"] = VK_TOKEN
    params["v"] = VK_API_VERSION

    response = requests.post(
        f"https://api.vk.com/method/{method}",
        data=params,
        timeout=15,
    )

    return response.json()


def send_message(user_id, message, keyboard=None):
    params = {
        "user_id": user_id,
        "message": message,
        "random_id": random.randint(1, 2_000_000_000),
    }

    if keyboard is not None:
        params["keyboard"] = json.dumps(
            keyboard,
            ensure_ascii=False,
        )

    result = vk_api(
        "messages.send",
        params,
    )

    return result


# ============================================================
# KEYBOARDS
# ============================================================

def button(label, color="secondary"):
    return {
        "action": {
            "type": "text",
            "label": label,
        },
        "color": color,
    }


def keyboard(rows, inline=False):
    return {
        "one_time": False,
        "inline": inline,
        "buttons": rows,
    }


def main_menu(user_id):
    rows = [
        [
            button("🏐 Записаться", "positive"),
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

    if user_id in ADMIN_IDS:
        rows.append([
            button("⚙️ Админ-панель", "primary")
        ])

    return keyboard(rows)


def back_keyboard():
    return keyboard([
        [
            button("⬅️ Назад", "secondary"),
        ]
    ])


def admin_menu():
    return keyboard([
        [
            button("➕ Добавить тренировку", "positive"),
        ],
        [
            button("📅 Управление расписанием", "primary"),
        ],
        [
            button("👥 Участники тренировок", "primary"),
        ],
        [
            button("🏠 Режим пользователя", "secondary"),
        ],
        [
            button("⬅️ Главное меню", "secondary"),
        ],
    ])


def category_keyboard():
    return keyboard([
        [
            button("👶 Дети", "positive"),
            button("🧑 Взрослые", "primary"),
        ],
        [
            button("⬅️ Назад", "secondary"),
        ],
    ])


def day_keyboard():
    return keyboard([
        [
            button("Понедельник", "secondary"),
            button("Вторник", "secondary"),
        ],
        [
            button("Среда", "secondary"),
            button("Четверг", "secondary"),
        ],
        [
            button("Пятница", "secondary"),
        ],
        [
            button("⬅️ Назад", "secondary"),
        ],
    ])


# ============================================================
# HELPERS
# ============================================================

DAY_NAMES = {
    1: "Понедельник",
    2: "Вторник",
    3: "Среда",
    4: "Четверг",
    5: "Пятница",
    6: "Суббота",
    7: "Воскресенье",
}


DAY_BUTTON_TO_NUMBER = {
    "Понедельник": 1,
    "Вторник": 2,
    "Среда": 3,
    "Четверг": 4,
    "Пятница": 5,
}


def training_category(training):
    category = training["category"]

    if category:
        return category

    title = (training["title"] or "").lower()

    if "дет" in title:
        return "children"

    return "adults"


def category_name(category):
    if category == "children":
        return "👶 Детские тренировки"

    return "🧑 Взрослые тренировки"


def format_training_date(training):
    return DAY_NAMES.get(
        training["day_of_week"],
        "День не указан",
    )


def training_label(training):
    return (
        f"{training['time']} — "
        f"{training['title']}"
    )


def training_details(training):
    count = get_registration_count(training["id"])

    level = training["level"] or "не указан"
    age = training["age_group"] or "не указан"
    training_format = training["format"] or "Группа"
    coach = training["coach"] or "не указан"

    return (
        f"🏐 {training['title']}\n\n"
        f"📅 {format_training_date(training)}\n"
        f"⏰ {training['time']}\n"
        f"🎯 Формат: {training_format}\n"
        f"📈 Уровень: {level}\n"
        f"👥 Возраст: {age}\n"
        f"👨‍🏫 Тренер: {coach}\n"
        f"💰 Стоимость: {training['price']}₽\n"
        f"👤 Записано: {count}/{training['capacity']}\n"
    )


def registration_time(training):
    """
    Определяет ближайшую дату конкретной тренировки
    относительно текущего дня.

    Пока расписание хранится как еженедельное.
    """

    now = datetime.now(TIMEZONE)

    target_weekday = training["day_of_week"]

    days_ahead = target_weekday - now.isoweekday()

    if days_ahead < 0:
        days_ahead += 7

    date = now.date() + timedelta(days=days_ahead)

    start_time = training["time"].split("-")[0]

    hour, minute = map(
        int,
        start_time.split(":"),
    )

    return datetime(
        date.year,
        date.month,
        date.day,
        hour,
        minute,
        tzinfo=TIMEZONE,
    )


def can_cancel_training(training):
    start = registration_time(training)
    now = datetime.now(TIMEZONE)

    return start - now >= timedelta(hours=24)


def set_state(user_id, state, data=None):
    user_states[user_id] = {
        "state": state,
        "data": data or {},
    }


def get_state(user_id):
    return user_states.get(user_id)


def clear_state(user_id):
    user_states.pop(user_id, None)


# ============================================================
# USERS
# ============================================================

def register_user(user_id):
    """
    Создаёт пользователя в базе при первом обращении.

    Имя пока не запрашиваем у пользователя.
    Позже можно автоматически получать имя через VK API.
    """

    user = get_user(user_id)

    if user is None:
        create_or_update_user(
            user_id=user_id,
        )


# ============================================================
# MAIN MENU
# ============================================================

def show_main_menu(user_id):
    send_message(
        user_id,
        "Главное меню 👇",
        main_menu(user_id),
    )


# ============================================================
# PRICES
# ============================================================

def show_prices(user_id):
    text = (
        "💰 Цены\n\n"
        "👶 Детские тренировки — 600₽\n\n"
        "🧑 Взрослые тренировки:\n"
        "• 1–6 человек — 1200₽ с человека\n"
        "• 7 человек и больше — 1000₽ с человека\n\n"
        "Минимальный размер взрослой группы — "
        "рекомендация, а не обязательное условие записи."
    )

    send_message(
        user_id,
        text,
        back_keyboard(),
    )


# ============================================================
# LOCATIONS
# ============================================================

def show_locations(user_id):
    text = (
        "📍 Где тренируемся\n\n"
        "☀️ Летом:\n"
        "Парк Гагарина, Челябинск.\n\n"
        "❄️ Зимой:\n"
        "СК «Арена»\n"
        "ул. Молодогвардейцев, 7.\n\n"
        "Тренировки проходят на песке круглый год."
    )

    send_message(
        user_id,
        text,
        back_keyboard(),
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
        "Выберите категорию:",
        category_keyboard(),
    )


def show_schedule(user_id, category):
    trainings = get_trainings_by_category(category)

    if not trainings:
        send_message(
            user_id,
            "Пока тренировок этой категории нет.",
            back_keyboard(),
        )
        return

    text = (
        f"{category_name(category)}\n\n"
    )

    current_day = None

    for training in trainings:

        day = training["day_of_week"]

        if day != current_day:
            current_day = day

            text += (
                f"\n📅 {DAY_NAMES.get(day, '')}\n"
            )

        count = get_registration_count(
            training["id"]
        )

        text += (
            f"⏰ {training['time']} — "
            f"{training['title']}\n"
            f"   {training['format'] or 'Группа'} | "
            f"{training['level'] or 'уровень не указан'} | "
            f"{training['age_group'] or '18+'}\n"
            f"   👥 {count}/{training['capacity']}\n"
        )

    send_message(
        user_id,
        text,
        back_keyboard(),
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
        "Кого записываем?",
        category_keyboard(),
    )


def show_booking_days(user_id, category):
    set_state(
        user_id,
        "booking_day",
        {
            "category": category,
        },
    )

    send_message(
        user_id,
        "Выберите день:",
        day_keyboard(),
    )


def show_booking_trainings(user_id, category, day):
    trainings = [
        training
        for training in get_trainings_by_day(day)
        if training_category(training) == category
    ]

    if not trainings:
        send_message(
            user_id,
            "В этот день подходящих тренировок нет.",
            day_keyboard(),
        )
        return

    rows = []

    for training in trainings:
        count = get_registration_count(
            training["id"]
        )

        rows.append([
            button(
                f"{training['time']} — "
                f"{training['title']}"
                f" ({count}/{training['capacity']})",
                "primary",
            )
        ])

    rows.append([
        button("⬅️ Назад", "secondary")
    ])

    set_state(
        user_id,
        "booking_training",
        {
            "category": category,
            "day": day,
        },
    )

    send_message(
        user_id,
        "Выберите тренировку:",
        keyboard(rows),
    )


def find_training_from_button(user_id, text):
    state = get_state(user_id)

    if not state:
        return None

    data = state.get("data", {})
    category = data.get("category")
    day = data.get("day")

    if not category or not day:
        return None

    trainings = [
        training
        for training in get_trainings_by_day(day)
        if training_category(training) == category
    ]

    for training in trainings:
        count = get_registration_count(
            training["id"]
        )

        expected = (
            f"{training['time']} — "
            f"{training['title']}"
            f" ({count}/{training['capacity']})"
        )

        if text == expected:
            return training

    return None


def show_booking_confirmation(user_id, training):
    count = get_registration_count(
        training["id"]
    )

    if count >= training["capacity"]:
        send_message(
            user_id,
            "На эту тренировку уже нет свободных мест.",
            back_keyboard(),
        )
        return

    text = (
        training_details(training)
        + "\n"
        + "Записаться на эту тренировку?"
    )

    set_state(
        user_id,
        "booking_confirm",
        {
            "training_id": training["id"],
        },
    )

    send_message(
        user_id,
        text,
        keyboard([
            [
                button("✅ Записаться", "positive"),
            ],
            [
                button("⬅️ Назад", "secondary"),
            ],
        ]),
    )


def confirm_booking(user_id):
    state = get_state(user_id)

    if not state:
        return

    training_id = state["data"].get(
        "training_id"
    )

    training = get_training(training_id)

    if not training:
        clear_state(user_id)

        send_message(
            user_id,
            "Тренировка не найдена.",
            main_menu(user_id),
        )
        return

    if get_registration(user_id=user_id, training_id=training_id):
        registration = get_registration(
            training_id,
            user_id,
        )

        if registration["status"] == "active":
            clear_state(user_id)

            send_message(
                user_id,
                "Вы уже записаны на эту тренировку.",
                main_menu(user_id),
            )
            return

    count = get_registration_count(
        training_id
    )

    if count >= training["capacity"]:
        clear_state(user_id)

        send_message(
            user_id,
            "К сожалению, свободных мест уже нет.",
            main_menu(user_id),
        )
        return

    success = add_registration(
        training_id=training_id,
        user_id=user_id,
    )

    clear_state(user_id)

    if success:
        send_message(
            user_id,
            "✅ Вы успешно записаны!\n\n"
            + training_details(training),
            main_menu(user_id),
        )

    else:
        send_message(
            user_id,
            "Не удалось записать вас. "
            "Возможно, запись уже существует.",
            main_menu(user_id),
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
            "У вас пока нет активных записей.",
            main_menu(user_id),
        )
        return

    rows = []
    text = "👤 Мои тренировки\n\n"

    for training in trainings:

        text += (
            f"📅 {DAY_NAMES.get(training['day_of_week'], '')}\n"
            f"⏰ {training['time']}\n"
            f"🏐 {training['title']}\n"
            f"👨‍🏫 {training['coach'] or 'не указан'}\n\n"
        )

        rows.append([
            button(
                f"❌ Отменить {training['time']} "
                f"{training['title']}",
                "negative",
            )
        ])

    rows.append([
        button("⬅️ Назад", "secondary")
    ])

    set_state(
        user_id,
        "my_trainings",
    )

    send_message(
        user_id,
        text,
        keyboard(rows),
    )


def find_my_training_from_button(user_id, text):
    trainings = get_user_registrations(
        user_id
    )

    for training in trainings:
        expected = (
            f"❌ Отменить {training['time']} "
            f"{training['title']}"
        )

        if text == expected:
            return training

    return None


def show_cancel_confirmation(user_id, training):
    actual_training = get_training(
        training["training_id"]
    )

    if not actual_training:
        send_message(
            user_id,
            "Тренировка не найдена.",
            main_menu(user_id),
        )
        return

    if not can_cancel_training(
        actual_training
    ):
        send_message(
            user_id,
            "❌ Отменить запись уже нельзя.\n\n"
            "До начала тренировки осталось меньше 24 часов.",
            main_menu(user_id),
        )
        return

    set_state(
        user_id,
        "cancel_confirm",
        {
            "training_id": training["training_id"],
        },
    )

    send_message(
        user_id,
        "Вы действительно хотите отменить запись?",
        keyboard([
            [
                button("✅ Да, отменить", "negative"),
            ],
            [
                button("⬅️ Назад", "secondary"),
            ],
        ]),
    )


def confirm_cancel(user_id):
    state = get_state(user_id)

    if not state:
        return

    training_id = state["data"].get(
        "training_id"
    )

    training = get_training(training_id)

    if not training:
        clear_state(user_id)

        send_message(
            user_id,
            "Тренировка не найдена.",
            main_menu(user_id),
        )
        return

    if not can_cancel_training(training):
        clear_state(user_id)

        send_message(
            user_id,
            "❌ Отмена невозможна.\n\n"
            "До начала тренировки осталось меньше 24 часов.",
            main_menu(user_id),
        )
        return

    success = cancel_registration(
        training_id,
        user_id,
        "Отмена пользователем",
    )

    clear_state(user_id)

    if success:
        send_message(
            user_id,
            "✅ Запись отменена.",
            main_menu(user_id),
        )
    else:
        send_message(
            user_id,
            "Активная запись не найдена.",
            main_menu(user_id),
        )


# ============================================================
# PARTICIPANTS
# ============================================================

def show_training_participants(
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
            admin_menu(),
        )
        return

    registrations = get_registrations(
        training_id
    )

    text = (
        f"👥 Участники\n\n"
        f"{training['title']}\n"
        f"{training['time']}\n\n"
    )

    if not registrations:
        text += "Пока никто не записан."
    else:
        for index, registration in enumerate(
            registrations,
            start=1,
        ):
            name = (
                registration["name"]
                or f"VK ID {registration['user_id']}"
            )

            text += (
                f"{index}. {name}\n"
            )

    send_message(
        user_id,
        text,
        admin_menu(),
    )


# ============================================================
# ADMIN PANEL
# ============================================================

def show_admin_panel(user_id):
    if user_id not in ADMIN_IDS:
        show_main_menu(user_id)
        return

    clear_state(user_id)

    send_message(
        user_id,
        "⚙️ Админ-панель\n\n"
        "Выберите действие:",
        admin_menu(),
    )


def show_admin_schedule(user_id):
    if user_id not in ADMIN_IDS:
        return

    trainings = get_trainings()

    if not trainings:
        send_message(
            user_id,
            "Расписание пустое.",
            admin_menu(),
        )
        return

    rows = []
    text = "📅 Управление расписанием\n\n"

    current_day = None

    for training in trainings:

        day = training["day_of_week"]

        if day != current_day:
            current_day = day

            text += (
                f"\n{DAY_NAMES.get(day, '')}\n"
            )

        text += (
            f"• {training['time']} — "
            f"{training['title']}\n"
        )

        rows.append([
            button(
                f"👥 {training['time']} — "
                f"{training['title']}",
                "secondary",
            )
        ])

    rows.append([
        button("⬅️ Админ-панель", "secondary")
    ])

    set_state(
        user_id,
        "admin_schedule",
    )

    send_message(
        user_id,
        text,
        keyboard(rows),
    )


def find_admin_training(
    user_id,
    text,
):
    trainings = get_trainings()

    for training in trainings:
        expected = (
            f"👥 {training['time']} — "
            f"{training['title']}"
        )

        if text == expected:
            return training

    return None


# ============================================================
# ADMIN — ADD TRAINING
# ============================================================

def start_add_training(user_id):
    if user_id not in ADMIN_IDS:
        return

    set_state(
        user_id,
        "admin_add_day",
    )

    send_message(
        user_id,
        "➕ Добавление тренировки\n\n"
        "Выберите день:",
        day_keyboard(),
    )


def add_training_day_selected(
    user_id,
    day,
):
    set_state(
        user_id,
        "admin_add_time",
        {
            "day": day,
        },
    )

    send_message(
        user_id,
        "Введите время тренировки.\n\n"
        "Например:\n"
        "19:00-20:30",
        back_keyboard(),
    )


def add_training_time_selected(
    user_id,
    time_text,
):
    state = get_state(user_id)

    data = state["data"]

    data["time"] = time_text.strip()

    set_state(
        user_id,
        "admin_add_title",
        data,
    )

    send_message(
        user_id,
        "Введите название тренировки.\n\n"
        "Например:\n"
        "Техничка",
        back_keyboard(),
    )


def add_training_title_selected(
    user_id,
    title,
):
    state = get_state(user_id)

    data = state["data"]

    data["title"] = title.strip()

    set_state(
        user_id,
        "admin_add_level",
        data,
    )

    send_message(
        user_id,
        "Введите уровень.\n\n"
        "Например:\n"
        "средний+\n\n"
        "Если уровень не нужен — напишите «нет».",
        back_keyboard(),
    )


def add_training_level_selected(
    user_id,
    level,
):
    state = get_state(user_id)

    data = state["data"]

    if level.strip().lower() == "нет":
        data["level"] = ""
    else:
        data["level"] = level.strip()

    set_state(
        user_id,
        "admin_add_age",
        data,
    )

    send_message(
        user_id,
        "Введите возраст.\n\n"
        "Например:\n"
        "11-14 лет\n\n"
        "Для взрослых — 18+.",
        back_keyboard(),
    )


def add_training_age_selected(
    user_id,
    age,
):
    state = get_state(user_id)

    data = state["data"]
    data["age_group"] = age.strip()

    set_state(
        user_id,
        "admin_add_price",
        data,
    )

    send_message(
        user_id,
        "Введите стоимость в рублях.\n\n"
        "Например: 1200",
        back_keyboard(),
    )


def add_training_price_selected(
    user_id,
    price_text,
):
    try:
        price = int(price_text.strip())
    except ValueError:
        send_message(
            user_id,
            "Введите стоимость числом.\n\n"
            "Например: 1200",
            back_keyboard(),
        )
        return

    state = get_state(user_id)

    data = state["data"]
    data["price"] = price

    set_state(
        user_id,
        "admin_add_capacity",
        data,
    )

    send_message(
        user_id,
        "Введите максимальное количество участников.\n\n"
        "Например: 10",
        back_keyboard(),
    )


def add_training_capacity_selected(
    user_id,
    capacity_text,
):
    try:
        capacity = int(
            capacity_text.strip()
        )
    except ValueError:
        send_message(
            user_id,
            "Введите количество числом.\n\n"
            "Например: 10",
            back_keyboard(),
        )
        return

    if capacity <= 0:
        send_message(
            user_id,
            "Количество участников должно быть больше нуля.",
            back_keyboard(),
        )
        return

    state = get_state(user_id)

    data = state["data"]
    data["capacity"] = capacity

    set_state(
        user_id,
        "admin_add_category",
        data,
    )

    send_message(
        user_id,
        "Выберите категорию:",
        category_keyboard(),
    )


def save_new_training(
    user_id,
    category,
):
    state = get_state(user_id)

    if not state:
        return

    data = state["data"]

    connection = sqlite3.connect(
        "volley_wave.db"
    )

    connection.execute("""
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
            format,
            coach,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data["day"],
        data["time"],
        data["title"],
        data["level"],
        data["age_group"],
        data["price"],
        data["capacity"],
        category,
        "Группа",
        "Алексей",
        "active",
    ))

    connection.commit()
    connection.close()

    add_admin_log(
        admin_id=user_id,
        action="add_training",
        entity="training",
        details=json.dumps(
            data,
            ensure_ascii=False,
        ),
    )

    clear_state(user_id)

    send_message(
        user_id,
        "✅ Тренировка добавлена в расписание.",
        admin_menu(),
    )


# ============================================================
# INDIVIDUAL TRAINING
# ============================================================

def start_individual_training(user_id):
    set_state(
        user_id,
        "individual_request",
    )

    send_message(
        user_id,
        "🎯 Индивидуальная тренировка\n\n"
        "Напишите удобные для вас дни и время, "
        "а также коротко расскажите, "
        "что хотите улучшить.\n\n"
        "Сообщение будет отправлено тренеру.",
        back_keyboard(),
    )


def send_request_to_admins(
    user_id,
    text,
    request_type,
):
    user = get_user(user_id)

    name = (
        user["name"]
        if user and user["name"]
        else f"VK ID {user_id}"
    )

    admin_text = (
        f"📩 Новая заявка\n\n"
        f"Тип: {request_type}\n"
        f"Пользователь: {name}\n"
        f"VK ID: {user_id}\n\n"
        f"{text}"
    )

    for admin_id in ADMIN_IDS:
        send_message(
            admin_id,
            admin_text,
            admin_menu(),
        )


# ============================================================
# QUESTIONS
# ============================================================

def start_question(user_id):
    set_state(
        user_id,
        "question",
    )

    send_message(
        user_id,
        "❓ Напишите свой вопрос.\n\n"
        "Он будет отправлен администраторам.",
        back_keyboard(),
    )


# ============================================================
# ADMIN USER MODE
# ============================================================

def enter_user_mode(user_id):
    set_state(
        user_id,
        "user_mode",
    )

    send_message(
        user_id,
        "🏠 Вы перешли в режим пользователя.\n\n"
        "Ваши права администратора сохранены.",
        main_menu(user_id),
    )


# ============================================================
# MESSAGE HANDLER
# ============================================================

def handle_message(user_id, text):
    text = text.strip()

    register_user(user_id)

    state = get_state(user_id)

    # ========================================================
    # GLOBAL NAVIGATION
    # ========================================================

    if text in (
        "⬅️ Главное меню",
        "🏠 Главное меню",
    ):
        clear_state(user_id)
        show_main_menu(user_id)
        return

    if text == "⬅️ Назад":
        clear_state(user_id)
        show_main_menu(user_id)
        return

    # ========================================================
    # ADMIN PANEL
    # ========================================================

    if text == "⚙️ Админ-панель":
        if user_id in ADMIN_IDS:
            show_admin_panel(user_id)
        return

    if text == "🏠 Режим пользователя":
        if user_id in ADMIN_IDS:
            enter_user_mode(user_id)
        return

    if text == "➕ Добавить тренировку":
        if user_id in ADMIN_IDS:
            start_add_training(user_id)
        return

    if text == "📅 Управление расписанием":
        if user_id in ADMIN_IDS:
            show_admin_schedule(user_id)
        return

    if text == "👥 Участники тренировок":
        if user_id in ADMIN_IDS:
            show_admin_schedule(user_id)
        return

    # ========================================================
    # ADMIN ADD TRAINING STATE
    # ========================================================

    if user_id in ADMIN_IDS and state:

        state_name = state["state"]

        if state_name == "admin_add_day":

            if text in DAY_BUTTON_TO_NUMBER:
                add_training_day_selected(
                    user_id,
                    DAY_BUTTON_TO_NUMBER[text],
                )
                return

        elif state_name == "admin_add_time":

            add_training_time_selected(
                user_id,
                text,
            )
            return

        elif state_name == "admin_add_title":

            add_training_title_selected(
                user_id,
                text,
            )
            return

        elif state_name == "admin_add_level":

            add_training_level_selected(
                user_id,
                text,
            )
            return

        elif state_name == "admin_add_age":

            add_training_age_selected(
                user_id,
                text,
            )
            return

        elif state_name == "admin_add_price":

            add_training_price_selected(
                user_id,
                text,
            )
            return

        elif state_name == "admin_add_capacity":

            add_training_capacity_selected(
                user_id,
                text,
            )
            return

        elif state_name == "admin_add_category":

            if text == "👶 Дети":
                save_new_training(
                    user_id,
                    "children",
                )
                return

            if text == "🧑 Взрослые":
                save_new_training(
                    user_id,
                    "adults",
                )
                return

    # ========================================================
    # ADMIN SCHEDULE
    # ========================================================

    if (
        user_id in ADMIN_IDS
        and state
        and state["state"] == "admin_schedule"
    ):
        training = find_admin_training(
            user_id,
            text,
        )

        if training:
            show_training_participants(
                user_id,
                training["id"],
            )
            return

    # ========================================================
    # MAIN MENU
    # ========================================================

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
        show_locations(user_id)
        return

    if text == "🎯 Индивидуальная тренировка":
        start_individual_training(user_id)
        return

    if text == "❓ Задать вопрос":
        start_question(user_id)
        return

    # ========================================================
    # SCHEDULE CATEGORY
    # ========================================================

    if (
        state
        and state["state"] == "schedule_category"
    ):

        if text == "👶 Дети":
            show_schedule(
                user_id,
                "children",
            )
            clear_state(user_id)
            return

        if text == "🧑 Взрослые":
            show_schedule(
                user_id,
                "adults",
            )
            clear_state(user_id)
            return

    # ========================================================
    # BOOKING CATEGORY
    # ========================================================

    if (
        state
        and state["state"] == "booking_category"
    ):

        if text == "👶 Дети":
            show_booking_days(
                user_id,
                "children",
            )
            return

        if text == "🧑 Взрослые":
            show_booking_days(
                user_id,
                "adults",
            )
            return

    # ========================================================
    # BOOKING DAY
    # ========================================================

    if (
        state
        and state["state"] == "booking_day"
    ):

        if text in DAY_BUTTON_TO_NUMBER:

            category = state["data"]["category"]

            show_booking_trainings(
                user_id,
                category,
                DAY_BUTTON_TO_NUMBER[text],
            )
            return

    # ========================================================
    # BOOKING TRAINING
    # ========================================================

    if (
        state
        and state["state"] == "booking_training"
    ):

        training = find_training_from_button(
            user_id,
            text,
        )

        if training:
            show_booking_confirmation(
                user_id,
                training,
            )
            return

    # ========================================================
    # BOOKING CONFIRM
    # ========================================================

    if (
        state
        and state["state"] == "booking_confirm"
    ):

        if text == "✅ Записаться":
            confirm_booking(user_id)
            return

    # ========================================================
    # MY TRAININGS
    # ========================================================

    if (
        state
        and state["state"] == "my_trainings"
    ):

        training = find_my_training_from_button(
            user_id,
            text,
        )

        if training:
            show_cancel_confirmation(
                user_id,
                training,
            )
            return

    # ========================================================
    # CANCEL CONFIRM
    # ========================================================

    if (
        state
        and state["state"] == "cancel_confirm"
    ):

        if text == "✅ Да, отменить":
            confirm_cancel(user_id)
            return

    # ========================================================
    # INDIVIDUAL REQUEST
    # ========================================================

    if (
        state
        and state["state"] == "individual_request"
    ):

        send_request_to_admins(
            user_id,
            text,
            "Индивидуальная тренировка",
        )

        clear_state(user_id)

        send_message(
            user_id,
            "✅ Заявка отправлена тренеру.\n\n"
            "С вами свяжутся для уточнения времени.",
            main_menu(user_id),
        )
        return

    # ========================================================
    # QUESTION
    # ========================================================

    if (
        state
        and state["state"] == "question"
    ):

        send_request_to_admins(
            user_id,
            text,
            "Вопрос",
        )

        clear_state(user_id)

        send_message(
            user_id,
            "✅ Вопрос отправлен администраторам.",
            main_menu(user_id),
        )
        return

    # ========================================================
    # DEFAULT
    # ========================================================

    send_message(
        user_id,
        "Не совсем понял команду.\n\n"
        "Выберите действие из меню 👇",
        main_menu(user_id),
    )


# ============================================================
# VK CALLBACK
# ============================================================

@app.route("/callback", methods=["POST"])
def callback():

    try:
        data = request.get_json(
            silent=True
        ) or {}

        event_type = data.get(
            "type"
        )

        # ----------------------------------------------------
        # CONFIRMATION
        # ----------------------------------------------------

        if event_type == "confirmation":
            return VK_CONFIRMATION_TOKEN

        # ----------------------------------------------------
        # MESSAGE_NEW
        # ----------------------------------------------------

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

            if not user_id:
                return "ok"

            handle_message(
                int(user_id),
                text,
            )

            return "ok"

        return "ok"

    except Exception as error:

        print(
            f"CALLBACK ERROR: {error}",
            flush=True,
        )

        return "ok"


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/", methods=["GET"])
def health():
    return "Volley Wave VK Bot is running"


# ============================================================
# START
# ============================================================

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
    )
