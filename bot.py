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

print("===================================")
print("DATABASE CHECK")

try:
    all_trainings = get_trainings()
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

except Exception as error:
    print("DATABASE ERROR:", error)

print("===================================")


DAYS = {
    1: "ПОНЕДЕЛЬНИК",
    2: "ВТОРНИК",
    3: "СРЕДА",
    4: "ЧЕТВЕРГ",
    5: "ПЯТНИЦА",
    6: "СУББОТА",
    7: "ВОСКРЕСЕНЬЕ"
}


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


def make_keyboard(buttons):
    return json.dumps(
        {
            "one_time": False,
            "buttons": buttons
        },
        ensure_ascii=False
    )


def main_keyboard():
    buttons = [
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
            }
        ]
    ]

    return make_keyboard(buttons)


def days_keyboard():
    buttons = [
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

    return make_keyboard(buttons)


def trainings_keyboard(trainings):
    buttons = []

    for training in trainings:
        label = f"{training['id']}. {training['time']}"

        buttons.append(
            [
                {
                    "action": {
                        "type": "text",
                        "label": label
                    }
                }
            ]
        )

    buttons.append(
        [
            {
                "action": {
                    "type": "text",
                    "label": "⬅️ Назад к дням"
                }
            }
        ]
    )

    return make_keyboard(buttons)


def get_day_number(text):
    days = {
        "Понедельник": 1,
        "Вторник": 2,
        "Среда": 3,
        "Четверг": 4,
        "Пятница": 5
    }

    return days.get(text)


def get_trainings_by_day(day_number):
    trainings = get_trainings()

    return [
        training
        for training in trainings
        if training["day_of_week"] == day_number
    ]


def format_training_title(training):
    title = training["title"]

    if training["level"]:
        title += f" — {training['level']}"

    if training["age_group"]:
        title += f" ({training['age_group']})"

    return title


def get_training_by_id(training_id):
    trainings = get_trainings()

    for training in trainings:
        if training["id"] == training_id:
            return training

    return None


def get_training_info(training):
    registered = get_registration_count(training["id"])
    capacity = training["capacity"]
    available = max(capacity - registered, 0)

    title = format_training_title(training)

    text = (
        f"🏐 {title}\n\n"
        f"🕐 Время: {training['time']}\n"
        f"💰 Стоимость: {training['price']} ₽\n"
        f"👥 Мест свободно: {available} из {capacity}\n\n"
        f"👤 Сейчас записано: {registered}\n\n"
        f"Пока здесь будет информация о записи."
    )

    return text


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
            lines.append(f"━━ {DAYS.get(day, '')} ━━")

        registered = get_registration_count(training["id"])
        capacity = training["capacity"]
        available = max(capacity - registered, 0)

        title = format_training_title(training)

        lines.append("")
        lines.append(
            f"🕐 {training['time']} — {title}"
        )

        lines.append(
            f"💰 {training['price']} ₽  |  "
            f"👥 свободно: {available}"
        )

    return "\n".join(lines)


@app.route("/callback", methods=["POST"])
def callback():

    data = request.json

    print("VK EVENT:", data)

    if SECRET_KEY and data.get("secret") != SECRET_KEY:
        return "invalid secret", 403

    if data.get("type") == "confirmation":
        return CONFIRMATION_TOKEN or ""

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

    if text == "Привет" or text.lower() == "привет":

        send_message(
            user_id,
            "Привет! 👋\n\n"
            "Добро пожаловать в VOLLEY WAVE 🏐\n"
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

    elif text in [
        "Понедельник",
        "Вторник",
        "Среда",
        "Четверг",
        "Пятница"
    ]:

        day_number = get_day_number(text)
        trainings = get_trainings_by_day(day_number)

        if not trainings:

            send_message(
                user_id,
                "На этот день тренировок пока нет.",
                days_keyboard()
            )

        else:

            message_text = (
                f"🏐 {text}\n\n"
                "Выберите тренировку:"
            )

            send_message(
                user_id,
                message_text,
                trainings_keyboard(trainings)
            )


    # =========================
    # ВОЗВРАТ К ДНЯМ
    # =========================

    elif text == "⬅️ Назад к дням":

        send_message(
            user_id,
            "🏐 Запись на тренировку\n\n"
            "Выберите день:",
            days_keyboard()
        )


    # =========================
    # НАЗАД В ГЛАВНОЕ МЕНЮ
    # =========================

    elif text == "⬅️ Назад":

        send_message(
            user_id,
            "Главное меню:",
            main_keyboard()
        )


    # =========================
    # ВЫБОР ТРЕНИРОВКИ
    # =========================

    elif "." in text and text.split(".")[0].isdigit():

        try:
            training_id = int(text.split(".")[0])

            training = get_training_by_id(training_id)

            if training:

                info = get_training_info(training)

                send_message(
                    user_id,
                    info,
                    main_keyboard()
                )

            else:

                send_message(
                    user_id,
                    "Не удалось найти эту тренировку.",
                    main_keyboard()
                )

        except Exception as error:

            print("TRAINING SELECTION ERROR:", error)

            send_message(
                user_id,
                "Произошла ошибка при выборе тренировки.",
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
            "Стоимость каждой тренировки указана в расписании.",
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


@app.route("/", methods=["GET"])
def home():
    return "VOLLEY WAVE VK BOT IS RUNNING"


if __name__ == "__main__":

    port = int(os.getenv("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port
    )
