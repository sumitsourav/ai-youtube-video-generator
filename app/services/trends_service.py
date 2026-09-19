# app/services/trends_service.py

import logging
import time
import xml.etree.ElementTree as ET

import requests

from app.services.script_service import _complete

logger = logging.getLogger("ai_video_generator")

TRENDS_RSS = "https://trends.google.com/trending/rss"

# Google Trends is the only one of the three that's actually reachable.
# YouTube's mostPopular chart needs a key with YouTube Data API v3 enabled -
# the AI Studio keys here are refused - and Instagram publishes no trending
# endpoint at all, only scrapers that break their terms.
DEFAULT_GEO = "IN"

# Trends move over hours, not seconds, and every refresh costs an LLM call, so
# the reframed list is held rather than rebuilt per page load.
_CACHE_TTL_SECONDS = 3 * 60 * 60
_cache = {}


def fetch_raw_trends(geo=DEFAULT_GEO, limit=15):
    response = requests.get(
        TRENDS_RSS,
        params={"geo": geo},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=20,
    )
    response.raise_for_status()

    root = ET.fromstring(response.content)
    titles = [item.findtext("title", "").strip() for item in root.findall(".//item")]
    return [title for title in titles if title][:limit]


def _reframe(raw_trends):
    """Turn raw search terms into topics a video can actually be made about.

    What trends are is a list like "sevilla vs barcelona", "ufc", "kenny
    minchey" - last night's results and names in today's news. Handing one of
    those to the script writer asks a model with a training cutoff to narrate
    the life of someone it has never heard of, and it will oblige by inventing
    one. Reframing each trend onto the durable subject behind it keeps the
    topicality while pointing the script at something real.
    """
    listed = "\n".join(f"- {trend}" for trend in raw_trends)
    prompt = f"""These are search terms trending right now:

{listed}

Turn them into topics for short documentary-style videos.

For each one, give the broader, durable subject behind the search - the history, the rivalry, the science, the institution - not the specific event or person in today's news. "sevilla vs barcelona" becomes "The history of Spanish football's fiercest rivalries". "ufc" becomes "How mixed martial arts became a global sport".

Rules:
- Skip any trend where you cannot identify a real subject you actually know about. Better to return fewer than to guess at who someone is.
- Never write about a named individual as the subject - use what they are known for instead
- Each topic is a phrase of 4-10 words that reads as a video title
- One per line, no numbering, no commentary, nothing else
"""
    text = _complete(prompt, max_tokens=900)
    topics = [
        line.strip().lstrip("-*• ").strip()
        for line in text.strip().splitlines()
        if line.strip()
    ]
    # A model that ignores the format tends to emit a sentence of preamble;
    # anything that long isn't a title.
    return [topic for topic in topics if 3 <= len(topic.split()) <= 14][:10]


def trending_topics(geo=DEFAULT_GEO):
    cached = _cache.get(geo)
    if cached and time.time() - cached["at"] < _CACHE_TTL_SECONDS:
        return cached["topics"]

    try:
        raw = fetch_raw_trends(geo)
    except Exception as exc:
        logger.warning("Could not fetch Google Trends for %s: %s", geo, exc)
        return cached["topics"] if cached else []

    if not raw:
        return cached["topics"] if cached else []

    try:
        topics = _reframe(raw)
    except Exception as exc:
        # Suggestions are a convenience; failing to reframe shouldn't surface
        # as an error, and serving raw trends would defeat the point.
        logger.warning("Could not reframe trends for %s: %s", geo, exc)
        return cached["topics"] if cached else []

    _cache[geo] = {"topics": topics, "at": time.time()}
    return topics
