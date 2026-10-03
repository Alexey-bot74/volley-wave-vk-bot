import sqlite3
from datetime import datetime

DB_NAME = "volley_wave.db"


def get_connection():
    connection = sqlite3.connect(DB_NAME)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db():
    connection = get_connection()

    # =========================
    # USERS
    # =========================

    connection.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            name TEXT,
            phone TEXT,
            is_blocked INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # =========================
    # TRAININGS
    # =========================

    connection.execute("""
        CREATE TABLE IF NOT EXISTS trainings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day_of_week INTEGER NOT NULL,
            time TEXT NOT NULL,
            title TEXT NOT NULL,
            level TEXT,
            age_group TEXT,
            price INTEGER NOT NULL,
            capacity INTEGER NOT NULL,

            category TEXT,
            format TEXT,
            coach TEXT,

            status TEXT NOT NULL DEFAULT 'active',

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # =========================
    # REGISTRATIONS
    # =========================

    connection.execute("""
        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            training_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            name TEXT,
            phone TEXT,

            status TEXT NOT NULL DEFAULT 'active',

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            cancelled_at TIMESTAMP,
            cancellation_reason TEXT,

            UNIQUE(training_id, user_id),

            FOREIGN KEY(training_id)
                REFERENCES trainings(id)
                ON DELETE CASCADE
        )
    """)

    # =========================
    # ATTENDANCE
    # =========================

    connection.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            registration_id INTEGER NOT NULL UNIQUE,

            status TEXT NOT NULL DEFAULT 'not_marked',

            marked_at TIMESTAMP,
            marked_by INTEGER,

            FOREIGN KEY(registration_id)
                REFERENCES registrations(id)
                ON DELETE CASCADE
        )
    """)

    # =========================
    # WAITLIST
    # =========================

    connection.execute("""
        CREATE TABLE IF NOT EXISTS waitlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            training_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,

            position INTEGER NOT NULL,

            status TEXT NOT NULL DEFAULT 'waiting',

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notified_at TIMESTAMP,

            UNIQUE(training_id, user_id),

            FOREIGN KEY(training_id)
                REFERENCES trainings(id)
                ON DELETE CASCADE
        )
    """)

    # =========================
    # PAYMENTS
    # =========================

    connection.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            user_id INTEGER NOT NULL,
            training_id INTEGER,

            amount INTEGER NOT NULL,

            status TEXT NOT NULL DEFAULT 'pending',

            method TEXT,
            external_id TEXT,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            paid_at TIMESTAMP,

            FOREIGN KEY(training_id)
                REFERENCES trainings(id)
                ON DELETE SET NULL
        )
    """)

    # =========================
    # ADMIN LOG
    # =========================

    connection.execute("""
        CREATE TABLE IF NOT EXISTS admin_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            admin_id INTEGER NOT NULL,

            action TEXT NOT NULL,
            entity TEXT,
            entity_id INTEGER,

            details TEXT,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # =========================
    # MIGRATION OF OLD DATABASE
    # =========================

    migrate_trainings_table(connection)

    # =========================
    # INITIAL SCHEDULE
    # =========================

    count = connection.execute(
        "SELECT COUNT(*) FROM trainings"
    ).fetchone()[0]

    if count == 0:
        schedule = [
            (
                1,
                "09:00-11:00",
                "Детская тренировка",
                "",
                "9-13 лет",
                600,
                10,
                "children",
                "Группа",
                "Алексей"
            ),
            (
                1,
                "17:00-19:00",
                "Детская тренировка",
                "средний",
                "11-14 лет",
                600,
                10,
                "children",
                "Группа",
                "Алексей"
            ),
            (
                1,
                "19:00-20:30",
                "Техничка",
                "техническая",
                "18+",
                1200,
                10,
                "adults",
                "Группа",
                "Алексей"
            ),

            (
                2,
                "09:00-11:00",
                "Общая тренировка",
                "любой уровень",
                "18+",
                1200,
                8,
                "adults",
                "Группа",
                "Алексей"
            ),
            (
                2,
                "17:00-18:30",
                "Детская тренировка",
                "средний",
                "11-14 лет",
                600,
                10,
                "children",
                "Группа",
                "Алексей"
            ),
            (
                2,
                "19:30-21:00",
                "Женская тренировка",
                "средний+",
                "18+",
                1200,
                8,
                "adults",
                "Женская группа",
                "Алексей"
            ),

            (
                3,
                "09:00-11:00",
                "Детская тренировка",
                "начальный / средний",
                "9-14 лет",
                600,
                10,
                "children",
                "Группа",
                "Алексей"
            ),
            (
                3,
                "17:00-18:00",
                "Детская тренировка",
                "начальный",
                "5-9 лет",
                600,
                10,
                "children",
                "Группа",
                "Ксения"
            ),
            (
                3,
                "18:00-19:30",
                "Тренировка",
                "продвинутый",
                "18+",
                1200,
                8,
                "adults",
                "Группа",
                "Алексей"
            ),
            (
                3,
                "19:30-21:00",
                "MIXED",
                "средний+",
                "18+",
                1200,
                8,
                "adults",
                "MIXED",
                "Алексей"
            ),

            (
                4,
                "09:00-11:00",
                "Общая тренировка",
                "любой уровень",
                "18+",
                1200,
                8,
                "adults",
                "Группа",
                "Алексей"
            ),
            (
                4,
                "17:00-19:00",
                "Детская тренировка",
                "средний",
                "11-14 лет",
                600,
                10,
                "children",
                "Группа",
                "Алексей"
            ),
            (
                4,
                "19:00-20:30",
                "Тренировка",
                "средний",
                "18+",
                1200,
                8,
                "adults",
                "Группа",
                "Алексей"
            ),

            (
                5,
                "09:00-11:00",
                "Детская тренировка",
                "начальный / средний",
                "9-14 лет",
                600,
                10,
                "children",
                "Группа",
                "Алексей"
            ),
            (
                5,
                "17:00-18:00",
                "Детская тренировка",
                "начальный",
                "5-10 лет",
                600,
                10,
                "children",
                "Группа",
                "Ксения"
            ),
            (
                5,
                "17:00-19:00",
                "Детская тренировка",
                "средний",
                "11-14 лет",
                600,
                10,
                "children",
                "Группа",
                "Алексей"
            ),
            (
                5,
                "19:00-20:30",
                "Техничка",
                "техническая",
                "18+",
                1200,
                10,
                "adults",
                "Группа",
                "Алексей"
            )
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
                capacity,
                category,
                format,
                coach
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            schedule
        )

    connection.commit()
    connection.close()


