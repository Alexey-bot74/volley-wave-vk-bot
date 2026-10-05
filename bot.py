import os
import json
import logging
import re
import threading
import time
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
    search_users,
    admin_add_registration,
    admin_remove_registration,
    get_training_registered_vk_ids,
    get_training_history,
    get_training_registrations_history,
    search_training_history_by_user,
    get_training_by_number,
    complete_training,
    cancel_training_as_not_held,
    mark_completion_check_sent,
    get_training_feedback,
    save_training_feedback,
    get_training_feedback_summary,
    update_training_comment,
    get_trainings_needing_completion_check,
    cancel_training,
    create_notification,
    get_pending_notifications,
    mark_notification_sent,
    mark_notification_failed,
    create_admin_notification_marker,
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


def compact_keyboard_buttons(buttons, max_rows=10, max_buttons_per_row=2):
    """Compact a list of single-button rows into VK-safe rows."""
    flat = []
    for row in buttons or []:
        for item in row or []:
            if item:
                flat.append(item)

    if max_buttons_per_row < 1:
        max_buttons_per_row = 1

    rows = [
        flat[i:i + max_buttons_per_row]
        for i in range(0, len(flat), max_buttons_per_row)
    ]

    if len(rows) <= max_rows:
        return rows

    # Keep navigation buttons at the bottom.
    nav = []
    content = []
    for item in flat:
        label = str(item.get("action", {}).get("label", ""))
        if label.startswith("⬅️") or label.startswith("🏠"):
            nav.append(item)
        else:
            content.append(item)

    content_rows = [
        content[i:i + max_buttons_per_row]
        for i in range(0, len(content), max_buttons_per_row)
    ]
    reserve = 1 if nav else 0
    allowed_content_rows = max(1, max_rows - reserve)
    content_rows = content_rows[:allowed_content_rows]
    if nav:
        content_rows.append(nav[:max_buttons_per_row])
    return content_rows


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
            ],
            [
                button(
                    "➕ Добавить тренировку",
                    "primary",
                ),
            ],
            [
                button(
                    "📚 Архив тренировок",
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


def training_has_passed(training, now=None):
    """True, если время окончания тренировки уже прошло."""
    if now is None:
        now = datetime.now(TIMEZONE)
    training_date = training_date_value(training)
    end_time = row_value(training, "end_time", "23:59") or "23:59"
    try:
        end_dt = datetime.combine(
            training_date,
            datetime.strptime(end_time, "%H:%M").time(),
        ).replace(tzinfo=TIMEZONE)
        return end_dt <= now
    except Exception:
        return False


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


def training_selection_label(training):
    """Короткая подпись кнопки: день, дата, время, формат и уровень."""

    training_date = training_date_value(training)
    start_time = row_value(training, "start_time", "")
    end_time = row_value(training, "end_time", "")
    training_format = row_value(training, "format", "") or ""
    level = row_value(training, "level", "") or ""

    if training_format == "Технический":
        training_format = "Техничка"

    return (
        f"{WEEKDAYS_SHORT[training_date.weekday()]} "
        f"{training_date.strftime('%d.%m')} "
        f"{start_time}–{end_time} | "
        f"{training_format} | {level}"
    )[:40]


def format_training(
    training,
    include_participants=False,
):
    training_id = row_value(training, "id")
    training_date = training_date_value(training)
    start_time = row_value(training, "start_time", "")
    end_time = row_value(training, "end_time", "")
    level = row_value(training, "level", "")
    training_format = row_value(training, "format", "")
    coach = row_value(training, "coach", "")
    price = row_value(training, "price", 0)
    location = row_value(training, "location", "")
    comment = row_value(training, "comment", "") or ""

    if training_format == "Технический":
        training_format = "Техничка"

    text = (
        f"📅 {format_date(training_date)}\n"
        f"⏰ {start_time}–{end_time}\n"
        f"🔹 Формат: {training_format}\n"
        f"📊 Уровень: {level}\n"
        f"🏅 Тренер: {coach}\n"
        f"📍 Место: {location}\n"
        f"💰 Цена: {price}₽"
    )

    if comment.strip():
        text += f"\n📝 Комментарий: {comment.strip()}"

    if include_participants and training_id:
        count = get_training_participant_count(training_id)
        text += f"\n\n👥 Записано: {count}/{training_capacity(training)}"

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
    set_state(user_id, "schedule_category", {})
    send_message(
        user_id,
        "📅 РАСПИСАНИЕ\n\nВыберите категорию:",
        {
            "one_time": False,
            "buttons": [
                [button("👧 Дети", "primary"), button("🧑 Взрослые", "primary")],
                [button("⬅️ Назад", "secondary")],
            ],
        },
    )


def schedule_training_button(training):
    training_date = training_date_value(training)
    start_time = row_value(training, "start_time", "")
    training_format = row_value(training, "format", "") or ""
    level = row_value(training, "level", "") or ""

    if training_format == "Технический":
        training_format = "Техничка"

    return button(
        f"{WEEKDAYS_SHORT[training_date.weekday()]} "
        f"{training_date.strftime('%d.%m')} "
        f"{start_time} | {training_format} | {level}"[:40],
        "primary",
    )


def week_start_for(value=None):
    if value is None:
        value = today_local()
    if isinstance(value, str):
        value = datetime.strptime(value, "%Y-%m-%d").date()
    return value - timedelta(days=value.weekday())


def show_schedule(user_id, category=None, week_start=None):
    today = today_local()
    current_week = week_start_for(today)
    if week_start is None:
        week_start = current_week
    elif isinstance(week_start, str):
        week_start = datetime.strptime(week_start, "%Y-%m-%d").date()

    if week_start < current_week:
        week_start = current_week

    end_date = week_start + timedelta(days=6)
    category_name = "Дети" if category == "children" else "Взрослые"

    try:
        trainings = get_upcoming_trainings(
            from_date=max(week_start, today).isoformat() if week_start == current_week else week_start.isoformat(),
            to_date=end_date.isoformat(),
            category=category_name,
        )
    except Exception:
        logger.exception("Failed to load schedule category=%s", category)
        send_message(user_id, "❌ Не удалось загрузить расписание.\n\nОшибка записана в лог Render.", back_keyboard(user_id))
        return

    trainings = [
        training for training in list(trainings or [])
        if not training_has_passed(training)
    ]
    grouped = {}
    for training in trainings:
        grouped.setdefault(training_date_value(training), []).append(training)

    text = f"📅 РАСПИСАНИЕ — {category_name.upper()}\n\n"
    text += f"📆 Неделя: {week_start.strftime('%d.%m')}–{end_date.strftime('%d.%m')}\n\n"
    buttons = []

    for current_date in sorted(grouped):
        text += f"📌 {format_date(current_date)}\n"
        row = []
        for training in grouped[current_date]:
            start_time = row_value(training, "start_time", "")
            end_time = row_value(training, "end_time", "")
            training_format = row_value(training, "format", "") or ""
            level = row_value(training, "level", "") or ""
            if training_format == "Технический":
                training_format = "Техничка"
            text += f"⏰ {start_time}–{end_time} | {training_format} | {level}\n"
            row.append(schedule_training_button(training))
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        text += "\n"

    if not trainings:
        text += "На этой неделе подходящих тренировок нет.\n\n"

    navigation = []
    if week_start > current_week:
        navigation.append(button("⬅️ Предыдущая неделя", "secondary"))
    if week_start < current_week + timedelta(days=28):
        navigation.append(button("Следующая неделя ➡️", "secondary"))
    if navigation:
        buttons.append(navigation)

    buttons.append([button("⬅️ Назад", "secondary"), button("🏠 Главное меню", "secondary")])
    buttons = compact_keyboard_buttons(buttons, max_rows=10, max_buttons_per_row=2)

    set_state(user_id, "schedule_week", {"category": category, "week_start": week_start.isoformat()})
    send_message(user_id, text.rstrip() + "\n\n📝 Нажмите кнопку тренировки, чтобы увидеть участников и записаться.", {"one_time": False, "buttons": buttons})


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
                        "⬅️ Назад",
                        "secondary",
                    ),
                ],
            ],
        },
    )


