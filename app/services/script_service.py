# app/services/script_service.py

import requests

def generate_script(topic):
    prompt = f"""
Write a YouTube documentary script about: {topic}

Requirements:
- Duration: 2-3 minutes
- Tone: emotional and cinematic
- Use simple English
- Add a strong hook at the beginning
- Keep sentences short and engaging
- End with a powerful conclusion
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