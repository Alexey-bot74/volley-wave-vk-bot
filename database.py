import sqlite3

DB_NAME = "volley_wave.db"

BASE_SCHEDULE = [
(1, "09:00-11:00", "Дети 9-13 лет", None, "9-13 лет", 10, "600"),
1, "17:00-19:00", "Дети 11-14 лет", None, "11-14 лет", 10, "600"),
(1, "19:00-20:30", "Техничка", "Общий уровень", None, 10, "1000-1200"),

(2, "09:00-11:00", "Взрослая группа", "Общий уровень", None, 8, "1000-1200"),
(2, "17:00-18:30", "Дети 11-14 лет", None, "11-14 лет", 10, "600"),
(2, "19:30-21:00", "Женская группа", "Средний и выше", None, 8, "1000-1200"),

(3, "09:00-11:00", "Дети 9-14 лет", None, "9-14 лет", 10, "600"),
(3, "17:00-18:00", "Дети 5-9 лет", None, "5-9 лет", 10, "600"),
(3, "18:00-19:30", "Взрослая группа", "Продвинутый уровень", None, 8, "1000-1200"),
(3, "19:30-21:00", "Миксты", "Средний и выше", None, 3, "1200"),

(4, "09:00-11:00", "Взрослая группа", "Общий уровень", None, 8, "1000-1200"),
(4, "17:00-19:00", "Дети 11-14 лет", None, "11-14 лет", 10, "600"),
(4, "19:00-20:30", "Взрослая группа", "Средний уровень", None, 8, "1000-1200"),

(5, "09:00-11:00", "Дети 9-14 лет", None, "9-14 лет", 10, "600"),
(5, "17:00-18:00", "Дети 5-10 лет", None, "5-10 лет", 10, "600"),
(5, "17:00-19:00", "Дети 11-14 лет", None, "11-14 лет", 10, "600"),
(5, "19:00-20:30", "Техничка", "Общий уровень", None, 10, "1000-1200"),
]


def get_connection():
    connection = sqlite3.connect(DB_NAME)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vk_id INTEGER UNIQUE NOT NULL,
            name TEXT,
            phone TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trainings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day_of_week INTEGER NOT NULL,
            time TEXT NOT NULL,
            title TEXT NOT NULL,
            level TEXT,
            age_group TEXT,
            location TEXT,
            capacity INTEGER NOT NULL DEFAULT 8,
            price TEXT NOT NULL DEFAULT '600',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            training_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'registered',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(training_id, user_id),
            FOREIGN KEY(training_id) REFERENCES trainings(id),
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            setting_key TEXT UNIQUE NOT NULL,
            setting_value TEXT
        )
    """)

    connection.commit()

    ensure_base_schedule(connection)

    connection.close()


def ensure_base_schedule(connection):
    cursor = connection.cursor()
    added = 0

    for item in BASE_SCHEDULE:
        day_of_week, time, title, level, age_group, capacity, price = item

        cursor.execute("""
            SELECT id
            FROM trainings
            WHERE day_of_week = ?
            AND time = ?
            AND title = ?
        """, (day_of_week, time, title))

        existing = cursor.fetchone()

        if existing is None:
            cursor.execute("""
                INSERT INTO trainings (
                    day_of_week,
                    time,
                    title,
                    level,
                    age_group,
                    capacity,
                    price,
                    active
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """, (
                day_of_week,
                time,
                title,
                level,
                age_group,
                capacity,
                price
            ))

            added += 1

    connection.commit()

    cursor.execute("SELECT COUNT(*) AS count FROM trainings")
    total = cursor.fetchone()["count"]

    print("SCHEDULE CHECK")
    print("ADDED:", added)
    print("TOTAL TRAININGS:", total)


def get_user_by_vk_id(vk_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM users
        WHERE vk_id = ?
    """, (vk_id,))

    user = cursor.fetchone()
    connection.close()

    return user


def create_user(vk_id, name=None, phone=None):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO users (vk_id, name, phone)
        VALUES (?, ?, ?)
    """, (vk_id, name, phone))

    connection.commit()

    user_id = cursor.lastrowid
    connection.close()

    return user_id


def update_user(vk_id, name=None, phone=None):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        UPDATE users
        SET name = COALESCE(?, name),
            phone = COALESCE(?, phone)
        WHERE vk_id = ?
    """, (name, phone, vk_id))

    connection.commit()
    connection.close()


