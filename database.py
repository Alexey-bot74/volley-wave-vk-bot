import sqlite3
from datetime import datetime
from pathlib import Path


# ============================================================
# НАСТРОЙКИ
# ============================================================

DB_PATH = Path(__file__).resolve().parent / "volley_wave.db"


# ============================================================
# ПОДКЛЮЧЕНИЕ
# ============================================================

def get_connection():
    conn = sqlite3.connect(
        DB_PATH,
        timeout=30,
    )

    conn.row_factory = sqlite3.Row

    conn.execute(
        "PRAGMA foreign_keys = ON"
    )

    return conn


# ============================================================
# ИНИЦИАЛИЗАЦИЯ
# ============================================================

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # --------------------------------------------------------
    # USERS
    # --------------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vk_id INTEGER UNIQUE NOT NULL,
            first_name TEXT,
            last_name TEXT,
            is_blocked INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    # --------------------------------------------------------
    # TRAINING TEMPLATES
    #
    # Шаблон повторяющегося расписания.
    # Например:
    # Понедельник 17:00-19:00, дети 11-14.
    #
    # Из шаблона создаются реальные тренировки
    # с конкретными датами.
    # --------------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS training_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            weekday INTEGER NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,

            title TEXT NOT NULL,
            category TEXT NOT NULL,

            age_group TEXT,
            level TEXT,
            format TEXT,
            coach TEXT,

            capacity INTEGER NOT NULL DEFAULT 10,
            price INTEGER NOT NULL DEFAULT 0,

            location TEXT,

            is_active INTEGER NOT NULL DEFAULT 1,

            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    # --------------------------------------------------------
    # TRAININGS
    #
    # Конкретная тренировка.
    #
    # Каждый экземпляр имеет свой номер и дату.
    # --------------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS trainings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            training_number INTEGER UNIQUE,

            training_date TEXT NOT NULL,
            weekday INTEGER NOT NULL,

            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,

            title TEXT NOT NULL,
            category TEXT NOT NULL,

            age_group TEXT,
            level TEXT,
            format TEXT,
            coach TEXT,

            capacity INTEGER NOT NULL DEFAULT 10,
            price INTEGER NOT NULL DEFAULT 0,

            location TEXT,

            status TEXT NOT NULL DEFAULT 'scheduled',

            template_id INTEGER,

            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,

            FOREIGN KEY (
                template_id
            )
            REFERENCES training_templates(id)
            ON DELETE SET NULL
        )
        """
    )

    # --------------------------------------------------------
    # REGISTRATIONS
    #
    # Запись пользователя на конкретную тренировку.
    # --------------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            training_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,

            status TEXT NOT NULL DEFAULT 'registered',

            registered_at TEXT NOT NULL,
            cancelled_at TEXT,

            cancellation_reason TEXT,

            FOREIGN KEY (
                training_id
            )
            REFERENCES trainings(id)
            ON DELETE CASCADE,

            FOREIGN KEY (
                user_id
            )
            REFERENCES users(id)
            ON DELETE CASCADE,

            UNIQUE (
                training_id,
                user_id
            )
        )
        """
    )

    # --------------------------------------------------------
    # WAITLIST
    # --------------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS waitlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            training_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,

            position INTEGER NOT NULL,

            status TEXT NOT NULL DEFAULT 'waiting',

            created_at TEXT NOT NULL,

            FOREIGN KEY (
                training_id
            )
            REFERENCES trainings(id)
            ON DELETE CASCADE,

            FOREIGN KEY (
                user_id
            )
            REFERENCES users(id)
            ON DELETE CASCADE,

            UNIQUE (
                training_id,
                user_id
            )
        )
        """
    )

    # --------------------------------------------------------
    # ATTENDANCE
    # --------------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            registration_id INTEGER NOT NULL,

            status TEXT NOT NULL DEFAULT 'unknown',

            marked_by INTEGER,
            marked_at TEXT,

            comment TEXT,

            FOREIGN KEY (
                registration_id
            )
            REFERENCES registrations(id)
            ON DELETE CASCADE
        )
        """
    )

    # --------------------------------------------------------
    # PAYMENTS
    # --------------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            user_id INTEGER NOT NULL,
            training_id INTEGER,

            amount INTEGER NOT NULL,

            status TEXT NOT NULL DEFAULT 'pending',

            payment_method TEXT,
            external_id TEXT,

            created_at TEXT NOT NULL,
            paid_at TEXT,

            FOREIGN KEY (
                user_id
            )
            REFERENCES users(id)
            ON DELETE CASCADE,

            FOREIGN KEY (
                training_id
            )
            REFERENCES trainings(id)
            ON DELETE SET NULL
        )
        """
    )

    # --------------------------------------------------------
    # ADMIN LOGS
    # --------------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS admin_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            admin_vk_id INTEGER NOT NULL,

            action TEXT NOT NULL,

            entity_type TEXT,
            entity_id INTEGER,

            details TEXT,

            created_at TEXT NOT NULL
        )
        """
    )

    # --------------------------------------------------------
    # NOTIFICATIONS
    #
    # Чтобы позже не отправлять повторно
    # напоминания одному и тому же пользователю.
    # --------------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            user_id INTEGER NOT NULL,
            training_id INTEGER,

            notification_type TEXT NOT NULL,

            scheduled_for TEXT NOT NULL,
            sent_at TEXT,

            status TEXT NOT NULL DEFAULT 'pending',

            created_at TEXT NOT NULL,

            FOREIGN KEY (
                user_id
            )
            REFERENCES users(id)
            ON DELETE CASCADE,

            FOREIGN KEY (
                training_id
            )
            REFERENCES trainings(id)
            ON DELETE CASCADE
        )
        """
    )

    # --------------------------------------------------------
    # ИНДЕКСЫ
    # --------------------------------------------------------

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_trainings_date
        ON trainings(training_date)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_trainings_status
        ON trainings(status)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_registrations_training
        ON registrations(training_id)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_registrations_user
        ON registrations(user_id)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_waitlist_training
        ON waitlist(training_id)
        """
    )

    conn.commit()
    conn.close()


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def now_text():
    return datetime.now().isoformat(
        timespec="seconds"
    )


