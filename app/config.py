import os
from dotenv import load_dotenv

load_dotenv()

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")

OUTPUT_DIR = "assets"
IMAGE_DIR = f"{OUTPUT_DIR}/images"
AUDIO_DIR = f"{OUTPUT_DIR}/audio"
VIDEO_DIR = f"{OUTPUT_DIR}/videos"

VIDEO_NAME = f"{VIDEO_DIR}/output.mp4"
AUDIO_NAME = f"{AUDIO_DIR}/voice.wav"