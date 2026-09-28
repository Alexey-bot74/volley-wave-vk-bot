import os
from flask import Flask, request

app = Flask(__name__)

CONFIRMATION_TOKEN = os.getenv("VK_CONFIRMATION_TOKEN")
SECRET_KEY = os.getenv("VK_SECRET_KEY")

@app.route("/callback", methods=["POST"])
def callback():
    data = request.json

    # Проверка секретного ключа ВК
    if SECRET_KEY and data.get("secret") != SECRET_KEY:
        return "invalid secret", 403

    # Подтверждение сервера ВК
    if data.get("type") == "confirmation":
        return CONFIRMATION_TOKEN or ""

    # Пока просто подтверждаем получение события
    return "ok"

@app.route("/", methods=["GET"])
def home():
    return "VOLLEY WAVE VK BOT IS RUNNING"

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
