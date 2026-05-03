import aiosqlite

from config import DATABASE_PATH


async def init_db():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                discord_user_id INTEGER NOT NULL,
                discord_username TEXT NOT NULL,
                minecraft_nick TEXT NOT NULL,
                age TEXT,
                experience TEXT,
                reason TEXT,
                rules_agreement TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                staff_message_id INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS application_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                application_id INTEGER NOT NULL,
                moderator_id INTEGER NOT NULL,
                moderator_username TEXT NOT NULL,
                decision TEXT NOT NULL,
                comment TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (application_id) REFERENCES applications (id)
            )
        """)

        await db.commit()


async def create_application(
    discord_user_id: int,
    discord_username: str,
    minecraft_nick: str,
    age: str,
    experience: str,
    reason: str,
    rules_agreement: str,
) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO applications (
                discord_user_id,
                discord_username,
                minecraft_nick,
                age,
                experience,
                reason,
                rules_agreement,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
            """,
            (
                discord_user_id,
                discord_username,
                minecraft_nick,
                age,
                experience,
                reason,
                rules_agreement,
            ),
        )

        await db.commit()
        return cursor.lastrowid


async def set_staff_message_id(application_id: int, staff_message_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            UPDATE applications
            SET staff_message_id = ?
            WHERE id = ?
            """,
            (staff_message_id, application_id),
        )
        await db.commit()


async def get_application_status(application_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            SELECT status
            FROM applications
            WHERE id = ?
            """,
            (application_id,),
        )
        return await cursor.fetchone()


async def update_application_status(application_id: int, status: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            UPDATE applications
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status, application_id),
        )
        await db.commit()


async def create_moderation_decision(
    application_id: int,
    moderator_id: int,
    moderator_username: str,
    decision: str,
):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO application_decisions (
                application_id,
                moderator_id,
                moderator_username,
                decision
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                application_id,
                moderator_id,
                moderator_username,
                decision,
            ),
        )
        await db.commit()


async def get_application_user_id(application_id: int) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            SELECT discord_user_id
            FROM applications
            WHERE id = ?
            """,
            (application_id,),
        )
        row = await cursor.fetchone()

    if row is None:
        raise ValueError(f"Application #{application_id} not found")

    return int(row[0])


async def get_latest_application_by_user(discord_user_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            SELECT id, status, created_at
            FROM applications
            WHERE discord_user_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (discord_user_id,),
        )
        return await cursor.fetchone()