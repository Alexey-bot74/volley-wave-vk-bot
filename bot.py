import os
import json
import logging
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

import requests
from flask import Flask, request

from database import (
    init_db,
    create_or_update_user,
    get_user,
    is_user_blocked,
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
    add_admin_log,
    get_connection,
)


# ============================================================
# CONFIG
# ============================================================

VK_TOKEN = os.getenv("VK_TOKEN")
VK_SECRET_KEY = os.getenv("VK_SECRET_KEY")
VK_CONFIRMATION_TOKEN = os.getenv("VK_CONFIRMATION_TOKEN")

VK_API_VERSION = "5.199"
PORT = int(os.getenv("PORT", "10000"))

TIMEZONE = ZoneInfo("Asia/Yekaterinburg")

GROUP_ID = 221776135

ADMINS = {
    87984447,
    172892670,
    148372158,
}


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("volley_wave_bot")


# ============================================================
# FLASK
# ============================================================

app = Flask(__name__)


# ============================================================
# STATES
# ============================================================

user_states = {}


def set_state(user_id, state, data=None):
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
    user_states.pop(user_id, None)


# ============================================================
# VK API
# ============================================================

def vk_api(method, params):
    if not VK_TOKEN:
        logger.error("VK_TOKEN is not configured")
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

        result = response.json()

        if "error" in result:
            logger.error(
                "VK API error in %s: %s",
                method,
                result["error"],
            )

        return result

    except Exception:
        logger.exception(
            "VK API request failed: %s",
            method,
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
            ensure_ascii=False,
        )

    return vk_api("messages.send", params)


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


def main_menu(user_id):
    buttons = [
        [
            button("🏐 Записаться", "primary"),
            button("📅 Расписание", "secondary"),
        ],
        [
            button("👤 Мои тренировки", "secondary"),
            button("💰 Цены", "secondary"),
        ],
        [
            button("📍 Где тренируемся", "secondary"),
            button(
                "🎯 Индивидуальная тренировка",
                "secondary",
            ),
        ],
        [
            button("❓ Задать вопрос", "secondary"),
        ],
    ]

    if user_id in ADMINS:
        buttons.append(
            [
                button(
                    "⚙️ Админ-панель",
                    "positive",
                ),
            ]
        )

    return {
        "one_time": False,
        "buttons": buttons,
    }


def back_keyboard(user_id):
    return {
        "one_time": False,
        "buttons": [
            [
                button("⬅️ Назад", "secondary"),
                button(
                    "🏠 Главное меню",
                    "secondary",
                ),
            ]
        ],
    }


def admin_menu():
    return {
        "one_time": False,
        "buttons": [
            [
                button(
                    "📅 Расписание",
                    "secondary",
                ),
                button(
                    "👥 Участники тренировок",
                    "secondary",
                ),
            ],
            [
                button(
                    "➕ Добавить тренировку",
                    "primary",
                ),
                button(
                    "🧩 Шаблоны",
                    "secondary",
                ),
            ],
            [
                button(
                    "👤 Режим пользователя",
                    "secondary",
                ),
            ],
            [
                button(
                    "🏠 Главное меню",
                    "secondary",
                ),
            ],
        ],
    }


def admin_back_keyboard():
    return {
        "one_time": False,
        "buttons": [
            [
                button(
                    "⬅️ Админ-панель",
                    "secondary",
                ),
                button(
                    "🏠 Главное меню",
                    "secondary",
                ),
            ]
        ],
    }


# ============================================================
# DATE / TEXT HELPERS
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


def today_local():
    return datetime.now(TIMEZONE).date()


def format_date(value):
    if isinstance(value, str):
        value = datetime.strptime(
            value,
            "%Y-%m-%d",
        ).date()

    return (
        f"{WEEKDAYS[value.weekday()]}, "
        f"{value.day} "
        f"{month_name(value.month)} "
        f"{value.year}"
    )


def format_short_date(value):
    if isinstance(value, str):
        value = datetime.strptime(
            value,
            "%Y-%m-%d",
        ).date()

    return (
        f"{WEEKDAYS_SHORT[value.weekday()]}, "
        f"{value.strftime('%d.%m')}"
    )


