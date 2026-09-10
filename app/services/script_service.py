# app/services/script_service.py

import logging
import re

from openai import OpenAI

from app.config import (
    CEREBRAS_API_KEY,
    GOOGLE_API_KEY,
    GOOGLE_API_KEY_2,
    GROQ_API_KEY,
    HUGGINGFACE_API_KEY,
    OPENROUTER_API_KEY,
    TTS_ENGINE,
)

logger = logging.getLogger("ai_video_generator")

# Free-tier quota is metered per (key, model), not per key - so every model
# listed under a key is its own separate daily allowance. Exhausting one model
# therefore costs us that model's quota, not the whole key's, and we just move
# down the list. Ordered fastest/highest-quality first within each provider.
#
# `extra` carries the provider's reasoning-suppression knob. Most of these are
# reasoning models that, left alone, spend the entire token budget on hidden
# chain-of-thought and then emit that thinking as the answer ("We need to
# produce a script about...") or return nothing at all. Measured on the real
# prompts: gpt-oss-120b went from 373 reasoning tokens to 6 with effort=low,
# and nemotron went from unusable to a clean 244-word script with exclude.
_PROVIDERS = [
    {
        "name": "groq",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key": GROQ_API_KEY,
        "models": [
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b",
            "qwen/qwen3.8-27b",
            "qwen/qwen3.6-27b",
        ],
        "extra": {"reasoning_effort": "low"},
    },
    {
        "name": "google-gemini-1",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "api_key": GOOGLE_API_KEY,
        "models": [
            "gemini-3.8-flash",
            "gemini-3.5-flash",
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
        ],
        "extra": {},
    },
    {
        "name": "google-gemini-2",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "api_key": GOOGLE_API_KEY_2,
        "models": [
            "gemini-3.8-flash",
            "gemini-3.5-flash",
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
        ],
        "extra": {},
    },
    {
        "name": "openrouter",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": OPENROUTER_API_KEY,
        "models": [
            "nvidia/nemotron-3-super-120b-a12b:free",
            "google/gemma-4-31b-it:free",
            "google/gemma-4-26b-a4b-it:free",
        ],
        "extra": {"extra_body": {"reasoning": {"effort": "low", "exclude": True}}},
    },
    {
        "name": "huggingface",
        "base_url": "https://router.huggingface.co/v1",
        "api_key": HUGGINGFACE_API_KEY,
        "models": ["openai/gpt-oss-120b:groq", "openai/gpt-oss-20b:groq"],
        "extra": {"reasoning_effort": "low"},
    },
    # Cerebras' free tier now requires a card on file (confirmed via a real 402
    # Payment Required response) - kept last as a no-op unless a funded key
    # shows up, rather than silently dropped.
    {
        "name": "cerebras",
        "base_url": "https://api.cerebras.ai/v1",
        "api_key": CEREBRAS_API_KEY,
        "models": ["gpt-oss-120b"],
        "extra": {"reasoning_effort": "low"},
    },
]

# Reasoning models that slip their scratchpad into the answer always open by
# restating the task back at us. Catching that here means a leak costs us one
# wasted model rather than shipping a video whose narration is the model
# talking to itself about writing narration.
_META_PREFIXES = (
    "we need",
    "we must",
    "we have to",
    "we should",
    "the user wants",
    "the user is asking",
    "the user asked",
    "let me",
    "i need to",
    "i should",
    "first, i",
    "okay,",
    "alright,",
)


def _looks_like_reasoning(text: str) -> bool:
    return text.strip().lower().startswith(_META_PREFIXES)


def _complete(prompt: str, max_tokens: int) -> str:
    errors = []
    for provider in _PROVIDERS:
        if not provider["api_key"]:
            continue
        client = OpenAI(api_key=provider["api_key"], base_url=provider["base_url"])
        for model in provider["models"]:
            label = f"{provider['name']}/{model}"
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                    **provider["extra"],
                )
                content = response.choices[0].message.content
                if not content or not content.strip():
                    errors.append(f"{label}: empty response")
                    continue
                if _looks_like_reasoning(content):
                    errors.append(f"{label}: returned reasoning instead of an answer")
                    logger.warning("%s leaked reasoning into content, trying next", label)
                    continue
                logger.info("Script generated via %s", label)
                return content
            except Exception as exc:
                errors.append(f"{label}: {exc}")
                logger.warning("Provider %s failed, trying next: %s", label, exc)

    raise RuntimeError(f"All LLM providers failed: {'; '.join(errors)}")