def show_booking_week(user_id, category, week_start=None):
    today = today_local()
    current_week = week_start_for(today)
    if week_start is None:
        week_start = current_week
    elif isinstance(week_start, str):
        week_start = datetime.strptime(week_start, "%Y-%m-%d").date()
    if week_start < current_week:
        week_start = current_week

    end_date = week_start + timedelta(days=6)
    category_names = {"children": "Дети", "adults": "Взрослые", "all": "Все"}
    category_name = category_names.get(category, "Все")

    try:
        trainings = get_upcoming_trainings(
            from_date=max(week_start, today).isoformat() if week_start == current_week else week_start.isoformat(),
            to_date=end_date.isoformat(),
            category=None if category == "all" else category_name,
        )
    except Exception:
        logger.exception("Failed to load booking week")
        send_message(user_id, "❌ Не удалось загрузить тренировки.", back_keyboard(user_id))
        return

    trainings = [
        training for training in list(trainings or [])
        if not training_has_passed(training)
    ]
    grouped = {}
    for training in trainings:
        grouped.setdefault(training_date_value(training), []).append(training)

    text = f"🏐 ЗАПИСЬ — {category_name.upper()}\n\n📆 Неделя: {week_start.strftime('%d.%m')}–{end_date.strftime('%d.%m')}\n\n"
    buttons = []
    for current_date in sorted(grouped):
        text += f"📌 {format_date(current_date)}\n"
        row = []
        for training in grouped[current_date]:
            text += f"⏰ {row_value(training, 'start_time', '')}–{row_value(training, 'end_time', '')} | {row_value(training, 'format', '')} | {row_value(training, 'level', '')}\n"
            row.append(button(training_selection_label(training), "primary"))
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        text += "\n"

    if not trainings:
        text += "На этой неделе подходящих тренировок нет.\n\n"

    navigation = []
    if week_start > current_week:
        navigation.append(button("⬅️ Предыдущая неделя", "secondary"))
    if week_start < current_week + timedelta(days=28):
        navigation.append(button("Следующая неделя ➡️", "secondary"))
    if navigation:
        buttons.append(navigation)
    buttons.append([button("⬅️ Назад", "secondary")])

    set_state(user_id, "booking_week", {"category": category, "week_start": week_start.isoformat()})
    send_message(user_id, text.rstrip() + "\n\nВыберите тренировку:", {"one_time": False, "buttons": compact_keyboard_buttons(buttons, max_rows=10, max_buttons_per_row=2)})


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
        label = training_selection_label(
            training
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

    status = row_value(
        training,
        "status",
        "scheduled",
    )

    if status not in ("scheduled", "active"):
        send_message(
            user_id,
            "❌ Эта тренировка недоступна для записи.",
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
            "registered",
        )

        if status != "registered":
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
        label = training_selection_label(
            training
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
                "scheduled",
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
    # ПОНЕДЕЛЬНИК
    {"weekday": 0, "start_time": "09:00", "end_time": "11:00", "title": "Детская тренировка", "category": "Дети", "age_group": "9–14", "level": "Общий", "format": "Тренировка", "coach": "Ксения", "capacity": 10, "price": 600, "location": "СК «Арена», ул. Молодогвардейцев, 7"},
    {"weekday": 0, "start_time": "17:00", "end_time": "19:00", "title": "Детская тренировка", "category": "Дети", "age_group": "11–14", "level": "Общий", "format": "Тренировка", "coach": "Ксения", "capacity": 10, "price": 600, "location": "СК «Арена», ул. Молодогвардейцев, 7"},
    {"weekday": 0, "start_time": "19:00", "end_time": "20:30", "title": "Техничка", "category": "Взрослые", "age_group": "18+", "level": "Общий", "format": "Техничка", "coach": "Ксения", "capacity": 10, "price": 1200, "location": "СК «Арена», ул. Молодогвардейцев, 7"},
    # ВТОРНИК
    {"weekday": 1, "start_time": "09:00", "end_time": "11:00", "title": "Тренировка", "category": "Взрослые", "age_group": "18+", "level": "Общий", "format": "Тренировка", "coach": "Алексей", "capacity": 8, "price": 1200, "location": "СК «Арена», ул. Молодогвардейцев, 7"},
    {"weekday": 1, "start_time": "17:00", "end_time": "18:30", "title": "Детская тренировка", "category": "Дети", "age_group": "11–14", "level": "Общий", "format": "Тренировка", "coach": "Алексей", "capacity": 10, "price": 600, "location": "СК «Арена», ул. Молодогвардейцев, 7"},
    {"weekday": 1, "start_time": "19:30", "end_time": "21:00", "title": "Женская", "category": "Взрослые", "age_group": "18+", "level": "Средний", "format": "Женская", "coach": "Алексей", "capacity": 8, "price": 1200, "location": "СК «Арена», ул. Молодогвардейцев, 7"},
    # СРЕДА
    {"weekday": 2, "start_time": "09:00", "end_time": "11:00", "title": "Детская тренировка", "category": "Дети", "age_group": "9–14", "level": "Общий", "format": "Тренировка", "coach": "Алексей", "capacity": 10, "price": 600, "location": "СК «Арена», ул. Молодогвардейцев, 7"},
    {"weekday": 2, "start_time": "18:00", "end_time": "19:30", "title": "Мужская", "category": "Взрослые", "age_group": "18+", "level": "Продвинутый", "format": "Мужская", "coach": "Алексей", "capacity": 8, "price": 1200, "location": "СК «Арена», ул. Молодогвардейцев, 7"},
    {"weekday": 2, "start_time": "19:30", "end_time": "21:00", "title": "Миксты", "category": "Взрослые", "age_group": "18+", "level": "Средний", "format": "Миксты", "coach": "Алексей", "capacity": 6, "price": 1200, "location": "СК «Арена», ул. Молодогвардейцев, 7"},
    # ЧЕТВЕРГ
    {"weekday": 3, "start_time": "09:00", "end_time": "11:00", "title": "Тренировка", "category": "Взрослые", "age_group": "18+", "level": "Общий", "format": "Тренировка", "coach": "Алексей", "capacity": 8, "price": 1200, "location": "СК «Арена», ул. Молодогвардейцев, 7"},
    {"weekday": 3, "start_time": "17:00", "end_time": "19:00", "title": "Детская тренировка", "category": "Дети", "age_group": "11–14", "level": "Общий", "format": "Тренировка", "coach": "Алексей", "capacity": 10, "price": 600, "location": "СК «Арена», ул. Молодогвардейцев, 7"},
    {"weekday": 3, "start_time": "19:00", "end_time": "20:30", "title": "Тренировка", "category": "Взрослые", "age_group": "18+", "level": "Средний", "format": "Тренировка", "coach": "Алексей", "capacity": 8, "price": 1200, "location": "СК «Арена», ул. Молодогвардейцев, 7"},
    # ПЯТНИЦА
    {"weekday": 4, "start_time": "09:00", "end_time": "11:00", "title": "Детская тренировка", "category": "Дети", "age_group": "9–14", "level": "Общий", "format": "Тренировка", "coach": "Алексей", "capacity": 10, "price": 600, "location": "СК «Арена», ул. Молодогвардейцев, 7"},
    {"weekday": 4, "start_time": "17:00", "end_time": "19:00", "title": "Детская тренировка", "category": "Дети", "age_group": "11–14", "level": "Общий", "format": "Тренировка", "coach": "Алексей", "capacity": 10, "price": 600, "location": "СК «Арена», ул. Молодогвардейцев, 7"},
    {"weekday": 4, "start_time": "19:00", "end_time": "20:30", "title": "Техничка", "category": "Взрослые", "age_group": "18+", "level": "Общий", "format": "Техничка", "coach": "Алексей", "capacity": 10, "price": 1200, "location": "СК «Арена», ул. Молодогвардейцев, 7"},
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
                "Replacing default training templates: %s existing rows",
                count,
            )
            cursor.execute("DELETE FROM training_templates")

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
                "scheduled",
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


def normalize_training_statuses():
    """Приводит старые тренировки со статусом active к scheduled."""

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            UPDATE trainings
            SET status = 'scheduled'
            WHERE status = 'active'
            """
        )

        changed = cursor.rowcount
        connection.commit()

        if changed:
            logger.info(
                "Normalized training statuses: %s",
                changed,
            )

    finally:
        connection.close()


LEGACY_DEFAULT_SLOT_KEYS = {
    (0, "09:00", "11:00"), (0, "17:00", "19:00"), (0, "19:00", "20:30"),
    (1, "09:00", "11:00"), (1, "17:00", "18:30"), (1, "19:30", "21:00"),
    (2, "09:00", "11:00"), (2, "17:00", "18:00"), (2, "18:00", "19:30"), (2, "19:30", "21:00"),
    (3, "09:00", "11:00"), (3, "17:00", "18:00"), (3, "17:00", "19:00"), (3, "19:00", "20:30"),
    (4, "09:00", "11:00"), (4, "17:00", "18:00"), (4, "17:00", "19:00"), (4, "19:00", "20:30"),
}

def sync_future_default_trainings():
    """Обновляет будущие тренировки под новое базовое расписание, не трогая уже записанных клиентов."""
    today = today_local()
    end_date = today + timedelta(days=42)
    expected = {
        (t["weekday"], t["start_time"], t["end_time"]): t
        for t in DEFAULT_TEMPLATES
    }
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM trainings WHERE training_date >= ? AND training_date <= ? AND status = 'scheduled'",
            (today.isoformat(), end_date.isoformat()),
        ).fetchall()
        for row in rows:
            key = (row["weekday"], row["start_time"], row["end_time"])
            if key not in LEGACY_DEFAULT_SLOT_KEYS:
                continue
            template = expected.get(key)
            registered = conn.execute(
                "SELECT COUNT(*) AS c FROM registrations WHERE training_id = ? AND status = 'registered'",
                (row["id"],),
            ).fetchone()["c"]
            if template:
                conn.execute(
                    """UPDATE trainings SET title=?, category=?, age_group=?, level=?, format=?, coach=?, capacity=?, price=?, location=?, updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                    (template["title"], template["category"], template["age_group"], template["level"], template["format"], template["coach"], template["capacity"], template["price"], template["location"], row["id"]),
                )
            elif registered == 0:
                conn.execute("DELETE FROM trainings WHERE id = ?", (row["id"],))
        conn.commit()
    except Exception:
        conn.rollback()
        logger.exception("Failed to sync future default trainings")
        raise
    finally:
        conn.close()


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
        normalize_training_statuses()
    except Exception:
        logger.exception(
            "Training status normalization failed"
        )

    try:
        ensure_default_templates()

    except Exception:
        logger.exception(
            "Template initialization failed"
        )

    try:
        sync_future_default_trainings()
    except Exception:
        logger.exception("Future default schedule sync failed")

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

    set_state(
        user_id,
        "admin_menu",
        {},
    )

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
        + timedelta(days=6)
    )

    try:
        trainings = admin_db_trainings(
            today.isoformat(),
            end_date.isoformat(),
        )
    except Exception as error:
        logger.exception(
            "ADMIN TRAININGS LOAD ERROR"
        )
        send_message(
            user_id,
            "❌ Не удалось загрузить данные тренировок.\n\n"
            "Ошибка записана в лог Render.",
            admin_back_keyboard(),
        )
        return

    trainings = [
        training for training in list(trainings or [])
        if not training_has_passed(training)
    ]

    if not trainings:
        send_message(
            user_id,
            "📅 На ближайшие 7 дней "
            "тренировок нет.",
            admin_back_keyboard(),
        )
        return

    buttons = []

    for training in trainings:
        training_format = row_value(
            training,
            "format",
            "",
        ) or ""
        if training_format == "Технический":
            training_format = "Техничка"

        training_date = training_date_value(training)
        count = get_training_participant_count(
            row_value(training, "id")
        )
        capacity = training_capacity(training)

        label = (
            f"{WEEKDAYS_SHORT[training_date.weekday()]} "
            f"{training_date.strftime('%d.%m')} "
            f"{row_value(training, 'start_time', '')} | "
            f"{training_format} | {count}/{capacity}"
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
    buttons = compact_keyboard_buttons(buttons, max_rows=10, max_buttons_per_row=2)

    # Подробная информация выводится отдельным текстом над кнопками.
    # Сами кнопки не меняем.
    schedule_text = "📅 РАСПИСАНИЕ\n\n"

    current_date = None
    for training in trainings:
        training_date = training_date_value(training)

        if training_date != current_date:
            if current_date is not None:
                schedule_text += "\n"
            schedule_text += (
                f"📌 {format_date(training_date)}\n"
            )
            current_date = training_date

        training_format = row_value(
            training,
            "format",
            "",
        ) or ""
        if training_format == "Технический":
            training_format = "Техничка"

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
        level = row_value(
            training,
            "level",
            "",
        )
        coach = row_value(
            training,
            "coach",
            "",
        )
        location = row_value(
            training,
            "location",
            "",
        )
        price = row_value(
            training,
            "price",
            0,
        )

        count = get_training_participant_count(
            row_value(training, "id")
        )
        capacity = training_capacity(training)

        schedule_text += (
            f"⏰ {start_time}–{end_time}\n"
            f"🔹 Формат: {training_format}\n"
            f"📊 Уровень: {level}\n"
            f"🏅 Тренер: {coach}\n"
            f"📍 Место: {location}\n"
            f"💰 Цена: {price}₽\n"
            f"👥 Записано: {count}/{capacity}\n\n"
        )

    schedule_text += "\nВыберите тренировку:"

    set_state(
        user_id,
        "admin_schedule_select",
        {},
    )

    send_message(
        user_id,
        schedule_text,
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

    training_comment = row_value(training, "comment", "") or ""
    if training_comment.strip():
        text += f"\n\n📝 Комментарий администратора:\n{training_comment.strip()}"

    text += (
        f"\n\n👥 УЧАСТНИКИ "
        f"({count}/{training_capacity(training)})"
    )

    try:
        registrations = list(
            get_registrations(training_id) or []
        )
    except Exception:
        registrations = []

    if not registrations:
        text += "\nПока никто не записан."
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
                f"{first_name} {last_name}"
            ).strip()

            if not name:
                name = "Участник"

            text += f"\n{index}. {name}"

    buttons = [
        [
            button(
                "✏️ Редактировать",
                "primary",
            ),
            button(
                "🗑 Удалить тренировку",
                "negative",
            ),
        ],
        [
            button(
                "📝 Комментарий",
                "secondary",
            ),
        ],
        [
            button(
                "➕ Добавить участника",
                "positive",
            ),
            button(
                "➖ Удалить участника",
                "negative",
            ),
        ],
        [
            button(
                "❌ Отменить тренировку",
                "negative",
            ),
            button(
                "📋 Посещаемость",
                "secondary",
            ),
        ],
        [
            button(
                "✅ Тренировка прошла",
                "positive",
            ),
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


def admin_update_training(training_id, data):
    connection = get_connection()

    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            UPDATE trainings
            SET training_date = ?,
                weekday = ?,
                start_time = ?,
                end_time = ?,
                title = ?,
                level = ?,
                format = ?,
                coach = ?,
                price = ?,
                location = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                data["training_date"],
                data["weekday"],
                data["start_time"],
                data["end_time"],
                data["title"],
                data["level"],
                data["format"],
                data["coach"],
                data["price"],
                data["location"],
                training_id,
            ),
        )
        if cursor.rowcount == 0:
            raise ValueError("Тренировка не найдена")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def admin_delete_training(training_id):
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            "DELETE FROM trainings WHERE id = ?",
            (training_id,),
        )
        if cursor.rowcount == 0:
            raise ValueError("Тренировка не найдена")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


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