def get_trainings():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM trainings
        WHERE active = 1
        ORDER BY day_of_week, time
    """)

    trainings = cursor.fetchall()
    connection.close()

    return trainings


def get_trainings_by_day(day_of_week):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM trainings
        WHERE day_of_week = ?
        AND active = 1
        ORDER BY time
    """, (day_of_week,))

    trainings = cursor.fetchall()
    connection.close()

    return trainings


def get_training(training_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM trainings
        WHERE id = ?
    """, (training_id,))

    training = cursor.fetchone()
    connection.close()

    return training


def create_training(
    day_of_week,
    time,
    title,
    level=None,
    age_group=None,
    location=None,
    capacity=8,
    price="600"
):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO trainings (
            day_of_week,
            time,
            title,
            level,
            age_group,
            location,
            capacity,
            price
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        day_of_week,
        time,
        title,
        level,
        age_group,
        location,
        capacity,
        price
    ))

    connection.commit()

    training_id = cursor.lastrowid
    connection.close()

    return training_id


def update_training(training_id, **kwargs):
    allowed_fields = {
        "day_of_week",
        "time",
        "title",
        "level",
        "age_group",
        "location",
        "capacity",
        "price",
        "active"
    }

    fields = []
    values = []

    for field, value in kwargs.items():
        if field in allowed_fields:
            fields.append(field + " = ?")
            values.append(value)

    if not fields:
        return

    values.append(training_id)

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        "UPDATE trainings SET " + ", ".join(fields) + " WHERE id = ?",
        values
    )

    connection.commit()
    connection.close()


def deactivate_training(training_id):
    update_training(training_id, active=0)


def get_registration_count(training_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT COUNT(*) AS count
        FROM registrations
        WHERE training_id = ?
        AND status = 'registered'
    """, (training_id,))

    count = cursor.fetchone()["count"]
    connection.close()

    return count


def get_available_spots(training_id):
    training = get_training(training_id)

    if not training:
        return 0

    registered = get_registration_count(training_id)

    return max(training["capacity"] - registered, 0)


def register_user(training_id, user_id):
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            INSERT INTO registrations (
                training_id,
                user_id,
                status
            )
            VALUES (?, ?, 'registered')
        """, (training_id, user_id))

        connection.commit()

        registration_id = cursor.lastrowid
        connection.close()

        return registration_id

    except sqlite3.IntegrityError:
        connection.close()
        return None


def cancel_registration(training_id, user_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        UPDATE registrations
        SET status = 'cancelled'
        WHERE training_id = ?
        AND user_id = ?
        AND status = 'registered'
    """, (training_id, user_id))

    connection.commit()
    connection.close()


def get_user_registrations(user_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            registrations.*,
            trainings.day_of_week,
            trainings.time,
            trainings.title,
            trainings.level,
            trainings.age_group,
            trainings.location,
            trainings.price
        FROM registrations
        JOIN trainings
            ON trainings.id = registrations.training_id
        WHERE registrations.user_id = ?
        AND registrations.status = 'registered'
        ORDER BY trainings.day_of_week, trainings.time
    """, (user_id,))

    registrations = cursor.fetchall()
    connection.close()

    return registrations


def get_training_participants(training_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            users.id,
            users.vk_id,
            users.name,
            users.phone,
            registrations.created_at
        FROM registrations
        JOIN users
            ON users.id = registrations.user_id
        WHERE registrations.training_id = ?
        AND registrations.status = 'registered'
        ORDER BY registrations.created_at
    """, (training_id,))

    participants = cursor.fetchall()
    connection.close()

    return participants


def set_setting(key, value):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO settings (setting_key, setting_value)
        VALUES (?, ?)
        ON CONFLICT(setting_key)
        DO UPDATE SET setting_value = excluded.setting_value
    """, (key, value))

    connection.commit()
    connection.close()


def get_setting(key, default=None):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT setting_value
        FROM settings
        WHERE setting_key = ?
    """, (key,))

    row = cursor.fetchone()
    connection.close()

    if row is None:
        return default

    return row["setting_value"]
