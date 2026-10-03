import sqlite3


DB_NAME = "volley_wave.db"


def get_connection():
    connection = sqlite3.connect(DB_NAME)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    connection = get_connection()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS trainings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day_of_week INTEGER NOT NULL,
            time TEXT NOT NULL,
            title TEXT NOT NULL,
            level TEXT,
            age_group TEXT,
            price INTEGER NOT NULL,
            capacity INTEGER NOT NULL
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            training_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            name TEXT,
            phone TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(training_id, user_id)
        )
    """)

    count = connection.execute(
        "SELECT COUNT(*) FROM trainings"
    ).fetchone()[0]

    if count == 0:

        schedule = [
            (1, "09:00-11:00", "Детская тренировка", "", "9-13 лет", 600, 10),
            (1, "17:00-19:00", "Детская тренировка", "", "11-14 лет", 600, 10),
            (1, "19:00-20:30", "Техничка", "любой уровень", "", 1200, 10),

            (2, "09:00-11:00", "Общая тренировка", "любой уровень", "", 1200, 8),
            (2, "17:00-18:30", "Детская тренировка", "", "11-14 лет", 600, 10),
            (2, "19:30-21:00", "Женская тренировка", "средний+", "", 1200, 8),

            (3, "09:00-11:00", "Детская тренировка", "", "9-14 лет", 600, 10),
            (3, "17:00-18:00", "Детская тренировка", "", "5-9 лет", 600, 10),
            (3, "18:00-19:30", "Тренировка", "продвинутый", "", 1200, 8),
            (3, "19:30-21:00", "MIXED", "средний+", "", 1200, 3),

            (4, "09:00-11:00", "Общая тренировка", "любой уровень", "", 1200, 8),
            (4, "17:00-19:00", "Детская тренировка", "", "11-14 лет", 600, 10),
            (4, "19:00-20:30", "Тренировка", "средний", "", 1200, 8),

            (5, "09:00-11:00", "Детская тренировка", "", "9-14 лет", 600, 10),
            (5, "17:00-18:00", "Детская тренировка", "", "5-10 лет", 600, 10),
            (5, "17:00-19:00", "Детская тренировка", "", "11-14 лет", 600, 10),
            (5, "19:00-20:30", "Техничка", "любой уровень", "", 1200, 10)
        ]

        connection.executemany(
            """
            INSERT INTO trainings
            (
                day_of_week,
                time,
                title,
                level,
                age_group,
                price,
                capacity
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            schedule
        )

    connection.commit()
    connection.close()


def get_trainings():
    connection = get_connection()

    rows = connection.execute("""
        SELECT *
        FROM trainings
        ORDER BY day_of_week, time
    """).fetchall()

    connection.close()

    return rows


def get_registration_count(training_id):
    connection = get_connection()

    row = connection.execute("""
        SELECT COUNT(*) AS count
        FROM registrations
        WHERE training_id = ?
    """, (training_id,)).fetchone()

    connection.close()

    return row["count"]


def get_registrations(training_id):
    connection = get_connection()

    rows = connection.execute("""
        SELECT *
        FROM registrations
        WHERE training_id = ?
        ORDER BY created_at
    """, (training_id,)).fetchall()

    connection.close()

    return rows


def add_registration(training_id, user_id, name=None, phone=None):
    connection = get_connection()

    try:
        connection.execute("""
            INSERT INTO registrations
            (
                training_id,
                user_id,
                name,
                phone
            )
            VALUES (?, ?, ?, ?)
        """, (
            training_id,
            user_id,
            name,
            phone
        ))

        connection.commit()
        result = True

    except sqlite3.IntegrityError:
        result = False

    connection.close()

    return result


def get_user_registrations(user_id):
    connection = get_connection()

    rows = connection.execute("""
        SELECT
            registrations.id AS registration_id,
            registrations.training_id,
            registrations.user_id,
            registrations.name,
            registrations.phone,
            registrations.created_at,
            trainings.day_of_week,
            trainings.time,
            trainings.title,
            trainings.level,
            trainings.age_group,
            trainings.price
        FROM registrations
        JOIN trainings
            ON registrations.training_id = trainings.id
        WHERE registrations.user_id = ?
        ORDER BY
            trainings.day_of_week,
            trainings.time
    """, (user_id,)).fetchall()

    connection.close()

    return rows


def delete_registration(training_id, user_id):
    connection = get_connection()

    cursor = connection.execute("""
        DELETE FROM registrations
        WHERE training_id = ?
        AND user_id = ?
    """, (
        training_id,
        user_id
    ))

    connection.commit()

    deleted = cursor.rowcount > 0

    connection.close()

    return deleted
