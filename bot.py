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
# НАСТРОЙКИ
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

TIMEZONE = "Asia/Yekaterinburg"

app = Flask(__name__)

# Состояния пользователей в памяти
user_states = {}

# Инициализация БД
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
        "random_id": random.randint(-2147483648, 2147483647),
    }

    if keyboard is not None:
        params["keyboard"] = json.dumps(
            keyboard,
            ensure_ascii=False,
        )

    result = vk_api("messages.send", params)

    return result


# ============================================================
# КЛАВИАТУРЫ
# ============================================================

def button(label, color="secondary"):
    return {
        "action": {
            "type": "text",
            "label": label,
        },
        "color": color,
    }


def keyboard(rows, one_time=False):
    return {
        "one_time": one_time,
        "buttons": rows,
    }


def back_button():
    return button("⬅️ Назад", "secondary")


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


def admin_menu():
    return keyboard([
        [
            button("📅 Управление расписанием", "primary"),
        ],
        [
            button("👥 Участники тренировок", "primary"),
        ],
        [
            button("➕ Добавить тренировку", "positive"),
        ],
        [
            button("👤 Пользовательский режим", "secondary"),
        ],
    ])


# ============================================================
# СОСТОЯНИЯ
# ============================================================

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
# ПОЛЬЗОВАТЕЛЬ
# ============================================================

def register_user(user_id):
    user = get_user(user_id)

    if user is None:
        create_or_update_user(
            vk_id=user_id,
            first_name=None,
            last_name=None,
        )


# ============================================================
# ОБЩИЕ ДАННЫЕ
# ============================================================

def format_category(category):
    if category == "children":
        return "👶 Дети"

    if category == "adults":
        return "🧑 Взрослые"

    return category or ""


def format_training(training):
    if not training:
        return "Тренировка"

    return training["title"]


def training_time(training):
    return training["start_time"]


def training_date_text(training):
    """
    Для текущего повторяющегося расписания определяем
    ближайшую дату тренировки.
    """

    weekday = training["weekday"]

    now = datetime.now(
        ZoneInfo(TIMEZONE)
    )

    days_ahead = (weekday - now.weekday()) % 7

    target = now + timedelta(days=days_ahead)

    # Если тренировка сегодня уже закончилась,
    # берём следующую неделю.
    if days_ahead == 0:
        try:
            start_time = datetime.strptime(
                training["start_time"],
                "%H:%M",
            ).time()

            if now.time() >= start_time:
                target += timedelta(days=7)

        except Exception:
            pass

    return target.strftime("%d.%m.%Y")


def registration_datetime(training):
    now = datetime.now(
        ZoneInfo(TIMEZONE)
    )

    weekday = training["weekday"]

    days_ahead = (weekday - now.weekday()) % 7

    target_date = now.date() + timedelta(days=days_ahead)

    try:
        start_time = datetime.strptime(
            training["start_time"],
            "%H:%M",
        ).time()
    except Exception:
        start_time = datetime.min.time()

    target = datetime.combine(
        target_date,
        start_time,
    ).replace(
        tzinfo=ZoneInfo(TIMEZONE)
    )

    if target <= now:
        target += timedelta(days=7)

    return target


def can_cancel_training(training):
    start = registration_datetime(training)
    now = datetime.now(
        ZoneInfo(TIMEZONE)
    )

    return start - now >= timedelta(hours=24)


# ============================================================
# ЦЕНЫ / МЕСТА
# ============================================================

def show_prices(user_id):
    text = (
        "💰 Цены\n\n"
        "👶 Дети — 600 ₽ за тренировку\n\n"
        "🧑 Взрослые:\n"
        "• 1–6 человек — 1200 ₽/чел.\n"
        "• 7 и более — 1000 ₽/чел.\n\n"
        "Минимальная группа для взрослой тренировки — "
        "4 человека."
    )

    send_message(
        user_id,
        text,
        keyboard([
            [back_button()],
        ]),
    )


