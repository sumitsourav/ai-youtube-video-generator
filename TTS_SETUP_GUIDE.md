# TTS (Text-to-Speech) Service Guide

## Overview

The upgraded TTS service supports **3 different backends** for generating professional voice narration:

| Engine | Cost | Speed | Quality | Setup |
|--------|------|-------|---------|-------|
| **pyttsx3** | Free | Instant | Good | Easy (local) |
| **gTTS** | Free | 2-5s | Fair | Easy |
| **ElevenLabs** | Paid | 1-2s | Excellent | Requires API key |

---

## 🎯 Quick Start

### Default: pyttsx3 (Recommended)

**Pros:**
- ✅ Free
- ✅ Works offline
- ✅ Natural sounding voices
- ✅ Multiple voices available
- ✅ No API keys needed

**Setup:**
```bash
pip install pyttsx3
```

**Usage:**
```bash
# Just run - it's already set as default
python -m app.main
```

---

## 📦 Installation Options

### Option 1: pyttsx3 (Default)
```bash
pip install pyttsx3
# Windows/Mac/Linux - works with system voices
```

### Option 2: Google TTS (gTTS)
```bash
pip install gTTS
# Free tier: limited requests, requires internet
```

Update `.env`:
```env
TTS_ENGINE=gtts
TTS_LANGUAGE=en
```

### Option 3: ElevenLabs (Premium)
```bash
pip install elevenlabs
```

**Get API Key:**
1. Visit: https://elevenlabs.io
2. Sign up (free trial: 10,000 characters)
3. Copy API key from settings
4. Paste in `.env`

Update `.env`:
```env
TTS_ENGINE=elevenlabs
ELEVENLABS_API_KEY=sk_xxxxxxxxxxxx
```

---

## ⚙️ Configuration

### .env Configuration
```env
# Choose engine: pyttsx3, gtts, or elevenlabs
TTS_ENGINE=pyttsx3

# pyttsx3 voice (optional - auto-selects if not set)
TTS_VOICE_NAME=default

# Speech rate: 75 (slow) to 300 (fast), default 150
TTS_RATE=150

# Volume: 0.0 to 1.0
TTS_VOLUME=1.0

# Language code: en, es, fr, de, etc.
TTS_LANGUAGE=en

# ElevenLabs voice ID (only if using ElevenLabs)
TTS_VOICE_ID=21m00Tcm4TlvDq8ikWAM
```

---

## 🎙️ Available pyttsx3 Voices

List available voices:
```python
from app.services.tts_service import TTSService

service = TTSService()
service.list_available_voices()
```

**Common voices by OS:**

**macOS:**
- Samantha (female)
- Victoria (female) - recommended
- Alex (male)
- Google UK English Female
- Google UK English Male

**Windows:**
- Microsoft Zira (female)
- Microsoft David (male)
- Microsoft Mark (male)

**Linux:**
- Depends on espeak installation
- Multiple synthetic voices available

---

## 🎚️ Voice Tuning

### Adjust Speech Rate & Volume

```python
from app.services.tts_service import TTSService

# Create service with custom settings
service = TTSService()
service.audio_path = "output.wav"

# Modify settings in .env for persistent config:
# TTS_RATE=120          # Slower speech
# TTS_VOLUME=0.8        # Lower volume
```

---

## 🔄 Switching Engines

### Switch at Runtime

```python
from app.services.tts_service import TTSService

# Use pyttsx3
tts_pyttsx = TTSService(engine="pyttsx3")
audio = tts_pyttsx.generate("Hello world")

# Switch to Google TTS
tts_google = TTSService(engine="gtts")
audio = tts_google.generate("Hello world")

# Use ElevenLabs
tts_eleven = TTSService(engine="elevenlabs")
audio = tts_eleven.generate("Hello world")
```

### Switch via .env

Edit `.env` and change:
```env
TTS_ENGINE=elevenlabs
```

Then run:
```bash
python -m app.main
```

---

## 💡 Recommendations

**For YouTube Videos:**

1. **Best Quality (Premium):** ElevenLabs
   - Most natural sounding
   - Professional narration quality
   - Worth the cost for serious channels

2. **Best Free Option:** pyttsx3
   - Good quality
   - No dependencies
   - Works offline
   - Recommended for starting out

3. **Fallback:** gTTS
   - Works everywhere
   - Good but slightly robotic

---

## 🚀 Performance Tips

### Speed Optimization
```env
# Faster generation: use gTTS or ElevenLabs
TTS_ENGINE=elevenlabs

# Slower but more natural: pyttsx3
TTS_ENGINE=pyttsx3
```

### Quality Settings
```env
# High quality (natural speech)
TTS_RATE=150
TTS_VOLUME=1.0

# Medium quality (faster generation)
TTS_RATE=200
TTS_VOLUME=0.9
```

---

## 🐛 Troubleshooting

### "pyttsx3 not found" error
```bash
pip install pyttsx3
```

### No sound output (macOS)
```bash
# pyttsx3 might need audio engine
pip install pyobjc-framework-Cocoa
pip install pyobjc-framework-CoreAudio
```

### ElevenLabs API error
1. Verify API key in `.env`
2. Check account has remaining credits
3. Ensure internet connection

### gTTS too slow
- Switch to pyttsx3 or ElevenLabs
- gTTS adds latency for Google cloud requests

### Voice inappropriate for content
- Try different `TTS_VOICE_NAME` for pyttsx3
- Adjust `TTS_RATE` for slower/faster speech
- Use different voice ID for ElevenLabs

---

## 📊 Comparison

```
Voice Quality:          ElevenLabs > pyttsx3 > gTTS
Setup Difficulty:       gTTS ~ pyttsx3 < ElevenLabs
Speed:                  pyttsx3 (instant) ~ gTTS < ElevenLabs
Cost:                   Free (pyttsx3/gTTS) vs Paid (ElevenLabs)
Internet Required:      No (pyttsx3) vs Yes (gTTS, ElevenLabs)
Language Support:       Limited (pyttsx3) ~ Good (gTTS) ~ Excellent (ElevenLabs)
```

---

## 🎬 Next: Audio Enhancement

After upgrading TTS, consider:
1. Audio normalization (loudness)
2. Background music mixing
3. Noise reduction
4. Audio effects (reverb, etc.)

See `video_service.py` for video composition tips.