def month_name(month):
    months = [
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

    return months[month]


def row_value(row, key, default=None):
    if row is None:
        return default

    try:
        return row[key]
    except Exception:
        try:
            return row.get(key, default)
        except Exception:
            return default


# ============================================================
# USER
# ============================================================

def ensure_user(user_id):
    try:
        info = vk_api(
            "users.get",
            {
                "user_ids": user_id,
                "fields": "first_name,last_name",
            },
        )

        first_name = ""
        last_name = ""

        if info and info.get("response"):
            user = info["response"][0]
            first_name = user.get(
                "first_name",
                "",
            )
            last_name = user.get(
                "last_name",
                "",
            )

        create_or_update_user(
            user_id,
            first_name,
            last_name,
        )

        return get_user(user_id)

    except Exception:
        logger.exception(
            "Failed to create/update user %s",
            user_id,
        )
        return get_user(user_id)


# ============================================================
# TRAINING HELPERS
# ============================================================

def training_title(training):
    title = row_value(
        training,
        "title",
        "Тренировка",
    )

    return title or "Тренировка"


def training_number(training):
    return row_value(
        training,
        "training_number",
        row_value(training, "id"),
    )


def training_date_value(training):
    value = row_value(
        training,
        "training_date",
    )

    if isinstance(value, date):
        return value

    return datetime.strptime(
        str(value),
        "%Y-%m-%d",
    ).date()


def training_capacity(training):
    value = row_value(
        training,
        "capacity",
        0,
    )

    try:
        return int(value)
    except Exception:
        return 0


def get_training_participant_count(training_id):
    try:
        return get_registration_count(
            training_id
        )

    except Exception:
        connection = get_connection()

        try:
            cursor = connection.cursor()

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM registrations
                WHERE training_id = ?
                  AND status = 'active'
                """,
                (training_id,),
            )

            return cursor.fetchone()[0]

        finally:
            connection.close()


def training_is_full(training):
    training_id = row_value(
        training,
        "id",
    )

    if training_id is None:
        return False

    count = get_training_participant_count(
        training_id
    )

    return count >= training_capacity(training)


def format_training(
    training,
    include_participants=True,
):
    training_id = row_value(
        training,
        "id",
    )

    number = training_number(training)
    training_date = training_date_value(
        training
    )

    start_time = row_value(
        training,
        "start_time",
        "",
    )

    end_time = row_value(
        training,
        "end_time",
        "",
    )

    title = training_title(training)

    category = row_value(
        training,
        "category",
        "",
    )

    age_group = row_value(
        training,
        "age_group",
        "",
    )

    level = row_value(
        training,
        "level",
        "",
    )

    training_format = row_value(
        training,
        "format",
        "",
    )

    coach = row_value(
        training,
        "coach",
        "",
    )

    capacity = training_capacity(
        training
    )

    price = row_value(
        training,
        "price",
        0,
    )

    location = row_value(
        training,
        "location",
        "",
    )

    status = row_value(
        training,
        "status",
        "active",
    )

    text = (
        f"🏐 Тренировка №{number}\n"
        f"📅 {format_date(training_date)}\n"
        f"⏰ {start_time}–{end_time}\n"
        f"📌 {title}\n"
    )

    if category:
        text += (
            f"👥 Категория: {category}\n"
        )

    if age_group:
        text += (
            f"🎂 Возраст: {age_group}\n"
        )

    if level:
        text += (
            f"📊 Уровень: {level}\n"
        )

    if training_format:
        text += (
            f"🔹 Формат: {training_format}\n"
        )

    if coach:
        text += (
            f"🏅 Тренер: {coach}\n"
        )

    if location:
        text += (
            f"📍 {location}\n"
        )

    if price is not None:
        text += (
            f"💰 {price}₽\n"
        )

    if include_participants and training_id:
        count = get_training_participant_count(
            training_id
        )

        text += (
            f"\n👤 Записано: "
            f"{count}/{capacity}"
        )

    if status != "active":
        text += (
            f"\n⚠️ Статус: {status}"
        )

    return text


# ============================================================
# USER MENU
# ============================================================

def show_main_menu(user_id):
    clear_state(user_id)

    send_message(
        user_id,
        "🏐 VOLLEY WAVE\n\n"
        "Выберите действие:",
        main_menu(user_id),
    )


def show_prices(user_id):
    send_message(
        user_id,
        "💰 ЦЕНЫ\n\n"
        "🏐 Детские тренировки — 600₽\n\n"
        "🏐 Взрослые тренировки:\n"
        "1–6 человек — 1200₽/человек\n"
        "7 и более — 1000₽/человек\n\n"
        "Минимальная группа взрослых — 4 человека.",
        back_keyboard(user_id),
    )


def show_locations(user_id):
    send_message(
        user_id,
        "📍 ГДЕ ТРЕНИРУЕМСЯ\n\n"
        "☀️ Летом:\n"
        "Парк Гагарина\n\n"
        "❄️ Зимой:\n"
        "СК «Арена»\n"
        "ул. Молодогвардейцев, 7",
        back_keyboard(user_id),
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
        {
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
                        "🏠 Все тренировки",
                        "secondary",
                    ),
                ],
                [
                    button(
                        "⬅️ Назад",
                        "secondary",
                    ),
                ],
            ],
        },
    )


def show_schedule(
    user_id,
    category=None,
):
    today = today_local()
    end_date = today + timedelta(
        days=7
    )

    try:
        if category == "children":
            trainings = get_upcoming_trainings(
                from_date=today.isoformat(),
                to_date=end_date.isoformat(),
                category="Дети",
            )

        elif category == "adults":
            trainings = get_upcoming_trainings(
                from_date=today.isoformat(),
                to_date=end_date.isoformat(),
                category="Взрослые",
            )

        else:
            trainings = get_upcoming_trainings(
                from_date=today.isoformat(),
                to_date=end_date.isoformat(),
            )

    except Exception:
        logger.exception(
            "Failed to load schedule"
        )
        trainings = []

    trainings = list(
        trainings or []
    )

    if not trainings:
        send_message(
            user_id,
            "📅 На ближайшие 7 дней "
            "тренировок нет.",
            back_keyboard(user_id),
        )
        return

    buttons = []

    for training in trainings:
        training_date = training_date_value(
            training
        )

        label = (
            f"№{training_number(training)} "
            f"{format_short_date(training_date)} "
            f"{row_value(training, 'start_time', '')}"
        )

        buttons.append(
            [
                button(
                    label[:40],
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
        "schedule_select_training",
        {
            "category": category,
        },
    )

    send_message(
        user_id,
        "📅 Ближайшие тренировки:\n\n"
        "Выберите тренировку:",
        {
            "one_time": False,
            "buttons": buttons,
        },
    )


# ============================================================
# BOOKING
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
        {
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
                        "🏠 Все тренировки",
                        "secondary",
                    ),
                ],
                [
                    button(
                        "⬅️ Назад",
                        "secondary",
                    ),
                ],
            ],
        },
    )


def show_booking_dates(
    user_id,
    category,
):
    today = today_local()

    dates = []

    for offset in range(7):
        current = today + timedelta(
            days=offset
        )

        try:
            trainings = get_trainings_by_date(
                current.isoformat()
            )
        except Exception:
            trainings = []

        trainings = list(
            trainings or []
        )

        if category == "children":
            trainings = [
                x
                for x in trainings
                if str(
                    row_value(
                        x,
                        "category",
                        "",
                    )
                ).lower()
                in (
                    "дети",
                    "children",
                )
            ]

        elif category == "adults":
            trainings = [
                x
                for x in trainings
                if str(
                    row_value(
                        x,
                        "category",
                        "",
                    )
                ).lower()
                in (
                    "взрослые",
                    "adults",
                )
            ]

        if trainings:
            dates.append(current)

    if not dates:
        send_message(
            user_id,
            "🏐 На ближайшие 7 дней "
            "подходящих тренировок нет.",
            back_keyboard(user_id),
        )
        return

    buttons = []

    for current in dates:
        buttons.append(
            [
                button(
                    format_short_date(current),
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
        {
            "category": category,
        },
    )

    send_message(
        user_id,
        "📅 Выберите день:",
        {
            "one_time": False,
            "buttons": buttons,
        },
    )


def show_booking_trainings(
    user_id,
    category,
    selected_date,
):
    try:
        trainings = get_trainings_by_date(
            selected_date.isoformat()
        )

    except Exception:
        logger.exception(
            "Failed to load trainings by date"
        )
        trainings = []

    trainings = list(
        trainings or []
    )

    if category == "children":
        trainings = [
            x
            for x in trainings
            if str(
                row_value(
                    x,
                    "category",
                    "",
                )
            ).lower()
            in (
                "дети",
                "children",
            )
        ]

    elif category == "adults":
        trainings = [
            x
            for x in trainings
            if str(
                row_value(
                    x,
                    "category",
                    "",
                )
            ).lower()
            in (
                "взрослые",
                "adults",
            )
        ]

    if not trainings:
        send_message(
            user_id,
            "На этот день подходящих "
            "тренировок нет.",
            back_keyboard(user_id),
        )
        return

    buttons = []

    for training in trainings:
        label = (
            f"№{training_number(training)} "
            f"{row_value(training, 'start_time', '')}–"
            f"{row_value(training, 'end_time', '')}"
        )

        buttons.append(
            [
                button(
                    label[:40],
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
        {
            "category": category,
            "date": selected_date.isoformat(),
        },
    )

    send_message(
        user_id,
        f"📅 {format_date(selected_date)}\n\n"
        "Выберите тренировку:",
        {
            "one_time": False,
            "buttons": buttons,
        },
    )


def show_training_for_booking(
    user_id,
    training,
):
    training_id = row_value(
        training,
        "id",
    )

    text = format_training(
        training
    )

    text += "\n\n👥 УЧАСТНИКИ\n"

    try:
        registrations = get_registrations(
            training_id
        )
    except Exception:
        registrations = []

    registrations = list(
        registrations or []
    )

    if not registrations:
        text += "Пока никто не записан."

    else:
        for index, registration in enumerate(
            registrations,
            start=1,
        ):
            first_name = row_value(
                registration,
                "first_name",
                "",
            )

            last_name = row_value(
                registration,
                "last_name",
                "",
            )

            name = (
                f"{first_name} "
                f"{last_name}"
            ).strip()

            if not name:
                name = "Участник"

            text += (
                f"\n{index}. {name}"
            )

    buttons = []

    registration = get_registration(
        training_id,
        user_id,
    )

    if registration:
        buttons.append(
            [
                button(
                    "❌ Отменить запись",
                    "negative",
                )
            ]
        )

    elif training_is_full(training):
        buttons.append(
            [
                button(
                    "⏳ Встать в лист ожидания",
                    "primary",
                )
            ]
        )

    else:
        buttons.append(
            [
                button(
                    "✅ Записаться",
                    "positive",
                )
            ]
        )

    buttons.append(
        [
            button(
                "⬅️ Назад",
                "secondary",
            ),
            button(
                "🏠 Главное меню",
                "secondary",
            ),
        ]
    )

    set_state(
        user_id,
        "training_details",
        {
            "training_id": training_id,
        },
    )

    send_message(
        user_id,
        text,
        {
            "one_time": False,
            "buttons": buttons,
        },
    )


def register_user_for_training(
    user_id,
    training_id,
):
    training = get_training(
        training_id
    )

    if not training:
        send_message(
            user_id,
            "❌ Тренировка не найдена.",
            back_keyboard(user_id),
        )
        return

    if row_value(
        training,
        "status",
        "active",
    ) != "active":
        send_message(
            user_id,
            "❌ Эта тренировка "
            "недоступна для записи.",
            back_keyboard(user_id),
        )
        return

    existing = get_registration(
        training_id,
        user_id,
    )

    if existing:
        send_message(
            user_id,
            "Вы уже записаны "
            "на эту тренировку.",
            back_keyboard(user_id),
        )
        return

    if training_is_full(training):
        existing_waitlist = (
            get_waitlist_entry(
                training_id,
                user_id,
            )
        )

        if existing_waitlist:
            send_message(
                user_id,
                "⏳ Вы уже находитесь "
                "в листе ожидания.",
                back_keyboard(user_id),
            )
            return

        add_to_waitlist(
            training_id,
            user_id,
        )

        add_admin_log(
            user_id,
            "waitlist_add",
            "training",
            training_id,
            "User added to waitlist",
        )

        send_message(
            user_id,
            "⏳ Тренировка заполнена.\n\n"
            "Вы добавлены в лист ожидания.",
            main_menu(user_id),
        )

        return

    try:
        add_registration(
            training_id,
            user_id,
        )

        add_admin_log(
            user_id,
            "registration_add",
            "training",
            training_id,
            "User registered",
        )

        send_message(
            user_id,
            "✅ Вы успешно записаны!\n\n"
            + format_training(training),
            main_menu(user_id),
        )

    except Exception as error:
        logger.exception(
            "Registration error"
        )

        send_message(
            user_id,
            "❌ Не удалось записаться.\n\n"
            f"Ошибка: {error}",
            main_menu(user_id),
        )


def cancel_user_registration(
    user_id,
    training_id,
):
    training = get_training(
        training_id
    )

    if not training:
        send_message(
            user_id,
            "❌ Тренировка не найдена.",
            main_menu(user_id),
        )
        return

    training_date = training_date_value(
        training
    )

    training_datetime = datetime.combine(
        training_date,
        datetime.strptime(
            row_value(
                training,
                "start_time",
                "00:00",
            ),
            "%H:%M",
        ).time(),
    ).replace(
        tzinfo=TIMEZONE
    )

    now = datetime.now(TIMEZONE)

    if (
        training_datetime - now
        < timedelta(hours=24)
    ):
        send_message(
            user_id,
            "❌ Отменить запись можно "
            "не позднее чем за 24 часа "
            "до тренировки.",
            main_menu(user_id),
        )
        return

    registration = get_registration(
        training_id,
        user_id,
    )

    if not registration:
        send_message(
            user_id,
            "Вы не записаны "
            "на эту тренировку.",
            main_menu(user_id),
        )
        return

    try:
        cancel_registration(
            training_id,
            user_id,
            "user_cancelled",
        )

        add_admin_log(
            user_id,
            "registration_cancel",
            "training",
            training_id,
            "User cancelled registration",
        )

        send_message(
            user_id,
            "✅ Запись отменена.",
            main_menu(user_id),
        )

    except Exception as error:
        logger.exception(
            "Cancellation error"
        )

        send_message(
            user_id,
            "❌ Не удалось отменить запись.\n\n"
            f"Ошибка: {error}",
            main_menu(user_id),
        )


# ============================================================
# MY TRAININGS
# ============================================================

def show_my_trainings(user_id):
    try:
        registrations = get_user_registrations(
            user_id
        )
    except Exception:
        logger.exception(
            "Failed to load user registrations"
        )
        registrations = []

    registrations = list(
        registrations or []
    )

    if not registrations:
        send_message(
            user_id,
            "👤 У вас пока нет "
            "активных записей.",
            back_keyboard(user_id),
        )
        return

    active = []

    for registration in registrations:
        status = row_value(
            registration,
            "status",
            "active",
        )

        if status != "active":
            continue

        training_id = row_value(
            registration,
            "training_id",
        )

        training = None

        if training_id:
            training = get_training(
                training_id
            )

        if training:
            active.append(training)

    active.sort(
        key=lambda x: (
            training_date_value(x),
            row_value(
                x,
                "start_time",
                "",
            ),
        )
    )

    if not active:
        send_message(
            user_id,
            "👤 У вас пока нет "
            "предстоящих тренировок.",
            back_keyboard(user_id),
        )
        return

    buttons = []

    for training in active:
        label = (
            f"№{training_number(training)} "
            f"{format_short_date(training_date_value(training))} "
            f"{row_value(training, 'start_time', '')}"
        )

        buttons.append(
            [
                button(
                    label[:40],
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
        "my_training_select",
        {},
    )

    send_message(
        user_id,
        "👤 МОИ ТРЕНИРОВКИ\n\n"
        "Выберите тренировку:",
        {
            "one_time": False,
            "buttons": buttons,
        },
    )


# ============================================================
# ADMIN — DIRECT DB HELPERS
# ============================================================

def admin_db_trainings(
    from_date=None,
    to_date=None,
):
    connection = get_connection()

    try:
        cursor = connection.cursor()

        query = """
            SELECT *
            FROM trainings
            WHERE 1 = 1
        """

        params = []

        if from_date:
            query += (
                " AND training_date >= ?"
            )
            params.append(from_date)

        if to_date:
            query += (
                " AND training_date <= ?"
            )
            params.append(to_date)

        query += """
            ORDER BY training_date ASC,
                     start_time ASC,
                     training_number ASC
        """

        cursor.execute(
            query,
            params,
        )

        return cursor.fetchall()

    finally:
        connection.close()


def admin_db_training(training_id):
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT *
            FROM trainings
            WHERE id = ?
            """,
            (training_id,),
        )

        return cursor.fetchone()

    finally:
        connection.close()


