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
    app.run(host="0.0.0.0", port=port)