def migrate_trainings_table(connection):
    """
    Добавляет новые поля в уже существующую базу.

    Старые данные не удаляются.
    """

    columns = connection.execute(
        "PRAGMA table_info(trainings)"
    ).fetchall()

    existing_columns = {
        column["name"]
        for column in columns
    }

    new_columns = {
        "category": "TEXT",
        "format": "TEXT",
        "coach": "TEXT",
        "status": "TEXT NOT NULL DEFAULT 'active'",
        "created_at": "TIMESTAMP",
        "updated_at": "TIMESTAMP"
    }

    for column_name, column_type in new_columns.items():

        if column_name not in existing_columns:
            connection.execute(
                f"""
                ALTER TABLE trainings
                ADD COLUMN {column_name} {column_type}
                """
            )

    connection.execute("""
        UPDATE trainings
        SET status = 'active'
        WHERE status IS NULL
    """)

    connection.execute("""
        UPDATE trainings
        SET created_at = CURRENT_TIMESTAMP
        WHERE created_at IS NULL
    """)

    connection.execute("""
        UPDATE trainings
        SET updated_at = CURRENT_TIMESTAMP
        WHERE updated_at IS NULL
    """)


# ============================================================
# USERS
# ============================================================

def create_or_update_user(user_id, name=None, phone=None):
    connection = get_connection()

    connection.execute("""
        INSERT INTO users
        (
            user_id,
            name,
            phone
        )
        VALUES (?, ?, ?)

        ON CONFLICT(user_id)
        DO UPDATE SET
            name = COALESCE(excluded.name, users.name),
            phone = COALESCE(excluded.phone, users.phone),
            updated_at = CURRENT_TIMESTAMP
    """, (
        user_id,
        name,
        phone
    ))

    connection.commit()
    connection.close()


def get_user(user_id):
    connection = get_connection()

    row = connection.execute("""
        SELECT *
        FROM users
        WHERE user_id = ?
    """, (user_id,)).fetchone()

    connection.close()

    return row


def is_user_blocked(user_id):
    user = get_user(user_id)

    if not user:
        return False

    return bool(user["is_blocked"])


def set_user_blocked(user_id, blocked=True):
    connection = get_connection()

    connection.execute("""
        UPDATE users
        SET
            is_blocked = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE user_id = ?
    """, (
        1 if blocked else 0,
        user_id
    ))

    connection.commit()
    connection.close()


# ============================================================
# TRAININGS
# ============================================================