def row_to_dict(row):
    if row is None:
        return None

    return dict(row)


# ============================================================
# USERS
# ============================================================

def create_or_update_user(
    vk_id,
    first_name=None,
    last_name=None,
):
    conn = get_connection()

    now = now_text()

    existing = conn.execute(
        """
        SELECT id
        FROM users
        WHERE vk_id = ?
        """,
        (vk_id,),
    ).fetchone()

    if existing:
        conn.execute(
            """
            UPDATE users
            SET
                first_name = COALESCE(?, first_name),
                last_name = COALESCE(?, last_name),
                updated_at = ?
            WHERE vk_id = ?
            """,
            (
                first_name,
                last_name,
                now,
                vk_id,
            ),
        )
    else:
        conn.execute(
            """
            INSERT INTO users (
                vk_id,
                first_name,
                last_name,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                vk_id,
                first_name,
                last_name,
                now,
                now,
            ),
        )

    conn.commit()
    conn.close()


def get_user(vk_id):
    conn = get_connection()

    row = conn.execute(
        """
        SELECT *
        FROM users
        WHERE vk_id = ?
        """,
        (vk_id,),
    ).fetchone()

    conn.close()

    return row


def is_user_blocked(vk_id):
    user = get_user(vk_id)

    if not user:
        return False

    return bool(
        user["is_blocked"]
    )


def set_user_blocked(
    vk_id,
    blocked=True,
):
    conn = get_connection()

    conn.execute(
        """
        UPDATE users
        SET
            is_blocked = ?,
            updated_at = ?
        WHERE vk_id = ?
        """,
        (
            1 if blocked else 0,
            now_text(),
            vk_id,
        ),
    )

    conn.commit()
    conn.close()


# ============================================================
# TRAINING TEMPLATES
# ============================================================

def create_training_template(
    weekday,
    start_time,
    end_time,
    title,
    category,
    age_group,
    level,
    format,
    coach,
    capacity,
    price,
    location,
):
    conn = get_connection()

    now = now_text()

    cursor = conn.execute(
        """
        INSERT INTO training_templates (
            weekday,
            start_time,
            end_time,
            title,
            category,
            age_group,
            level,
            format,
            coach,
            capacity,
            price,
            location,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            weekday,
            start_time,
            end_time,
            title,
            category,
            age_group,
            level,
            format,
            coach,
            capacity,
            price,
            location,
            now,
            now,
        ),
    )

    template_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return template_id