def show_locations(user_id):
    text = (
        "📍 Где тренируемся\n\n"
        "☀️ Летом\n"
        "Парк Гагарина, Челябинск.\n\n"
        "❄️ Зимой\n"
        "СК «Арена»\n"
        "ул. Молодогвардейцев, 7\n\n"
        "Тренировки проходят на песке."
    )

    send_message(
        user_id,
        text,
        keyboard([
            [back_button()],
        ]),
    )


# ============================================================
# РАСПИСАНИЕ
# ============================================================

def show_schedule_categories(user_id):
    send_message(
        user_id,
        "📅 Выберите категорию:",
        keyboard([
            [
                button("👶 Дети", "positive"),
                button("🧑 Взрослые", "primary"),
            ],
            [
                back_button(),
            ],
        ]),
    )


def show_full_week_schedule(user_id, category):
    trainings = get_trainings_by_category(category)

    if not trainings:
        send_message(
            user_id,
            "На данный момент тренировок нет.",
            keyboard([
                [back_button()],
            ]),
        )
        return

    days = {}

    for training in trainings:
        weekday = training["weekday"]
        days.setdefault(weekday, []).append(training)

    weekday_names = [
        "Понедельник",
        "Вторник",
        "Среда",
        "Четверг",
        "Пятница",
        "Суббота",
        "Воскресенье",
    ]

    lines = [
        f"📅 Расписание — {format_category(category)}",
        "",
    ]

    for weekday in sorted(days.keys()):
        lines.append(
            f"🔹 {weekday_names[weekday]}"
        )

        for training in days[weekday]:
            count = get_registration_count(
                training["id"]
            )

            lines.append(
                f"• {training['start_time']}–{training['end_time']} — "
                f"{training['title']} "
                f"({count}/{training['capacity']})"
            )

        lines.append("")

    send_message(
        user_id,
        "\n".join(lines),
        keyboard([
            [back_button()],
        ]),
    )


# ============================================================
# ЗАПИСЬ НА ТРЕНИРОВКУ
# ============================================================

def show_booking_categories(user_id):
    set_state(
        user_id,
        "booking_category",
    )

    send_message(
        user_id,
        "🏐 На какую тренировку хотите записаться?",
        keyboard([
            [
                button("👶 Дети", "positive"),
                button("🧑 Взрослые", "primary"),
            ],
            [
                back_button(),
            ],
        ]),
    )


def show_booking_days(user_id, category):
    set_state(
        user_id,
        "booking_day",
        {
            "category": category,
        },
    )

    trainings = get_trainings_by_category(category)

    days = sorted(
        set(
            training["weekday"]
            for training in trainings
        )
    )

    weekday_names = [
        "Понедельник",
        "Вторник",
        "Среда",
        "Четверг",
        "Пятница",
        "Суббота",
        "Воскресенье",
    ]

    rows = []

    for weekday in days:
        rows.append([
            button(
                weekday_names[weekday],
                "primary",
            )
        ])

    rows.append([
        back_button(),
    ])

    send_message(
        user_id,
        "📅 Выберите день:",
        keyboard(rows),
    )


def show_booking_trainings(user_id, category, weekday):
    set_state(
        user_id,
        "booking_training",
        {
            "category": category,
            "weekday": weekday,
        },
    )

    trainings = get_trainings_by_day(
        weekday
    )

    trainings = [
        training
        for training in trainings
        if training["category"] == category
    ]

    if not trainings:
        send_message(
            user_id,
            "На этот день тренировок нет.",
            keyboard([
                [back_button()],
            ]),
        )
        return

    rows = []

    for training in trainings:
        count = get_registration_count(
            training["id"]
        )

        label = (
            f"{training['start_time']} — "
            f"{training['title']} "
            f"({count}/{training['capacity']})"
        )

        rows.append([
            button(label, "primary")
        ])

    rows.append([
        back_button(),
    ])

    send_message(
        user_id,
        "🏐 Выберите тренировку:",
        keyboard(rows),
    )


