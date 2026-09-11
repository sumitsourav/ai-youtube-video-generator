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
    # Calibrated end-to-end on real generated scripts, not on clean prose.
    # Polly reads continuous paragraphs at 148 wpm here, but real scripts are
    # full of short sentences and paragraph breaks that it pauses on, and the
    # model tends to run a few percent over the word target - together those
    # drag the delivered pace down to ~122. Calibrating on the flowing-prose
    # number instead produced a 2:35 video for a 2:00 request. Only valid
    # while POLLY_RATE stays at 70%.
    "polly": 122,
    "elevenlabs": 140,
}

WORDS_PER_MINUTE = _WORDS_PER_MINUTE_BY_ENGINE.get(TTS_ENGINE, 120)

def _compensated_word_target(length_minutes):
    """Ask for fewer words than the arithmetic suggests, because the model
    reliably overruns the number it's given - and overruns it further the
    larger the number gets. Measured against real generations: +6% at 2
    minutes, +11% at 3, +15% at 5. Asking for the raw target therefore drifts
    a 5-minute video nearly a minute long, so the known overshoot is divided
    back out here. The correction has to taper to nothing at the short end -
    a flat per-minute rate over-corrected a 2-minute script into 1:47."""
    expected_overshoot = 0.03 * (length_minutes - 1)
    return round(length_minutes * WORDS_PER_MINUTE / (1 + expected_overshoot))


_SCRIPT_MARKER = "===SCRIPT==="
_KEYWORDS_MARKER = "===KEYWORDS==="
_LIST_MARKER = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")

_BEAT_MARKER = "===BEAT==="
_PHRASE_LABEL = "PHRASE:"
_NARRATION_LABEL = "NARRATION:"


def _beat_count(length_minutes):
    """Enough beats that the footage keeps up with the narration, few enough
    that the model actually writes all of them.

    Nine is where compliance stops: asked for nine the model writes nine, and
    asked for ten it writes five and quits mid-story. Longer videos therefore
    get more words per beat rather than more beats. Cut frequency doesn't
    depend on this, since shots are subdivided within each beat.
    """
    return max(4, min(9, length_minutes * 3))


def generate_script_and_keywords(topic, length_minutes=2):
    """Generate the narration already divided into beats, each carrying the
    search phrase for what should be on screen while it's spoken.

    Returns (full_script, beats) where each beat is {"text", "phrase"}.

    Asking for one set of phrases for the whole video meant footage had no
    relationship to what was being said at any given moment - a tribute to a
    cricketer played forest footage under the line about the World Cup. Tying
    each phrase to the beat it illustrates is what lets the render place a
    clip during the narration it actually matches.

    Phrases have to stay generic: stock libraries have no footage of specific
    people or events, so a phrase naming one returns something unrelated
    rather than nothing.
    """
    target_words = _compensated_word_target(length_minutes)
    beats = _beat_count(length_minutes)
    per_beat_words = max(20, round(target_words / beats))
    prompt = f"""
Write exactly {beats} beats of a YouTube documentary voiceover script about: {topic}

Each beat is approximately {per_beat_words} words of narration ({target_words} words total). Write all {beats} beats and give each one its full {per_beat_words} words - do not stop early because the story feels finished. Read end to end the beats are one continuous script; a listener should not hear where one ends and the next begins.

Each beat also gets a stock-footage search phrase for what is ON SCREEN while it is spoken:
- 2-4 words naming concrete filmable things: objects, places, actions, nature, settings
- It must match what THAT beat is talking about
- Never a proper noun - stock libraries hold no footage of specific people or events, so describe the generic scene ("cricket stadium crowd", never "Sachin Tendulkar")
- Each phrase is searched on its own with no other context, so name the subject in every one. For a cricket story write "cricket crowd cheering", not "crowd cheering" - the bare phrase returns football and rugby instead.

Narration content:
- Open with the single most surprising, specific, or little-known fact - not scene-setting
- Concrete detail throughout: real names, numbers, dates, places, events
- One throughline, not disconnected inspirational statements
- Include at least one fact most people wouldn't know
- Vary sentence length; avoid clichés like "the human spirit", "against all odds", "a beacon of hope"
- Narration text only: no scene descriptions, no speaker labels, no brackets, no "cut to"

Reply in exactly this format, with no other text:
{_BEAT_MARKER}
{_PHRASE_LABEL} <search phrase>
{_NARRATION_LABEL} <narration for this beat>
{_BEAT_MARKER}
{_PHRASE_LABEL} <search phrase>
{_NARRATION_LABEL} <narration for this beat>
"""
    # Reasoning models bill their hidden thinking against this same budget, so
    # the allowance covers the script, the beats, and room to think.
    text = _complete(prompt, max_tokens=target_words * 3 + 1500)
    return _parse_beats(text, topic)


def _parse_beats(text, topic):
    beats = []
    for block in text.split(_BEAT_MARKER)[1:]:
        phrase = narration = ""
        collecting = None
        for line in block.splitlines():
            stripped = _LIST_MARKER.sub("", line).strip()
            if stripped.upper().startswith(_PHRASE_LABEL):
                phrase = stripped[len(_PHRASE_LABEL):].strip()
                collecting = "phrase"
            elif stripped.upper().startswith(_NARRATION_LABEL):
                narration = stripped[len(_NARRATION_LABEL):].strip()
                collecting = "narration"
            elif stripped and collecting == "narration":
                # Narration that wrapped onto its own lines.
                narration = f"{narration} {stripped}".strip()

        if narration:
            beats.append({"text": narration, "phrase": phrase or topic})

    if not beats:
        # Model ignored the format. Rather than spend another provider's quota
        # retrying, fall back to the old whole-script behaviour: usable video,
        # just without beat-aligned footage.
        fallback = text.split(_SCRIPT_MARKER, 1)[-1].split(_KEYWORDS_MARKER, 1)[0].strip()
        if not fallback:
            raise RuntimeError("Script generation returned no usable narration")
        return fallback, [{"text": fallback, "phrase": topic}]

    script = "\n\n".join(beat["text"] for beat in beats)
    return script, beats


def generate_script(topic, length_minutes=2):
    script, _ = generate_script_and_keywords(topic, length_minutes=length_minutes)
    return script
