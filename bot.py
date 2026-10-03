import os
import json
import requests
from flask import Flask, request

from database import (
    init_db,
    get_trainings,
    get_registration_count
)

app = Flask(__name__)

CONFIRMATION_TOKEN = os.getenv("VK_CONFIRMATION_TOKEN")
SECRET_KEY = os.getenv("VK_SECRET_KEY")
VK_TOKEN = os.getenv("VK_TOKEN")

init_db()


# =========================
# ПРОВЕРКА БАЗЫ
# =========================

try:
    all_trainings = get_trainings()

    print("===================================")
    print("DATABASE CHECK")
    print("TRAININGS COUNT:", len(all_trainings))

    for training in all_trainings:
        print(
            training["id"],
            training["day_of_week"],
            training["time"],
            training["title"],
            training["price"],
            training["capacity"]
        )

    print("===================================")

except Exception as error:
    print("DATABASE ERROR:", error)


# =========================
# ДНИ НЕДЕЛИ
# =========================

DAYS = {
    1: "ПОНЕДЕЛЬНИК",
    2: "ВТОРНИК",
    3: "СРЕДА",
    4: "ЧЕТВЕРГ",
    5: "ПЯТНИЦА",
    6: "СУББОТА",
    7: "ВОСКРЕСЕНЬЕ"
}


DAY_NUMBERS = {
    "Понедельник": 1,
    "Вторник": 2,
    "Среда": 3,
    "Четверг": 4,
    "Пятница": 5
}


# =========================
# ОТПРАВКА СООБЩЕНИЯ
# =========================

def send_message(user_id, message, keyboard=None):

    url = "https://api.vk.com/method/messages.send"

    params = {
        "access_token": VK_TOKEN,
        "v": "5.199",
        "user_id": user_id,
        "random_id": 0,
        "message": message
    }

    if keyboard:
        params["keyboard"] = keyboard

    response = requests.get(url, params=params)

    print("VK RESPONSE:", response.text)


# =========================
# ГЛАВНОЕ МЕНЮ
# =========================

def main_keyboard():

    return json.dumps({
        "one_time": False,
        "buttons": [
            [
                {
                    "action": {
                        "type": "text",
                        "label": "🏐 Записаться"
                    }
                },
                {
                    "action": {
                        "type": "text",
                        "label": "📅 Расписание"
                    }
                }
            ],
            [
                {
                    "action": {
                        "type": "text",
                        "label": "👤 Мои тренировки"
                    }
                },
                {
                    "action": {
                        "type": "text",
                        "label": "💰 Цены"
                    }
                }
            ],
            [
                {
                    "action": {
                        "type": "text",
                        "label": "👶 Детские группы"
                    }
                },
                {
                    "action": {
                        "type": "text",
                        "label": "📍 Где тренируемся"
                    }
                }
            ],
            [
                {
                    "action": {
                        "type": "text",
                        "label": "❓ Задать вопрос"
                    }
                ]
            ]
        ]
    }, ensure_ascii=False)


# =========================
# КНОПКИ ДНЕЙ
# =========================

def days_keyboard():

    return json.dumps({
        "one_time": False,
        "buttons": [
            [
                {
                    "action": {
                        "type": "text",
                        "label": "Понедельник"
                    }
                },
                {
                    "action": {
                        "type": "text",
                        "label": "Вторник"
                    }
                }
            ],
            [
                {
                    "action": {
                        "type": "text",
                        "label": "Среда"
                    }
                },
                {
                    "action": {
                        "type": "text",
                        "label": "Четверг"
                    }
                }
            ],
            [
                {
                    "action": {
                        "type": "text",
                        "label": "Пятница"
                    }
                }
            ],
            [
                {
                    "action": {
                        "type": "text",
                        "label": "⬅️ Назад"
                    }
                }
            ]
        ]
    }, ensure_ascii=False)


# =========================
# КНОПКИ ТРЕНИРОВОК
# =========================