def find_training_from_button(
    user_id,
    text,
):
    state = get_state(user_id)

    category = state["data"].get("category")
    weekday = state["data"].get("weekday")

    if category is None or weekday is None:
        return None

    trainings = get_trainings_by_day(
        weekday
    )

    trainings = [
        training
        for training in trainings
        if training["category"] == category
    ]

    for training in trainings:
        count = get_registration_count(
            training["id"]
        )

        expected = (
            f"{training['start_time']} — "
            f"{training['title']} "
            f"({count}/{training['capacity']})"
        )

        if text == expected:
            return training

    # Дополнительный поиск по времени и названию,
    # чтобы изменение количества участников
    # между показом кнопки и нажатием не ломало выбор.
    for training in trainings:
        prefix = (
            f"{training['start_time']} — "
            f"{training['title']} "
        )

        if text.startswith(prefix):
            return training

    return None


def show_booking_confirmation(user_id, training):
    count = get_registration_count(
        training["id"]
    )

    registrations = get_registrations(
        training["id"]
    )

    lines = [
        "🏐 Тренировка",
        "",
        f"📅 {training_date_text(training)}",
        f"⏰ {training['start_time']}–{training['end_time']}",
        f"👥 Формат: {training['format']}",
        f"🎯 Уровень: {training['level']}",
        f"👶 Возраст: {training['age_group']}",
        f"🏐 Тренер: {training['coach']}",
        f"💰 Цена: {training['price']} ₽",
        "",
        f"Свободно: {count}/{training['capacity']}",
    ]

    if registrations:
        lines.append("")
        lines.append("👥 Уже записались:")

        for index, registration in enumerate(
            registrations,
            start=1,
        ):
            first_name = registration["first_name"]
            last_name = registration["last_name"]

            name = " ".join(
                part
                for part in [
                    first_name,
                    last_name,
                ]
                if part
            )

            if not name:
                name = f"Участник {index}"

            lines.append(
                f"{index}. {name}"
            )

    rows = []

    if count < training["capacity"]:
        rows.append([
            button("✅ Записаться", "positive")
        ])

    rows.append([
        back_button()
    ])

    send_message(
        user_id,
        "\n".join(lines),
        keyboard(rows),
    )

    set_state(
        user_id,
        "booking_confirm",
        {
            "training_id": training["id"],
        },
    )


def book_training(user_id, training_id):
    training = get_training(training_id)

    if training is None:
        send_message(
            user_id,
            "Тренировка не найдена.",
            keyboard(main_menu(user_id)),
        )
        clear_state(user_id)
        return

    count = get_registration_count(
        training_id
    )

    if count >= training["capacity"]:
        send_message(
            user_id,
            "❌ К сожалению, свободных мест больше нет.",
            keyboard(main_menu(user_id)),
        )
        clear_state(user_id)
        return

    existing = get_registration(
        training_id,
        user_id,
    )

    if existing:
        send_message(
            user_id,
            "Вы уже записаны на эту тренировку.",
            keyboard(main_menu(user_id)),
        )
        clear_state(user_id)
        return

    try:
        add_registration(
            training_id,
            user_id,
        )

        send_message(
            user_id,
            (
                "✅ Вы записаны!\n\n"
                f"{training['title']}\n"
                f"{training['start_time']}–{training['end_time']}\n"
                f"{training_date_text(training)}"
            ),
            keyboard(main_menu(user_id)),
        )

        clear_state(user_id)

    except Exception as error:
        print(
            f"BOOKING ERROR: {error}"
        )

        send_message(
            user_id,
            "Не удалось записать вас на тренировку.",
            keyboard(main_menu(user_id)),
        )

        clear_state(user_id)


# ============================================================
# МОИ ТРЕНИРОВКИ
# ============================================================

def show_my_trainings(user_id):
    """
    Показывает все активные записи пользователя.

    Важно:
    функция не проверяет, является ли пользователь админом.
    Поэтому администратор тоже может пользоваться этой кнопкой.
    """

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
            keyboard([
                [back_button()],
            ]),
        )
        return

    if not registrations:
        send_message(
            user_id,
            (
                "👤 Мои тренировки\n\n"
                "У вас пока нет записей на тренировки."
            ),
            keyboard([
                [back_button()],
            ]),
        )
        return

    lines = [
        "👤 Мои тренировки",
        "",
    ]

    rows = []

    for registration in registrations:
        training_id = registration["training_id"]

        training = get_training(
            training_id
        )

        if training is None:
            continue

        date_text = training_date_text(
            training
        )

        lines.append(
            f"🏐 {training['title']}"
        )
        lines.append(
            f"📅 {date_text}"
        )
        lines.append(
            f"⏰ {training['start_time']}–{training['end_time']}"
        )
        lines.append(
            f"🏐 Тренер: {training['coach']}"
        )
        lines.append("")

        rows.append([
            button(
                f"❌ Отменить: {training['start_time']} — {training['title']}",
                "negative",
            )
        ])

    rows.append([
        back_button()
    ])

    send_message(
        user_id,
        "\n".join(lines),
        keyboard(rows),
    )


