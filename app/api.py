# app/api.py

import logging
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import bcrypt
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

from app.config import AUDIO_DIR, HTTPS_ONLY_COOKIES, IMAGE_DIR, SESSION_SECRET, VIDEO_DIR
from app.services.auth_store import create_user, get_user_by_id, get_user_by_username, list_users_with_job_counts
from app.services.db import init_db
from app.services.job_store import create_job, delete_job, get_job, list_all_jobs, list_jobs, update_job
from app.services.script_service import generate_script_and_keywords
from app.services.storage_service import (
    delete_video,
    get_download_url,
    is_configured as storage_configured,
    upload_video,
)
from app.services.topic_wise_video import topic_wise_video
from app.services.tts_service import generate_audio
from app.services.video_fetch_service import fetch_videos
from app.services.video_service import create_video
from app.utils.file_utils import ensure_dirs

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai_video_generator")

if not SESSION_SECRET:
    raise RuntimeError("SESSION_SECRET must be set (see .env.example)")


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_dirs([IMAGE_DIR, AUDIO_DIR, VIDEO_DIR])
    init_db()
    yield


app = FastAPI(title="AI YouTube Video Generator", lifespan=lifespan)

app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, https_only=HTTPS_ONLY_COOKIES)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

MAX_TOPIC_LENGTH = 200
MIN_PASSWORD_LENGTH = 8
MAX_USERNAME_LENGTH = 50
MIN_LENGTH_MINUTES = 1
MAX_LENGTH_MINUTES = 5
STUCK_AFTER_MINUTES = 30


# ---------------------------------------------------------------------------
# auth
# ---------------------------------------------------------------------------

class AuthRequest(BaseModel):
    username: str
    password: str


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def get_current_user(request: Request) -> dict:
    user_id = request.session.get("user_id")
    user = get_user_by_id(user_id) if user_id else None
    if user is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    return user


def get_current_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="admin access required")
    return current_user


@app.post("/auth/signup")
def signup(payload: AuthRequest, request: Request):
    username = payload.username.strip()
    if not username or len(username) > MAX_USERNAME_LENGTH:
        raise HTTPException(status_code=400, detail="invalid username")
    if len(payload.password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"password must be at least {MIN_PASSWORD_LENGTH} characters",
        )
    if get_user_by_username(username):
        raise HTTPException(status_code=409, detail="username already taken")

    user_id = create_user(
        username, hash_password(payload.password), datetime.now(timezone.utc).isoformat()
    )
    request.session["user_id"] = user_id
    return {"username": username}


@app.post("/auth/login")
def login(payload: AuthRequest, request: Request):
    user = get_user_by_username(payload.username.strip())
    if user is None or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="invalid username or password")
    request.session["user_id"] = user["id"]
    return {"username": user["username"]}


@app.post("/auth/logout")
def logout(request: Request):
    request.session.clear()
    return {"status": "ok"}


@app.get("/auth/me")
def auth_me(current_user: dict = Depends(get_current_user)):
    return {"username": current_user["username"], "is_admin": bool(current_user.get("is_admin"))}


# ---------------------------------------------------------------------------
# video pipeline
# ---------------------------------------------------------------------------

def _validate_topic(topic: str) -> str:
    topic = topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="topic must not be empty")
    if len(topic) > MAX_TOPIC_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"topic must be at most {MAX_TOPIC_LENGTH} characters",
        )
    return topic


def _get_owned_job(job_id: str, current_user: dict) -> dict:
    job = get_job(job_id)
    is_owner = job is not None and job.get("user_id") == current_user["id"]
    if job is None or not (is_owner or current_user.get("is_admin")):
        raise HTTPException(status_code=404, detail="job not found")
    return job


_STEP_LABELS = {
    "queued": "startup",
    "generating_script": "script generation",
    "generating_audio": "voiceover generation",
    "fetching_videos": "fetching stock footage",
    "rendering_video": "video rendering",
    "uploading": "uploading to storage",
}


def _set_step(job_id: str, step: str):
    update_job(job_id, status=step, last_step=step)


