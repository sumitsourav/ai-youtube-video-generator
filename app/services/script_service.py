# app/services/script_service.py

import google.generativeai as genai
from app.config import GOOGLE_API_KEY

genai.configure(api_key=GOOGLE_API_KEY)

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

    model = genai.GenerativeModel('gemini-2.5-flash')
    response = model.generate_content(prompt)
    
    return response.text