def get_training_templates(
    active_only=True,
):
    conn = get_connection()

    if active_only:
        rows = conn.execute(
            """
            SELECT *
            FROM training_templates
            WHERE is_active = 1
            ORDER BY weekday, start_time
            """
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT *
            FROM training_templates
            ORDER BY weekday, start_time
            """
        ).fetchall()

    conn.close()

    return rows


def get_training_template(
    template_id,
):
    conn = get_connection()

    row = conn.execute(
        """
        SELECT *
        FROM training_templates
        WHERE id = ?
        """,
        (template_id,),
    ).fetchone()

    conn.close()

    return row


def update_training_template(
    template_id,
    **fields,
):
    allowed = {
        "weekday",
        "start_time",
        "end_time",
        "title",
        "category",
        "age_group",
        "level",
        "format",
        "coach",
        "capacity",
        "price",
        "location",
        "is_active",
    }

    updates = []

    values = []

    for key, value in fields.items():
        if key in allowed:
            updates.append(
                f"{key} = ?"
            )
            values.append(value)

    if not updates:
        return

    updates.append(
        "updated_at = ?"
    )
    values.append(now_text())

    values.append(template_id)

    conn = get_connection()

    conn.execute(
        f"""
        UPDATE training_templates
        SET {", ".join(updates)}
        WHERE id = ?
        """,
        values,
    )

    conn.commit()
    conn.close()


# ============================================================
# TRAININGS
# ============================================================

def _next_training_number(conn):
    row = conn.execute(
        """
        SELECT MAX(training_number)
        AS max_number
        FROM trainings
        """
    ).fetchone()

    max_number = row["max_number"]

    if max_number is None:
        return 1

    return max_number + 1


def create_training(
    training_date,
    weekday,
    start_time,
    end_time,
    title,
    category,
    age_group,
    level,
    format,
    coach,
    capacity,
    price,
    location,
    template_id=None,
):
    conn = get_connection()

    now = now_text()

    training_number = _next_training_number(
        conn
    )

    cursor = conn.execute(
        """
        INSERT INTO trainings (
            training_number,
            training_date,
            weekday,
            start_time,
            end_time,
            title,
            category,
            age_group,
            level,
            format,
            coach,
            capacity,
            price,
            location,
            status,
            template_id,
            created_at,
            updated_at
        )
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        (
            training_number,
            training_date,
            weekday,
            start_time,
            end_time,
            title,
            category,
            age_group,
            level,
            format,
            coach,
            capacity,
            price,
            location,
            "scheduled",
            template_id,
            now,
            now,
        ),
    )

    training_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return training_id


def get_training(
    training_id,
):
    conn = get_connection()

    row = conn.execute(
        """
        SELECT *
        FROM trainings
        WHERE id = ?
        """,
        (training_id,),
    ).fetchone()

    conn.close()

    return row


def get_training_by_number(
    training_number,
):
    conn = get_connection()

    row = conn.execute(
        """
        SELECT *
        FROM trainings
        WHERE training_number = ?
        """,
        (training_number,),
    ).fetchone()

    conn.close()

    return row


def get_trainings(
    include_cancelled=False,
):
    conn = get_connection()

    if include_cancelled:
        rows = conn.execute(
            """
            SELECT *
            FROM trainings
            ORDER BY training_date, start_time, id
            """
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT *
            FROM trainings
            WHERE status != 'cancelled'
            ORDER BY training_date, start_time, id
            """
        ).fetchall()

    conn.close()

    return rows


def get_upcoming_trainings(
    from_date=None,
    to_date=None,
    category=None,
):
    conn = get_connection()

    query = """
        SELECT *
        FROM trainings
        WHERE status = 'scheduled'
    """

    params = []

    if from_date:
        query += """
            AND training_date >= ?
        """
        params.append(from_date)

    if to_date:
        query += """
            AND training_date <= ?
        """
        params.append(to_date)

    if category:
        query += """
            AND category = ?
        """
        params.append(category)

    query += """
        ORDER BY training_date, start_time, id
    """

    rows = conn.execute(
        query,
        params,
    ).fetchall()

    conn.close()

    return rows


def get_trainings_by_date(
    training_date,
    category=None,
):
    conn = get_connection()

    if category:
        rows = conn.execute(
            """
            SELECT *
            FROM trainings
            WHERE training_date = ?
              AND category = ?
              AND status != 'cancelled'
            ORDER BY start_time, id
            """,
            (
                training_date,
                category,
            ),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT *
            FROM trainings
            WHERE training_date = ?
              AND status != 'cancelled'
            ORDER BY start_time, id
            """,
            (training_date,),
        ).fetchall()

    conn.close()

    return rows


