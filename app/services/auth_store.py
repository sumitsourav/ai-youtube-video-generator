# app/services/auth_store.py

from contextlib import closing

from app.services.db import connect


def create_user(username: str, password_hash: str, created_at: str) -> int:
    with closing(connect()) as conn:
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
            (username, password_hash, created_at),
        )
        conn.commit()
        return cursor.lastrowid


def get_user_by_username(username: str):
    with closing(connect()) as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: int):
    with closing(connect()) as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def list_users_with_job_counts():
    with closing(connect()) as conn:
        rows = conn.execute(
            """
            SELECT
                users.id, users.username, users.is_admin, users.created_at,
                COUNT(jobs.job_id) AS job_count,
                SUM(CASE WHEN jobs.status = 'done' THEN 1 ELSE 0 END) AS done_count
            FROM users
            LEFT JOIN jobs ON jobs.user_id = users.id
            GROUP BY users.id
            ORDER BY users.created_at DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]
