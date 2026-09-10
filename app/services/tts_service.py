# app/services/tts_service.py

import os
import re
import subprocess
import sys
import tempfile
from app.config import (
    AUDIO_NAME,
    ELEVENLABS_API_KEY,
    POLLY_ENGINE,
    POLLY_REGION,
    POLLY_VOICE_ID,
    TTS_ENGINE,
    TTS_LANGUAGE,
    TTS_RATE,
    TTS_VOICE_ID,
    TTS_VOICE_NAME,
    TTS_VOLUME,
)

# Polly's SynthesizeSpeech caps a request at 3000 billed characters. Scripts
# run past that at the longer video lengths (a 5-minute script is ~3500), so
# they're split on sentence boundaries and the parts concatenated. Kept under
# the ceiling rather than at it so a single long sentence can't tip a chunk
# over.
_POLLY_CHUNK_CHARS = 2500

class TTSService:
    """Unified TTS service supporting multiple backends"""
    
    def __init__(self, engine=None, output_path=None):
        self.engine = engine or TTS_ENGINE
        self.audio_path = output_path or AUDIO_NAME
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
        elif self.engine == "polly":
            try:
                import boto3  # noqa: F401
            except ImportError:
                raise ImportError("boto3 not installed. Run: pip install boto3")
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
    
    def generate_polly(self, text):
        """Generate audio using Amazon Polly neural voices (most realistic)"""
        print("🎙️  Generating audio using Amazon Polly...")
        import boto3

        # No explicit credentials: boto3's default chain picks up the EC2
        # instance role, so nothing secret has to live in .env.
        client = boto3.client("polly", region_name=POLLY_REGION)

        chunks = _split_for_polly(text)
        parts = []
        try:
            for index, chunk in enumerate(chunks):
                response = client.synthesize_speech(
                    Text=chunk,
                    OutputFormat="mp3",
                    VoiceId=POLLY_VOICE_ID,
                    Engine=POLLY_ENGINE,
                )
                part_path = f"{self.audio_path}.part{index}.mp3"
                with open(part_path, "wb") as handle:
                    handle.write(response["AudioStream"].read())
                parts.append(part_path)

            _concat_audio(parts, self.audio_path)
        finally:
            for part in parts:
                if os.path.exists(part):
                    os.remove(part)

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
        elif self.engine == "polly":
            return self.generate_polly(text)
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


def _split_for_polly(text, limit=_POLLY_CHUNK_CHARS):
    """Split on sentence boundaries so no chunk ends mid-sentence - Polly would
    otherwise drop the intonation of a clipped sentence and the seam would be
    audible where the parts join."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    chunks = []
    current = ""
    for sentence in sentences:
        if current and len(current) + len(sentence) + 1 > limit:
            chunks.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        chunks.append(current)
    return chunks or [text]


def _concat_audio(parts, output_path):
    """Join the synthesized parts. Re-encoding through ffmpeg's concat demuxer
    rather than splicing the MP3 bytes directly, so the result carries one
    coherent timeline - the render step measures this file's duration to time
    the captions, and a byte-spliced MP3 reports its length unreliably."""
    if len(parts) == 1:
        os.replace(parts[0], output_path)
        return

    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as manifest:
        for part in parts:
            manifest.write(f"file '{os.path.abspath(part)}'\n")
        manifest_path = manifest.name

    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", manifest_path, "-c", "copy", output_path,
            ],
            check=True,
            capture_output=True,
        )
    finally:
        os.remove(manifest_path)


# Backward compatibility function
def generate_audio(text, engine=None, output_path=None):
    """Legacy function for backward compatibility"""
    service = TTSService(engine=engine, output_path=output_path)
    return service.generate(text)