# app/services/script_service.py

import requests

def generate_script(topic):
    prompt = f"""
Write a YouTube documentary voiceover script about: {topic}

Rules:
- Only narration text
- No scene descriptions
- No labels like Narrator
- No brackets []
- No "cut to", "scene", "shot"
- Write in paragraph format

Style:
- Emotional, cinematic
- Simple English
- Short sentences
- Strong hook at start
- Engaging flow
- Powerful ending

Length: 2-3 minutes
"""

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "phi3",
            "prompt": prompt,
            "stream": False
        }
    )

    return response.json()["response"]