def get_trainings_by_category(
    category,
    from_date=None,
    to_date=None,
):
    conn = get_connection()

    query = """
        SELECT *
        FROM trainings
        WHERE category = ?
          AND status != 'cancelled'
    """

    params = [category]

    if from_date:
        query += """
            AND training_date >= ?
        """
        params.append(from_date)

    if to_date:
        query += """
            AND training_date <= ?
        """
        params.append(to_date)

    query += """
        ORDER BY training_date, start_time, id
    """

    rows = conn.execute(
        query,
        params,
    ).fetchall()

    conn.close()

    return rows


def update_training(
    training_id,
    **fields,
):
    allowed = {
        "training_date",
        "weekday",
        "start_time",
        "end_time",
        "title",
        "category",
        "age_group",
        "level",
        "format",
        "coach",
        "capacity",
        "price",
        "location",
        "status",
    }

    updates = []
    values = []

    for key, value in fields.items():
        if key in allowed:
            updates.append(
                f"{key} = ?"
            )
            values.append(value)

    if not updates:
        return

    updates.append(
        "updated_at = ?"
    )
    values.append(now_text())

    values.append(training_id)

    conn = get_connection()

    conn.execute(
        f"""
        UPDATE trainings
        SET {", ".join(updates)}
        WHERE id = ?
        """,
        values,
    )

    conn.commit()
    conn.close()


def cancel_training(
    training_id,
):
    update_training(
        training_id,
        status="cancelled",
    )


def complete_training(
    training_id,
):
    update_training(
        training_id,
        status="completed",
    )


# ============================================================
# РЕГИСТРАЦИИ
# ============================================================

def get_registration(
    training_id,
    user_vk_id,
):
    conn = get_connection()

    row = conn.execute(
        """
        SELECT
            registrations.*,
            users.vk_id,
            users.first_name,
            users.last_name
        FROM registrations
        JOIN users
            ON users.id = registrations.user_id
        WHERE registrations.training_id = ?
          AND users.vk_id = ?
          AND registrations.status = 'registered'
        """,
        (
            training_id,
            user_vk_id,
        ),
    ).fetchone()

    conn.close()

    return row


def get_registration_by_id(
    registration_id,
):
    conn = get_connection()

    row = conn.execute(
        """
        SELECT
            registrations.*,
            users.vk_id,
            users.first_name,
            users.last_name
        FROM registrations
        JOIN users
            ON users.id = registrations.user_id
        WHERE registrations.id = ?
        """,
        (registration_id,),
    ).fetchone()

    conn.close()

    return row


def get_registration_count(
    training_id,
):
    conn = get_connection()

    row = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM registrations
        WHERE training_id = ?
          AND status = 'registered'
        """,
        (training_id,),
    ).fetchone()

    conn.close()

    return row["count"]


def get_registrations(
    training_id,
):
    conn = get_connection()

    rows = conn.execute(
        """
        SELECT
            registrations.*,
            users.vk_id,
            users.first_name,
            users.last_name
        FROM registrations
        JOIN users
            ON users.id = registrations.user_id
        WHERE registrations.training_id = ?
          AND registrations.status = 'registered'
        ORDER BY registrations.registered_at
        """,
        (training_id,),
    ).fetchall()

    conn.close()

    return rows


def add_registration(
    training_id,
    user_vk_id,
):
    conn = get_connection()

    now = now_text()

    user = conn.execute(
        """
        SELECT id
        FROM users
        WHERE vk_id = ?
        """,
        (user_vk_id,),
    ).fetchone()

    if not user:
        conn.close()
        raise ValueError(
            "Пользователь не найден"
        )

    training = conn.execute(
        """
        SELECT *
        FROM trainings
        WHERE id = ?
        """,
        (training_id,),
    ).fetchone()

    if not training:
        conn.close()
        raise ValueError(
            "Тренировка не найдена"
        )

    existing = conn.execute(
        """
        SELECT *
        FROM registrations
        WHERE training_id = ?
          AND user_id = ?
        """,
        (
            training_id,
            user["id"],
        ),
    ).fetchone()

    if existing:
        if existing["status"] == "registered":
            conn.close()
            raise ValueError(
                "Пользователь уже записан"
            )

        conn.execute(
            """
            UPDATE registrations
            SET
                status = 'registered',
                registered_at = ?,
                cancelled_at = NULL,
                cancellation_reason = NULL
            WHERE id = ?
            """,
            (
                now,
                existing["id"],
            ),
        )

        conn.commit()
        conn.close()

        return existing["id"]

    count_row = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM registrations
        WHERE training_id = ?
          AND status = 'registered'
        """,
        (training_id,),
    ).fetchone()

    if count_row["count"] >= training["capacity"]:
        conn.close()
        raise ValueError(
            "Тренировка заполнена"
        )

    cursor = conn.execute(
        """
        INSERT INTO registrations (
            training_id,
            user_id,
            status,
            registered_at
        )
        VALUES (?, ?, 'registered', ?)
        """,
        (
            training_id,
            user["id"],
            now,
        ),
    )

    registration_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return registration_id


