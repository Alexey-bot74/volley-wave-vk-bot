import sqlite3

DB_NAME = "volley_wave.db"


def get_connection():
    connection = sqlite3.connect(DB_NAME)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    connection = get_connection()
    cursor = connection.cursor()

    # Пользователи
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vk_id INTEGER UNIQUE NOT NULL,
            name TEXT,
            phone TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Базовое недельное расписание
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

            price TEXT NOT NULL DEFAULT '600₽',

            active INTEGER NOT NULL DEFAULT 1,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Записи пользователей на тренировки
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            training_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,

            status TEXT NOT NULL DEFAULT 'registered',

            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            UNIQUE(training_id, user_id),

            FOREIGN KEY(training_id)
                REFERENCES trainings(id),

            FOREIGN KEY(user_id)
                REFERENCES users(id)
        )
    """)

    # Настройки школы
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            setting_key TEXT UNIQUE NOT NULL,
            setting_value TEXT
        )
    """)

    connection.commit()
    connection.close()


# =========================================================
# ПОЛЬЗОВАТЕЛИ
# =========================================================

def get_user_by_vk_id(vk_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        "SELECT * FROM users WHERE vk_id = ?",
        (vk_id,)
    )

    user = cursor.fetchone()

    connection.close()

    return user


def create_user(vk_id, name=None, phone=None):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT OR IGNORE INTO users (
            vk_id,
            name,
            phone
        )
        VALUES (?, ?, ?)
    """, (
        vk_id,
        name,
        phone
    ))

    connection.commit()

    cursor.execute(
        "SELECT * FROM users WHERE vk_id = ?",
        (vk_id,)
    )

    user = cursor.fetchone()

    connection.close()

    return user


def update_user(vk_id, name=None, phone=None):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        UPDATE users
        SET
            name = COALESCE(?, name),
            phone = COALESCE(?, phone)
        WHERE vk_id = ?
    """, (
        name,
        phone,
        vk_id
    ))

    connection.commit()
    connection.close()


# =========================================================
# РАСПИСАНИЕ
# =========================================================

def get_trainings(active_only=True):
    connection = get_connection()
    cursor = connection.cursor()

    if active_only:
        cursor.execute("""
            SELECT *
            FROM trainings
            WHERE active = 1
            ORDER BY day_of_week, time
        """)
    else:
        cursor.execute("""
            SELECT *
            FROM trainings
            ORDER BY day_of_week, time
        """)

    trainings = cursor.fetchall()

    connection.close()

    return trainings


def get_trainings_by_day(day_of_week, active_only=True):
    connection = get_connection()
    cursor = connection.cursor()

    if active_only:
        cursor.execute("""
            SELECT *
            FROM trainings
            WHERE day_of_week = ?
            AND active = 1
            ORDER BY time
        """, (day_of_week,))
    else:
        cursor.execute("""
            SELECT *
            FROM trainings
            WHERE day_of_week = ?
            ORDER BY time
        """, (day_of_week,))

    trainings = cursor.fetchall()

    connection.close()

    return trainings


def get_training(training_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        "SELECT * FROM trainings WHERE id = ?",
        (training_id,)
    )

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
    price="600₽"
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


def update_training(
    training_id,
    day_of_week=None,
    time=None,
    title=None,
    level=None,
    age_group=None,
    location=None,
    capacity=None,
    price=None,
    active=None
):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        "SELECT id FROM trainings WHERE id = ?",
        (training_id,)
    )

    training = cursor.fetchone()

    if not training:
        connection.close()
        return False

    cursor.execute("""
        UPDATE trainings
        SET
            day_of_week = COALESCE(?, day_of_week),
            time = COALESCE(?, time),
            title = COALESCE(?, title),
            level = COALESCE(?, level),
            age_group = COALESCE(?, age_group),
            location = COALESCE(?, location),
            capacity = COALESCE(?, capacity),
            price = COALESCE(?, price),
            active = COALESCE(?, active)
        WHERE id = ?
    """, (
        day_of_week,
        time,
        title,
        level,
        age_group,
        location,
        capacity,
        price,
        active,
        training_id
    ))

    connection.commit()
    connection.close()

    return True


def deactivate_training(training_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        UPDATE trainings
        SET active = 0
        WHERE id = ?
    """, (training_id,))

    connection.commit()
    connection.close()


# =========================================================
# ЗАПИСИ НА ТРЕНИРОВКИ
# =========================================================

def get_registration_count(training_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT COUNT(*) AS count
        FROM registrations
        WHERE training_id = ?
        AND status = 'registered'
    """, (training_id,))

    result = cursor.fetchone()

    connection.close()

    return result["count"]


def get_available_spots(training_id):
    training = get_training(training_id)

    if not training:
        return 0

    registered = get_registration_count(training_id)

    return max(
        training["capacity"] - registered,
        0
    )


def register_user(training_id, vk_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        "SELECT id FROM users WHERE vk_id = ?",
        (vk_id,)
    )

    user = cursor.fetchone()

    if not user:
        connection.close()
        return False, "user_not_found"

    cursor.execute("""
        SELECT id
        FROM registrations
        WHERE training_id = ?
        AND user_id = ?
        AND status = 'registered'
    """, (
        training_id,
        user["id"]
    ))

    existing = cursor.fetchone()

    if existing:
        connection.close()
        return False, "already_registered"

    cursor.execute("""
        SELECT capacity
        FROM trainings
        WHERE id = ?
        AND active = 1
    """, (training_id,))

    training = cursor.fetchone()

    if not training:
        connection.close()
        return False, "training_not_found"

    cursor.execute("""
        SELECT COUNT(*) AS count
        FROM registrations
        WHERE training_id = ?
        AND status = 'registered'
    """, (training_id,))

    registered = cursor.fetchone()["count"]

    if registered >= training["capacity"]:
        connection.close()
        return False, "no_spots"

    cursor.execute("""
        INSERT INTO registrations (
            training_id,
            user_id,
            status
        )
        VALUES (?, ?, 'registered')
    """, (
        training_id,
        user["id"]
    ))

    connection.commit()
    connection.close()

    return True, "registered"


def cancel_registration(training_id, vk_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        "SELECT id FROM users WHERE vk_id = ?",
        (vk_id,)
    )

    user = cursor.fetchone()

    if not user:
        connection.close()
        return False

    cursor.execute("""
        UPDATE registrations
        SET status = 'cancelled'
        WHERE training_id = ?
        AND user_id = ?
        AND status = 'registered'
    """, (
        training_id,
        user["id"]
    ))

    changed = cursor.rowcount > 0

    connection.commit()
    connection.close()

    return changed


def get_user_registrations(vk_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            registrations.id AS registration_id,
            registrations.status,

            trainings.id AS training_id,
            trainings.day_of_week,
            trainings.time,
            trainings.title,
            trainings.level,
            trainings.age_group,
            trainings.location,
            trainings.price

        FROM registrations

        JOIN users
            ON users.id = registrations.user_id

        JOIN trainings
            ON trainings.id = registrations.training_id

        WHERE users.vk_id = ?
        AND registrations.status = 'registered'

        ORDER BY
            trainings.day_of_week,
            trainings.time
    """, (vk_id,))

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
            users.phone

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


# =========================================================
# НАСТРОЙКИ
# =========================================================

def set_setting(key, value):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO settings (
            setting_key,
            setting_value
        )
        VALUES (?, ?)

        ON CONFLICT(setting_key)
        DO UPDATE SET
            setting_value = excluded.setting_value
    """, (
        key,
        str(value)
    ))

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

    result = cursor.fetchone()

    connection.close()

    if result:
        return result["setting_value"]

    return default
