import os
import json
import requests
from flask import Flask, request

from database import (
    init_db,
    get_trainings,
    get_registration_count,
    get_registrations,
    add_registration,
    get_user_registrations,
    delete_registration
)


app = Flask(__name__)

CONFIRMATION_TOKEN = os.getenv("VK_CONFIRMATION_TOKEN")
SECRET_KEY = os.getenv("VK_SECRET_KEY")
VK_TOKEN = os.getenv("VK_TOKEN")


init_db()


DAYS = {
    1: "ПОНЕДЕЛЬНИК",
    2: "ВТОРНИК",
    3: "СРЕДА",
    4: "ЧЕТВЕРГ",
    5: "ПЯТНИЦА",
    6: "СУББОТА",
    7: "ВОСКРЕСЕНЬЕ"
}


DAY_NAMES = {
    "Понедельник": 1,
    "Вторник": 2,
    "Среда": 3,
    "Четверг": 4,
    "Пятница": 5
}


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


# =========================================================
# VK
# =========================================================

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

    try:
        response = requests.get(
            url,
            params=params,
            timeout=15
        )

        print("VK RESPONSE:", response.text)

    except Exception as error:
        print("VK SEND ERROR:", error)


def make_keyboard(buttons):

    return json.dumps(
        {
            "one_time": False,
            "buttons": buttons
        },
        ensure_ascii=False
    )


# =========================================================
# ГЛАВНОЕ МЕНЮ
# =========================================================

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


# =========================================================
# ДНИ
# =========================================================

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
                    "label": "🏠 Главное меню"
                }
            }
        ]

    ]

    return make_keyboard(buttons)


# =========================================================
# ТРЕНИРОВКИ
# =========================================================

def trainings_keyboard(trainings):

    buttons = []

    for training in trainings:

        registered = get_registration_count(
            training["id"]
        )

        available = max(
            training["capacity"] - registered,
            0
        )

        label = (
            f"{training['id']}. "
            f"{training['time']} "
            f"({available} мест)"
        )

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


def training_keyboard(training_id, available):

    buttons = []

    if available > 0:

        buttons.append(
            [
                {
                    "action": {
                        "type": "text",
                        "label": f"✅ Записаться #{training_id}"
                    }
                }
            ]
        )

    buttons.extend(
        [
            [
                {
                    "action": {
                        "type": "text",
                        "label": "⬅️ Назад к тренировкам"
                    }
                }
            ],
            [
                {
                    "action": {
                        "type": "text",
                        "label": "🏠 Главное меню"
                    }
                }
            ]
        ]
    )

    return make_keyboard(buttons)


# =========================================================
# МОИ ТРЕНИРОВКИ
# =========================================================

def my_trainings_keyboard(registrations):

    buttons = []

    for registration in registrations:

        label = (
            f"❌ Отменить #{registration['training_id']}"
        )

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
                    "label": "🏠 Главное меню"
                }
            }
        ]
    )

    return make_keyboard(buttons)


# =========================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =========================================================

def get_day_number(text):

    return DAY_NAMES.get(text)


def get_trainings_by_day(day_number):

    trainings = get_trainings()

    return [
        training
        for training in trainings
        if training["day_of_week"] == day_number
    ]


def get_training_by_id(training_id):

    trainings = get_trainings()

    for training in trainings:

        if training["id"] == training_id:
            return training

    return None


def format_training_title(training):

    title = training["title"]

    if training["level"]:
        title += f" — {training['level']}"

    if training["age_group"]:
        title += f" ({training['age_group']})"

    return title


def get_vk_user_name(user_id):

    url = "https://api.vk.com/method/users.get"

    params = {
        "access_token": VK_TOKEN,
        "v": "5.199",
        "user_ids": user_id
    }

    try:

        response = requests.get(
            url,
            params=params,
            timeout=15
        )

        data = response.json()

        if data.get("response"):

            user = data["response"][0]

            name = (
                f"{user.get('first_name', '')} "
                f"{user.get('last_name', '')}"
            ).strip()

            if name:
                return name

    except Exception as error:

        print("VK USER ERROR:", error)

    return f"Участник {user_id}"