def admin_finish_training(user_id, training_id):
    if user_id not in ADMINS:
        return

    training = admin_db_training(training_id)
    if not training:
        send_message(user_id, "❌ Тренировка не найдена.", admin_back_keyboard())
        return

    if row_value(training, "status", "") == "completed":
        admin_show_attendance(user_id, training_id)
        return

    if row_value(training, "status", "") == "cancelled":
        send_message(user_id, "❌ Эта тренировка уже отменена.", admin_back_keyboard())
        return

    if complete_training(training_id, user_id):
        add_admin_log(
            user_id,
            "training_completed",
            "training",
            training_id,
            "Training marked as completed; registered participants marked present",
        )
        send_training_feedback_requests(training_id)
        admin_show_attendance(user_id, training_id)
    else:
        send_message(user_id, "❌ Не удалось отметить тренировку.", admin_back_keyboard())


def admin_mark_training_not_held(user_id, training_id):
    if user_id not in ADMINS:
        return

    training = admin_db_training(training_id)
    if not training:
        send_message(user_id, "❌ Тренировка не найдена.", admin_back_keyboard())
        return

    if cancel_training_as_not_held(training_id):
        add_admin_log(
            user_id,
            "training_not_held",
            "training",
            training_id,
            "Training marked as not held",
        )
        send_message(
            user_id,
            "❌ Тренировка отмечена как не состоявшаяся.\n\nПосещаемость не выставлена.",
            admin_back_keyboard(),
        )
    else:
        send_message(user_id, "❌ Не удалось изменить статус тренировки.", admin_back_keyboard())


def admin_mark_attendance_from_button(user_id, training_id, registration_id, status):
    if user_id not in ADMINS:
        return

    training = admin_db_training(training_id)
    if not training:
        send_message(user_id, "❌ Тренировка не найдена.", admin_back_keyboard())
        return

    mark_attendance(registration_id, status, marked_by=user_id)
    admin_show_attendance(user_id, training_id)


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

    feedback_summary = get_training_feedback_summary(training_id)

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

    buttons = []
    for index, registration in enumerate(registrations, start=1):
        first_name = row_value(registration, "first_name", "")
        last_name = row_value(registration, "last_name", "")
        name = (f"{first_name} {last_name}").strip() or "Участник"
        short_name = name[:28]
        registration_id = row_value(registration, "id")
        status = attendance_map.get(registration_id, "not_marked")

        if status == "present":
            label = f"❌ {index}. {short_name}"
        else:
            label = f"✅ {index}. {short_name}"

        buttons.append([button(label, "secondary")])

    buttons.append([button("⬅️ К тренировке", "secondary")])
    buttons.append([button("⚙️ Админ-панель", "secondary")])

    set_state(
        user_id,
        "admin_attendance",
        {"training_id": training_id},
    )

    send_message(
        user_id,
        text + "\n\nНажмите на участника, чтобы переключить отметку.",
        {"one_time": False, "buttons": buttons},
    )


def admin_start_add_participant(user_id, training_id):
    if user_id not in ADMINS:
        return

    training = admin_db_training(training_id)
    if not training:
        send_message(user_id, "❌ Тренировка не найдена.", admin_back_keyboard())
        return

    if training_is_full(training):
        send_message(
            user_id,
            "❌ Тренировка уже заполнена. Сначала освободите место.",
            admin_back_keyboard(),
        )
        return

    set_state(
        user_id,
        "admin_add_participant_search",
        {"training_id": training_id},
    )
    send_message(
        user_id,
        "➕ ДОБАВЛЕНИЕ УЧАСТНИКА\n\n"
        "Введите имя, фамилию или VK ID пользователя.",
        admin_back_keyboard(),
    )


def admin_start_remove_participant(user_id, training_id):
    if user_id not in ADMINS:
        return

    training = admin_db_training(training_id)
    if not training:
        send_message(user_id, "❌ Тренировка не найдена.", admin_back_keyboard())
        return

    registrations = list(get_registrations(training_id) or [])
    if not registrations:
        send_message(
            user_id,
            "На тренировке пока нет участников.",
            admin_back_keyboard(),
        )
        return

    buttons = []
    for registration in registrations:
        first_name = row_value(registration, "first_name", "") or ""
        last_name = row_value(registration, "last_name", "") or ""
        name = f"{first_name} {last_name}".strip() or "Участник"
        vk_id = row_value(registration, "vk_id", "")
        buttons.append([button(f"➖ {name} | {vk_id}"[:40], "negative")])

    buttons.append([button("⬅️ К тренировке", "secondary")])
    buttons = compact_keyboard_buttons(buttons, max_rows=10, max_buttons_per_row=1)
    set_state(user_id, "admin_remove_participant", {"training_id": training_id})
    send_message(
        user_id,
        "➖ УДАЛЕНИЕ УЧАСТНИКА\n\nВыберите участника:",
        {"one_time": False, "buttons": buttons},
    )


def admin_search_participants(user_id, training_id, search_text, mode="add"):
    users = list(search_users(search_text, limit=20) or [])
    registered_ids = {row_value(x, "vk_id") for x in (get_registrations(training_id) or [])}

    buttons = []
    mapping = {}
    number = 1
    for user in users:
        vk_id = row_value(user, "vk_id")
        first_name = row_value(user, "first_name", "") or ""
        last_name = row_value(user, "last_name", "") or ""
        name = f"{first_name} {last_name}".strip() or "Без имени"
        if mode == "add" and vk_id in registered_ids:
            continue
        if mode == "add":
            label = f"➕ {name}"[:40]
            buttons.append([button(label, "positive")])
            mapping[label] = vk_id
            number += 1

    buttons.append([button("⬅️ К тренировке", "secondary")])
    buttons = compact_keyboard_buttons(buttons, max_rows=10, max_buttons_per_row=1)

    if mode == "add":
        if not users or len(mapping) == 0:
            send_message(user_id, "❌ Пользователь не найден.\n\nПопробуйте другое написание имени или фамилии.", admin_back_keyboard())
            set_state(user_id, "admin_add_participant_search", {"training_id": training_id})
            return
        set_state(user_id, "admin_add_participant_select", {"training_id": training_id, "user_mapping": mapping})
        send_message(user_id, "👤 Найдены пользователи. Выберите нужного:", {"one_time": False, "buttons": buttons})


