import os
import requests
from flask import Flask, request
from database import init_db

app = Flask(__name__)

CONFIRMATION_TOKEN = os.getenv("VK_CONFIRMATION_TOKEN")
SECRET_KEY = os.getenv("VK_SECRET_KEY")
VK_TOKEN = os.getenv("VK_TOKEN")

init_db()

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

def main_keyboard():
    return """{
        "one_time": false,
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
                }
            ]
        ]
    }"""

@app.route("/callback", methods=["POST"])
def callback():
    data = request.json

    if SECRET_KEY and data.get("secret") != SECRET_KEY:
        return "invalid secret", 403

    if data.get("type") == "confirmation":
        return CONFIRMATION_TOKEN or ""

    if data.get("type") == "message_new":

        message = data.get("object", {})
        vk_message = message.get("message", {})

        user_id = vk_message.get("from_id")
        text = vk_message.get("text", "").strip()

        if user_id:

            if text == "🏐 Записаться":
                send_message(
                    user_id,
                    "🏐 Запись на тренировку\n\n"
                    "Здесь можно будет выбрать подходящую тренировку."
                )

            elif text == "📅 Расписание":
                send_message(
                    user_id,
                    "📅 Расписание\n\n"
                    "Скоро здесь появится актуальное расписание тренировок."
                )

            elif text == "👤 Мои тренировки":
                send_message(
                    user_id,
                    "👤 Мои тренировки\n\n"
                    "Здесь будут отображаться ваши записи на тренировки."
                )

            elif text == "💰 Цены":
                send_message(
                    user_id,
                    "💰 Цены\n\n"
                    "Здесь появится актуальная стоимость тренировок."
                )

            elif text == "👶 Детские группы":
                send_message(
                    user_id,
                    "👶 Детские группы\n\n"
                    "Здесь появится информация о детских группах."
                )

            elif text == "📍 Где тренируемся":
                send_message(
                    user_id,
                    "📍 Где тренируемся\n\n"
                    "Здесь появится информация о площадках VOLLEY WAVE."
                )

            elif text == "❓ Задать вопрос"


send_message(
                    user_id,
                    "❓ Задать вопрос\n\n"
                    "Напишите свой вопрос следующим сообщением."
                )

            else:
                send_message(
                    user_id,
                    "Привет! 👋\n\n"
                    "Добро пожаловать в VOLLEY WAVE 🏐\n"
                    "Выберите нужный раздел:",
                    main_keyboard()
                )

        return "ok"

    return "ok"

@app.route("/", methods=["GET"])
def home():
    return "VOLLEY WAVE VK BOT IS RUNNING"

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port):
