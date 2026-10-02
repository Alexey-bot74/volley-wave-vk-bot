trations
        SET status = 'cancelled'
        WHERE training_id = ?
        AND user_id = ?
        AND status = 'registered'
    """, (training_id, user["id"]))

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
            trainings.date,
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

        ORDER BY trainings.date, trainings.time
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
    """, (key, str(value)))

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

    return default l