def admin_add_participant(user_id, training_id, vk_id):
    try:
        training = admin_db_training(training_id)
        if not training:
            raise ValueError("Тренировка не найдена")
        if training_is_full(training):
            raise ValueError("Тренировка заполнена")
        user = get_user(vk_id)
        if not user:
            raise ValueError("Пользователь не найден")
        admin_add_registration(training_id, vk_id)
        add_admin_log(user_id, "admin_registration_add", "training", training_id, f"Added VK {vk_id}")
        send_message(
            user_id,
            "✅ Участник добавлен.\n\n" + format_training(admin_db_training(training_id), include_participants=True),
            admin_back_keyboard(),
        )
        send_message(
            vk_id,
            "✅ Администратор записал вас на тренировку.\n\n" + format_training(admin_db_training(training_id)),
            main_menu(vk_id),
        )
    except Exception as error:
        logger.exception("ADMIN ADD PARTICIPANT ERROR")
        send_message(user_id, f"❌ Не удалось добавить участника.\n\nОшибка: {error}", admin_back_keyboard())


def admin_remove_participant(user_id, training_id, vk_id):
    try:
        removed = admin_remove_registration(training_id, vk_id)
        if not removed:
            raise ValueError("Участник не найден в записи")
        add_admin_log(user_id, "admin_registration_remove", "training", training_id, f"Removed VK {vk_id}")
        training = admin_db_training(training_id)
        send_message(
            user_id,
            "✅ Участник удалён.\n\n" + format_training(training, include_participants=True),
            admin_back_keyboard(),
        )
        try:
            send_message(
                vk_id,
                "❌ Администратор отменил вашу запись на тренировку.\n\n" + format_training(training),
                main_menu(vk_id),
            )
        except Exception:
            logger.exception("Failed to notify removed participant %s", vk_id)
    except Exception as error:
        logger.exception("ADMIN REMOVE PARTICIPANT ERROR")
        send_message(user_id, f"❌ Не удалось удалить участника.\n\nОшибка: {error}", admin_back_keyboard())


def admin_start_cancel_training(user_id, training_id):
    if user_id not in ADMINS:
        return
    training = admin_db_training(training_id)
    if not training:
        send_message(user_id, "❌ Тренировка не найдена.", admin_back_keyboard())
        return
    if row_value(training, "status", "") == "cancelled":
        send_message(user_id, "Эта тренировка уже отменена.", admin_back_keyboard())
        return
    set_state(user_id, "admin_cancel_training", {"training_id": training_id})
    count = get_training_participant_count(training_id)
    send_message(
        user_id,
        "❌ ОТМЕНА ТРЕНИРОВКИ\n\n" +
        format_training(training) +
        f"\n\n👥 Записано: {count}/{training_capacity(training)}\n\n"
        "После отмены уведомление получат только записанные участники.\n\n"
        "Отменить тренировку?",
        {"one_time": False, "buttons": [[button("❌ Да, отменить", "negative"), button("⬅️ Назад", "secondary")]]},
    )


def admin_cancel_training_and_notify(user_id, training_id):
    training = admin_db_training(training_id)
    if not training:
        send_message(user_id, "❌ Тренировка не найдена.", admin_back_keyboard())
        return

    recipient_ids = get_training_registered_vk_ids(training_id)
    try:
        cancel_training(training_id)
        add_admin_log(
            user_id,
            "training_cancel",
            "training",
            training_id,
            f"Training cancelled; notified {len(recipient_ids)} registered users",
        )
    except Exception as error:
        logger.exception("ADMIN CANCEL TRAINING ERROR")
        send_message(user_id, f"❌ Не удалось отменить тренировку.\n\nОшибка: {error}", admin_back_keyboard())
        return

    message = (
        "❌ ТРЕНИРОВКА ОТМЕНЕНА\n\n" +
        format_training(training) +
        "\n\nПриносим извинения за неудобства."
    )
    sent = 0
    for vk_id in recipient_ids:
        try:
            result = send_message(vk_id, message, main_menu(vk_id))
            if result and result.get("response") is not None:
                sent += 1
        except Exception:
            logger.exception("Failed cancellation notification to %s", vk_id)

    updated = admin_db_training(training_id)
    send_message(
        user_id,
        "✅ Тренировка отменена.\n\n"
        f"Уведомление отправлено: {sent}/{len(recipient_ids)} записанным участникам.",
        admin_back_keyboard(),
    )
    if updated:
        set_state(user_id, "admin_training_details", {"training_id": training_id})


def admin_show_archive_menu(user_id):
    if user_id not in ADMINS:
        return
    set_state(user_id, "admin_archive_menu", {})
    send_message(
        user_id,
        "📚 АРХИВ ТРЕНИРОВОК\n\nВыберите способ поиска:",
        {"one_time": False, "buttons": [
            [button("📅 По дате", "primary"), button("👤 По участнику", "primary")],
            [button("⬅️ Админ-панель", "secondary")],
        ]},
    )


def admin_archive_by_date(user_id, date_text):
    raw = str(date_text).strip().replace("/", ".")
    parsed = None
    for fmt in ("%d.%m.%Y", "%d.%m.%y", "%d.%m"):
        try:
            parsed = datetime.strptime(raw, fmt).date()
            if fmt == "%d.%m":
                parsed = parsed.replace(year=today_local().year)
            break
        except ValueError:
            pass
    if not parsed:
        send_message(user_id, "❌ Дата должна быть в формате ДД.ММ.ГГГГ или ДД.ММ.", admin_back_keyboard())
        return

    # Для сегодняшней даты дополнительно восстанавливаем отсутствующие
    # стандартные слоты перед чтением архива. Это важно, если бот был
    # перезапущен после изменения базового расписания.
    if parsed >= today_local():
        try:
            generate_default_trainings(weeks=6)
            sync_future_default_trainings()
        except Exception:
            logger.exception("Failed to repair default schedule before archive lookup")

    trainings = list(get_training_history(parsed.isoformat(), parsed.isoformat(), include_future=False) or [])
    if not trainings:
        send_message(user_id, f"📚 На {format_date(parsed)} тренировок в архиве не найдено.", admin_back_keyboard())
        return

    text = f"📚 АРХИВ — {format_date(parsed)}\n\n"
    for training in trainings:
        training_id = row_value(training, "id")
        registrations = list(get_training_registrations_history(training_id) or [])
        count = len([r for r in registrations if row_value(r, "registration_status") == "registered"])
        status = row_value(training, "status", "")
        if status == "scheduled" and training_has_passed(training):
            status_text = "⚠️ требует отметки"
        else:
            status_text = {
                "cancelled": "❌ отменена",
                "completed": "✅ завершена",
                "scheduled": "🕐 запланирована",
            }.get(status, status)
        text += (
            f"⏰ {row_value(training, 'start_time', '')}–{row_value(training, 'end_time', '')} | "
            f"{row_value(training, 'format', '')}\n"
            f"📊 {row_value(training, 'level', '')} | 👥 {count}/{training_capacity(training)} | {status_text}\n"
        )
        if registrations:
            text += "👤 Записанные: "
            names = []
            for registration in registrations:
                first_name = row_value(registration, "first_name", "") or ""
                last_name = row_value(registration, "last_name", "") or ""
                name = f"{first_name} {last_name}".strip() or f"VK {row_value(registration, 'vk_id', '')}"
                reg_status = row_value(registration, "registration_status", "")
                attendance = row_value(registration, "attendance_status", "")
                suffix = ""
                if reg_status != "registered":
                    suffix = " — отменил запись"
                elif attendance == "present":
                    suffix = " — был"
                elif attendance == "absent":
                    suffix = " — не был"
                names.append(f"{name}{suffix}")
            text += "\n".join(f"• {name}" for name in names) + "\n"
        else:
            text += "👤 Записанных нет.\n"
        text += "\n"
    archive_buttons = []
    for training in trainings:
        training_id = row_value(training, "id")
        status = row_value(training, "status", "")
        if status == "scheduled" and training_has_passed(training):
            number = training_number(training)
            archive_buttons.append([
                button(f"✅ Прошла №{number}", "positive"),
                button(f"❌ Не прошла №{number}", "negative"),
            ])

    if archive_buttons:
        archive_buttons.append([button("⬅️ Админ-панель", "secondary")])
        send_message(
            user_id,
            text.rstrip(),
            {"one_time": False, "buttons": archive_buttons},
        )
    else:
        send_message(user_id, text.rstrip(), admin_back_keyboard())


