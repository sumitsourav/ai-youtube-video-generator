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
    POLLY_RATE,
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

# Measured end-to-end on a real generated script, paragraph breaks and all -
# clean prose reads much faster and calibrating on it produced a 2:35 video
# for a 2:00 request. Gregory on the long-form engine delivers ~127 wpm at
# its natural rate; the same script ran 108 wpm at 85% and 90 at 70%, so
# duration scales linearly with the rate, which is what lets _fit_rate solve
# for it. Rate is a voice-quality setting as much as a timing one, hence the
# clamp: ~89 wpm at the floor already drags, and the ceiling keeps a long
# script from being rushed.
_BASE_RATE_PERCENT = 100
_BASE_WPM = 127
_MIN_RATE_PERCENT = 70
_MAX_RATE_PERCENT = 130

# Past this much drift the audio is resynthesised once at a corrected rate.
# Set below the 15s the video is allowed to be off by, so a correction only
# fires when it would otherwise miss.
_RETRY_TOLERANCE_SECONDS = 8

class TTSService:
    """Unified TTS service supporting multiple backends"""
    
    def __init__(self, engine=None, output_path=None, target_seconds=None, voice=None):
        self.engine = engine or TTS_ENGINE
        self.audio_path = output_path or AUDIO_NAME
        self.target_seconds = target_seconds
        self.voice = voice or POLLY_VOICE_ID
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

        rate = _fit_rate(text, self.target_seconds)
        self._synthesize_at(client, text, rate)

        # Predicting the rate from an average words-per-minute leaves a few
        # percent of error, which is invisible on a one-minute video and about
        # 25 seconds on a five-minute one. The finished audio is right here to
        # measure, so rather than trust the estimate, check it and correct once
        # against what was actually produced.
        if self.target_seconds:
            actual = _probe_duration(self.audio_path)
            if actual and abs(actual - self.target_seconds) > _RETRY_TOLERANCE_SECONDS:
                corrected = _scale_rate(rate, actual / self.target_seconds)
                if corrected != rate:
                    print(f"   {actual:.0f}s vs {self.target_seconds}s target, retrying at {corrected}")
                    self._synthesize_at(client, text, corrected)

        print(f"✅ Audio saved to {self.audio_path}")
        return self.audio_path

    def _synthesize_at(self, client, text, rate):
        parts = []
        try:
            for index, chunk in enumerate(_split_for_polly(text)):
                response = client.synthesize_speech(
                    Text=_to_ssml(chunk, rate),
                    TextType="ssml",
                    OutputFormat="mp3",
                    VoiceId=self.voice,
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


def _to_ssml(text, rate=None):
    """Wrap narration in SSML so its rate can be set. The escape matters: an
    unescaped & or < in a script would make Polly reject the whole request as
    malformed SSML."""
    escaped = (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )
    return f'<speak><prosody rate="{rate or POLLY_RATE}">{escaped}</prosody></speak>'


def _probe_duration(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", path],
        capture_output=True, text=True,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return None


def _scale_rate(rate, factor):
    """Speaking faster by `factor` shortens the audio by the same factor, so
    the correction is just the current rate times how far off it came out."""
    current = float(rate.rstrip("%"))
    scaled = current * factor
    return f"{round(max(_MIN_RATE_PERCENT, min(_MAX_RATE_PERCENT, scaled)))}%"


def _fit_rate(text, target_seconds):
    """Pick the speaking rate that makes this script land on the requested
    length.

    The model will not reliably write to a word count. Asked for the same
    3-minute script twice it returned 344 words once and 212 the next time,
    which is the difference between a 3:14 video and a 1:47 one, and no amount
    of prompt tightening made it dependable. Rather than keep guessing at the
    word target, the script is taken as given and the delivery is fitted to
    it, which is arithmetic rather than persuasion.

    Clamped because rate is a voice quality setting as much as a timing one -
    past these bounds the narration starts to sound wrong, so an extremely
    short script stays short instead of being dragged out into a drawl.
    """
    words = len(text.split())
    if not words or not target_seconds:
        return POLLY_RATE

    required_wpm = words / (target_seconds / 60)
    rate = _BASE_RATE_PERCENT * required_wpm / _BASE_WPM
    return f"{round(max(_MIN_RATE_PERCENT, min(_MAX_RATE_PERCENT, rate)))}%"


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
def generate_audio(text, engine=None, output_path=None, target_seconds=None, voice=None):
    """Legacy function for backward compatibility"""
    service = TTSService(engine=engine, output_path=output_path, target_seconds=target_seconds, voice=voice)
    return service.generate(text)