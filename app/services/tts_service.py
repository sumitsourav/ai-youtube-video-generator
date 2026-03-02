# app/services/tts_service.py

import os
import sys
from app.config import AUDIO_NAME, TTS_ENGINE, TTS_VOICE_NAME, TTS_RATE, TTS_VOLUME, TTS_LANGUAGE, ELEVENLABS_API_KEY, TTS_VOICE_ID

class TTSService:
    """Unified TTS service supporting multiple backends"""
    
    def __init__(self, engine=None):
        self.engine = engine or TTS_ENGINE
        self.audio_path = AUDIO_NAME
        self.validate_engine()
    
    def validate_engine(self):
        """Check if selected engine is available"""
        if self.engine == "pyttsx3":
            try:
                import pyttsx3
            except ImportError:
                raise ImportError("pyttsx3 not installed. Run: pip install pyttsx3")
        elif self.engine == "gtts":
            try:
                from gtts import gTTS
            except ImportError:
                raise ImportError("gTTS not installed. Run: pip install gTTS")
        elif self.engine == "elevenlabs":
            try:
                from elevenlabs.client import ElevenLabs
            except ImportError:
                raise ImportError("elevenlabs not installed. Run: pip install elevenlabs")
            if not ELEVENLABS_API_KEY:
                raise ValueError("ELEVENLABS_API_KEY not set in .env")
        else:
            raise ValueError(f"Unknown TTS engine: {self.engine}")
    
    def generate_pyttsx3(self, text):
        """Generate audio using pyttsx3 (free, local, natural)"""
        print("🎙️  Generating audio using pyttsx3...")
        import pyttsx3
        
        engine = pyttsx3.init()
        
        # Set voice
        voices = engine.getProperty('voices')
        if TTS_VOICE_NAME != "default" and len(voices) > 0:
            for voice in voices:
                if TTS_VOICE_NAME.lower() in voice.name.lower():
                    engine.setProperty('voice', voice.id)
                    break
        
        # Set speech rate and volume
        engine.setProperty('rate', TTS_RATE)
        engine.setProperty('volume', TTS_VOLUME)
        
        # Save to file
        engine.save_to_file(text, self.audio_path)
        engine.runAndWait()
        engine.stop()
        
        print(f"✅ Audio saved to {self.audio_path}")
        return self.audio_path
    
    def generate_gtts(self, text):
        """Generate audio using Google Text-to-Speech (free)"""
        print("🎙️  Generating audio using Google TTS...")
        from gtts import gTTS
        
        tts = gTTS(text=text, lang=TTS_LANGUAGE, slow=False)
        tts.save(self.audio_path)
        
        print(f"✅ Audio saved to {self.audio_path}")
        return self.audio_path
    
    def generate_elevenlabs(self, text):
        """Generate audio using ElevenLabs (premium, best quality)"""
        print("🎙️  Generating audio using ElevenLabs...")
        try:
            from elevenlabs.client import ElevenLabs
        except ImportError:
            from elevenlabs import ElevenLabs
        
        client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
        
        # Default voice IDs if not specified
        voice_id = TTS_VOICE_ID or "21m00Tcm4TlvDq8ikWAM"  # Rachel voice
        
        audio = client.generate(
            text=text,
            voice=voice_id,
            model="eleven_monolingual_v1"
        )
        
        # Save audio
        with open(self.audio_path, 'wb') as f:
            for chunk in audio:
                f.write(chunk)
        
        print(f"✅ Audio saved to {self.audio_path}")
        return self.audio_path
    
    def generate(self, text):
        """Generate audio using configured engine"""
        if not text or len(text.strip()) == 0:
            raise ValueError("Text cannot be empty")
        
        if self.engine == "pyttsx3":
            return self.generate_pyttsx3(text)
        elif self.engine == "gtts":
            return self.generate_gtts(text)
        elif self.engine == "elevenlabs":
            return self.generate_elevenlabs(text)
        else:
            raise ValueError(f"Unknown engine: {self.engine}")
    
    def list_available_voices(self):
        """List available voices for current engine"""
        if self.engine == "pyttsx3":
            import pyttsx3
            engine = pyttsx3.init()
            voices = engine.getProperty('voices')
            print("\n📢 Available pyttsx3 voices:")
            for i, voice in enumerate(voices):
                print(f"  {i}: {voice.name}")
            return voices
        else:
            print(f"Voice listing not implemented for {self.engine}")
            return []


# Backward compatibility function
def generate_audio(text, engine=None):
    """Legacy function for backward compatibility"""
    service = TTSService(engine=engine)
    return service.generate(text)