def find_my_training_from_button(
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

        if training is None:
            continue

        expected = (
            f"❌ Отменить: "
            f"{training['start_time']} — "
            f"{training['title']}"
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
            keyboard([
                [back_button()],
            ]),
        )
        return

    registration = get_registration(
        training["id"],
        user_id,
    )

    if not registration:
        send_message(
            user_id,
            "Вы не записаны на эту тренировку.",
            keyboard(main_menu(user_id)),
        )
        return

    try:
        cancel_registration(
            training["id"],
            user_id,
        )

        send_message(
            user_id,
            (
                "✅ Запись отменена.\n\n"
                f"{training['title']}\n"
                f"{training['start_time']}–{training['end_time']}"
            ),
            keyboard(main_menu(user_id)),
        )

    except Exception as error:
        print(
            f"CANCEL ERROR: {error}"
        )

        send_message(
            user_id,
            "Не удалось отменить запись.",
            keyboard(main_menu(user_id)),
        )


# ============================================================
# АДМИН-ПАНЕЛЬ
# ============================================================

def show_admin_panel(user_id):
    if user_id not in ADMIN_IDS:
        send_message(
            user_id,
            "Нет доступа.",
            keyboard(main_menu(user_id)),
        )
        return

    clear_state(user_id)

    send_message(
        user_id,
        (
            "⚙️ Админ-панель\n\n"
            "Здесь можно управлять расписанием "
            "и смотреть участников тренировок."
        ),
        keyboard(admin_menu()),
    )


# ============================================================
# АДМИН — РАСПИСАНИЕ / УЧАСТНИКИ
# ============================================================

def show_admin_schedule(
    user_id,
    mode="participants",
):
    if user_id not in ADMIN_IDS:
        send_message(
            user_id,
            "Нет доступа.",
            keyboard(main_menu(user_id)),
        )
        return

    trainings = get_trainings()

    if not trainings:
        send_message(
            user_id,
            "Тренировок пока нет.",
            keyboard([
                [
                    button(
                        "⬅️ В админ-панель",
                        "secondary",
                    )
                ],
            ]),
        )
        return

    weekday_names = [
        "Пн",
        "Вт",
        "Ср",
        "Чт",
        "Пт",
        "Сб",
        "Вс",
    ]

    rows = []

    for training in trainings:
        count = get_registration_count(
            training["id"]
        )

        weekday = weekday_names[
            training["weekday"]
        ]

        label = (
            f"{weekday} "
            f"{training['start_time']} — "
            f"{training['title']} "
            f"({count}/{training['capacity']})"
        )

        rows.append([
            button(
                label,
                "primary",
            )
        ])

    rows.append([
        button(
            "⬅️ В админ-панель",
            "secondary",
        )
    ])

    set_state(
        user_id,
        "admin_training_select",
        {
            "mode": mode,
        },
    )

    title = (
        "👥 Выберите тренировку, "
        "чтобы посмотреть участников:"
        if mode == "participants"
        else
        "📅 Выберите тренировку:"
    )

    send_message(
        user_id,
        title,
        keyboard(rows),
    )


def find_admin_training(
    user_id,
    text,
):
    trainings = get_trainings()

    weekday_names = [
        "Пн",
        "Вт",
        "Ср",
        "Чт",
        "Пт",
        "Сб",
        "Вс",
    ]

    # Сначала точное совпадение
    for training in trainings:
        count = get_registration_count(
            training["id"]
        )

        expected = (
            f"{weekday_names[training['weekday']]} "
            f"{training['start_time']} — "
            f"{training['title']} "
            f"({count}/{training['capacity']})"
        )

        if text == expected:
            return training

    # Затем поиск без количества участников
    # — чтобы изменение количества не ломало кнопку.
    for training in trainings:
        prefix = (
            f"{weekday_names[training['weekday']]} "
            f"{training['start_time']} — "
            f"{training['title']}"
        )

        if text.startswith(prefix):
            return training

    return None


def show_training_participants(
    user_id,
    training,
):
    if user_id not in ADMIN_IDS:
        return

    count = get_registration_count(
        training["id"]
    )

    registrations = get_registrations(
        training["id"]
    )

    lines = [
        "👥 Участники тренировки",
        "",
        f"🏐 {training['title']}",
        f"📅 {training_date_text(training)}",
        f"⏰ {training['start_time']}–{training['end_time']}",
        f"👨‍🏫 Тренер: {training['coach']}",
        f"📊 Записано: {count}/{training['capacity']}",
        "",
    ]

    if not registrations:
        lines.append(
            "Пока никто не записался."
        )

    else:
        lines.append(
            "Список участников:"
        )

        for index, registration in enumerate(
            registrations,
            start=1,
        ):
            first_name = registration["first_name"]
            last_name = registration["last_name"]

            name = " ".join(
                part
                for part in [
                    first_name,
                    last_name,
                ]
                if part
            )

            if not name:
                name = (
                    f"VK ID "
                    f"{registration['user_id']}"
                )

            lines.append(
                f"{index}. {name}"
            )

    send_message(
        user_id,
        "\n".join(lines),
        keyboard([
            [
                button(
                    "⬅️ К тренировкам",
                    "secondary",
                )
            ],
            [
                button(
                    "⚙️ В админ-панель",
                    "primary",
                )
            ],
        ]),
    )


# ============================================================
# ДОБАВЛЕНИЕ ТРЕНИРОВКИ
# ============================================================

def start_add_training(user_id):
    if user_id not in ADMIN_IDS:
        return

    set_state(
        user_id,
        "add_training_day",
    )

    send_message(
        user_id,
        "➕ Добавление тренировки\n\nВыберите день:",
        keyboard([
            [button("Понедельник", "primary")],
            [button("Вторник", "primary")],
            [button("Среда", "primary")],
            [button("Четверг", "primary")],
            [button("Пятница", "primary")],
            [
                button(
                    "⬅️ В админ-панель",
                    "secondary",
                )
            ],
        ]),
    )


def save_new_training(
    user_id,
    data,
):
    try:
        conn = sqlite3.connect(
            "volley_wave.db"
        )

        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO trainings
            (
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
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
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
                "active",
            ),
        )

        conn.commit()
        conn.close()

        add_admin_log(
            user_id,
            "create_training",
            data["title"],
        )

        send_message(
            user_id,
            "✅ Тренировка добавлена.",
            keyboard(admin_menu()),
        )

        clear_state(user_id)

    except Exception as error:
        print(
            f"ADD TRAINING ERROR: {error}"
        )

        send_message(
            user_id,
            "❌ Не удалось добавить тренировку.",
            keyboard(admin_menu()),
        )

        clear_state(user_id)