def admin_create_training(data):
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT COALESCE(
                MAX(training_number),
                0
            ) + 1
            FROM trainings
            """
        )

        training_number_value = (
            cursor.fetchone()[0]
        )

        cursor.execute(
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
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            )
            """,
            (
                training_number_value,
                data["training_date"],
                data["weekday"],
                data["start_time"],
                data["end_time"],
                data["title"],
                data["category"],
                data["age_group"],
                data["level"],
                data["format"],
                data["coach"],
                data["capacity"],
                data["price"],
                data["location"],
                "active",
                data.get("template_id"),
            ),
        )

        training_id = cursor.lastrowid

        connection.commit()

        return training_id

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# ============================================================
# DEFAULT TRAINING SCHEDULE
# ============================================================

DEFAULT_TEMPLATES = [
    {
        "weekday": 0,
        "start_time": "09:00",
        "end_time": "11:00",
        "title": "Детская тренировка",
        "category": "Дети",
        "age_group": "9–13",
        "level": "Начальный / средний",
        "format": "Группа",
        "coach": "Алексей",
        "capacity": 10,
        "price": 600,
        "location": "СК «Арена», ул. Молодогвардейцев, 7",
    },
    {
        "weekday": 0,
        "start_time": "17:00",
        "end_time": "19:00",
        "title": "Детская тренировка",
        "category": "Дети",
        "age_group": "11–14",
        "level": "Средний",
        "format": "Группа",
        "coach": "Алексей",
        "capacity": 10,
        "price": 600,
        "location": "СК «Арена», ул. Молодогвардейцев, 7",
    },
    {
        "weekday": 0,
        "start_time": "19:00",
        "end_time": "20:30",
        "title": "Техническая тренировка",
        "category": "Взрослые",
        "age_group": "18+",
        "level": "Технический",
        "format": "Группа",
        "coach": "Алексей",
        "capacity": 10,
        "price": 1200,
        "location": "СК «Арена», ул. Молодогвардейцев, 7",
    },
    {
        "weekday": 1,
        "start_time": "09:00",
        "end_time": "11:00",
        "title": "Общая тренировка",
        "category": "Взрослые",
        "age_group": "18+",
        "level": "Общий",
        "format": "Группа",
        "coach": "Алексей",
        "capacity": 8,
        "price": 1200,
        "location": "СК «Арена», ул. Молодогвардейцев, 7",
    },
    {
        "weekday": 1,
        "start_time": "17:00",
        "end_time": "18:30",
        "title": "Детская тренировка",
        "category": "Дети",
        "age_group": "11–14",
        "level": "Средний",
        "format": "Группа",
        "coach": "Алексей",
        "capacity": 10,
        "price": 600,
        "location": "СК «Арена», ул. Молодогвардейцев, 7",
    },
    {
        "weekday": 1,
        "start_time": "19:30",
        "end_time": "21:00",
        "title": "Женская тренировка",
        "category": "Взрослые",
        "age_group": "18+",
        "level": "Средний+",
        "format": "Женская группа",
        "coach": "Алексей",
        "capacity": 8,
        "price": 1200,
        "location": "СК «Арена», ул. Молодогвардейцев, 7",
    },
    {
        "weekday": 2,
        "start_time": "09:00",
        "end_time": "11:00",
        "title": "Детская тренировка",
        "category": "Дети",
        "age_group": "9–14",
        "level": "Начальный / средний",
        "format": "Группа",
        "coach": "Алексей",
        "capacity": 10,
        "price": 600,
        "location": "СК «Арена», ул. Молодогвардейцев, 7",
    },
    {
        "weekday": 2,
        "start_time": "17:00",
        "end_time": "18:00",
        "title": "Детская тренировка",
        "category": "Дети",
        "age_group": "5–9",
        "level": "Начальный",
        "format": "Группа",
        "coach": "Ксения",
        "capacity": 10,
        "price": 600,
        "location": "СК «Арена», ул. Молодогвардейцев, 7",
    },
    {
        "weekday": 2,
        "start_time": "18:00",
        "end_time": "19:30",
        "title": "Продвинутая тренировка",
        "category": "Взрослые",
        "age_group": "18+",
        "level": "Продвинутый",
        "format": "Группа",
        "coach": "Алексей",
        "capacity": 8,
        "price": 1200,
        "location": "СК «Арена», ул. Молодогвардейцев, 7",
    },
    {
        "weekday": 2,
        "start_time": "19:30",
        "end_time": "21:00",
        "title": "MIXED",
        "category": "Взрослые",
        "age_group": "18+",
        "level": "Средний+",
        "format": "MIXED",
        "coach": "Алексей",
        "capacity": 8,
        "price": 1200,
        "location": "СК «Арена», ул. Молодогвардейцев, 7",
    },
    {
        "weekday": 3,
        "start_time": "09:00",
        "end_time": "11:00",
        "title": "Общая тренировка",
        "category": "Взрослые",
        "age_group": "18+",
        "level": "Общий",
        "format": "Группа",
        "coach": "Алексей",
        "capacity": 8,
        "price": 1200,
        "location": "СК «Арена», ул. Молодогвардейцев, 7",
    },
    {
        "weekday": 3,
        "start_time": "17:00",
        "end_time": "19:00",
        "title": "Детская тренировка",
        "category": "Дети",
        "age_group": "11–14",
        "level": "Средний",
        "format": "Группа",
        "coach": "Алексей",
        "capacity": 10,
        "price": 600,
        "location": "СК «Арена», ул. Молодогвардейцев, 7",
    },
    {
        "weekday": 3,
        "start_time": "19:00",
        "end_time": "20:30",
        "title": "Тренировка для взрослых",
        "category": "Взрослые",
        "age_group": "18+",
        "level": "Средний",
        "format": "Группа",
        "coach": "Алексей",
        "capacity": 8,
        "price": 1200,
        "location": "СК «Арена», ул. Молодогвардейцев, 7",
    },
    {
        "weekday": 4,
        "start_time": "09:00",
        "end_time": "11:00",
        "title": "Детская тренировка",
        "category": "Дети",
        "age_group": "9–14",
        "level": "Начальный / средний",
        "format": "Группа",
        "coach": "Алексей",
        "capacity": 10,
        "price": 600,
        "location": "СК «Арена», ул. Молодогвардейцев, 7",
    },
    {
        "weekday": 4,
        "start_time": "17:00",
        "end_time": "18:00",
        "title": "Детская тренировка",
        "category": "Дети",
        "age_group": "5–10",
        "level": "Начальный",
        "format": "Группа",
        "coach": "Ксения",
        "capacity": 10,
        "price": 600,
        "location": "СК «Арена», ул. Молодогвардейцев, 7",
    },
    {
        "weekday": 4,
        "start_time": "17:00",
        "end_time": "19:00",
        "title": "Детская тренировка",
        "category": "Дети",
        "age_group": "11–14",
        "level": "Средний",
        "format": "Группа",
        "coach": "Алексей",
        "capacity": 10,
        "price": 600,
        "location": "СК «Арена», ул. Молодогвардейцев, 7",
    },
    {
        "weekday": 4,
        "start_time": "19:00",
        "end_time": "20:30",
        "title": "Техническая тренировка",
        "category": "Взрослые",
        "age_group": "18+",
        "level": "Технический",
        "format": "Группа",
        "coach": "Алексей",
        "capacity": 10,
        "price": 1200,
        "location": "СК «Арена», ул. Молодогвардейцев, 7",
    },
]