# =========================================================
# ИНФОРМАЦИЯ О ТРЕНИРОВКЕ
# =========================================================

def get_training_info(training):

    registered = get_registration_count(
        training["id"]
    )

    capacity = training["capacity"]

    available = max(
        capacity - registered,
        0
    )

    title = format_training_title(
        training
    )

    lines = [

        f"🏐 {title}",
        "",
        f"🕐 Время: {training['time']}",
        f"💰 Стоимость: {training['price']} ₽",
        f"👥 Свободно: {available} из {capacity}",
        ""
    ]

    if registered == 0:

        lines.append(
            "👤 Пока никто не записан."
        )

    else:

        lines.append(
            f"👤 Уже записались: {registered}"
        )

        lines.append("")

        registrations = get_registrations(
            training["id"]
        )

        for number, registration in enumerate(
            registrations,
            1
        ):

            name = registration["name"]

            if not name:
                name = f"Участник {registration['user_id']}"

            lines.append(
                f"{number}. {name}"
            )

    if available == 0:

        lines.append("")
        lines.append(
            "❌ Свободных мест нет."
        )

    return "\n".join(lines), available


# =========================================================
# РАСПИСАНИЕ
# =========================================================

def format_schedule():

    trainings = get_trainings()

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

        available = max(
            training["capacity"] - registered,
            0
        )

        title = format_training_title(
            training
        )

        lines.append("")

        lines.append(
            f"🕐 {training['time']} — {title}"
        )

        lines.append(
            f"💰 {training['price']} ₽  |  "
            f"👥 свободно: {available}"
        )

    return "\n".join(lines)


# =========================================================
# МОИ ТРЕНИРОВКИ
# =========================================================

def format_my_trainings(user_id):

    registrations = get_user_registrations(
        user_id
    )

    if not registrations:

        return (
            "👤 МОИ ТРЕНИРОВКИ\n\n"
            "У вас пока нет записей."
        ), None

    lines = [
        "👤 МОИ ТРЕНИРОВКИ",
        ""
    ]

    for registration in registrations:

        day = DAYS.get(
            registration["day_of_week"],
            ""
        )

        title = (
            f"{registration['title']}"
        )

        if registration["level"]:
            title += (
                f" — {registration['level']}"
            )

        if registration["age_group"]:
            title += (
                f" ({registration['age_group']})"
            )

        lines.append(
            f"🏐 {day}"
        )

        lines.append(
            f"🕐 {registration['time']}"
        )

        lines.append(
            f"{title}"
        )

        lines.append(
            f"💰 {registration['price']} ₽"
        )

        lines.append("")

    return "\n".join(lines), registrations


# =========================================================
# CALLBACK
# =========================================================

