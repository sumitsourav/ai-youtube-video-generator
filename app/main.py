# app/main.py

from app.services.script_service import generate_script
from app.services.tts_service import generate_audio
from app.services.image_service import fetch_images
from app.services.video_fetch_service import fetch_videos
from app.services.video_service import create_video
from app.utils.file_utils import ensure_dirs
from app.config import IMAGE_DIR, AUDIO_DIR, VIDEO_DIR, TTS_ENGINE

print("✅ Main application loaded")
print(f"📢 Using TTS Engine: {TTS_ENGINE}")

def run(topic):
    try:
        ensure_dirs([IMAGE_DIR, AUDIO_DIR, VIDEO_DIR])

        print("\n📝 Generating script...")
        script = generate_script(topic)

        if not script:
            raise Exception("Script generation failed")

        print("\n🎙️  Generating audio...")
        audio = generate_audio(script)

        #print("\n📸 Fetching images...")
        #images = fetch_images(topic)

        print("\n🎥 Fetching videos...")
        videos = fetch_videos(topic)

        if not videos:
            raise Exception("No images found")

        print("\n🎬 Creating video...")
        video = create_video(videos, audio, script)

        print(f"\n🎉 Done! Video: {video}")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("▶️  Running AI YouTube Video Generator...")
    topic = input("📌 Enter topic: ")
    run(topic)