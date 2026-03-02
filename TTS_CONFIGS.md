# TTS Configuration Examples

## Quick Reference: Copy-Paste Configurations

### Config 1: Professional Female Voice (Free)
```env
TTS_ENGINE=pyttsx3
TTS_VOICE_NAME=Victoria
TTS_RATE=140
TTS_VOLUME=1.0
TTS_LANGUAGE=en
```

**Result:** Natural, professional female narration, slightly slower than default

---

### Config 2: Professional Male Voice (Free)
```env
TTS_ENGINE=pyttsx3
TTS_VOICE_NAME=Daniel
TTS_RATE=140
TTS_VOLUME=1.0
TTS_LANGUAGE=en
```

**Result:** Natural, professional male narration

---

### Config 3: Fast Narrator (Free)
```env
TTS_ENGINE=pyttsx3
TTS_VOICE_NAME=Ellen
TTS_RATE=200
TTS_VOLUME=0.95
TTS_LANGUAGE=en
```

**Result:** Fast-paced, energetic narration for educational content

---

### Config 4: Deep, Authoritative Voice (Free)
```env
TTS_ENGINE=pyttsx3
TTS_VOICE_NAME=Albert
TTS_RATE=130
TTS_VOLUME=1.0
TTS_LANGUAGE=en
```

**Result:** Deep, authoritative tone for documentaries

---

### Config 5: Google Cloud Quality (Free)
```env
TTS_ENGINE=gtts
TTS_LANGUAGE=en
```

**Result:** Reliable, Google-backed quality narration

---

### Config 6: Premium ElevenLabs - Best Quality
```env
TTS_ENGINE=elevenlabs
ELEVENLABS_API_KEY=sk_xxxxxxxxxxxx
TTS_VOICE_ID=21m00Tcm4TlvDq8ikWAM
```

**Result:** Professional, most natural sounding (requires credit card)

---

### Config 7: Multilingual - Spanish
```env
TTS_ENGINE=pyttsx3
TTS_VOICE_NAME=Monica          # Spanish voice
TTS_LANGUAGE=es
TTS_RATE=140
```

**Result:** Spanish language support

---

### Config 8: Multilingual - French
```env
TTS_ENGINE=pyttsx3
TTS_VOICE_NAME=Amélie          # French voice
TTS_LANGUAGE=fr
TTS_RATE=140
```

**Result:** French language support

---

### Config 9: Multilingual - German
```env
TTS_ENGINE=pyttsx3
TTS_VOICE_NAME=Eddy            # German voice
TTS_LANGUAGE=de
TTS_RATE=140
```

**Result:** German language support

---

### Config 10: Multilingual - Japanese
```env
TTS_ENGINE=pyttsx3
TTS_VOICE_NAME=Kyoko           # Japanese voice
TTS_LANGUAGE=ja
TTS_RATE=150
```

**Result:** Japanese language support

---

## Available Voices by Category

### Female Voices (Professional)
- Victoria
- Ellen
- Moira
- Samantha
- Yelda
- Tessa
- Nora
- Karen
- Flo

### Male Voices (Professional)
- Daniel
- Albert
- Fred
- Ralph
- Thomas
- Junior
- Rishi

### Unique/Fun Voices
- Cellos
- Bells
- Organ
- Whisper
- Jester
- Zarvox
- Trinoids

---

## Performance Tips

### For YouTube Shorts (Fast, Energetic)
```env
TTS_ENGINE=pyttsx3
TTS_VOICE_NAME=Ellen
TTS_RATE=200
TTS_VOLUME=1.0
```

### For Long-Form Content (Professional, Clear)
```env
TTS_ENGINE=elevenlabs
TTS_RATE=150
TTS_VOLUME=1.0
```

### For Documentaries (Deep, Authoritative)
```env
TTS_ENGINE=pyttsx3
TTS_VOICE_NAME=Albert
TTS_RATE=130
TTS_VOLUME=1.0
```

### For Educational Content (Clear, Friendly)
```env
TTS_ENGINE=pyttsx3
TTS_VOICE_NAME=Karen
TTS_RATE=150
TTS_VOLUME=0.95
```

---

## Cost Comparison

### Free Options
- **pyttsx3:** ✅ Unlimited (local processing)
- **gTTS:** ✅ Unlimited (Google's free tier)

### Premium Options
- **ElevenLabs:** 
  - Free tier: 10,000 chars/month
  - Paid: ~$0.30 per 1M characters
  - Pro: $99/month unlimited

---

## How to Switch Configurations

1. **Copy configuration above to `.env`**
2. **Save file**
3. **Run:**
   ```bash
   python -m app.main
   ```

That's it! The TTS service automatically loads the new configuration.

---

## Testing a Configuration

```bash
# Test current configuration
python test_tts.py

# Generate sample with current settings
python -c "from app.services.tts_service import generate_audio; generate_audio('Test your new voice configuration')"
```

---

## Recommended Starting Points

**If you want free + best quality:**
```env
TTS_ENGINE=pyttsx3
TTS_VOICE_NAME=Victoria
```

**If you want professional quality and don't mind paying:**
```env
TTS_ENGINE=elevenlabs
```

**If you need multilingual support:**
```env
TTS_ENGINE=pyttsx3
# Then change TTS_VOICE_NAME and TTS_LANGUAGE per video
```
