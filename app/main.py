# app/main.py

from app.services.script_service import generate_script
from app.services.tts_service import generate_audio
from app.services.image_service import fetch_images
from app.services.video_service import create_video
from app.utils.file_utils import ensure_dirs
from app.config import IMAGE_DIR, AUDIO_DIR, VIDEO_DIR

print("Main file loaded")

def run(topic):
    try:
        ensure_dirs([IMAGE_DIR, AUDIO_DIR, VIDEO_DIR])

        print("Generating script...")
        script = generate_script(topic)

        if not script:
            raise Exception("Script generation failed")

        print("Generating audio...")
        audio = generate_audio(script)

        print("Fetching images...")
        images = fetch_images(topic)

        if not images:
            raise Exception("No images found")

        print("Creating video...")
        video = create_video(images, audio, script)

        print("Done! Video:", video)

    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    print("Running application...")
    topic = input("Enter topic: ")
    run(topic)