def admin_archive_by_user(user_id, search_text):
    rows = list(search_training_history_by_user(search_text) or [])
    if not rows:
        send_message(user_id, "❌ По этому пользователю записей в архиве не найдено.", admin_back_keyboard())
        return

    first_name = row_value(rows[0], "first_name", "") or ""
    last_name = row_value(rows[0], "last_name", "") or ""
    name = f"{first_name} {last_name}".strip() or str(search_text)
    text = f"📚 АРХИВ УЧАСТНИКА\n\n👤 {name}\n\n"
    for row in rows:
        status = row_value(row, "registration_status", "")
        attendance = row_value(row, "attendance_status", "")
        reg_mark = "записан" if status == "registered" else "отменил запись"
        attendance_mark = {"present": "присутствовал", "absent": "отсутствовал", "unknown": "не отмечен", None: "не отмечен"}.get(attendance, attendance)
        training_status = row_value(row, "status", "")
        if training_status == "cancelled":
            training_mark = "❌ тренировка отменена"
        elif training_status == "completed":
            training_mark = "✅ завершена"
        else:
            training_mark = "🕐 запланирована"
        text += (
            f"📅 {format_date(training_date_value(row))}\n"
            f"⏰ {row_value(row, 'start_time', '')}–{row_value(row, 'end_time', '')} | {row_value(row, 'format', '')}\n"
            f"{training_mark} | {reg_mark} | {attendance_mark}\n\n"
        )
    send_message(user_id, text.rstrip(), admin_back_keyboard())


def admin_start_edit_training(user_id, training_id):
    if user_id not in ADMINS:
        return

    training = admin_db_training(training_id)
    if not training:
        send_message(user_id, "❌ Тренировка не найдена.", admin_back_keyboard())
        return

    set_state(user_id, "admin_edit_training", {"training_id": training_id})
    training_date = training_date_value(training)
    time_line = (
        f"{row_value(training, 'start_time', '')}–"
        f"{row_value(training, 'end_time', '')}"
    )
    message = (
        "✏️ РЕДАКТИРОВАНИЕ ТРЕНИРОВКИ\n\n"
        "Отправьте одним сообщением 7 строк:\n\n"
        f"1. {training_date.strftime('%d.%m.%Y')}\n"
        f"2. {time_line}\n"
        f"3. {row_value(training, 'format', '')}\n"
        f"4. {row_value(training, 'level', '')}\n"
        f"5. {row_value(training, 'price', 0)}\n"
        f"6. {row_value(training, 'coach', '')}\n"
        f"7. {row_value(training, 'location', '')}\n\n"
        "Измените нужные строки и отправьте их снова.\n"
        "Категория и вместимость сохранятся без изменений."
    )
    send_message(user_id, message, admin_back_keyboard())


def admin_confirm_delete_training(user_id, training_id):
    if user_id not in ADMINS:
        return

    training = admin_db_training(training_id)
    if not training:
        send_message(user_id, "❌ Тренировка не найдена.", admin_back_keyboard())
        return

    set_state(user_id, "admin_delete_training", {"training_id": training_id})
    count = get_training_participant_count(training_id)
    text = (
        "🗑 УДАЛЕНИЕ ТРЕНИРОВКИ\n\n"
        + format_training(training)
        + f"\n\n👥 Записано: {count}/{training_capacity(training)}\n\n"
        "Удалить эту тренировку?"
    )
    send_message(
        user_id,
        text,
        {
            "one_time": False,
            "buttons": [[
                button("🗑 Да, удалить", "negative"),
                button("⬅️ Назад", "secondary"),
            ]],
        },
    )


def admin_save_edited_training(user_id, training_id, data):
    try:
        raw_date = str(data["date"]).strip()
        parsed_date = None
        for date_format in ("%d.%m.%Y", "%d.%m.%y", "%d.%m"):
            try:
                parsed_date = datetime.strptime(raw_date, date_format).date()
                if date_format == "%d.%m":
                    parsed_date = parsed_date.replace(year=today_local().year)
                break
            except ValueError:
                continue
        if parsed_date is None:
            raise ValueError("Дата должна быть в формате ДД.ММ.ГГГГ или ДД.ММ")

        start_time = data["start_time"]
        end_time = data["end_time"]
        datetime.strptime(start_time, "%H:%M")
        datetime.strptime(end_time, "%H:%M")
        if start_time >= end_time:
            raise ValueError("Время окончания должно быть позже времени начала")

        format_aliases = {
            "техничка": "Техничка",
            "технический": "Техничка",
            "женская": "Женская",
            "женская тренировка": "Женская",
            "миксты": "Миксты",
            "микст": "Миксты",
            "мужская": "Мужская",
            "мужская тренировка": "Мужская",
            "тренировка": "Тренировка",
            "игровая": "Игровая",
            "турнир": "Турнир",
        }
        level_aliases = {
            "общий": "Общий",
            "начальный": "Начальный",
            "средний": "Средний",
            "продвинутый": "Продвинутый",
        }
        format_key = re.sub(r"\s+", " ", data["format"].strip().lower())
        level_key = re.sub(r"\s+", " ", data["level"].strip().lower())
        if format_key not in format_aliases:
            raise ValueError("Неизвестный формат тренировки")
        if level_key not in level_aliases:
            raise ValueError("Неизвестный уровень тренировки")

        price = int(
            str(data["price"])
            .replace("₽", "")
            .replace("руб.", "")
            .replace("руб", "")
            .strip()
        )
        if price < 0:
            raise ValueError("Стоимость не может быть отрицательной")
        if not data["coach"].strip():
            raise ValueError("Не указан тренер")
        if not data["location"].strip():
            raise ValueError("Не указано место")

        training_data = {
            "training_date": parsed_date.isoformat(),
            "weekday": parsed_date.weekday(),
            "start_time": start_time,
            "end_time": end_time,
            "title": format_aliases[format_key],
            "level": level_aliases[level_key],
            "format": format_aliases[format_key],
            "coach": data["coach"].strip(),
            "price": price,
            "location": data["location"].strip(),
        }
        admin_update_training(training_id, training_data)
        add_admin_log(
            user_id,
            "training_update",
            "training",
            training_id,
            f"Training updated: {training_data}",
        )
        training = admin_db_training(training_id)
        admin_show_training(user_id, training)
        send_message(user_id, "✅ Тренировка обновлена.")
    except Exception as error:
        logger.exception("ADMIN EDIT TRAINING ERROR")
        send_message(
            user_id,
            "❌ Не удалось изменить тренировку.\n\n"
            f"{error}\n\n"
            "Отправьте 7 строк ещё раз.",
            admin_back_keyboard(),
        )
        set_state(user_id, "admin_edit_training", {"training_id": training_id})


# ============================================================
# ADMIN ADD TRAINING
# ============================================================

def admin_start_add_training(user_id):
    if user_id not in ADMINS:
        return

    set_state(user_id, "admin_add_training", {})

    send_message(
        user_id,
        "➕ ДОБАВЛЕНИЕ ТРЕНИРОВКИ\n\n"
        "Отправьте одним сообщением 7 строк:\n\n"
        "1. Дата\n"
        "2. Время\n"
        "3. Формат\n"
        "4. Уровень\n"
        "5. Стоимость\n"
        "6. Тренер\n"
        "7. Место",
        admin_back_keyboard(),
    )