def cancel_registration(
    training_id,
    user_vk_id,
    reason=None,
):
    conn = get_connection()

    user = conn.execute(
        """
        SELECT id
        FROM users
        WHERE vk_id = ?
        """,
        (user_vk_id,),
    ).fetchone()

    if not user:
        conn.close()
        return False

    cursor = conn.execute(
        """
        UPDATE registrations
        SET
            status = 'cancelled',
            cancelled_at = ?,
            cancellation_reason = ?
        WHERE training_id = ?
          AND user_id = ?
          AND status = 'registered'
        """,
        (
            now_text(),
            reason,
            training_id,
            user["id"],
        ),
    )

    conn.commit()
    conn.close()

    return cursor.rowcount > 0


def delete_registration(
    training_id,
    user_vk_id,
):
    return cancel_registration(
        training_id,
        user_vk_id,
    )


def get_user_registrations(
    user_vk_id,
    include_cancelled=False,
):
    conn = get_connection()

    query = """
        SELECT
            registrations.*,

            trainings.training_number,
            trainings.training_date,
            trainings.weekday,
            trainings.start_time,
            trainings.end_time,
            trainings.title,
            trainings.category,
            trainings.age_group,
            trainings.level,
            trainings.format,
            trainings.coach,
            trainings.capacity,
            trainings.price,
            trainings.location,
            trainings.status AS training_status

        FROM registrations

        JOIN users
            ON users.id = registrations.user_id

        JOIN trainings
            ON trainings.id = registrations.training_id

        WHERE users.vk_id = ?
    """

    params = [user_vk_id]

    if not include_cancelled:
        query += """
            AND registrations.status = 'registered'
            AND trainings.status != 'cancelled'
        """

    query += """
        ORDER BY
            trainings.training_date,
            trainings.start_time
    """

    rows = conn.execute(
        query,
        params,
    ).fetchall()

    conn.close()

    return rows


# ============================================================
# WAITLIST
# ============================================================

def get_waitlist(
    training_id,
):
    conn = get_connection()

    rows = conn.execute(
        """
        SELECT
            waitlist.*,
            users.vk_id,
            users.first_name,
            users.last_name
        FROM waitlist
        JOIN users
            ON users.id = waitlist.user_id
        WHERE waitlist.training_id = ?
          AND waitlist.status = 'waiting'
        ORDER BY waitlist.position
        """,
        (training_id,),
    ).fetchall()

    conn.close()

    return rows


def get_waitlist_entry(
    training_id,
    user_vk_id,
):
    conn = get_connection()

    row = conn.execute(
        """
        SELECT
            waitlist.*,
            users.vk_id,
            users.first_name,
            users.last_name
        FROM waitlist
        JOIN users
            ON users.id = waitlist.user_id
        WHERE waitlist.training_id = ?
          AND users.vk_id = ?
          AND waitlist.status = 'waiting'
        """,
        (
            training_id,
            user_vk_id,
        ),
    ).fetchone()

    conn.close()

    return row