def trainings_keyboard(trainings):

    buttons = []

    for training in trainings:

        title = training["title"]

        if training["level"]:
            title += f" — {training['level']}"

        if training["age_group"]:
            title += f" ({training['age_group']})"

        label = f"{training['id']}. {training['time']} — {title}"

        buttons.append([
            {
                "action": {
                    "type": "text",
                    "label": label[:40]
                }
            }
        ])

    buttons.append([
        {
            "action": {
                "type": "text",
                "label": "⬅️ Назад к дням"
            }
        }
    ])

    return json.dumps({
        "one_time": False,
        "buttons": buttons
    }, ensure_ascii=False)


# =========================
# ФОРМАТИРОВАНИЕ РАСПИСАНИЯ
# =========================

def format_schedule():

    trainings = get_trainings()

    print("FORMAT SCHEDULE - TRAININGS:", len(trainings))

    if not trainings:
        return "📅 Расписание пока пустое."

    lines = [
        "📅 РАСПИСАНИЕ VOLLEY WAVE",
        "",
        "Базовое расписание на неделю:"
    ]

    current_day = None

    for training in trainings:

        day = training["day_of_week"]

        if day != current_day:

            current_day = day

            lines.append("")
            lines.append(
                f"━━ {DAYS.get(day, '')} ━━"
            )

        registered = get_registration_count(
            training["id"]
        )

        capacity = training["capacity"]

        available = max(
            capacity - registered,
            0
        )

        title = training["title"]

        if training["level"]:
            title += f" — {training['level']}"

        if training["age_group"]:
            title += f" ({training['age_group']})"

        lines.append("")
        lines.append(
            f"🕐 {training['time']} — {title}"
        )

        lines.append(
            f"💰 {training['price']} ₽  |  "
            f"👥 свободно: {available}"
        )

    return "\n".join(lines)


# =========================
# ИНФОРМАЦИЯ О ТРЕНИРОВКЕ
# =========================

def get_training_info(training_id):

    trainings = get_trainings()

    training = None

    for item in trainings:

        if item["id"] == training_id:
            training = item
            break

    if not training:
        return None

    registered = get_registration_count(
        training_id
    )

    capacity = training["capacity"]

    available = max(
        capacity - registered,
        0
    )

    title = training["title"]

    if training["level"]:
        title += f" — {training['level']}"

    if training["age_group"]:
        title += f" ({training['age_group']})"

    text = (
        "🏐 ТРЕНИРОВКА\n\n"
        f"🕐 Время: {training['time']}\n"
        f"🏐 {title}\n"
        f"💰 Стоимость: {training['price']} ₽\n"
        f"👥 Мест всего: {capacity}\n"
        f"🟢 Свободно: {available}\n\n"
    )

    text += (
        "👤 Уже записаны:\n"
        "Пока записей нет."
    )

    return text


# =========================
# CALLBACK
# =========================