def get_trainings():
    connection = get_connection()

    rows = connection.execute("""
        SELECT *
        FROM trainings
        WHERE status = 'active'
        ORDER BY day_of_week, time
    """).fetchall()

    connection.close()

    return rows


def get_training(training_id):
    connection = get_connection()

    row = connection.execute("""
        SELECT *
        FROM trainings
        WHERE id = ?
    """, (training_id,)).fetchone()

    connection.close()

    return row


def get_trainings_by_day(day_of_week):
    connection = get_connection()

    rows = connection.execute("""
        SELECT *
        FROM trainings
        WHERE day_of_week = ?
        AND status = 'active'
        ORDER BY time
    """, (day_of_week,)).fetchall()

    connection.close()

    return rows


def get_trainings_by_category(category):
    connection = get_connection()

    rows = connection.execute("""
        SELECT *
        FROM trainings
        WHERE category = ?
        AND status = 'active'
        ORDER BY day_of_week, time
    """, (category,)).fetchall()

    connection.close()

    return rows


# ============================================================
# REGISTRATIONS
# ============================================================

def get_registration_count(training_id):
    connection = get_connection()

    row = connection.execute("""
        SELECT COUNT(*) AS count
        FROM registrations
        WHERE training_id = ?
        AND status = 'active'
    """, (training_id,)).fetchone()

    connection.close()

    return row["count"]


def get_registrations(training_id):
    connection = get_connection()

    rows = connection.execute("""
        SELECT *
        FROM registrations
        WHERE training_id = ?
        AND status = 'active'
        ORDER BY created_at
    """, (training_id,)).fetchall()

    connection.close()

    return rows


def get_registration(training_id, user_id):
    connection = get_connection()

    row = connection.execute("""
        SELECT *
        FROM registrations
        WHERE training_id = ?
        AND user_id = ?
    """, (
        training_id,
        user_id
    )).fetchone()

    connection.close()

    return row


def add_registration(
    training_id,
    user_id,
    name=None,
    phone=None
):
    connection = get_connection()

    try:
        # Проверяем существующую запись
        existing = connection.execute("""
            SELECT *
            FROM registrations
            WHERE training_id = ?
            AND user_id = ?
        """, (
            training_id,
            user_id
        )).fetchone()

        if existing:

            if existing["status"] == "active":
                connection.close()
                return False

            connection.execute("""
                UPDATE registrations
                SET
                    status = 'active',
                    name = COALESCE(?, name),
                    phone = COALESCE(?, phone),
                    cancelled_at = NULL,
                    cancellation_reason = NULL
                WHERE training_id = ?
                AND user_id = ?
            """, (
                name,
                phone,
                training_id,
                user_id
            ))

        else:

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
        connection.rollback()
        result = False

    finally:
        connection.close()

    return result


def cancel_registration(
    training_id,
    user_id,
    reason=None
):
    connection = get_connection()

    cursor = connection.execute("""
        UPDATE registrations
        SET
            status = 'cancelled',
            cancelled_at = CURRENT_TIMESTAMP,
            cancellation_reason = ?
        WHERE training_id = ?
        AND user_id = ?
        AND status = 'active'
    """, (
        reason,
        training_id,
        user_id
    ))

    connection.commit()

    cancelled = cursor.rowcount > 0

    connection.close()

    return cancelled