# ============================================================
# ИНДИВИДУАЛЬНАЯ ТРЕНИРОВКА
# ============================================================

def start_individual_request(user_id):
    set_state(
        user_id,
        "individual_request",
    )

    send_message(
        user_id,
        (
            "🎯 Индивидуальная тренировка\n\n"
            "Напишите сообщение с удобным для вас "
            "днём и временем."
        ),
        keyboard([
            [back_button()],
        ]),
    )


def send_request_to_admins(
    user_id,
    text,
    request_type,
):
    user = get_user(user_id)

    if user:
        first_name = user["first_name"]
        last_name = user["last_name"]
    else:
        first_name = None
        last_name = None

    name = " ".join(
        part
        for part in [
            first_name,
            last_name,
        ]
        if part
    )

    if not name:
        name = f"VK ID {user_id}"

    if request_type == "individual":
        title = "🎯 Новая заявка на индивидуальную тренировку"
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
            keyboard([
                [
                    button(
                        "⚙️ Админ-панель",
                        "primary",
                    )
                ]
            ]),
        )


# ============================================================
# ВОПРОС
# ============================================================

def start_question(user_id):
    set_state(
        user_id,
        "question",
    )

    send_message(
        user_id,
        (
            "❓ Задать вопрос\n\n"
            "Напишите свой вопрос одним сообщением."
        ),
        keyboard([
            [back_button()],
        ]),
    )


