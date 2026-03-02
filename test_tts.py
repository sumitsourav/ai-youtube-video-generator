#!/usr/bin/env python3
"""
Quick TTS Service Test
Tests all three TTS backends to ensure setup is correct
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.tts_service import TTSService
from app.config import TTS_ENGINE

def test_tts_service():
    """Test TTS service configuration"""
    
    test_text = "Hello! This is a test of the text to speech service. The AI YouTube video generator is now ready to create amazing videos."
    
    print("=" * 60)
    print("🎙️  TTS SERVICE VALIDATION TEST")
    print("=" * 60)
    print()
    
    # Test current engine
    print(f"📢 Current TTS Engine: {TTS_ENGINE}")
    print()
    
    try:
        print(f"🔧 Testing {TTS_ENGINE} backend...")
        service = TTSService(engine=TTS_ENGINE)
        
        # List available voices if pyttsx3
        if TTS_ENGINE == "pyttsx3":
            service.list_available_voices()
            print()
        
        print(f"⏳ Generating audio with {TTS_ENGINE}...")
        audio_path = service.generate(test_text)
        
        print(f"✅ SUCCESS! Audio generated: {audio_path}")
        print(f"📊 File size: {os.path.getsize(audio_path)} bytes")
        print()
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        print()
        return False
    
    # Test other engines availability
    print("=" * 60)
    print("📋 AVAILABLE BACKENDS:")
    print("=" * 60)
    print()
    
    for engine in ["pyttsx3", "gtts", "elevenlabs"]:
        try:
            if engine == "pyttsx3":
                import pyttsx3
                status = "✅ Available"
            elif engine == "gtts":
                from gtts import gTTS
                status = "✅ Available"
            elif engine == "elevenlabs":
                from elevenlabs.client import ElevenLabs
                from app.config import ELEVENLABS_API_KEY
                if ELEVENLABS_API_KEY:
                    status = "✅ Available (API Key set)"
                else:
                    status = "⚠️  Available (no API key)"
            
            print(f"  {engine.upper():<15} {status}")
        except ImportError:
            print(f"  {engine.upper():<15} ❌ Not installed")
    
    print()
    print("=" * 60)
    print("💡 SWITCHING ENGINES:")
    print("=" * 60)
    print()
    print("To use a different TTS engine:")
    print()
    print("1. Edit .env file and change:")
    print("   TTS_ENGINE=pyttsx3    # or: gtts, elevenlabs")
    print()
    print("2. Or switch programmatically:")
    print("   service = TTSService(engine='gtts')")
    print()
    print("3. For ElevenLabs:")
    print("   - Get API key from https://elevenlabs.io")
    print("   - Add to .env: ELEVENLABS_API_KEY=sk_xxx")
    print()
    
    return True

if __name__ == "__main__":
    success = test_tts_service()
    sys.exit(0 if success else 1)