# ============================================================
# SCHEDULE GENERATION
# ============================================================

def get_table_columns(
    connection,
    table_name,
):
    cursor = connection.cursor()

    cursor.execute(
        f"PRAGMA table_info({table_name})"
    )

    rows = cursor.fetchall()

    result = []

    for row in rows:
        name = row_value(
            row,
            "name",
        )

        if name:
            result.append(name)

    return result


def ensure_default_templates():
    """
    Восстанавливает шаблоны, если база была
    очищена после перезапуска Render.

    Функция специально использует PRAGMA,
    чтобы не зависеть от точной версии
    database.py.
    """

    connection = get_connection()

    try:
        columns = get_table_columns(
            connection,
            "training_templates",
        )

        if not columns:
            logger.warning(
                "training_templates table "
                "has no columns"
            )
            return

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM training_templates
            """
        )

        count = cursor.fetchone()[0]

        if count > 0:
            logger.info(
                "Training templates already exist: %s",
                count,
            )
            return

        logger.info(
            "Creating default training templates..."
        )

        for template in DEFAULT_TEMPLATES:
            values = {}

            for column in columns:

                if column == "weekday":
                    values[column] = (
                        template["weekday"]
                    )

                elif column in template:
                    values[column] = template[column]

                elif column == "active":
                    values[column] = 1

                elif column == "is_active":
                    values[column] = 1

                elif column == "created_at":
                    values[column] = datetime.now().isoformat(
                        timespec="seconds"
                    )

                elif column == "updated_at":
                    values[column] = datetime.now().isoformat(
                        timespec="seconds"
                    )

            if not values:
                continue

            column_names = list(
                values.keys()
            )

            placeholders = ", ".join(
                ["?"] * len(column_names)
            )

            sql = (
                "INSERT INTO training_templates "
                f"({', '.join(column_names)}) "
                f"VALUES ({placeholders})"
            )

            cursor.execute(
                sql,
                [
                    values[column]
                    for column in column_names
                ],
            )

        connection.commit()

        logger.info(
            "Default templates created: %s",
            len(DEFAULT_TEMPLATES),
        )

    except Exception:
        connection.rollback()

        logger.exception(
            "Failed to create default templates"
        )

        raise

    finally:
        connection.close()


def create_training_directly(
    template,
    training_date,
):
    """
    Создаёт конкретную тренировку напрямую
    через SQLite.

    Это позволяет не зависеть от того,
    что именно возвращает create_training()
    в database.py.
    """

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT id
            FROM trainings
            WHERE training_date = ?
              AND start_time = ?
              AND end_time = ?
            LIMIT 1
            """,
            (
                training_date.isoformat(),
                template["start_time"],
                template["end_time"],
            ),
        )

        existing = cursor.fetchone()

        if existing:
            return False

        cursor.execute(
            """
            SELECT COALESCE(
                MAX(training_number),
                0
            ) + 1
            FROM trainings
            """
        )

        training_number_value = (
            cursor.fetchone()[0]
        )

        cursor.execute(
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
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            )
            """,
            (
                training_number_value,
                training_date.isoformat(),
                WEEKDAYS[
                    training_date.weekday()
                ],
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
                template["location"],
                "active",
                None,
            ),
        )

        connection.commit()

        return True

    except Exception:
        connection.rollback()

        logger.exception(
            "Failed to create training %s %s",
            training_date,
            template.get("start_time"),
        )

        raise

    finally:
        connection.close()


def generate_default_trainings(
    weeks=6,
):
    """
    Создаёт конкретные тренировки на weeks
    недель вперёд.

    Важно:
    повторный запуск не создаёт дубликаты.
    """

    today = today_local()

    end_date = (
        today
        + timedelta(days=weeks * 7)
    )

    created = 0

    current_date = today

    while current_date <= end_date:

        for template in DEFAULT_TEMPLATES:

            if (
                current_date.weekday()
                != template["weekday"]
            ):
                continue

            try:
                was_created = (
                    create_training_directly(
                        template,
                        current_date,
                    )
                )

                if was_created:
                    created += 1

            except Exception:
                logger.exception(
                    "Generation error "
                    "for %s",
                    current_date,
                )

        current_date += timedelta(
            days=1
        )

    logger.info(
        "Training generation complete. "
        "Created: %s",
        created,
    )

    return created


def ensure_schedule():
    """
    Главная функция восстановления расписания.

    После init_db():
    1. пытаемся восстановить шаблоны;
    2. создаём конкретные тренировки;
    3. повторно ничего не дублируем.
    """

    logger.info(
        "Checking training schedule..."
    )

    try:
        ensure_default_templates()

    except Exception:
        logger.exception(
            "Template initialization failed"
        )

    try:
        created = generate_default_trainings(
            weeks=6
        )

        logger.info(
            "Schedule check finished. "
            "Created %s new trainings.",
            created,
        )

    except Exception:
        logger.exception(
            "Training generation failed"
        )


# ============================================================
# ADMIN MENU
# ============================================================

def show_admin_menu(user_id):
    if user_id not in ADMINS:
        show_main_menu(user_id)
        return

    clear_state(user_id)

    send_message(
        user_id,
        "⚙️ АДМИН-ПАНЕЛЬ\n\n"
        "Выберите действие:",
        admin_menu(),
    )


# ============================================================
# ADMIN SCHEDULE
# ============================================================

def admin_show_schedule(user_id):
    if user_id not in ADMINS:
        return

    logger.info(
        "ADMIN %s opened schedule",
        user_id,
    )

    today = today_local()

    end_date = (
        today
        + timedelta(days=14)
    )

    trainings = admin_db_trainings(
        today.isoformat(),
        end_date.isoformat(),
    )

    trainings = list(
        trainings or []
    )

    if not trainings:
        send_message(
            user_id,
            "📅 На ближайшие 14 дней "
            "тренировок нет.",
            admin_back_keyboard(),
        )
        return

    buttons = []

    for training in trainings:
        label = (
            f"№{training_number(training)} "
            f"{format_short_date(training_date_value(training))} "
            f"{row_value(training, 'start_time', '')}"
        )

        buttons.append(
            [
                button(
                    label[:40],
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
        "admin_schedule_select",
        {},
    )

    send_message(
        user_id,
        "📅 РАСПИСАНИЕ\n\n"
        "Выберите тренировку:",
        {
            "one_time": False,
            "buttons": buttons,
        },
    )


def admin_show_training(
    user_id,
    training,
):
    if user_id not in ADMINS:
        return

    training_id = row_value(
        training,
        "id",
    )

    count = get_training_participant_count(
        training_id
    )

    text = format_training(
        training
    )

    text += (
        f"\n\n👥 Участников: "
        f"{count}/"
        f"{training_capacity(training)}"
    )

    buttons = [
        [
            button(
                "👥 Посмотреть участников",
                "primary",
            )
        ],
        [
            button(
                "📋 Посещаемость",
                "secondary",
            )
        ],
        [
            button(
                "⬅️ Назад",
                "secondary",
            )
        ],
    ]

    set_state(
        user_id,
        "admin_training_details",
        {
            "training_id": training_id,
        },
    )

    send_message(
        user_id,
        text,
        {
            "one_time": False,
            "buttons": buttons,
        },
    )


# ============================================================
# ADMIN PARTICIPANTS
# ============================================================

def admin_show_participants(
    user_id,
    training_id,
):
    if user_id not in ADMINS:
        return

    logger.info(
        "ADMIN %s requested participants "
        "for training %s",
        user_id,
        training_id,
    )

    training = admin_db_training(
        training_id
    )

    if not training:
        send_message(
            user_id,
            "❌ Тренировка не найдена.",
            admin_back_keyboard(),
        )
        return

    try:
        registrations = get_registrations(
            training_id
        )
    except Exception:
        logger.exception(
            "Failed to get registrations "
            "for training %s",
            training_id,
        )
        registrations = []

    registrations = list(
        registrations or []
    )

    text = (
        f"👥 УЧАСТНИКИ ТРЕНИРОВКИ №"
        f"{training_number(training)}\n\n"
        f"📅 "
        f"{format_date(training_date_value(training))}\n"
        f"⏰ "
        f"{row_value(training, 'start_time', '')}–"
        f"{row_value(training, 'end_time', '')}\n\n"
    )

    if not registrations:
        text += (
            "Пока никто не записан."
        )

    else:
        for index, registration in enumerate(
            registrations,
            start=1,
        ):
            first_name = row_value(
                registration,
                "first_name",
                "",
            )

            last_name = row_value(
                registration,
                "last_name",
                "",
            )

            vk_id = row_value(
                registration,
                "vk_id",
                row_value(
                    registration,
                    "user_id",
                    "",
                ),
            )

            name = (
                f"{first_name} "
                f"{last_name}"
            ).strip()

            if not name:
                name = (
                    f"Пользователь {vk_id}"
                )

            text += (
                f"{index}. {name}"
            )

            if vk_id:
                text += (
                    f" — ID {vk_id}"
                )

            text += "\n"

    buttons = [
        [
            button(
                "📋 Посещаемость",
                "secondary",
            )
        ],
        [
            button(
                "⬅️ К тренировке",
                "secondary",
            )
        ],
        [
            button(
                "⚙️ Админ-панель",
                "secondary",
            )
        ],
    ]

    set_state(
        user_id,
        "admin_participants",
        {
            "training_id": training_id,
        },
    )

    send_message(
        user_id,
        text,
        {
            "one_time": False,
            "buttons": buttons,
        },
    )


# ============================================================
# ADMIN ATTENDANCE
# ============================================================

def admin_show_attendance(
    user_id,
    training_id,
):
    if user_id not in ADMINS:
        return

    training = admin_db_training(
        training_id
    )

    if not training:
        send_message(
            user_id,
            "❌ Тренировка не найдена.",
            admin_back_keyboard(),
        )
        return

    try:
        registrations = get_registrations(
            training_id
        )
    except Exception:
        registrations = []

    registrations = list(
        registrations or []
    )

    try:
        attendance = (
            get_training_attendance(
                training_id
            )
        )
    except Exception:
        attendance = []

    attendance = list(
        attendance or []
    )

    attendance_map = {}

    for item in attendance:
        registration_id = row_value(
            item,
            "registration_id",
        )

        status = row_value(
            item,
            "status",
            "absent",
        )

        attendance_map[
            registration_id
        ] = status

    text = (
        "📋 ПОСЕЩАЕМОСТЬ\n\n"
        f"🏐 Тренировка №"
        f"{training_number(training)}\n"
        f"📅 "
        f"{format_date(training_date_value(training))}\n\n"
    )

    if not registrations:
        text += "Участников нет."

    else:
        for index, registration in enumerate(
            registrations,
            start=1,
        ):
            registration_id = row_value(
                registration,
                "id",
            )

            first_name = row_value(
                registration,
                "first_name",
                "",
            )

            last_name = row_value(
                registration,
                "last_name",
                "",
            )

            name = (
                f"{first_name} "
                f"{last_name}"
            ).strip()

            if not name:
                name = "Участник"

            status = attendance_map.get(
                registration_id,
                "not_marked",
            )

            if status == "present":
                mark = "✅"
            elif status == "absent":
                mark = "❌"
            else:
                mark = "⚪"

            text += (
                f"{index}. {mark} {name}\n"
            )

    send_message(
        user_id,
        text,
        admin_back_keyboard(),
    )


# ============================================================
# ADMIN ADD TRAINING
# ============================================================

def admin_start_add_training(user_id):
    if user_id not in ADMINS:
        return

    set_state(
        user_id,
        "admin_add_date",
        {},
    )

    send_message(
        user_id,
        "➕ ДОБАВЛЕНИЕ ТРЕНИРОВКИ\n\n"
        "Введите дату в формате:\n"
        "ДД.ММ.ГГГГ\n\n"
        "Например: 05.10.2026",
        admin_back_keyboard(),
    )


def admin_save_training(
    user_id,
    data,
):
    try:
        training_date = datetime.strptime(
            data["date"],
            "%d.%m.%Y",
        ).date()

        start_time = data["start_time"]
        end_time = data["end_time"]

        datetime.strptime(
            start_time,
            "%H:%M",
        )

        datetime.strptime(
            end_time,
            "%H:%M",
        )

        training_data = {
            "training_date":
                training_date.isoformat(),

            "weekday":
                WEEKDAYS[
                    training_date.weekday()
                ],

            "start_time":
                start_time,

            "end_time":
                end_time,

            "title":
                data["title"],

            "category":
                data["category"],

            "age_group":
                data["age_group"],

            "level":
                data["level"],

            "format":
                data["format"],

            "coach":
                data["coach"],

            "capacity":
                int(data["capacity"]),

            "price":
                int(data["price"]),

            "location":
                data.get(
                    "location",
                    "СК «Арена», "
                    "ул. Молодогвардейцев, 7",
                ),
        }

        training_id = admin_create_training(
            training_data
        )

        add_admin_log(
            user_id,
            "training_create",
            "training",
            training_id,
            f"Training created: "
            f"{training_data}",
        )

        training = admin_db_training(
            training_id
        )

        send_message(
            user_id,
            "✅ Тренировка создана!\n\n"
            + format_training(training),
            admin_menu(),
        )

    except Exception as error:
        logger.exception(
            "ADMIN CREATE TRAINING ERROR"
        )

        send_message(
            user_id,
            "❌ Не удалось создать "
            "тренировку.\n\n"
            f"Ошибка: {error}",
            admin_menu(),
        )


# ============================================================
# ADMIN TEMPLATES
# ============================================================

def admin_show_templates(user_id):
    if user_id not in ADMINS:
        return

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT *
            FROM training_templates
            ORDER BY weekday ASC,
                     start_time ASC
            """
        )

        templates = cursor.fetchall()

    finally:
        connection.close()

    templates = list(
        templates or []
    )

    if not templates:
        send_message(
            user_id,
            "🧩 Шаблонов тренировок "
            "пока нет.",
            admin_back_keyboard(),
        )
        return

    text = (
        "🧩 ШАБЛОНЫ ТРЕНИРОВОК\n\n"
    )

    for template in templates:
        text += (
            f"#{row_value(template, 'id')} "
            f"{row_value(template, 'weekday', '')} "
            f"{row_value(template, 'start_time', '')}–"
            f"{row_value(template, 'end_time', '')}\n"
            f"{row_value(template, 'title', '')}\n"
            f"Категория: "
            f"{row_value(template, 'category', '')}\n"
            f"Тренер: "
            f"{row_value(template, 'coach', '')}\n\n"
        )

    send_message(
        user_id,
        text,
        admin_back_keyboard(),
    )