# ============================================================
# ОБРАБОТКА СООБЩЕНИЙ
# ============================================================

def handle_message(
    user_id,
    text,
):
    register_user(user_id)

    text = (text or "").strip()

    state = get_state(user_id)
    state_name = state["state"]

    # --------------------------------------------------------
    # НАЗАД
    # --------------------------------------------------------

    if text == "⬅️ Назад":
        clear_state(user_id)

        send_message(
            user_id,
            "Главное меню:",
            keyboard(main_menu(user_id)),
        )
        return

    if text == "⬅️ В админ-панель":
        clear_state(user_id)
        show_admin_panel(user_id)
        return

    if text == "⚙️ В админ-панель":
        clear_state(user_id)
        show_admin_panel(user_id)
        return

    # --------------------------------------------------------
    # ГЛАВНОЕ МЕНЮ
    # --------------------------------------------------------

    if text == "🏐 Записаться":
        show_booking_categories(user_id)
        return

    if text == "📅 Расписание":
        show_schedule_categories(user_id)
        return

    if text == "👤 Мои тренировки":
        clear_state(user_id)
        show_my_trainings(user_id)
        return

    if text == "💰 Цены":
        clear_state(user_id)
        show_prices(user_id)
        return

    if text == "📍 Где тренируемся":
        clear_state(user_id)
        show_locations(user_id)
        return

    if text == "🎯 Индивидуальная тренировка":
        start_individual_request(user_id)
        return

    if text == "❓ Задать вопрос":
        start_question(user_id)
        return

    # --------------------------------------------------------
    # АДМИН
    # --------------------------------------------------------

    if text == "⚙️ Админ-панель":
        show_admin_panel(user_id)
        return

    if user_id in ADMIN_IDS:

        if text == "👤 Пользовательский режим":
            clear_state(user_id)

            send_message(
                user_id,
                (
                    "👤 Пользовательский режим\n\n"
                    "Теперь доступны все обычные функции."
                ),
                keyboard(main_menu(user_id)),
            )
            return

        if text == "👥 Участники тренировок":
            show_admin_schedule(
                user_id,
                mode="participants",
            )
            return

        if text == "📅 Управление расписанием":
            show_admin_schedule(
                user_id,
                mode="schedule",
            )
            return

        if text == "➕ Добавить тренировку":
            start_add_training(user_id)
            return

    # --------------------------------------------------------
    # СОСТОЯНИЕ: ВЫБОР КАТЕГОРИИ ДЛЯ ЗАПИСИ
    # --------------------------------------------------------

    if state_name == "booking_category":

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

    # --------------------------------------------------------
    # СОСТОЯНИЕ: ВЫБОР ДНЯ
    # --------------------------------------------------------

    if state_name == "booking_day":

        weekday_names = {
            "Понедельник": 0,
            "Вторник": 1,
            "Среда": 2,
            "Четверг": 3,
            "Пятница": 4,
            "Суббота": 5,
            "Воскресенье": 6,
        }

        if text in weekday_names:
            show_booking_trainings(
                user_id,
                state["data"]["category"],
                weekday_names[text],
            )
            return

    # --------------------------------------------------------
    # СОСТОЯНИЕ: ВЫБОР ТРЕНИРОВКИ
    # --------------------------------------------------------

    if state_name == "booking_training":

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

    # --------------------------------------------------------
    # ПОДТВЕРЖДЕНИЕ ЗАПИСИ
    # --------------------------------------------------------

    if state_name == "booking_confirm":

        if text == "✅ Записаться":
            training_id = state["data"].get(
                "training_id"
            )

            if training_id:
                book_training(
                    user_id,
                    training_id,
                )
                return

    # --------------------------------------------------------
    # МОИ ТРЕНИРОВКИ — ОТМЕНА
    # --------------------------------------------------------

    training = find_my_training_from_button(
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
            user_id,
            text,
        )

        if training:
            mode = state["data"].get(
                "mode",
                "participants",
            )

            if mode == "participants":
                show_training_participants(
                    user_id,
                    training,
                )
            else:
                show_training_participants(
                    user_id,
                    training,
                )

            return

    # --------------------------------------------------------
    # АДМИН — ДОБАВЛЕНИЕ ТРЕНИРОВКИ
    # --------------------------------------------------------

    if (
        user_id in ADMIN_IDS
        and state_name == "add_training_day"
    ):
        weekday_names = {
            "Понедельник": 0,
            "Вторник": 1,
            "Среда": 2,
            "Четверг": 3,
            "Пятница": 4,
        }

        if text in weekday_names:
            set_state(
                user_id,
                "add_training_time",
                {
                    "weekday": weekday_names[text],
                },
            )

            send_message(
                user_id,
                (
                    "Введите время в формате:\n"
                    "17:00-19:00"
                ),
                keyboard([
                    [
                        button(
                            "⬅️ В админ-панель",
                            "secondary",
                        )
                    ]
                ]),
            )
            return

    if (
        user_id in ADMIN_IDS
        and state_name == "add_training_time"
    ):
        try:
            start_time, end_time = text.split("-")

            start_time = start_time.strip()
            end_time = end_time.strip()

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
                keyboard([
                    [
                        button(
                            "⬅️ В админ-панель",
                            "secondary",
                        )
                    ]
                ]),
            )
            return

        except Exception:
            send_message(
                user_id,
                "❌ Формат должен быть, например: 17:00-19:00",
                keyboard([
                    [
                        button(
                            "⬅️ В админ-панель",
                            "secondary",
                        )
                    ]
                ]),
            )
            return

    if (
        user_id in ADMIN_IDS
        and state_name == "add_training_title"
    ):
        data = {
            **state["data"],
            "title": text,
            "category": "adults",
            "age_group": "18+",
            "level": "General",
            "format": "Группа",
            "coach": "Алексей",
            "capacity": 8,
            "price": 1200,
        }

        save_new_training(
            user_id,
            data,
        )
        return

    # --------------------------------------------------------
    # ИНДИВИДУАЛЬНАЯ ТРЕНИРОВКА
    # --------------------------------------------------------

    if state_name == "individual_request":

        send_request_to_admins(
            user_id,
            text,
            "individual",
        )

        clear_state(user_id)

        send_message(
            user_id,
            (
                "✅ Заявка отправлена тренеру.\n\n"
                "С вами свяжутся для согласования "
                "времени и деталей."
            ),
            keyboard(main_menu(user_id)),
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

        clear_state(user_id)

        send_message(
            user_id,
            (
                "✅ Вопрос отправлен.\n\n"
                "Мы постараемся ответить вам как можно скорее."
            ),
            keyboard(main_menu(user_id)),
        )
        return

    # --------------------------------------------------------
    # РАСПИСАНИЕ
    # --------------------------------------------------------

    if state_name is None:

        if text == "👶 Дети":
            show_full_week_schedule(
                user_id,
                "children",
            )
            return

        if text == "🧑 Взрослые":
            show_full_week_schedule(
                user_id,
                "adults",
            )
            return

    # --------------------------------------------------------
    # ЕСЛИ НЕ НАШЛИ
    # --------------------------------------------------------

    send_message(
        user_id,
        "Выберите действие из меню:",
        keyboard(main_menu(user_id)),
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

    # Проверка VK confirmation
    if data.get("type") == "confirmation":
        return VK_CONFIRMATION_TOKEN

    # Проверка secret
    if (
        VK_SECRET_KEY
        and data.get("secret") != VK_SECRET_KEY
    ):
        return "invalid secret", 403

    obj = data.get(
        "object",
        {},
    )

    # VK Callback API 5.199:
    # сообщение находится внутри object["message"]
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
            f"VK MESSAGE: user_id={user_id}, text={text}"
        )

        try:
            handle_message(
                int(user_id),
                text,
            )

        except Exception as error:
            print(
                f"HANDLER ERROR: {error}"
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