@app.route("/callback", methods=["POST"])
def callback():

    data = request.json

    print("VK EVENT:", data)

    # Проверка секретного ключа
    if SECRET_KEY and data.get("secret") != SECRET_KEY:
        return "invalid secret", 403

    # Подтверждение сервера VK
    if data.get("type") == "confirmation":
        return CONFIRMATION_TOKEN or ""

    # Нас интересуют только новые сообщения
    if data.get("type") != "message_new":
        return "ok"

    obj = data.get("object", {})

    message = obj.get("message", {})

    user_id = message.get("from_id")

    text = message.get("text", "").strip()

    print("USER ID:", user_id)
    print("TEXT:", text)

    if not user_id:
        return "ok"


    # =========================
    # ПРИВЕТСТВИЕ
    # =========================

    if text.lower() == "привет":

        send_message(
            user_id,
            "Привет! 👋\n\n"
            "Добро пожаловать в VOLLEY WAVE 🏐\n\n"
            "Выберите нужный раздел:",
            main_keyboard()
        )


    # =========================
    # ЗАПИСАТЬСЯ
    # =========================

    elif text == "🏐 Записаться":

        send_message(
            user_id,
            "🏐 Запись на тренировку\n\n"
            "Выберите день:",
            days_keyboard()
        )


    # =========================
    # ВЫБОР ДНЯ
    # =========================

    elif text in DAY_NUMBERS:

        selected_day = DAY_NUMBERS[text]

        trainings = [
            training
            for training in get_trainings()
            if training["day_of_week"] == selected_day
        ]

        if not trainings:

            send_message(
                user_id,
                "В этот день тренировок пока нет.",
                days_keyboard()
            )

        else:

            send_message(
                user_id,
                f"🏐 {text.upper()}\n\n"
                "Выберите тренировку:",
                trainings_keyboard(trainings)
            )


    # =========================
    # НАЗАД К ДНЯМ
    # =========================

    elif text == "⬅️ Назад к дням":

        send_message(
            user_id,
            "🏐 Выберите день:",
            days_keyboard()
        )


    # =========================
    # ВЫБОР ТРЕНИРОВКИ
    # =========================

    elif text[:1].isdigit() and "." in text:

        try:

            training_id = int(
                text.split(".")[0]
            )

            training_info = get_training_info(
                training_id
            )

            if training_info:

                send_message(
                    user_id,
                    training_info,
                    main_keyboard()
                )

            else:

                send_message(
                    user_id,
                    "Не удалось найти эту тренировку.",
                    main_keyboard()
                )

        except Exception as error:

            print(
                "TRAINING SELECTION ERROR:",
                error
            )

            send_message(
                user_id,
                "Не удалось выбрать тренировку.",
                main_keyboard()
            )


    # =========================
    # РАСПИСАНИЕ
    # =========================

    elif text == "📅 Расписание":

        schedule = format_schedule()

        send_message(
            user_id,
            schedule,
            main_keyboard()
        )


    # =========================
    # МОИ ТРЕНИРОВКИ
    # =========================

    elif text == "👤 Мои тренировки":

        send_message(
            user_id,
            "👤 Мои тренировки\n\n"
            "Здесь будут отображаться ваши записи.",
            main_keyboard()
        )


    # =========================
    # ЦЕНЫ
    # =========================

    elif text == "💰 Цены":

        send_message(
            user_id,
            "💰 Цены\n\n"
            "Стоимость тренировок указана в расписании.",
            main_keyboard()
        )


    # =========================
    # ДЕТСКИЕ ГРУППЫ
    # =========================

    elif text == "👶 Детские группы":

        send_message(
            user_id,
            "👶 Детские группы\n\n"
            "Здесь появится информация о детских группах.",
            main_keyboard()
        )


    # =========================
    # ГДЕ ТРЕНИРУЕМСЯ
    # =========================

    elif text == "📍 Где тренируемся":

        send_message(
            user_id,
            "📍 Где тренируемся\n\n"
            "Здесь появится информация о площадках VOLLEY WAVE.",
            main_keyboard()
        )


    # =========================
    # ЗАДАТЬ ВОПРОС
    # =========================

    elif text == "❓ Задать вопрос":

        send_message(
            user_id,
            "❓ Задать вопрос\n\n"
            "Напишите свой вопрос следующим сообщением.",
            main_keyboard()
        )


    # =========================
    # НЕИЗВЕСТНОЕ СООБЩЕНИЕ
    # =========================

    else:

        send_message(
            user_id,
            "Я пока не понял сообщение 🤔\n\n"
            "Выберите раздел из меню:",
            main_keyboard()
        )

    return "ok"


# =========================
# ГЛАВНАЯ СТРАНИЦА
# =========================

@app.route("/", methods=["GET"])
def home():

    return "VOLLEY WAVE VK BOT IS RUNNING"


# =========================
# ЗАПУСК
# =========================

if __name__ == "__main__":

    port = int(
        os.getenv("PORT", 10000)
    )

    app.run(
        host="0.0.0.0",
        port=port
    )