# ============================================================
# QUESTIONS / INDIVIDUAL
# ============================================================

def contact_admins(
    user_id,
    subject,
):
    set_state(
        user_id,
        "contact_message",
        {
            "subject": subject,
        },
    )

    send_message(
        user_id,
        "✍️ Напишите сообщение "
        "одним сообщением.\n\n"
        "Мы передадим его администраторам.",
        back_keyboard(user_id),
    )


def send_question_to_admins(
    user_id,
    subject,
    message,
):
    user = get_user(
        user_id
    )

    first_name = row_value(
        user,
        "first_name",
        "",
    )

    last_name = row_value(
        user,
        "last_name",
        "",
    )

    user_name = (
        f"{first_name} "
        f"{last_name}"
    ).strip()

    if not user_name:
        user_name = (
            f"VK ID {user_id}"
        )

    admin_text = (
        "📩 НОВОЕ СООБЩЕНИЕ\n\n"
        f"Тема: {subject}\n"
        f"От: {user_name}\n"
        f"VK ID: {user_id}\n\n"
        f"{message}"
    )

    for admin_id in ADMINS:
        send_message(
            admin_id,
            admin_text,
        )

    send_message(
        user_id,
        "✅ Сообщение отправлено "
        "администраторам.\n\n"
        "Мы свяжемся с вами.",
        main_menu(user_id),
    )


