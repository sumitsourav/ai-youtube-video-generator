import os
from dotenv import load_dotenv

load_dotenv()

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

OUTPUT_DIR = "assets"
IMAGE_DIR = f"{OUTPUT_DIR}/images"
AUDIO_DIR = f"{OUTPUT_DIR}/audio"
VIDEO_DIR = f"{OUTPUT_DIR}/videos"

VIDEO_NAME = f"{VIDEO_DIR}/output.mp4"
AUDIO_NAME = f"{AUDIO_DIR}/voice.wav"

# TTS Configuration
# Options: "pyttsx3" (default, free, natural), "gtts" (free, google), "elevenlabs" (premium, best quality)
TTS_ENGINE = os.getenv("TTS_ENGINE", "pyttsx3")
TTS_VOICE_ID = os.getenv("TTS_VOICE_ID", "")  # For ElevenLabs: use voice ID
TTS_VOICE_NAME = os.getenv("TTS_VOICE_NAME", "default")  # For pyttsx3: voice name
TTS_RATE = int(os.getenv("TTS_RATE", "150"))  # Speech rate (75-300, default 150)
TTS_VOLUME = float(os.getenv("TTS_VOLUME", "1.0"))  # Volume (0.0-1.0)
TTS_LANGUAGE = os.getenv("TTS_LANGUAGE", "en")  # Language code