# app/services/db.py

import os
import sqlite3
from contextlib import closing

from app.config import OUTPUT_DIR

DB_PATH = os.path.join(OUTPUT_DIR, "jobs.db")

_JOBS_MIGRATION_COLUMNS = {
    "video_key": "TEXT",
    "last_step": "TEXT",
    "script": "TEXT",
    "user_id": "INTEGER",
    "render_progress": "INTEGER",
    "length_minutes": "INTEGER",
    "actual_duration_seconds": "REAL",
    "video_size_bytes": "INTEGER",
    "image_credits": "TEXT",
    "template": "TEXT",
}

_USERS_MIGRATION_COLUMNS = {
    "is_admin": "INTEGER NOT NULL DEFAULT 0",
}


def connect():
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with closing(connect()) as conn:
        conn.execute("PRAGMA journal_mode=WAL")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                user_id INTEGER,
                topic TEXT NOT NULL,
                status TEXT NOT NULL,
                last_step TEXT,
                script TEXT,
                video_path TEXT,
                video_key TEXT,
                error TEXT,
                created_at TEXT NOT NULL,
                finished_at TEXT
            )
            """
        )
        for column, column_type in _JOBS_MIGRATION_COLUMNS.items():
            try:
                conn.execute(f"ALTER TABLE jobs ADD COLUMN {column} {column_type}")
            except sqlite3.OperationalError:
                pass  # column already exists on a pre-existing db file

        for column, column_type in _USERS_MIGRATION_COLUMNS.items():
            try:
                conn.execute(f"ALTER TABLE users ADD COLUMN {column} {column_type}")
            except sqlite3.OperationalError:
                pass  # column already exists on a pre-existing db file

        conn.commit()
