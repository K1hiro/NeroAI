import sqlite3
from contextlib import closing
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "data" / "neroai.db"


def initialize_database():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with closing(sqlite3.connect(DB_PATH)) as connection:
        with connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    role TEXT NOT NULL CHECK (
                        role IN ('user', 'assistant')
                    ),
                    content TEXT NOT NULL
                )
            """)
            connection.execute("""
                CREATE INDEX IF NOT EXISTS conversation_index
                ON messages (channel_id, user_id, id)
            """)


def load_history(channel_id, user_id, limit=20):
    with closing(sqlite3.connect(DB_PATH)) as connection:
        rows = connection.execute(
            """
            SELECT role, content
            FROM messages
            WHERE channel_id = ? AND user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (channel_id, user_id, limit),
        ).fetchall()

    # The query gets newest first; the model needs oldest first.
    return [
        {"role": role, "content": content}
        for role, content in reversed(rows)
    ]


def save_turn(channel_id, user_id, question, reply, limit=20):
    with closing(sqlite3.connect(DB_PATH)) as connection:
        with connection:
            connection.executemany(
                """
                INSERT INTO messages (channel_id, user_id, role, content)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (channel_id, user_id, "user", question),
                    (channel_id, user_id, "assistant", reply),
                ],
            )

            # Keep only the latest messages for this conversation.
            connection.execute(
                """
                DELETE FROM messages
                WHERE channel_id = ? AND user_id = ?
                  AND id NOT IN (
                      SELECT id
                      FROM messages
                      WHERE channel_id = ? AND user_id = ?
                      ORDER BY id DESC
                      LIMIT ?
                  )
                """,
                (channel_id, user_id, channel_id, user_id, limit),
            )


def clear_history(channel_id, user_id):
    with closing(sqlite3.connect(DB_PATH)) as connection:
        with connection:
            connection.execute(
                """
                DELETE FROM messages
                WHERE channel_id = ? AND user_id = ?
                """,
                (channel_id, user_id),
            )
