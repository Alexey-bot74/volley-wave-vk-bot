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
