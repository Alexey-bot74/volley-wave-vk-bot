import os
import requests
from flask import Flask, request

app = Flask(__name__)

CONFIRMATION_TOKEN = os.getenv("VK_CONFIRMATION_TOKEN")
SECRET_KEY = os.getenv("VK_SECRET_KEY")
VK_TOKEN = os.getenv("VK_TOKEN")

def send_message(user_id, message):
    url = "https://api.vk.com/method/messages.send"

    params = {
        "access_token": VK_TOKEN,
        "v": "5.199",
        "user_id": user_id,
        "random_id": 0,
        "message": message
    }

    response = requests.get(url, params=params)
    print("VK RESPONSE:", response.text)

@app.route("/callback", methods=["POST"])
def callback():
    data = request.json

    # Проверка секретного ключа ВК
    if SECRET_KEY and data.get("secret") != SECRET_KEY:
        return "invalid secret", 403

    # Подтверждение сервера ВК
    if data.get("type") == "confirmation":
        return CONFIRMATION_TOKEN or ""

    # Новое сообщение
    if data.get("type") == "message_new":
        message = data.get("object", {})
        user_id = message.get("from_id")

        if user_id:
            send_message(
                user_id,
                "Привет! 👋\n\nЭто бот школы пляжного волейбола VOLLEY WAVE 🏐"
            )

        return "ok"

    return "ok"

@app.route("/", methods=["GET"])
def home():
    return "VOLLEY WAVE VK BOT IS RUNNING"

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