@app.route("/callback", methods=["POST"])
def callback():

    data = request.json

    print("VK EVENT:", data)

    if SECRET_KEY:

        if data.get("secret") != SECRET_KEY:

            return "invalid secret", 403

    if data.get("type") == "confirmation":

        return CONFIRMATION_TOKEN or ""

    if data.get("type") != "message_new":

        return "ok"

    obj = data.get(
        "object",
        {}
    )

    message = obj.get(
        "message",
        {}
    )

    user_id = message.get(
        "from_id"
    )

    text = message.get(
        "text",
        ""
    ).strip()

    print("USER ID:", user_id)
    print("TEXT:", text)

    if not user_id:

        return "ok"


    # =====================================================
    # ПРИВЕТ
    # =====================================================

    if text.lower() == "привет":

        send_message(

            user_id,

            "Привет! 👋\n\n"
            "Добро пожаловать в VOLLEY WAVE 🏐\n"
            "Выберите нужный раздел:",

            main_keyboard()
        )


    # =====================================================
    # ЗАПИСАТЬСЯ
    # =====================================================

    elif text == "🏐 Записаться":

        send_message(

            user_id,

            "🏐 Запись на тренировку\n\n"
            "Выберите день:",

            days_keyboard()
        )


    # =====================================================
    # ВЫБОР ДНЯ
    # =====================================================

    elif text in DAY_NAMES:

        day_number = get_day_number(
            text
        )

        trainings = get_trainings_by_day(
            day_number
        )

        if not trainings:

            send_message(

                user_id,

                "На этот день тренировок пока нет.",

                days_keyboard()
            )

        else:

            send_message(

                user_id,

                f"🏐 {text}\n\n"
                "Выберите тренировку:",

                trainings_keyboard(
                    trainings
                )
            )


    # =====================================================
    # ВЫБОР ТРЕНИРОВКИ
    # =====================================================

    elif (
        "." in text
        and text.split(".")[0].isdigit()
    ):

        try:

            training_id = int(
                text.split(".")[0]
            )

            training = get_training_by_id(
                training_id
            )

            if training:

                info, available = get_training_info(
                    training
                )

                send_message(

                    user_id,

                    info,

                    training_keyboard(
                        training_id,
                        available
                    )
                )

            else:

                send_message(

                    user_id,

                    "❌ Тренировка не найдена.",

                    main_keyboard()
                )

        except Exception as error:

            print(
                "TRAINING SELECTION ERROR:",
                error
            )

            send_message(

                user_id,

                "❌ Произошла ошибка.",

                main_keyboard()
            )


    # =====================================================
    # ЗАПИСЬ
    # =====================================================

    elif text.startswith(
        "✅ Записаться #"
    ):

        try:

            training_id = int(
                text.split("#")[1]
            )

            training = get_training_by_id(
                training_id
            )

            if not training:

                send_message(

                    user_id,

                    "❌ Тренировка не найдена.",

                    main_keyboard()
                )

            else:

                registered = get_registration_count(
                    training_id
                )

                capacity = training["capacity"]

                if registered >= capacity:

                    send_message(

                        user_id,

                        "❌ На эту тренировку "
                        "свободных мест уже нет.",

                        main_keyboard()
                    )

                else:

                    user_name = get_vk_user_name(
                        user_id
                    )

                    success = add_registration(

                        training_id,
                        user_id,
                        user_name,
                        None
                    )

                    if success:

                        available = max(
                            capacity -
                            get_registration_count(
                                training_id
                            ),
                            0
                        )

                        send_message(

                            user_id,

                            "✅ Вы записаны!\n\n"
                            f"🏐 {format_training_title(training)}\n"
                            f"🕐 {training['time']}\n"
                            f"💰 {training['price']} ₽\n\n"
                            f"👥 Свободных мест: {available}",

                            main_keyboard()
                        )

                    else:

                        send_message(

                            user_id,

                            "ℹ️ Вы уже записаны "
                            "на эту тренировку.",

                            main_keyboard()
                        )

        except Exception as error:

            print(
                "REGISTRATION ERROR:",
                error
            )

            send_message(

                user_id,

                "❌ Не удалось записать вас.",

                main_keyboard()
            )


    # =====================================================
    # МОИ ТРЕНИРОВКИ
    # =====================================================

    elif text == "👤 Мои тренировки":

        info, registrations = format_my_trainings(
            user_id
        )

        if registrations:

            send_message(

                user_id,

                info,

                my_trainings_keyboard(
                    registrations
                )
            )

        else:

            send_message(

                user_id,

                info,

                main_keyboard()
            )


    # =====================================================
    # ОТМЕНА ЗАПИСИ
    # =====================================================

    elif text.startswith(
        "❌ Отменить #"
    ):

        try:

            training_id = int(
                text.split("#")[1]
            )

            training = get_training_by_id(
                training_id
            )

            if not training:

                send_message(

                    user_id,

                    "❌ Тренировка не найдена.",

                    main_keyboard()
                )

            else:

                deleted = delete_registration(
                    training_id,
                    user_id
                )

                if deleted:

                    send_message(

                        user_id,

                        "✅ Запись отменена.\n\n"
                        f"🏐 {format_training_title(training)}\n"
                        f"🕐 {training['time']}\n\n"
                        "Место снова доступно.",

                        main_keyboard()
                    )

                else:

                    send_message(

                        user_id,

                        "ℹ️ Вы не были записаны "
                        "на эту тренировку.",

                        main_keyboard()
                    )

        except Exception as error:

            print(
                "CANCEL ERROR:",
                error
            )

            send_message(

                user_id,

                "❌ Не удалось отменить запись.",

                main_keyboard()
            )


    # =====================================================
    # РАСПИСАНИЕ
    # =====================================================

    elif text == "📅 Расписание":

        send_message(

            user_id,

            format_schedule(),

            main_keyboard()
        )


    # =====================================================
    # ЦЕНЫ
    # =====================================================

    elif text == "💰 Цены":

        send_message(

            user_id,

            "💰 ЦЕНЫ VOLLEY WAVE\n\n"
            "🏐 Взрослые тренировки — 1200 ₽\n"
            "👶 Детские тренировки — 600 ₽\n\n"
            "Точная стоимость каждой тренировки "
            "указана в расписании.",

            main_keyboard()
        )


    # =====================================================
    # ДЕТСКИЕ ГРУППЫ
    # =====================================================

    elif text == "👶 Детские группы":

        send_message(

            user_id,

            "👶 ДЕТСКИЕ ГРУППЫ VOLLEY WAVE\n\n"
            "🏐 Тренировки проходят на песке "
            "круглый год.\n\n"
            "Группы:\n"
            "• 5–9 лет\n"
            "• 5–10 лет\n"
            "• 9–13 лет\n"
            "• 9–14 лет\n"
            "• 11–14 лет\n\n"
            "Расписание и свободные места "
            "можно посмотреть через кнопку "
            "«🏐 Записаться».",

            main_keyboard()
        )


    # =====================================================
    # ГДЕ ТРЕНИРУЕМСЯ
    # =====================================================

    elif text == "📍 Где тренируемся":

        send_message(

            user_id,

            "📍 ГДЕ ТРЕНИРУЕМСЯ\n\n"
            "🏐 VOLLEY WAVE\n"
            "Тренировки проходят на песке "
            "в течение всего года.\n\n"
            "Актуальный адрес конкретной "
            "тренировки сообщается при записи.",

            main_keyboard()
        )


    # =====================================================
    # ЗАДАТЬ ВОПРОС
    # =====================================================

    elif text == "❓ Задать вопрос":

        send_message(

            user_id,

            "❓ ЗАДАТЬ ВОПРОС\n\n"
            "Напишите свой вопрос следующим "
            "сообщением — администратор VOLLEY WAVE "
            "ответит вам.",

            main_keyboard()
        )


    # =====================================================
    # НАЗАД К ДНЯМ
    # =====================================================

    elif text == "⬅️ Назад к дням":

        send_message(

            user_id,

            "🏐 Запись на тренировку\n\n"
            "Выберите день:",

            days_keyboard()
        )


    # =====================================================
    # НАЗАД К ТРЕНИРОВКАМ
    # =====================================================

    elif text == "⬅️ Назад к тренировкам":

        send_message(

            user_id,

            "🏐 Вернитесь в раздел "
            "«🏐 Записаться» и выберите день.",

            main_keyboard()
        )


    # =====================================================
    # ГЛАВНОЕ МЕНЮ
    # =====================================================

    elif text == "🏠 Главное меню":

        send_message(

            user_id,

            "🏠 Главное меню:",

            main_keyboard()
        )


    # =====================================================
    # НАЗАД
    # =====================================================

    elif text == "⬅️ Назад":

        send_message(

            user_id,

            "🏠 Главное меню:",

            main_keyboard()
        )


    # =====================================================
    # НЕИЗВЕСТНОЕ СООБЩЕНИЕ
    # =====================================================

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

    port = int(
        os.getenv(
            "PORT",
            10000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