# Measured narration pace per engine (real audio duration / word count from a
# test script), not a generic "average speaking rate" assumption. The model has
# no way to know how fast the TTS engine will read its output, and defaults to
# a much faster implicit pace (~200 wpm) than gTTS's real one - giving it a raw
# "N minutes" target overshot by 1.6x, which is what made a 3-minute request
# render as 4:54. The word count has to be derived from the pace of whichever
# engine actually speaks it, so switching engines without remeasuring here
# brings that bug straight back.
_WORDS_PER_MINUTE_BY_ENGINE = {
    "gtts": 120,
    "pyttsx3": 120,
    # Polly neural reads faster than gTTS. Starting estimate - confirm against
    # a real render and correct before trusting the length targeting.
    "polly": 150,
    "elevenlabs": 140,
}

WORDS_PER_MINUTE = _WORDS_PER_MINUTE_BY_ENGINE.get(TTS_ENGINE, 120)

_SCRIPT_MARKER = "===SCRIPT==="
_KEYWORDS_MARKER = "===KEYWORDS==="
_LIST_MARKER = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")


def generate_script_and_keywords(topic, length_minutes=2, max_keywords=4):
    """One request for both the narration and the stock-footage search phrases.

    These used to be two separate calls. They need the same context and the
    keywords are a few dozen tokens, so folding them together halves the
    requests charged against the free-tier daily quotas at no cost to either
    output.

    Keywords exist because a raw topic search ("quantum computing") returns
    nothing usable from stock libraries - the model translates it into
    concrete, filmable subjects.
    """
    target_words = length_minutes * WORDS_PER_MINUTE
    prompt = f"""
Write a YouTube documentary voiceover script about: {topic}

Content:
- Open with the single most surprising, specific, or little-known fact about this topic - not generic scene-setting
- Use concrete details throughout: real names, numbers, dates, places, specific events - not vague generalities
- Tell it as a story with a throughline, not a list of disconnected inspirational statements
- Include at least one fact most people wouldn't already know
- Prioritize genuinely interesting or counterintuitive information over abstract emotion

Rules:
- Only narration text
- No scene descriptions
- No labels like Narrator
- No brackets []
- No "cut to", "scene", "shot"
- Write in paragraph format

Style:
- Vary sentence length - mix short punchy lines with longer flowing ones, not a monotonous run of short sentences
- Specific and vivid language, not generic
- Avoid clichés like "the human spirit," "journey," "forever changed," "against all odds," "a beacon of hope"
- Concrete, specific hook in the first two sentences - not an abstract mood-setter
- Confident, cinematic narration voice, grounded in real detail rather than empty inspiration

Length: approximately {target_words} words total (this is a hard target - it will be read aloud as narration at a measured pace, so stick close to this word count rather than what "feels right" for the topic)

Then list {max_keywords} short search phrases (2-4 words each) for finding stock video footage to illustrate this script.
- Only concrete, filmable things: objects, places, actions, nature, settings
- No abstract ideas or concepts
- One phrase per line, no numbering, no bullets

Reply in exactly this format, with no other text:
{_SCRIPT_MARKER}
<the narration script>
{_KEYWORDS_MARKER}
<phrase>
<phrase>
"""
    # Reasoning models bill their hidden thinking against this same budget, so
    # the allowance covers the script, the keywords, and room to think.
    text = _complete(prompt, max_tokens=target_words * 3 + 1200)
    return _parse_script_and_keywords(text, topic)


def _parse_script_and_keywords(text, topic):
    body = text.split(_SCRIPT_MARKER, 1)[-1]

    if _KEYWORDS_MARKER in body:
        script_part, keyword_part = body.split(_KEYWORDS_MARKER, 1)
        # Strips a leading bullet or "1." only - a blunt digit strip would eat
        # the year out of phrases like "18th century coffee house".
        keywords = [
            _LIST_MARKER.sub("", line).strip()
            for line in keyword_part.strip().splitlines()
            if line.strip()
        ]
        keywords = [k for k in keywords if k] or [topic]
    else:
        # Model ignored the format but still produced usable narration - keep
        # the script rather than burning another provider's quota on a retry.
        script_part, keywords = body, [topic]

    return script_part.strip(), keywords


def generate_script(topic, length_minutes=2):
    script, _ = generate_script_and_keywords(topic, length_minutes=length_minutes)
    return script
