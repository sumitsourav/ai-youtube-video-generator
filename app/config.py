import os
from dotenv import load_dotenv

load_dotenv()

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

# LLM providers for script generation, tried in priority order in
# script_service.py so a daily quota hit on one doesn't block generation.
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_API_KEY_2 = os.getenv("GOOGLE_API_KEY_2")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY")
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY")

# Backblaze B2 (optional). When all four are set, finished videos are uploaded
# here instead of only staying on local disk, so they survive redeploys/restarts.
B2_KEY_ID = os.getenv("B2_KEY_ID")
B2_APPLICATION_KEY = os.getenv("B2_APPLICATION_KEY")
B2_BUCKET_NAME = os.getenv("B2_BUCKET_NAME")
B2_ENDPOINT = os.getenv("B2_ENDPOINT")

# Signs session cookies for login. Required.
SESSION_SECRET = os.getenv("SESSION_SECRET")

# Set to "true" once the app is only reachable over HTTPS (e.g. behind Caddy)
# so session cookies get the Secure flag. Leave unset for local HTTP dev.
HTTPS_ONLY_COOKIES = os.getenv("HTTPS_ONLY_COOKIES", "false").lower() == "true"

OUTPUT_DIR = "assets"
IMAGE_DIR = f"{OUTPUT_DIR}/images"
AUDIO_DIR = f"{OUTPUT_DIR}/audio"
VIDEO_DIR = f"{OUTPUT_DIR}/videos"

VIDEO_NAME = f"{VIDEO_DIR}/output2.mp4"
AUDIO_NAME = f"{AUDIO_DIR}/voice.wav"

# TTS Configuration
# Options: "polly" (AWS neural, most realistic), "gtts" (free, google),
# "pyttsx3" (free, offline), "elevenlabs" (premium, tiny free quota)
TTS_ENGINE = os.getenv("TTS_ENGINE", "pyttsx3")

# Amazon Polly. Credentials come from the standard boto3 chain - on EC2 that's
# the instance's IAM role, so no keys need to live in .env.
POLLY_REGION = os.getenv("POLLY_REGION", "ap-south-1")
POLLY_VOICE_ID = os.getenv("POLLY_VOICE_ID", "Matthew")
POLLY_ENGINE = os.getenv("POLLY_ENGINE", "neural")
TTS_VOICE_ID = os.getenv("TTS_VOICE_ID", "")  # For ElevenLabs: use voice ID
TTS_VOICE_NAME = os.getenv("TTS_VOICE_NAME", "default")  # For pyttsx3: voice name
TTS_RATE = int(os.getenv("TTS_RATE", "150"))  # Speech rate (75-300, default 150)
TTS_VOLUME = float(os.getenv("TTS_VOLUME", "1.0"))  # Volume (0.0-1.0)
TTS_LANGUAGE = os.getenv("TTS_LANGUAGE", "en")  # Language code