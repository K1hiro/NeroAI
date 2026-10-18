import sqlite3
from contextlib import closing
from datetime import datetime, timezone

from memory_store import DB_PATH


def initialize_warning_database():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with closing(sqlite3.connect(DB_PATH)) as connection:
        with connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS warnings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    moderator_id INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

            connection.execute("""
                CREATE INDEX IF NOT EXISTS warnings_member_index
                ON warnings (guild_id, user_id, id)
            """)


def record_warning(guild_id, user_id, moderator_id, reason):
    reason = reason.strip()
    if not reason:
        raise ValueError("A warning must have a reason.")

    created_at = datetime.now(timezone.utc).isoformat()

    with closing(sqlite3.connect(DB_PATH)) as connection:
        with connection:
            cursor = connection.execute(
                """
                INSERT INTO warnings (
                    guild_id,
                    user_id,
                    moderator_id,
                    reason,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    guild_id,
                    user_id,
                    moderator_id,
                    reason,
                    created_at,
                ),
            )

            warning_id = cursor.lastrowid

    return warning_id
