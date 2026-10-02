import os
import requests
from flask import Flask, request

app = Flask(__name__)

CONFIRMATION_TOKEN = os.getenv("VK_CONFIRMATION_TOKEN")
SECRET_KEY = os.getenv("VK_SECRET_KEY")
VK_TOKEN = os.getenv("VK_TOKEN")

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
                {"action": {"type": "text", "label": "🏐 Записаться"}},
                {"action": {"type": "text", "label": "📅 Расписание"}}
            ],
            [
                {"action": {"type": "text", "label": "👤 Мои тренировки"}},
                {"action": {"type": "text", "label": "💰 Цены"}}
            ],
            [
                {"action": {"type": "text", "label": "👶 Детские группы"}},
                {"action": {"type": "text", "label": "📍 Где тренируемся"}}
            ],
            [
                {"action": {"type": "text", "label": "❓ Задать вопрос"}}
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
        user_id = message.get("message", {}).get("from_id")

        if user_id:
            send_message(
                user_id,
                "Привет! 👋\n\n"
                "Добро пожаловать в VOLLEY WAVE 🏐\n"
                "Выбери нужный раздел:",
                main_keyboard()
            )

        return "ok"

    return "ok"

@app.route("/", methods=["GET"])
def home():
    return "VOLLEY WAVE VK BOT IS RUNNING"

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