def add_to_waitlist(
    training_id,
    user_vk_id,
):
    conn = get_connection()

    user = conn.execute(
        """
        SELECT id
        FROM users
        WHERE vk_id = ?
        """,
        (user_vk_id,),
    ).fetchone()

    if not user:
        conn.close()
        raise ValueError(
            "Пользователь не найден"
        )

    existing = conn.execute(
        """
        SELECT *
        FROM waitlist
        WHERE training_id = ?
          AND user_id = ?
          AND status = 'waiting'
        """,
        (
            training_id,
            user["id"],
        ),
    ).fetchone()

    if existing:
        conn.close()
        return existing["id"]

    row = conn.execute(
        """
        SELECT MAX(position) AS max_position
        FROM waitlist
        WHERE training_id = ?
          AND status = 'waiting'
        """,
        (training_id,),
    ).fetchone()

    position = (
        (row["max_position"] or 0) + 1
    )

    cursor = conn.execute(
        """
        INSERT INTO waitlist (
            training_id,
            user_id,
            position,
            status,
            created_at
        )
        VALUES (?, ?, ?, 'waiting', ?)
        """,
        (
            training_id,
            user["id"],
            position,
            now_text(),
        ),
    )

    waitlist_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return waitlist_id


def remove_from_waitlist(
    training_id,
    user_vk_id,
):
    conn = get_connection()

    user = conn.execute(
        """
        SELECT id
        FROM users
        WHERE vk_id = ?
        """,
        (user_vk_id,),
    ).fetchone()

    if not user:
        conn.close()
        return False

    cursor = conn.execute(
        """
        UPDATE waitlist
        SET status = 'removed'
        WHERE training_id = ?
          AND user_id = ?
          AND status = 'waiting'
        """,
        (
            training_id,
            user["id"],
        ),
    )

    conn.commit()
    conn.close()

    return cursor.rowcount > 0


# ============================================================
# ATTENDANCE
# ============================================================

def create_attendance_for_registration(
    registration_id,
):
    conn = get_connection()

    existing = conn.execute(
        """
        SELECT id
        FROM attendance
        WHERE registration_id = ?
        """,
        (registration_id,),
    ).fetchone()

    if existing:
        conn.close()
        return existing["id"]

    cursor = conn.execute(
        """
        INSERT INTO attendance (
            registration_id,
            status
        )
        VALUES (?, 'unknown')
        """,
        (registration_id,),
    )

    attendance_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return attendance_id


