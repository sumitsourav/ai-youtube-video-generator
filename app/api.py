# app/api.py

from fastapi import FastAPI
from app.services.script_service import generate_script
from app.services.tts_service import generate_audio
from app.services.image_service import fetch_images
from app.services.video_fetch_service import fetch_videos
from app.services.video_service import create_video
from app.services.topic_wise_video import topic_wise_video
from fastapi import BackgroundTasks

app = FastAPI()

def complete_video_pipeline(topic: str, script: str, audio: str):
    videos = fetch_videos(topic)
    video = create_video(videos, audio, script)
    print(f"Video ready at: {video}")

@app.post("/generate")
async def generate_video(topic: str, background_tasks: BackgroundTasks):
    script = generate_script(topic)
    audio = generate_audio(script)
    background_tasks.add_task(complete_video_pipeline, topic, script, audio)
    # videos = fetch_videos(topic)
    return {"status": "Task started", "message": "Video is being generated in the background."}

@app.get("/video_by_topic")
def get_video(topic: str):
    # This endpoint can be used to fetch a pre-generated video for a topic
    # For simplicity, we will just return the latest generated video
    selected_videos = topic_wise_video(topic)
    return selected_videos

# if __name__ == "__main__":
#     print("▶️  Running AI YouTube Video Generator...")
#     topic = input("📌 Enter topic: ")
#     run(topic)