def run_video_pipeline(job_id: str, topic: str, length_minutes: int):
    try:
        _set_step(job_id, "generating_script")
        script, keywords = generate_script_and_keywords(
            topic, length_minutes=length_minutes
        )
        if not script:
            raise RuntimeError("Script generation returned empty text")
        update_job(job_id, script=script)

        # Footage doesn't depend on the audio, so it downloads in the
        # background while the (much slower) voiceover renders, keeping it off
        # the critical path.
        with ThreadPoolExecutor(max_workers=1) as fetch_executor:
            fetch_future = fetch_executor.submit(fetch_videos, keywords)

            _set_step(job_id, "generating_audio")
            audio_path = os.path.join(AUDIO_DIR, f"{job_id}.wav")
            generate_audio(script, output_path=audio_path)

            _set_step(job_id, "fetching_videos")
            videos = fetch_future.result()

        if not videos:
            raise RuntimeError("No source videos found for this topic")

        _set_step(job_id, "rendering_video")
        update_job(job_id, render_progress=0)
        video_path = os.path.join(VIDEO_DIR, f"{job_id}.mp4")
        _, actual_duration_seconds = create_video(
            videos,
            audio_path,
            script,
            output_path=video_path,
            progress_callback=lambda pct: update_job(job_id, render_progress=pct),
        )
        # Recorded before the B2 upload, which deletes the local copy.
        update_job(
            job_id,
            actual_duration_seconds=actual_duration_seconds,
            video_size_bytes=os.path.getsize(video_path),
        )

        video_key = None
        if storage_configured():
            _set_step(job_id, "uploading")
            video_key = f"{job_id}.mp4"
            upload_video(video_path, video_key)
            try:
                os.remove(video_path)
            except OSError:
                logger.warning("Could not remove local copy after upload: %s", video_path)

        update_job(
            job_id,
            status="done",
            video_path=video_path,
            video_key=video_key,
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
        logger.info("Job %s finished (video_key=%s)", job_id, video_key)
    except Exception as exc:
        logger.exception("Job %s failed", job_id)
        current_job = get_job(job_id)
        failed_step = (current_job or {}).get("last_step")
        step_label = _STEP_LABELS.get(failed_step, failed_step or "the pipeline")
        update_job(
            job_id,
            status="failed",
            error=f"Failed during {step_label}: {exc}",
            finished_at=datetime.now(timezone.utc).isoformat(),
        )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def index():
    return FileResponse(
        os.path.join(STATIC_DIR, "index.html"),
        headers={"Cache-Control": "no-cache"},
    )


@app.post("/generate")
def generate_video(
    background_tasks: BackgroundTasks,
    topic: str = Query(...),
    length_minutes: int = Query(2, ge=MIN_LENGTH_MINUTES, le=MAX_LENGTH_MINUTES),
    current_user: dict = Depends(get_current_user),
):
    topic = _validate_topic(topic)

    job_id = uuid.uuid4().hex
    create_job(
        job_id,
        topic,
        "queued",
        datetime.now(timezone.utc).isoformat(),
        user_id=current_user["id"],
        length_minutes=length_minutes,
    )

    background_tasks.add_task(run_video_pipeline, job_id, topic, length_minutes)

    return {
        "job_id": job_id,
        "status": "queued",
        "status_url": f"/status/{job_id}",
    }


@app.get("/status/{job_id}")
def get_status(job_id: str, current_user: dict = Depends(get_current_user)):
    return _get_owned_job(job_id, current_user)


@app.get("/jobs")
def get_jobs(limit: int = Query(20, ge=1, le=100), current_user: dict = Depends(get_current_user)):
    return {"jobs": list_jobs(user_id=current_user["id"], limit=limit)}


@app.get("/download/{job_id}")
def download_video(job_id: str, current_user: dict = Depends(get_current_user)):
    job = _get_owned_job(job_id, current_user)
    if job["status"] != "done":
        raise HTTPException(status_code=409, detail=f"job is {job['status']}, not ready yet")

    if job.get("video_key"):
        return RedirectResponse(get_download_url(job["video_key"]))

    video_path = job["video_path"]
    if not video_path or not os.path.exists(video_path):
        raise HTTPException(status_code=410, detail="video file no longer available")

    return FileResponse(video_path, media_type="video/mp4", filename=f"{job_id}.mp4")


@app.get("/jobs/{job_id}/link")
def get_job_link(job_id: str, current_user: dict = Depends(get_current_user)):
    job = _get_owned_job(job_id, current_user)
    if job["status"] != "done":
        raise HTTPException(status_code=409, detail=f"job is {job['status']}, not ready yet")
    if not job.get("video_key"):
        raise HTTPException(status_code=404, detail="no shareable link available for this video")
    return {"url": get_download_url(job["video_key"])}


def _is_stuck(job: dict) -> bool:
    if job["status"] in ("done", "failed"):
        return False
    age = datetime.now(timezone.utc) - datetime.fromisoformat(job["created_at"])
    return age.total_seconds() / 60 > STUCK_AFTER_MINUTES


@app.delete("/jobs/{job_id}")
def delete_job_route(job_id: str, current_user: dict = Depends(get_current_user)):
    job = _get_owned_job(job_id, current_user)
    if job["status"] not in ("done", "failed") and not _is_stuck(job):
        raise HTTPException(status_code=409, detail="cannot delete a job that is still in progress")

    if job.get("video_key") and storage_configured():
        try:
            delete_video(job["video_key"])
        except Exception:
            logger.exception("Failed to delete %s from storage", job["video_key"])

    video_path = job.get("video_path")
    if video_path and os.path.exists(video_path):
        try:
            os.remove(video_path)
        except OSError:
            logger.warning("Could not remove local video file: %s", video_path)

    delete_job(job_id)
    return {"status": "deleted"}


@app.get("/video_by_topic")
def get_video(topic: str, current_user: dict = Depends(get_current_user)):
    topic = _validate_topic(topic)
    return {"videos": topic_wise_video(topic)}


# ---------------------------------------------------------------------------
# admin
# ---------------------------------------------------------------------------

@app.get("/admin/users")
def admin_list_users(admin: dict = Depends(get_current_admin)):
    return {"users": list_users_with_job_counts()}


@app.get("/admin/jobs")
def admin_list_jobs(limit: int = Query(100, ge=1, le=500), admin: dict = Depends(get_current_admin)):
    return {"jobs": list_all_jobs(limit=limit)}


@app.get("/admin")
def admin_page():
    return FileResponse(
        os.path.join(STATIC_DIR, "admin.html"),
        headers={"Cache-Control": "no-cache"},
    )