def delete_registration(training_id, user_id):
    """
    Старую функцию сохраняем для совместимости
    с текущим bot.py.

    Фактически запись переводится в cancelled,
    а не удаляется из базы.
    """

    return cancel_registration(
        training_id,
        user_id,
        "Отмена пользователем"
    )


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
            registrations.status,

            trainings.day_of_week,
            trainings.time,
            trainings.title,
            trainings.level,
            trainings.age_group,
            trainings.price,
            trainings.capacity,
            trainings.category,
            trainings.format,
            trainings.coach

        FROM registrations

        JOIN trainings
            ON registrations.training_id = trainings.id

        WHERE registrations.user_id = ?
        AND registrations.status = 'active'

        ORDER BY
            trainings.day_of_week,
            trainings.time
    """, (user_id,)).fetchall()

    connection.close()

    return rows


# ============================================================
# ATTENDANCE
# ============================================================

def create_attendance_for_registration(registration_id):
    connection = get_connection()

    connection.execute("""
        INSERT OR IGNORE INTO attendance
        (
            registration_id
        )
        VALUES (?)
    """, (registration_id,))

    connection.commit()
    connection.close()


def mark_attendance(
    registration_id,
    status,
    admin_id=None
):
    connection = get_connection()

    connection.execute("""
        INSERT INTO attendance
        (
            registration_id,
            status,
            marked_at,
            marked_by
        )
        VALUES (?, ?, CURRENT_TIMESTAMP, ?)

        ON CONFLICT(registration_id)
        DO UPDATE SET
            status = excluded.status,
            marked_at = CURRENT_TIMESTAMP,
            marked_by = excluded.marked_by
    """, (
        registration_id,
        status,
        admin_id
    ))

    connection.commit()
    connection.close()


def get_training_attendance(training_id):
    connection = get_connection()

    rows = connection.execute("""
        SELECT
            registrations.id AS registration_id,
            registrations.user_id,
            registrations.name,
            registrations.phone,
            registrations.status AS registration_status,

            attendance.status AS attendance_status,
            attendance.marked_at,
            attendance.marked_by

        FROM registrations

        LEFT JOIN attendance
            ON attendance.registration_id = registrations.id

        WHERE registrations.training_id = ?

        ORDER BY registrations.created_at
    """, (training_id,)).fetchall()

    connection.close()

    return rows


# ============================================================
# WAITLIST
# ============================================================

def add_to_waitlist(training_id, user_id):
    connection = get_connection()

    existing = connection.execute("""
        SELECT *
        FROM waitlist
        WHERE training_id = ?
        AND user_id = ?
        AND status = 'waiting'
    """, (
        training_id,
        user_id
    )).fetchone()

    if existing:
        connection.close()
        return False

    position_row = connection.execute("""
        SELECT COALESCE(MAX(position), 0) + 1 AS position
        FROM waitlist
        WHERE training_id = ?
        AND status = 'waiting'
    """, (training_id,)).fetchone()

    position = position_row["position"]

    connection.execute("""
        INSERT INTO waitlist
        (
            training_id,
            user_id,
            position
        )
        VALUES (?, ?, ?)
    """, (
        training_id,
        user_id,
        position
    ))

    connection.commit()
    connection.close()

    return True


def get_waitlist(training_id):
    connection = get_connection()

    rows = connection.execute("""
        SELECT *
        FROM waitlist
        WHERE training_id = ?
        AND status = 'waiting'
        ORDER BY position
    """, (training_id,)).fetchall()

    connection.close()

    return rows


def remove_from_waitlist(training_id, user_id):
    connection = get_connection()

    cursor = connection.execute("""
        UPDATE waitlist
        SET status = 'cancelled'
        WHERE training_id = ?
        AND user_id = ?
        AND status = 'waiting'
    """, (
        training_id,
        user_id
    ))

    connection.commit()

    removed = cursor.rowcount > 0

    connection.close()

    return removed


# ============================================================
# PAYMENTS
# ============================================================

def create_payment(
    user_id,
    amount,
    training_id=None,
    method=None,
    external_id=None
):
    connection = get_connection()

    cursor = connection.execute("""
        INSERT INTO payments
        (
            user_id,
            training_id,
            amount,
            method,
            external_id
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        user_id,
        training_id,
        amount,
        method,
        external_id
    ))

    payment_id = cursor.lastrowid

    connection.commit()
    connection.close()

    return payment_id


def update_payment_status(
    payment_id,
    status
):
    connection = get_connection()

    if status == "paid":
        connection.execute("""
            UPDATE payments
            SET
                status = ?,
                paid_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            status,
            payment_id
        ))

    else:
        connection.execute("""
            UPDATE payments
            SET status = ?
            WHERE id = ?
        """, (
            status,
            payment_id
        ))

    connection.commit()
    connection.close()


def get_user_payments(user_id):
    connection = get_connection()

    rows = connection.execute("""
        SELECT *
        FROM payments
        WHERE user_id = ?
        ORDER BY created_at DESC
    """, (user_id,)).fetchall()

    connection.close()

    return rows


# ============================================================
# ADMIN LOG
# ============================================================

def add_admin_log(
    admin_id,
    action,
    entity=None,
    entity_id=None,
    details=None
):
    connection = get_connection()

    connection.execute("""
        INSERT INTO admin_logs
        (
            admin_id,
            action,
            entity,
            entity_id,
            details
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        admin_id,
        action,
        entity,
        entity_id,
        details
    ))

    connection.commit()
    connection.close()


def get_admin_logs(limit=100):
    connection = get_connection()

    rows = connection.execute("""
        SELECT *
        FROM admin_logs
        ORDER BY created_at DESC
        LIMIT ?
    """, (limit,)).fetchall()

    connection.close()

    return rows
