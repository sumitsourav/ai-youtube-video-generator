# app/services/tts_service.py

from gtts import gTTS
from app.config import AUDIO_NAME

def generate_audio(text):
    print("Generating audio using gTTS...")
    tts = gTTS(text)
    tts.save(AUDIO_NAME)
    return AUDIO_NAME