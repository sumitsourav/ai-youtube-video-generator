# app/services/job_store.py

from contextlib import closing

from app.services.db import connect

_ALLOWED_UPDATE_FIELDS = {
    "status",
    "last_step",
    "script",
    "video_path",
    "video_key",
    "error",
    "finished_at",
    "render_progress",
    "actual_duration_seconds",
}


def create_job(job_id: str, topic: str, status: str, created_at: str, user_id: int, length_minutes: int):
    with closing(connect()) as conn:
        conn.execute(
            "INSERT INTO jobs (job_id, user_id, topic, status, created_at, length_minutes) VALUES (?, ?, ?, ?, ?, ?)",
            (job_id, user_id, topic, status, created_at, length_minutes),
        )
        conn.commit()


def update_job(job_id: str, **fields):
    if not fields:
        return
    unknown = set(fields) - _ALLOWED_UPDATE_FIELDS
    if unknown:
        raise ValueError(f"Cannot update unknown job fields: {unknown}")

    assignments = ", ".join(f"{key} = ?" for key in fields)
    values = [*fields.values(), job_id]
    with closing(connect()) as conn:
        conn.execute(f"UPDATE jobs SET {assignments} WHERE job_id = ?", values)
        conn.commit()


def get_job(job_id: str):
    with closing(connect()) as conn:
        row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    return dict(row) if row else None


def list_jobs(user_id: int, limit: int = 20):
    with closing(connect()) as conn:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def delete_job(job_id: str):
    with closing(connect()) as conn:
        conn.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
        conn.commit()


def list_all_jobs(limit: int = 100):
    """Admin use only - every job across every user, with the owning
    username attached, not scoped to a single account."""
    with closing(connect()) as conn:
        rows = conn.execute(
            """
            SELECT jobs.*, users.username
            FROM jobs
            LEFT JOIN users ON users.id = jobs.user_id
            ORDER BY jobs.created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]
