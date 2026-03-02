# app/api.py

from fastapi import FastAPI
from app.services.script_service import generate_script
from app.services.tts_service import generate_audio
from app.services.image_service import fetch_images
from app.services.video_fetch_service import fetch_videos
from app.services.video_service import create_video

app = FastAPI()

@app.post("/generate")
def generate_video(topic: str):
    script = generate_script(topic)
    audio = generate_audio(script)
    videos = fetch_videos(topic)
    video = create_video(videos, audio, script)

    return {"video_path": video}