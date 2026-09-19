# app/services/music_service.py

import os

import requests

from app.config import JAMENDO_CLIENT_ID, IMAGE_DIR
from app.utils.file_utils import temp_filename

SEARCH_URL = "https://api.jamendo.com/v3.0/tracks"

# Jamendo's catalogue includes tracks under every Creative Commons variant.
# ccnc=false excludes NonCommercial licenses outright - this service generates
# videos for other people, which is commercial use - and instrumental-only
# avoids a second voice competing with the narration underneath it.
_LICENSE_FILTERS = {"ccnc": "false"}


def is_configured():
    return bool(JAMENDO_CLIENT_ID)


def fetch_background_track(mood, duration_hint=180):
    """One instrumental track suited to `mood` (a tag like "cinematic" or
    "playful"), long enough to loop under a video without looping too often.
    Returns a local file path, or None if Jamendo has nothing usable or the
    client isn't configured - callers render without music rather than fail."""
    if not is_configured():
        return None

    try:
        response = requests.get(
            SEARCH_URL,
            params={
                "client_id": JAMENDO_CLIENT_ID,
                "format": "json",
                "limit": 5,
                "tags": mood,
                "vocalinstrumental": "instrumental",
                "durationbetween": f"{duration_hint}_600",
                "audioformat": "mp31",
                "order": "popularity_total",
                **_LICENSE_FILTERS,
            },
            timeout=20,
        )
        response.raise_for_status()
        tracks = response.json().get("results", [])
    except requests.RequestException:
        return None

    for track in tracks:
        url = track.get("audiodownload") or track.get("audio")
        if not url:
            continue
        try:
            audio = requests.get(url, timeout=30)
            audio.raise_for_status()
        except requests.RequestException:
            continue

        path = os.path.join(IMAGE_DIR, temp_filename("mp3"))
        with open(path, "wb") as handle:
            handle.write(audio.content)
        return path

    return None