def mark_attendance(
    registration_id,
    status,
    marked_by=None,
    comment=None,
):
    conn = get_connection()

    existing = conn.execute(
        """
        SELECT id
        FROM attendance
        WHERE registration_id = ?
        """,
        (registration_id,),
    ).fetchone()

    if existing:
        conn.execute(
            """
            UPDATE attendance
            SET
                status = ?,
                marked_by = ?,
                marked_at = ?,
                comment = ?
            WHERE registration_id = ?
            """,
            (
                status,
                marked_by,
                now_text(),
                comment,
                registration_id,
            ),
        )
    else:
        conn.execute(
            """
            INSERT INTO attendance (
                registration_id,
                status,
                marked_by,
                marked_at,
                comment
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                registration_id,
                status,
                marked_by,
                now_text(),
                comment,
            ),
        )

    conn.commit()
    conn.close()


def get_training_attendance(
    training_id,
):
    conn = get_connection()

    rows = conn.execute(
        """
        SELECT
            attendance.*,

            registrations.user_id,

            users.vk_id,
            users.first_name,
            users.last_name

        FROM attendance

        JOIN registrations
            ON registrations.id =
               attendance.registration_id

        JOIN users
            ON users.id = registrations.user_id

        WHERE registrations.training_id = ?

        ORDER BY users.first_name, users.last_name
        """,
        (training_id,),
    ).fetchall()

    conn.close()

    return rows


# ============================================================
# PAYMENTS
# ============================================================

def create_payment(
    user_vk_id,
    amount,
    training_id=None,
    payment_method=None,
    external_id=None,
):
    conn = get_connection()

    user = conn.execute(
        """
        SELECT id
        FROM users
        WHERE vk_id = ?
        """,
        (user_vk_id,),
    ).fetchone()

    if not user:
        conn.close()
        raise ValueError(
            "Пользователь не найден"
        )

    cursor = conn.execute(
        """
        INSERT INTO payments (
            user_id,
            training_id,
            amount,
            status,
            payment_method,
            external_id,
            created_at
        )
        VALUES (
            ?, ?, ?, 'pending', ?, ?, ?
        )
        """,
        (
            user["id"],
            training_id,
            amount,
            payment_method,
            external_id,
            now_text(),
        ),
    )

    payment_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return payment_id


def update_payment_status(
    payment_id,
    status,
):
    conn = get_connection()

    paid_at = (
        now_text()
        if status == "paid"
        else None
    )

    conn.execute(
        """
        UPDATE payments
        SET
            status = ?,
            paid_at = COALESCE(?, paid_at)
        WHERE id = ?
        """,
        (
            status,
            paid_at,
            payment_id,
        ),
    )

    conn.commit()
    conn.close()


def get_user_payments(
    user_vk_id,
):
    conn = get_connection()

    rows = conn.execute(
        """
        SELECT payments.*

        FROM payments

        JOIN users
            ON users.id = payments.user_id

        WHERE users.vk_id = ?

        ORDER BY payments.created_at DESC
        """,
        (user_vk_id,),
    ).fetchall()

    conn.close()

    return rows


# ============================================================
# NOTIFICATIONS
# ============================================================

def create_notification(
    user_vk_id,
    training_id,
    notification_type,
    scheduled_for,
):
    conn = get_connection()

    user = conn.execute(
        """
        SELECT id
        FROM users
        WHERE vk_id = ?
        """,
        (user_vk_id,),
    ).fetchone()

    if not user:
        conn.close()
        raise ValueError(
            "Пользователь не найден"
        )

    existing = conn.execute(
        """
        SELECT id
        FROM notifications
        WHERE user_id = ?
          AND training_id = ?
          AND notification_type = ?
        """,
        (
            user["id"],
            training_id,
            notification_type,
        ),
    ).fetchone()

    if existing:
        conn.close()
        return existing["id"]

    cursor = conn.execute(
        """
        INSERT INTO notifications (
            user_id,
            training_id,
            notification_type,
            scheduled_for,
            status,
            created_at
        )
        VALUES (
            ?, ?, ?, ?, 'pending', ?
        )
        """,
        (
            user["id"],
            training_id,
            notification_type,
            scheduled_for,
            now_text(),
        ),
    )

    notification_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return notification_id


def get_pending_notifications(
    current_time,
):
    conn = get_connection()

    rows = conn.execute(
        """
        SELECT
            notifications.*,
            users.vk_id

        FROM notifications

        JOIN users
            ON users.id = notifications.user_id

        WHERE notifications.status = 'pending'
          AND notifications.scheduled_for <= ?

        ORDER BY notifications.scheduled_for
        """,
        (current_time,),
    ).fetchall()

    conn.close()

    return rows


def mark_notification_sent(
    notification_id,
):
    conn = get_connection()

    conn.execute(
        """
        UPDATE notifications
        SET
            status = 'sent',
            sent_at = ?
        WHERE id = ?
        """,
        (
            now_text(),
            notification_id,
        ),
    )

    conn.commit()
    conn.close()


def mark_notification_failed(
    notification_id,
):
    conn = get_connection()

    conn.execute(
        """
        UPDATE notifications
        SET status = 'failed'
        WHERE id = ?
        """,
        (notification_id,),
    )

    conn.commit()
    conn.close()


# ============================================================
# ADMIN LOG
# ============================================================

def add_admin_log(
    admin_vk_id,
    action,
    details=None,
    entity_type=None,
    entity_id=None,
):
    conn = get_connection()

    conn.execute(
        """
        INSERT INTO admin_logs (
            admin_vk_id,
            action,
            entity_type,
            entity_id,
            details,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            admin_vk_id,
            action,
            entity_type,
            entity_id,
            details,
            now_text(),
        ),
    )

    conn.commit()
    conn.close()


def get_admin_logs(
    limit=100,
):
    conn = get_connection()

    rows = conn.execute(
        """
        SELECT *
        FROM admin_logs
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    conn.close()

    return rows


# ============================================================
# СЛУЖЕБНЫЕ ФУНКЦИИ
# ============================================================

def get_database_stats():
    conn = get_connection()

    stats = {}

    tables = [
        "users",
        "training_templates",
        "trainings",
        "registrations",
        "waitlist",
        "attendance",
        "payments",
        "notifications",
        "admin_logs",
    ]

    for table in tables:
        row = conn.execute(
            f"""
            SELECT COUNT(*) AS count
            FROM {table}
            """
        ).fetchone()

        stats[table] = row["count"]

    conn.close()

    return stats