# ============================================================
# DATE PARSING
# ============================================================

def parse_short_date_button(text):
    parts = text.split(",")

    if len(parts) != 2:
        raise ValueError

    value = parts[1].strip()

    day, month = value.split(".")

    year = today_local().year

    result = date(
        year,
        int(month),
        int(day),
    )

    if (
        result
        < today_local()
        - timedelta(days=1)
    ):
        result = date(
            year + 1,
            int(month),
            int(day),
        )

    return result


def find_training_from_button(text):
    if not text.startswith("№"):
        return None

    try:
        number_part = (
            text.split()[0]
        )

        number = int(
            number_part.replace(
                "№",
                "",
            )
        )

    except Exception:
        return None

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT *
            FROM trainings
            WHERE training_number = ?
            LIMIT 1
            """,
            (number,),
        )

        return cursor.fetchone()

    finally:
        connection.close()


# ============================================================
# ADMIN PARTICIPANTS LIST
# ============================================================

def admin_show_participants_list(
    user_id,
):
    if user_id not in ADMINS:
        return

    logger.info(
        "ADMIN %s opened participants list",
        user_id,
    )

    today = today_local()

    end_date = (
        today
        + timedelta(days=14)
    )

    trainings = admin_db_trainings(
        today.isoformat(),
        end_date.isoformat(),
    )

    trainings = list(
        trainings or []
    )

    if not trainings:
        send_message(
            user_id,
            "👥 На ближайшие 14 дней "
            "тренировок нет.",
            admin_back_keyboard(),
        )
        return

    buttons = []

    for training in trainings:
        count = (
            get_training_participant_count(
                row_value(
                    training,
                    "id",
                )
            )
        )

        label = (
            f"№{training_number(training)} "
            f"{format_short_date(training_date_value(training))} "
            f"{row_value(training, 'start_time', '')} "
            f"({count}/"
            f"{training_capacity(training)})"
        )

        buttons.append(
            [
                button(
                    label[:40],
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
        "admin_participants_select",
        {},
    )

    send_message(
        user_id,
        "👥 УЧАСТНИКИ ТРЕНИРОВОК\n\n"
        "Выберите тренировку:",
        {
            "one_time": False,
            "buttons": buttons,
        },
    )


# ============================================================
# ADMIN EXTRA STATE
# ============================================================

def handle_admin_extra_state(
    user_id,
    text,
    state,
    state_data,
):
    if user_id not in ADMINS:
        return False

    if state == "admin_participants_select":

        training = (
            find_training_from_button(
                text
            )
        )

        if training:
            admin_show_participants(
                user_id,
                row_value(
                    training,
                    "id",
                ),
            )

        return True

    return False


# ============================================================
# EVENT ROUTER
# ============================================================

def handle_text(
    user_id,
    text,
):
    text = text.strip()

    logger.info(
        "MESSAGE user=%s text=%r",
        user_id,
        text,
    )

    if is_user_blocked(user_id):
        send_message(
            user_id,
            "❌ Доступ к боту ограничен.",
        )
        return

    ensure_user(user_id)

    # --------------------------------------------------------
    # GLOBAL BUTTONS
    # --------------------------------------------------------

    if text == "🏠 Главное меню":
        show_main_menu(user_id)
        return

    if text == "⬅️ Назад":
        state = get_state(
            user_id
        )["state"]

        if (
            state
            and state.startswith("admin_")
        ):
            show_admin_menu(user_id)

        else:
            show_main_menu(user_id)

        return

    # --------------------------------------------------------
    # START
    # --------------------------------------------------------

    if text in (
        "Привет",
        "Начать",
        "/start",
        "start",
    ):
        show_main_menu(user_id)
        return

    # --------------------------------------------------------
    # MAIN MENU
    # --------------------------------------------------------

    if text == "🏐 Записаться":
        show_booking_categories(
            user_id
        )
        return

    if text == "📅 Расписание":
        show_schedule_categories(
            user_id
        )
        return

    if text == "👤 Мои тренировки":
        show_my_trainings(
            user_id
        )
        return

    if text == "💰 Цены":
        show_prices(user_id)
        return

    if text == "📍 Где тренируемся":
        show_locations(user_id)
        return

    if text == "🎯 Индивидуальная тренировка":
        contact_admins(
            user_id,
            "Индивидуальная тренировка",
        )
        return

    if text == "❓ Задать вопрос":
        contact_admins(
            user_id,
            "Вопрос",
        )
        return

    # --------------------------------------------------------
    # ADMIN ENTRY
    # --------------------------------------------------------

    if text == "⚙️ Админ-панель":
        if user_id in ADMINS:
            show_admin_menu(user_id)
        else:
            show_main_menu(user_id)

        return

    # --------------------------------------------------------
    # ADMIN MENU
    # --------------------------------------------------------

    if user_id in ADMINS:

        if text == "📅 Расписание":
            admin_show_schedule(
                user_id
            )
            return

        if text == "👥 Участники тренировок":
            logger.info(
                "ADMIN PARTICIPANTS BUTTON "
                "user=%s",
                user_id,
            )

            admin_show_participants_list(
                user_id
            )
            return

        if text == "➕ Добавить тренировку":
            admin_start_add_training(
                user_id
            )
            return

        if text == "🧩 Шаблоны":
            admin_show_templates(
                user_id
            )
            return

        if text == "👤 Режим пользователя":
            show_main_menu(user_id)
            return

    # --------------------------------------------------------
    # STATE
    # --------------------------------------------------------

    state_info = get_state(
        user_id
    )

    state = state_info.get(
        "state"
    )

    state_data = state_info.get(
        "data",
        {},
    )

    # --------------------------------------------------------
    # ADMIN EXTRA STATE
    # --------------------------------------------------------

    if handle_admin_extra_state(
        user_id,
        text,
        state,
        state_data,
    ):
        return

    # --------------------------------------------------------
    # BOOKING CATEGORY
    # --------------------------------------------------------

    if state == "booking_category":

        if text == "👧 Дети":
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

        if text == "🏠 Все тренировки":
            show_booking_dates(
                user_id,
                "all",
            )
            return

    # --------------------------------------------------------
    # BOOKING DATE
    # --------------------------------------------------------

    if state == "booking_date":

        try:
            selected_date = (
                parse_short_date_button(
                    text
                )
            )

            show_booking_trainings(
                user_id,
                state_data.get(
                    "category"
                ),
                selected_date,
            )

            return

        except Exception:
            pass

    # --------------------------------------------------------
    # BOOKING TRAINING
    # --------------------------------------------------------

    if state == "booking_training":

        training = (
            find_training_from_button(
                text
            )
        )

        if training:
            show_training_for_booking(
                user_id,
                training,
            )
            return

    # --------------------------------------------------------
    # TRAINING DETAILS
    # --------------------------------------------------------

    if state == "training_details":

        training_id = state_data.get(
            "training_id"
        )

        if text == "✅ Записаться":
            register_user_for_training(
                user_id,
                training_id,
            )
            return

        if (
            text
            == "⏳ Встать в лист ожидания"
        ):
            try:
                add_to_waitlist(
                    training_id,
                    user_id,
                )

                send_message(
                    user_id,
                    "⏳ Вы добавлены "
                    "в лист ожидания.",
                    main_menu(user_id),
                )

            except Exception as error:
                send_message(
                    user_id,
                    f"❌ Ошибка: {error}",
                    main_menu(user_id),
                )

            return

        if text == "❌ Отменить запись":
            cancel_user_registration(
                user_id,
                training_id,
            )
            return

    # --------------------------------------------------------
    # MY TRAININGS
    # --------------------------------------------------------

    if state == "my_training_select":

        training = (
            find_training_from_button(
                text
            )
        )

        if training:
            training_id = row_value(
                training,
                "id",
            )

            registration = (
                get_registration(
                    training_id,
                    user_id,
                )
            )

            if registration:
                send_message(
                    user_id,
                    format_training(
                        training
                    ),
                    {
                        "one_time": False,
                        "buttons": [
                            [
                                button(
                                    "❌ Отменить запись",
                                    "negative",
                                )
                            ],
                            [
                                button(
                                    "🏠 Главное меню",
                                    "secondary",
                                )
                            ],
                        ],
                    },
                )

                set_state(
                    user_id,
                    "my_training_details",
                    {
                        "training_id":
                            training_id,
                    },
                )

            return

    if state == "my_training_details":

        training_id = state_data.get(
            "training_id"
        )

        if text == "❌ Отменить запись":
            cancel_user_registration(
                user_id,
                training_id,
            )
            return

    # --------------------------------------------------------
    # SCHEDULE CATEGORY
    # --------------------------------------------------------

    if state == "schedule_category":

        if text == "👧 Дети":
            show_schedule(
                user_id,
                "children",
            )
            return

        if text == "🧑 Взрослые":
            show_schedule(
                user_id,
                "adults",
            )
            return

        if text == "🏠 Все тренировки":
            show_schedule(
                user_id,
                None,
            )
            return

    # --------------------------------------------------------
    # SCHEDULE TRAINING
    # --------------------------------------------------------

    if state == "schedule_select_training":

        training = (
            find_training_from_button(
                text
            )
        )

        if training:
            send_message(
                user_id,
                format_training(
                    training
                ),
                back_keyboard(user_id),
            )

            return

    # --------------------------------------------------------
    # CONTACT
    # --------------------------------------------------------

    if state == "contact_message":

        send_question_to_admins(
            user_id,
            state_data.get(
                "subject",
                "Вопрос",
            ),
            text,
        )

        return

    # --------------------------------------------------------
    # ADMIN STATES
    # --------------------------------------------------------

    if user_id in ADMINS:

        if state == "admin_schedule_select":

            training = (
                find_training_from_button(
                    text
                )
            )

            if training:
                admin_show_training(
                    user_id,
                    training,
                )

            return

        if state == "admin_training_details":

            training_id = state_data.get(
                "training_id"
            )

            if (
                text
                == "👥 Посмотреть участников"
            ):
                admin_show_participants(
                    user_id,
                    training_id,
                )
                return

            if text == "📋 Посещаемость":
                admin_show_attendance(
                    user_id,
                    training_id,
                )
                return

        if state == "admin_participants":

            training_id = state_data.get(
                "training_id"
            )

            if text == "📋 Посещаемость":
                admin_show_attendance(
                    user_id,
                    training_id,
                )
                return

            if text == "⬅️ К тренировке":
                training = (
                    admin_db_training(
                        training_id
                    )
                )

                if training:
                    admin_show_training(
                        user_id,
                        training,
                    )

                return

        # ----------------------------------------------------
        # ADD TRAINING
        # ----------------------------------------------------

        if state == "admin_add_date":

            try:
                datetime.strptime(
                    text,
                    "%d.%m.%Y",
                )

                set_state(
                    user_id,
                    "admin_add_start_time",
                    {
                        "date": text,
                    },
                )

                send_message(
                    user_id,
                    "⏰ Введите время начала:\n\n"
                    "Например: 17:00",
                    admin_back_keyboard(),
                )

            except ValueError:
                send_message(
                    user_id,
                    "❌ Неверный формат.\n\n"
                    "Введите дату как "
                    "ДД.ММ.ГГГГ",
                    admin_back_keyboard(),
                )

            return

        if state == "admin_add_start_time":

            try:
                datetime.strptime(
                    text,
                    "%H:%M",
                )

                data = dict(
                    state_data
                )

                data["start_time"] = text

                set_state(
                    user_id,
                    "admin_add_end_time",
                    data,
                )

                send_message(
                    user_id,
                    "⏰ Введите время окончания:\n\n"
                    "Например: 19:00",
                    admin_back_keyboard(),
                )

            except ValueError:
                send_message(
                    user_id,
                    "❌ Неверный формат.\n\n"
                    "Введите время как ЧЧ:ММ",
                    admin_back_keyboard(),
                )

            return

        if state == "admin_add_end_time":

            try:
                datetime.strptime(
                    text,
                    "%H:%M",
                )

                data = dict(
                    state_data
                )

                data["end_time"] = text

                set_state(
                    user_id,
                    "admin_add_title",
                    data,
                )

                send_message(
                    user_id,
                    "📌 Введите название "
                    "тренировки:",
                    admin_back_keyboard(),
                )

            except ValueError:
                send_message(
                    user_id,
                    "❌ Неверный формат времени.",
                    admin_back_keyboard(),
                )

            return

        if state == "admin_add_title":

            data = dict(
                state_data
            )

            data["title"] = text

            set_state(
                user_id,
                "admin_add_category",
                data,
            )

            send_message(
                user_id,
                "👥 Выберите категорию:",
                {
                    "one_time": False,
                    "buttons": [
                        [
                            button(
                                "Дети",
                                "primary",
                            ),
                            button(
                                "Взрослые",
                                "primary",
                            ),
                        ],
                        [
                            button(
                                "Другое",
                                "secondary",
                            ),
                        ],
                    ],
                },
            )

            return

        if state == "admin_add_category":

            data = dict(
                state_data
            )

            data["category"] = text

            set_state(
                user_id,
                "admin_add_age",
                data,
            )

            send_message(
                user_id,
                "🎂 Введите возрастную "
                "группу:\n\n"
                "Например: 11–14\n"
                "или: 18+",
                admin_back_keyboard(),
            )

            return

        if state == "admin_add_age":

            data = dict(
                state_data
            )

            data["age_group"] = text

            set_state(
                user_id,
                "admin_add_level",
                data,
            )

            send_message(
                user_id,
                "📊 Введите уровень:\n\n"
                "Например: Начальный\n"
                "Средний\n"
                "Продвинутый",
                admin_back_keyboard(),
            )

            return

        if state == "admin_add_level":

            data = dict(
                state_data
            )

            data["level"] = text

            set_state(
                user_id,
                "admin_add_format",
                data,
            )

            send_message(
                user_id,
                "🔹 Введите формат:\n\n"
                "Например: Группа",
                admin_back_keyboard(),
            )

            return

        if state == "admin_add_format":

            data = dict(
                state_data
            )

            data["format"] = text

            set_state(
                user_id,
                "admin_add_coach",
                data,
            )

            send_message(
                user_id,
                "🏅 Введите имя тренера:",
                admin_back_keyboard(),
            )

            return

        if state == "admin_add_coach":

            data = dict(
                state_data
            )

            data["coach"] = text

            set_state(
                user_id,
                "admin_add_capacity",
                data,
            )

            send_message(
                user_id,
                "👥 Введите максимальное "
                "количество участников:\n\n"
                "Например: 10",
                admin_back_keyboard(),
            )

            return

        if state == "admin_add_capacity":

            try:
                capacity = int(text)

                if capacity <= 0:
                    raise ValueError

                data = dict(
                    state_data
                )

                data["capacity"] = capacity

                set_state(
                    user_id,
                    "admin_add_price",
                    data,
                )

                send_message(
                    user_id,
                    "💰 Введите стоимость:\n\n"
                    "Например: 600",
                    admin_back_keyboard(),
                )

            except ValueError:
                send_message(
                    user_id,
                    "❌ Введите целое число.",
                    admin_back_keyboard(),
                )

            return

        if state == "admin_add_price":

            try:
                price = int(text)

                if price < 0:
                    raise ValueError

                data = dict(
                    state_data
                )

                data["price"] = price

                set_state(
                    user_id,
                    "admin_add_location",
                    data,
                )

                send_message(
                    user_id,
                    "📍 Введите место "
                    "тренировки:\n\n"
                    "Например:\n"
                    "СК «Арена», "
                    "ул. Молодогвардейцев, 7",
                    admin_back_keyboard(),
                )

            except ValueError:
                send_message(
                    user_id,
                    "❌ Введите целое число.",
                    admin_back_keyboard(),
                )

            return

        if state == "admin_add_location":

            data = dict(
                state_data
            )

            data["location"] = text

            admin_save_training(
                user_id,
                data,
            )

            clear_state(
                user_id
            )

            return

    # --------------------------------------------------------
    # UNKNOWN
    # --------------------------------------------------------

    logger.info(
        "UNHANDLED MESSAGE "
        "user=%s state=%s text=%r",
        user_id,
        state,
        text,
    )

    show_main_menu(user_id)


# ============================================================
# VK CALLBACK
# ============================================================

@app.route(
    "/callback",
    methods=["POST"],
)
def callback():

    try:
        data = (
            request.get_json(
                silent=True
            )
            or {}
        )

        logger.info(
            "VK EVENT: %s",
            data,
        )

        if VK_SECRET_KEY:
            secret = data.get(
                "secret"
            )

            if secret != VK_SECRET_KEY:
                logger.warning(
                    "Invalid secret key"
                )
                return (
                    "invalid secret",
                    403,
                )

        event_type = data.get(
            "type"
        )

        if event_type == "confirmation":
            logger.info(
                "VK confirmation request"
            )

            return (
                VK_CONFIRMATION_TOKEN
                or "",
                200,
            )

        if event_type != "message_new":
            return "ok", 200

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
            logger.warning(
                "No user_id in event"
            )
            return "ok", 200

        logger.info(
            "MESSAGE_NEW user=%s text=%r",
            user_id,
            text,
        )

        handle_text(
            int(user_id),
            str(text),
        )

        return "ok", 200

    except Exception:
        logger.exception(
            "CALLBACK ERROR"
        )

        return "ok", 200


# ============================================================
# HEALTH
# ============================================================

@app.route(
    "/",
    methods=["GET"],
)
def health():
    return (
        "VOLLEY WAVE VK BOT: OK",
        200,
    )


@app.route(
    "/health",
    methods=["GET"],
)
def health_check():
    return {
        "status": "ok",
        "service": "volley-wave-vk-bot",
    }, 200


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
        sorted(ADMINS),
    )

    # --------------------------------------------------------
    # DATABASE
    # --------------------------------------------------------

    init_db()

    logger.info(
        "Database initialized"
    )

    # --------------------------------------------------------
    # TRAINING SCHEDULE
    # --------------------------------------------------------

    ensure_schedule()

    # --------------------------------------------------------
    # FINAL DATABASE CHECK
    # --------------------------------------------------------

    try:
        today = today_local()

        end_date = (
            today
            + timedelta(days=14)
        )

        trainings = admin_db_trainings(
            today.isoformat(),
            end_date.isoformat(),
        )

        logger.info(
            "Upcoming trainings in DB: %s",
            len(trainings),
        )

        if trainings:
            first = trainings[0]

            logger.info(
                "First upcoming training: "
                "№%s %s %s",
                training_number(first),
                row_value(
                    first,
                    "training_date",
                    "",
                ),
                row_value(
                    first,
                    "start_time",
                    "",
                ),
            )

    except Exception:
        logger.exception(
            "Failed final schedule check"
        )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    startup()

    app.run(
        host="0.0.0.0",
        port=PORT,
    )
