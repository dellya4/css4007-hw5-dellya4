import os
import re
import sqlite3
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_DIR = Path(__file__).resolve().parent.parent

storage = Path(os.getenv(
    "HELPDESK_STORAGE_DIR", "local-storage"
))

if not storage.is_absolute():
    storage = PROJECT_DIR / storage

STORAGE_DIR = storage


class UserMemory:
    def __init__(self, database_path):
        self.conn = sqlite3.connect(database_path)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id TEXT PRIMARY KEY,
                language TEXT NOT NULL
            )
        """)
        self.conn.commit()

    def get_language(self, user_id):
        row = self.conn.execute(
            """
            SELECT language
            FROM user_preferences
            WHERE user_id = ?
            """,
            (user_id,)
        ).fetchone()

        return row[0] if row else None

    def save_language(self, user_id, language):
        self.conn.execute(
            """
            INSERT INTO user_preferences (user_id, language)
            VALUES (?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET language = excluded.language
            """,
            (user_id, language)
        )
        self.conn.commit()

    def close(self):
        self.conn.close()


def extract_language_preference(message):
    """
    Detect an explicit language preference.
    This is a simple rule for the HW5 demo.
    """
    text = message.lower()

    patterns = [
        r"(?:prefer|want|choose)\s+(?:your\s+)?replies\s+in\s+(kazakh|english|russian)",
        r"(?:reply|respond|answer|speak)\s+(?:to me\s+)?in\s+(kazakh|english|russian)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).capitalize()

    return None