def admin_save_training(
    user_id,
    data,
):
    try:
        raw_date = str(data["date"]).strip()
        training_date = None
        for date_format in ("%d.%m.%Y", "%d.%m.%y", "%d.%m"):
            try:
                training_date = datetime.strptime(
                    raw_date,
                    date_format,
                ).date()
                if date_format == "%d.%m":
                    training_date = training_date.replace(
                        year=today_local().year
                    )
                break
            except ValueError:
                continue
        if training_date is None:
            raise ValueError(
                "Дата должна быть в формате ДД.ММ.ГГГГ или ДД.ММ"
            )

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

        if start_time >= end_time:
            raise ValueError(
                "Время окончания должно быть позже времени начала"
            )

        training_data = {
            "training_date": training_date.isoformat(),
            "weekday": WEEKDAYS[training_date.weekday()],
            "start_time": start_time,
            "end_time": end_time,
            "title": data["format"],
            "category": "Взрослые",
            "age_group": None,
            "level": data["level"],
            "format": data["format"],
            "coach": data["coach"],
            "capacity": 10,
            "price": int(data["price"]),
            "location": data["location"],
        }

        training_id = admin_create_training(
            training_data
        )

        add_admin_log(
            user_id,
            "training_create",
            "training",
            training_id,
            f"Training created: {training_data}",
        )

        training = admin_db_training(
            training_id
        )

        set_state(
            user_id,
            "admin_menu",
            {},
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
            "❌ Не удалось создать тренировку.\n\n"
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

    if subject == "Индивидуальная тренировка":
        message = (
            "🎯 ИНДИВИДУАЛЬНАЯ ТРЕНИРОВКА\n\n"
            "Для подробной информации напишите сообщение одним сообщением.\n\n"
            "Мы передадим его администратору."
        )
    else:
        message = (
            "✍️ Напишите сообщение одним сообщением.\n\n"
            "Мы передадим его администраторам."
        )

    send_message(user_id, message, back_keyboard(user_id))


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
    """
    Finds a training from a schedule button.

    training_number remains in the database as an internal identifier,
    but it is no longer shown in new UI buttons. Old №N buttons remain
    supported for backward compatibility.
    """
    import re

    text = str(text or "").strip()
    connection = get_connection()

    try:
        cursor = connection.cursor()

        # Old buttons.
        number_match = re.search(r"№\s*(\d+)", text)
        if number_match:
            number_text = number_match.group(1)
            cursor.execute(
                "SELECT * FROM trainings "
                "WHERE CAST(training_number AS INTEGER) = ? "
                "ORDER BY id DESC LIMIT 1",
                (int(number_text),),
            )
            return cursor.fetchone()

        # New buttons: "Пн 05.10 17:00 | Миксты | Средний"
        match = re.search(
            r"(Пн|Вт|Ср|Чт|Пт|Сб|Вс)\s+"
            r"(\d{1,2})\.(\d{1,2})\s+"
            r"(\d{1,2}:\d{2})",
            text,
            re.IGNORECASE,
        )

        if not match:
            logger.warning(
                "TRAINING BUTTON DATE/TIME NOT FOUND: %r",
                text,
            )
            return None

        day = int(match.group(2))
        month = int(match.group(3))
        start_time = match.group(4)
        year = today_local().year

        selected_date = date(year, month, day)

        cursor.execute(
            "SELECT * FROM trainings "
            "WHERE training_date = ? AND start_time = ? "
            "ORDER BY id DESC",
            (
                selected_date.isoformat(),
                start_time,
            ),
        )
        rows = cursor.fetchall()

        # New year transition.
        if not rows and month == 1 and today_local().month == 12:
            selected_date = date(year + 1, month, day)
            cursor.execute(
                "SELECT * FROM trainings "
                "WHERE training_date = ? AND start_time = ? "
                "ORDER BY id DESC",
                (
                    selected_date.isoformat(),
                    start_time,
                ),
            )
            rows = cursor.fetchall()

        # If several trainings have the same start time, use format/level.
        if len(rows) > 1:
            normalized = text.lower()

            for row in rows:
                training_format = str(
                    row_value(row, "format", "") or ""
                ).lower()

                level = str(
                    row_value(row, "level", "") or ""
                ).lower()

                if (
                    training_format
                    and training_format in normalized
                    and level
                    and level in normalized
                ):
                    logger.info(
                        "TRAINING BUTTON LOOKUP resolved by "
                        "date/time/format/level id=%s",
                        row_value(row, "id"),
                    )
                    return row

        training = rows[0] if rows else None

        logger.info(
            "TRAINING BUTTON LOOKUP date=%s time=%s found=%s count=%s",
            selected_date.isoformat(),
            start_time,
            bool(training),
            len(rows),
        )

        return training

    except Exception:
        logger.exception(
            "TRAINING BUTTON LOOKUP ERROR text=%r",
            text,
        )
        return None

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
        + timedelta(days=6)
    )

    try:
        trainings = admin_db_trainings(
            today.isoformat(),
            end_date.isoformat(),
        )
    except Exception as error:
        logger.exception(
            "ADMIN TRAININGS LOAD ERROR"
        )
        send_message(
            user_id,
            "❌ Не удалось загрузить данные тренировок.\n\n"
            "Ошибка записана в лог Render.",
            admin_back_keyboard(),
        )
        return

    trainings = list(
        trainings or []
    )

    if not trainings:
        send_message(
            user_id,
            "👥 На ближайшие 7 дней "
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

        training_date = training_date_value(training)
        label = (
            f"{WEEKDAYS_SHORT[training_date.weekday()]} "
            f"{training_date.strftime('%d.%m')} "
            f"{row_value(training, 'start_time', '')} | "
            f"{count}/{training_capacity(training)}"
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
    buttons = compact_keyboard_buttons(buttons, max_rows=10)

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

    if state == "admin_schedule_select":

        logger.info("ADMIN schedule selection user=%s state=%s text=%r", user_id, state, text)
        training = find_training_from_button(text)

        if training:
            admin_show_training(
                user_id,
                training,
            )
        else:
            send_message(
                user_id,
                "❌ Не удалось найти выбранную тренировку. Откройте расписание ещё раз.",
                admin_back_keyboard(),
            )

        return True

    if state == "admin_participants_select":

        training = find_training_from_button(text)

        if training:
            admin_show_participants(
                user_id,
                row_value(training, "id"),
            )
        else:
            send_message(
                user_id,
                "❌ Не удалось найти выбранную тренировку. Откройте список участников ещё раз.",
                admin_back_keyboard(),
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

    if state == "training_feedback_rating":
        training_id = state_data.get("training_id")
        rating_match = re.search(r"([1-5])", text)
        if not rating_match:
            send_message(user_id, "Пожалуйста, выберите оценку от 1 до 5.")
            return
        rating = int(rating_match.group(1))
        set_state(user_id, "training_feedback_comment", {"training_id": training_id, "rating": rating})
        send_message(
            user_id,
            "Спасибо! 🙌\n\n"
            "Если хотите, напишите комментарий о тренировке в свободной форме.\n"
            "Или нажмите «Пропустить».",
            {"one_time": False, "buttons": [[button("Пропустить", "secondary")]]},
        )
        return

    if state == "training_feedback_comment":
        training_id = state_data.get("training_id")
        rating = int(state_data.get("rating", 0))
        comment = "" if text == "Пропустить" else text
        try:
            save_training_feedback(training_id, user_id, rating, comment)
            clear_state(user_id)
            send_message(user_id, "✅ Спасибо за обратную связь! Она сохранена.", main_menu(user_id))
        except Exception:
            logger.exception("Failed to save training feedback")
            send_message(user_id, "❌ Не удалось сохранить отзыв. Попробуйте ещё раз.")
        return

    # --------------------------------------------------------
    # ADMIN MODE
    # --------------------------------------------------------
    # Администратор должен иметь возможность пользоваться
    # обычным пользовательским меню. Поэтому админские кнопки
    # обрабатываем только когда пользователь уже находится
    # в admin_menu/admin_* состоянии.

    admin_mode = (
        user_id in ADMINS
        and state
        and (
            state == "admin_menu"
            or state.startswith("admin_")
        )
    )

    if admin_mode:

        if text == "📅 Расписание":
            admin_show_schedule(
                user_id
            )
            return

        if text == "➕ Добавить тренировку":
            admin_start_add_training(
                user_id
            )
            return

        if text == "📚 Архив тренировок":
            admin_show_archive_menu(user_id)
            return

        if text == "👤 Режим пользователя":
            show_main_menu(user_id)
            return

        if text == "⚙️ Админ-панель":
            show_admin_menu(user_id)
            return

    # --------------------------------------------------------
    # GLOBAL BUTTONS
    # --------------------------------------------------------

    if text == "🏠 Главное меню":
        show_main_menu(user_id)
        return

    if text == "⬅️ Админ-панель":
        if user_id in ADMINS:
            show_admin_menu(user_id)
        else:
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
    # WEEK SCHEDULE -> DIRECT BOOKING
    # --------------------------------------------------------

    if state == "schedule_week":
        training = find_training_from_button(text)
        if training:
            show_training_for_booking(user_id, training)
        else:
            send_message(
                user_id,
                "❌ Тренировка не найдена. Откройте расписание ещё раз.",
                back_keyboard(user_id),
            )
        return

    # --------------------------------------------------------
    # SCHEDULE WEEK NAVIGATION
    # --------------------------------------------------------

    if state == "schedule_week":
        category = state_data.get("category")
        current = week_start_for(state_data.get("week_start"))
        today_week = week_start_for(today_local())

        if text == "⬅️ Предыдущая неделя":
            target = max(today_week, current - timedelta(days=7))
            show_schedule(user_id, category, target)
            return

        if text == "Следующая неделя ➡️":
            target = current + timedelta(days=7)
            if target <= today_week + timedelta(days=28):
                show_schedule(user_id, category, target)
            return

    # --------------------------------------------------------
    # BOOKING WEEK NAVIGATION
    # --------------------------------------------------------

    if state == "booking_week":
        category = state_data.get("category")
        current = week_start_for(state_data.get("week_start"))
        today_week = week_start_for(today_local())

        if text == "⬅️ Предыдущая неделя":
            target = max(today_week, current - timedelta(days=7))
            show_booking_week(user_id, category, target)
            return

        if text == "Следующая неделя ➡️":
            target = current + timedelta(days=7)
            if target <= today_week + timedelta(days=28):
                show_booking_week(user_id, category, target)
            return

        training = find_training_from_button(text)
        if training:
            show_training_for_booking(user_id, training)
            return

    # --------------------------------------------------------
    # BOOKING CATEGORY
    # --------------------------------------------------------

    if state == "booking_category":

        if text == "👧 Дети":
            show_booking_week(user_id, "children")
            return

        if text == "🧑 Взрослые":
            show_booking_week(user_id, "adults")
            return

        if text == "🏠 Все тренировки":
            show_booking_week(user_id, "all")
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

        completion_match = re.match(
            r"^(?:✅ (?:Тренировка прошла|Прошла)|❌ (?:Тренировка не прошла|Не прошла)) №(\d+)$",
            text,
        )
        if completion_match:
            training = get_training_by_number(int(completion_match.group(1)))
            if not training:
                send_message(user_id, "❌ Тренировка не найдена.", admin_back_keyboard())
                return
            if text.startswith("✅"):
                admin_finish_training(user_id, row_value(training, "id"))
            else:
                admin_mark_training_not_held(user_id, row_value(training, "id"))
            return

        if state == "admin_attendance":
            training_id = state_data.get("training_id")
            if text == "⬅️ К тренировке":
                training = admin_db_training(training_id)
                if training:
                    admin_show_training(user_id, training)
                return
            if text == "⚙️ Админ-панель":
                admin_panel(user_id)
                return

            match = re.match(r"^(?:❌|✅)\s+(\d+)\.", text)
            if match:
                index = int(match.group(1))
                registrations = list(get_registrations(training_id) or [])
                if 1 <= index <= len(registrations):
                    registration = registrations[index - 1]
                    registration_id = row_value(registration, "id")
                    current = None
                    for item in (get_training_attendance(training_id) or []):
                        if row_value(item, "registration_id") == registration_id:
                            current = row_value(item, "status")
                            break
                    new_status = "absent" if current == "present" else "present"
                    admin_mark_attendance_from_button(
                        user_id, training_id, registration_id, new_status
                    )
                return

        if state == "admin_archive_menu":
            if text == "📅 По дате":
                set_state(user_id, "admin_archive_date", {})
                send_message(user_id, "📅 Введите дату в формате ДД.ММ.ГГГГ или ДД.ММ", admin_back_keyboard())
                return
            if text == "👤 По участнику":
                set_state(user_id, "admin_archive_user", {})
                send_message(user_id, "👤 Введите имя, фамилию или VK ID участника", admin_back_keyboard())
                return

        if state == "admin_archive_date":
            admin_archive_by_date(user_id, text)
            return

        if state == "admin_archive_user":
            admin_archive_by_user(user_id, text)
            return

        if state == "admin_add_participant_search":
            admin_search_participants(user_id, state_data.get("training_id"), text, "add")
            return

        if state == "admin_add_participant_select":
            training_id = state_data.get("training_id")
            mapping = state_data.get("user_mapping", {})
            vk_id = mapping.get(text)
            if vk_id is None:
                send_message(user_id, "❌ Не удалось определить пользователя. Выберите кнопку ещё раз.", admin_back_keyboard())
                return
            admin_add_participant(user_id, training_id, int(vk_id))
            return

        if state == "admin_remove_participant":
            if text == "⬅️ К тренировке":
                training = admin_db_training(state_data.get("training_id"))
                if training:
                    admin_show_training(user_id, training)
                return
            match = re.search(r"\|\s*(\d+)\s*$", text)
            if not match:
                send_message(user_id, "❌ Не удалось определить участника.", admin_back_keyboard())
                return
            admin_remove_participant(user_id, state_data.get("training_id"), int(match.group(1)))
            return

        if state == "admin_cancel_training":
            if text == "❌ Да, отменить":
                admin_cancel_training_and_notify(user_id, state_data.get("training_id"))
                return

        if state == "admin_training_details":

            training_id = state_data.get(
                "training_id"
            )

            if text == "➕ Добавить участника":
                admin_start_add_participant(user_id, training_id)
                return

            if text == "➖ Удалить участника":
                admin_start_remove_participant(user_id, training_id)
                return

            if text == "❌ Отменить тренировку":
                admin_start_cancel_training(user_id, training_id)
                return

            if text == "📝 Комментарий":
                training = admin_db_training(training_id)
                current_comment = row_value(training, "comment", "") if training else ""
                set_state(user_id, "admin_training_comment", {"training_id": training_id})
                send_message(
                    user_id,
                    "📝 КОММЕНТАРИЙ К ТРЕНИРОВКЕ\n\n"
                    "Отправьте текст комментария одним сообщением.\n"
                    "Если хотите удалить комментарий — отправьте: УДАЛИТЬ\n\n"
                    f"Текущий комментарий:\n{current_comment or 'нет'}",
                    admin_back_keyboard(),
                )
                return

            if text == "📋 Посещаемость":
                admin_show_attendance(
                    user_id,
                    training_id,
                )
                return

            if text == "✅ Тренировка прошла":
                admin_finish_training(user_id, training_id)
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

        if state == "admin_training_details":
            training_id = state_data.get("training_id")
            if text == "✏️ Редактировать":
                admin_start_edit_training(user_id, training_id)
                return
            if text == "🗑 Удалить тренировку":
                admin_confirm_delete_training(user_id, training_id)
                return
            if text == "📋 Посещаемость":
                admin_show_attendance(user_id, training_id)
                return

        if state == "admin_delete_training":
            training_id = state_data.get("training_id")
            if text == "🗑 Да, удалить":
                try:
                    admin_delete_training(training_id)
                    add_admin_log(
                        user_id,
                        "training_delete",
                        "training",
                        training_id,
                        "Training deleted",
                    )
                    show_admin_menu(user_id)
                    send_message(user_id, "✅ Тренировка удалена.", admin_menu())
                except Exception as error:
                    logger.exception("ADMIN DELETE TRAINING ERROR")
                    send_message(
                        user_id,
                        "❌ Не удалось удалить тренировку.\n\n"
                        f"Ошибка: {error}",
                        admin_back_keyboard(),
                    )
                return

        if state == "admin_training_comment":
            training_id = state_data.get("training_id")
            comment = "" if text.upper() == "УДАЛИТЬ" else text
            if update_training_comment(training_id, comment):
                add_admin_log(user_id, "training_comment_update", "training", training_id, comment[:500])
                training = admin_db_training(training_id)
                if training:
                    admin_show_training(user_id, training)
                return
            send_message(user_id, "❌ Не удалось сохранить комментарий.", admin_back_keyboard())
            return

        if state == "admin_edit_training":
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            lines = [
                re.sub(r"^\s*\d+\s*[.)]\s*", "", line).strip()
                for line in lines
            ]
            if len(lines) != 7:
                send_message(
                    user_id,
                    "❌ Нужно ровно 7 строк:\n\n"
                    "1. Дата\n2. Время\n3. Формат\n4. Уровень\n5. Стоимость\n6. Тренер\n7. Место",
                    admin_back_keyboard(),
                )
                return
            try:
                date_text = (
                    lines[0].replace("/", ".")
                    .replace("—", ".")
                    .replace("–", ".")
                    .replace("-", ".")
                    .strip()
                )
                parsed_date = None
                for date_format in ("%d.%m.%Y", "%d.%m.%y", "%d.%m"):
                    try:
                        parsed_date = datetime.strptime(date_text, date_format).date()
                        if date_format == "%d.%m":
                            parsed_date = parsed_date.replace(year=today_local().year)
                        break
                    except ValueError:
                        continue
                if parsed_date is None:
                    raise ValueError("Дата: ДД.ММ.ГГГГ или ДД.ММ")

                time_line = lines[1].replace("—", "–").replace("-", "–")
                if "–" not in time_line:
                    raise ValueError("Время нужно указать как ЧЧ:ММ–ЧЧ:ММ")
                start_time, end_time = [x.strip() for x in time_line.split("–", 1)]
                datetime.strptime(start_time, "%H:%M")
                datetime.strptime(end_time, "%H:%M")
                if start_time >= end_time:
                    raise ValueError("Время окончания должно быть позже времени начала")

                price_text = (
                    lines[4].replace("₽", "")
                    .replace("руб.", "")
                    .replace("руб", "")
                    .strip()
                )
                data = {
                    "date": parsed_date.strftime("%d.%m.%Y"),
                    "start_time": start_time,
                    "end_time": end_time,
                    "format": lines[2],
                    "level": lines[3],
                    "price": price_text,
                    "coach": lines[5],
                    "location": lines[6],
                }
                admin_save_edited_training(
                    user_id,
                    state_data.get("training_id"),
                    data,
                )
            except (ValueError, TypeError) as error:
                send_message(
                    user_id,
                    "❌ Не удалось разобрать изменения.\n\n"
                    f"{error}\n\nОтправьте 7 строк ещё раз.",
                    admin_back_keyboard(),
                )
                set_state(
                    user_id,
                    "admin_edit_training",
                    {"training_id": state_data.get("training_id")},
                )
            return

        # ----------------------------------------------------
        # ADD TRAINING — ONE MESSAGE
        # ----------------------------------------------------

        if state == "admin_add_training":

            lines = [
                line.strip()
                for line in text.splitlines()
                if line.strip()
            ]

            # Разрешаем отправлять строки с нумерацией, например:
            # 1. 07.10.2026
            # 2. 17:00–19:00
            # Нумерация удаляется только в начале строки.
            lines = [
                re.sub(r"^\s*\d+\s*[.)]\s*", "", line).strip()
                for line in lines
            ]

            if len(lines) != 7:
                send_message(
                    user_id,
                    "❌ Нужно ровно 7 строк.\n\n"
                    "1. Дата\n"
                    "2. Время\n"
                    "3. Формат\n"
                    "4. Уровень\n"
                    "5. Стоимость\n"
                    "6. Тренер\n"
                    "7. Место",
                    admin_back_keyboard(),
                )
                return

            format_aliases = {
                "техничка": "Техничка",
                "технический": "Техничка",
                "техническая": "Техничка",
                "техническая тренировка": "Техничка",
                "женская": "Женская",
                "женская тренировка": "Женская",
                "женская группа": "Женская",
                "миксты": "Миксты",
                "микст": "Миксты",
                "mixed": "Миксты",
                "mix": "Миксты",
                "мужская": "Мужская",
                "мужская тренировка": "Мужская",
                "мужская группа": "Мужская",
                "тренировка": "Тренировка",
                "игровая": "Игровая",
                "турнир": "Турнир",
            }

            level_aliases = {
                "общий": "Общий",
                "начальный": "Начальный",
                "средний": "Средний",
                "продвинутый": "Продвинутый",
            }

            try:
                date_text = (
                    lines[0]
                    .replace("/", ".")
                    .replace("—", ".")
                    .replace("–", ".")
                    .replace("-", ".")
                    .strip()
                )
                date_text = re.sub(r"\s*\.\s*", ".", date_text)

                # Дата может прийти как "1.07.10" — это номер строки 1 + дата 07.10.
                # Также поддерживаем обычные "07.10" и "07.10.2026".
                if re.match(r"^\d\.\d{1,2}\.\d{1,4}$", date_text):
                    prefix, rest = date_text.split(".", 1)
                    if len(rest.split(".")) == 2:
                        date_text = rest

                # Поддерживаем и запись с номером строки без пробела:
                # "1.07.10" -> "07.10".
                numbered_short_date = re.match(
                    r"^([1-7])\.(\d{1,2})\.(\d{1,2})$",
                    date_text,
                )
                if numbered_short_date:
                    date_text = (
                        numbered_short_date.group(2)
                        + "."
                        + numbered_short_date.group(3)
                    )

                parsed_date = None
                for date_format in ("%d.%m.%Y", "%d.%m.%y", "%d.%m"):
                    try:
                        parsed_date = datetime.strptime(
                            date_text,
                            date_format,
                        ).date()
                        if date_format == "%d.%m":
                            parsed_date = parsed_date.replace(
                                year=today_local().year
                            )
                        break
                    except ValueError:
                        continue

                if parsed_date is None:
                    raise ValueError(
                        "Дата: ДД.ММ.ГГГГ, ДД.ММ или ДД.ММ.ГГГГ с номером строки"
                    )

                lines[0] = parsed_date.strftime("%d.%m.%Y")

                time_line = (
                    lines[1]
                    .replace("—", "–")
                    .replace("-", "–")
                )

                if "–" not in time_line:
                    raise ValueError(
                        "Время нужно указать как ЧЧ:ММ–ЧЧ:ММ"
                    )

                start_time, end_time = [
                    item.strip()
                    for item in time_line.split("–", 1)
                ]

                datetime.strptime(
                    start_time,
                    "%H:%M",
                )

                datetime.strptime(
                    end_time,
                    "%H:%M",
                )

                if start_time >= end_time:
                    raise ValueError(
                        "Время окончания должно быть позже времени начала"
                    )

                format_key = re.sub(r"\s+", " ", lines[2].strip().lower())
                level_key = re.sub(r"\s+", " ", lines[3].strip().lower())
                if format_key not in format_aliases:
                    raise ValueError("Неизвестный формат тренировки. Можно: техничка, женская, миксты, мужская, тренировка.")
                if level_key not in level_aliases:
                    raise ValueError("Неизвестный уровень. Можно: начальный, средний, продвинутый.")
                lines[2] = format_aliases[format_key]
                lines[3] = level_aliases[level_key]

                price_text = (
                    lines[4]
                    .replace("₽", "")
                    .replace("руб", "")
                    .replace("руб.", "")
                    .strip()
                )

                price = int(price_text)

                if price < 0:
                    raise ValueError(
                        "Стоимость не может быть отрицательной"
                    )

                if not lines[5]:
                    raise ValueError(
                        "Не указан тренер"
                    )

                if not lines[6]:
                    raise ValueError(
                        "Не указано место"
                    )

                logger.info(
                    "ADMIN %s parsed training input: %r",
                    user_id,
                    lines,
                )

                data = {
                    "date": lines[0],
                    "start_time": start_time,
                    "end_time": end_time,
                    "format": lines[2],
                    "level": lines[3],
                    "price": price,
                    "coach": lines[5],
                    "location": lines[6],
                }

                admin_save_training(
                    user_id,
                    data,
                )

            except (ValueError, TypeError) as error:
                send_message(
                    user_id,
                    "❌ Не удалось разобрать тренировку.\n\n"
                    f"{error}\n\n"
                    "Отправьте эти 7 строк ещё раз. Режим добавления тренировки сохранён.",
                    admin_back_keyboard(),
                )
                set_state(user_id, "admin_add_training", {})

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
# NOTIFICATION WORKER
# ============================================================

def training_start_datetime(training):
    training_date = training_date_value(training)
    start_time = row_value(training, "start_time", "00:00")
    parsed_time = datetime.strptime(start_time, "%H:%M").time()
    return datetime.combine(training_date, parsed_time).replace(tzinfo=TIMEZONE)


def notification_text(training, hours_before):
    if hours_before == 24:
        title = "ЗАВТРА У ВАС ТРЕНИРОВКА"
        lead = "Напоминаем, что завтра у вас тренировка."
    else:
        title = "ТРЕНИРОВКА ЧЕРЕЗ 2 ЧАСА"
        lead = "Напоминаем, что через 2 часа у вас тренировка."
    return (
        f"🏐 {title}\n\n"
        f"{lead}\n\n"
        + format_training(training)
        + "\n\nДо встречи на площадке!"
    )


def prepare_training_notifications(now):
    today = now.date()
    end_date = today + timedelta(days=2)
    trainings = admin_db_trainings(today.isoformat(), end_date.isoformat())

    for training in trainings:
        if row_value(training, "status", "") != "scheduled":
            continue
        try:
            start_dt = training_start_datetime(training)
        except Exception:
            logger.exception("Invalid training datetime for notification")
            continue
        if start_dt <= now:
            continue

        for hours_before, notification_type in ((24, "training_24h"), (2, "training_2h")):
            scheduled_for = start_dt - timedelta(hours=hours_before)
            if scheduled_for > now:
                continue
            for vk_id in get_training_registered_vk_ids(row_value(training, "id")):
                try:
                    create_notification(
                        vk_id,
                        row_value(training, "id"),
                        notification_type,
                        scheduled_for.isoformat(),
                    )
                except Exception:
                    logger.exception("Failed to create notification for %s", vk_id)


def send_training_feedback_requests(training_id):
    training = admin_db_training(training_id)
    if not training:
        return
    recipients = get_training_registered_vk_ids(training_id)
    for vk_id in recipients:
        try:
            existing = get_training_feedback(training_id, vk_id)
            if existing:
                continue
            buttons = [
                [button("⭐ 1", "negative"), button("⭐ 2", "negative"), button("⭐ 3", "secondary")],
                [button("⭐ 4", "positive"), button("⭐ 5", "positive")],
            ]
            set_state(vk_id, "training_feedback_rating", {"training_id": training_id})
            send_message(
                vk_id,
                "💬 ОЦЕНКА ТРЕНИРОВКИ\n\n"
                "Как вам сегодняшняя тренировка?\n"
                "Поставьте оценку от 1 до 5.",
                {"one_time": False, "buttons": buttons},
            )
        except Exception:
            logger.exception("Failed to request feedback from %s", vk_id)


def completion_check_text(training):
    return (
        "🏐 ПРОВЕРКА ТРЕНИРОВКИ\n\n"
        "Тренировка уже должна была закончиться. Прошла ли она?\n\n"
        + format_training(training)
        + "\n\nВыберите вариант:"
    )


def prepare_admin_minimum_set_notifications(now):
    """Уведомляет админов за сутки до тренировки, набран ли минимум из 4 участников."""
    minimum = 4
    today = now.date()
    end_date = today + timedelta(days=2)
    trainings = admin_db_trainings(today.isoformat(), end_date.isoformat())

    for training in trainings:
        if row_value(training, "status", "") != "scheduled":
            continue
        try:
            start_dt = training_start_datetime(training)
        except Exception:
            logger.exception("Invalid training datetime for minimum set notification")
            continue

        if start_dt <= now:
            continue
        if start_dt - timedelta(hours=24) > now:
            continue

        training_id = row_value(training, "id")
        count = get_registration_count(training_id)
        capacity = training_capacity(training)
        if count >= minimum:
            status_text = "✅ МИНИМАЛЬНЫЙ НАБОР НАБРАН"
            detail = f"На тренировку записано {count} человек. Минимум — {minimum}."
        else:
            status_text = "⚠️ МИНИМАЛЬНЫЙ НАБОР НЕ НАБРАН"
            detail = f"На тренировку записано {count} человек. Минимум — {minimum}. Не хватает {minimum - count}."

        message = (
            f"{status_text}\n\n"
            f"🏐 Тренировка через 24 часа\n\n"
            f"{format_training(training)}\n\n"
            f"👥 {detail}\n"
            f"Вместимость: {capacity} мест."
        )

        for admin_id in ADMINS:
            try:
                should_send = create_admin_notification_marker(
                    admin_id,
                    training_id,
                    "minimum_set_24h",
                )
                if should_send:
                    result = send_message(admin_id, message, admin_back_keyboard())
                    if result and result.get("error"):
                        logger.warning(
                            "Admin minimum-set notification failed for %s / %s",
                            admin_id, training_id,
                        )
            except Exception:
                logger.exception(
                    "Failed to send minimum-set notification for training %s to admin %s",
                    training_id,
                    admin_id,
                )


def process_completion_checks():
    now = datetime.now(TIMEZONE)
    try:
        trainings = get_trainings_needing_completion_check(
            now.isoformat(),
            delay_minutes=10,
        )
    except Exception:
        logger.exception("Failed to get trainings needing completion check")
        return

    for training in trainings:
        training_id = row_value(training, "id")
        number = training_number(training)
        buttons = [
            [
                button(f"✅ Тренировка прошла №{number}", "positive"),
                button(f"❌ Тренировка не прошла №{number}", "negative"),
            ]
        ]

        sent_any = False
        for admin_id in ADMINS:
            try:
                result = send_message(
                    admin_id,
                    completion_check_text(training),
                    {"one_time": False, "buttons": buttons},
                )
                if not result or not result.get("error"):
                    sent_any = True
            except Exception:
                logger.exception(
                    "Failed to send completion check for training %s to admin %s",
                    training_id, admin_id,
                )

        if sent_any:
            try:
                mark_completion_check_sent(training_id)
            except Exception:
                logger.exception(
                    "Failed to mark completion check sent for training %s",
                    training_id,
                )


def process_pending_notifications():
    now = datetime.now(TIMEZONE)
    prepare_training_notifications(now)
    current_text = now.isoformat()
    pending = get_pending_notifications(current_text)

    for notification in pending:
        notification_id = row_value(notification, "id")
        user_id = row_value(notification, "vk_id")
        training_id = row_value(notification, "training_id")
        notification_type = row_value(notification, "notification_type", "")

        training = admin_db_training(training_id)
        if not training or row_value(training, "status", "") != "scheduled":
            mark_notification_failed(notification_id)
            continue

        try:
            if notification_type == "training_24h":
                hours_before = 24
            elif notification_type == "training_2h":
                hours_before = 2
            else:
                mark_notification_failed(notification_id)
                continue

            result = send_message(
                user_id,
                notification_text(training, hours_before),
                main_menu(user_id),
            )
            if result and result.get("error"):
                mark_notification_failed(notification_id)
            else:
                mark_notification_sent(notification_id)
        except Exception:
            logger.exception("Failed to send notification %s", notification_id)
            mark_notification_failed(notification_id)


def notification_worker():
    logger.info("Notification worker started")
    while True:
        try:
            now = datetime.now(TIMEZONE)
            prepare_admin_minimum_set_notifications(now)
            process_completion_checks()
            process_pending_notifications()
        except Exception:
            logger.exception("Notification worker iteration failed")
        time.sleep(60)


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
            + timedelta(days=6)
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

    notification_thread = threading.Thread(
        target=notification_worker,
        name="volley-wave-notifications",
        daemon=True,
    )
    notification_thread.start()

    app.run(
        host="0.0.0.0",
        port=PORT,
    )
