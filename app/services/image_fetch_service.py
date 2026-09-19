# app/services/image_fetch_service.py

import os
import re
from concurrent.futures import ThreadPoolExecutor

import requests
from app.config import IMAGE_DIR
from app.utils.file_utils import temp_filename

COMMONS_API = "https://commons.wikimedia.org/w/api.php"

# Wikimedia asks that API clients identify themselves; anonymous bulk requests
# get throttled or blocked.
_USER_AGENT = "AIVideoGenerator/1.0 (https://sastahiggsfield.duckdns.org)"

# Stock libraries hold no footage of specific people or events, which is the
# one gap beat-aligned search can't close - a tribute to a cricketer can only
# ever get generic cricket clips. Commons does hold photographs of the actual
# person, so those beats are illustrated with real archival stills instead.
# Everything on Commons is licensed for commercial use, but most of it
# requires crediting the photographer, so attribution is collected alongside
# the file rather than left for later.
_USABLE_MIME = {"image/jpeg", "image/png"}
_MIN_IMAGE_WIDTH = 640

_HTML_TAG = re.compile(r"<[^>]+>")


def _clean(value):
    """Commons returns the author as an HTML fragment with links in it."""
    return _HTML_TAG.sub("", value or "").strip()


def _search(subject, limit):
    response = requests.get(
        COMMONS_API,
        params={
            "action": "query",
            "generator": "search",
            "gsrsearch": subject,
            "gsrnamespace": "6",  # File: namespace
            "gsrlimit": str(limit * 3),  # over-fetch; most get filtered out
            "prop": "imageinfo",
            "iiprop": "url|mime|extmetadata",
            "iiurlwidth": "1280",
            "format": "json",
        },
        headers={"User-Agent": _USER_AGENT},
        timeout=20,
    )
    if response.status_code != 200:
        return []

    pages = response.json().get("query", {}).get("pages", {})
    results = []
    for page in pages.values():
        info = (page.get("imageinfo") or [{}])[0]
        url = info.get("thumburl") or info.get("url")
        if not url or info.get("mime") not in _USABLE_MIME:
            continue

        # The still gets scaled up to fill a 720x1280 frame and then slowly
        # pushed into, so anything small arrives visibly soft. Commons holds
        # plenty of thumbnails and icons alongside the photographs.
        if (info.get("thumbwidth") or 0) < _MIN_IMAGE_WIDTH:
            continue

        meta = info.get("extmetadata", {})
        results.append(
            {
                "url": url,
                "title": page.get("title", "").replace("File:", ""),
                "artist": _clean(meta.get("Artist", {}).get("value")),
                "license": _clean(meta.get("LicenseShortName", {}).get("value")),
            }
        )
    return results[:limit]


def _download(result):
    data = requests.get(result["url"], headers={"User-Agent": _USER_AGENT}, timeout=30).content
    path = os.path.join(IMAGE_DIR, temp_filename("jpg"))
    with open(path, "wb") as handle:
        handle.write(data)
    return {**result, "path": path}


def fetch_archival_images(subject, limit=2):
    """Photographs of a real subject from Wikimedia Commons.

    Returns dicts with "path" plus the credit fields. An empty list means
    Commons had nothing usable, and the caller should fall back to stock
    footage.
    """
    results = _search(subject, limit)

    # The subject names the person and the occasion ("Sachin Tendulkar 1998
    # South Africa tour") because the bare occasion matches the wrong event
    # entirely - a US presidential visit, in that case. But an archive rarely
    # holds a photograph of that exact occasion, so a subject precise enough to
    # be unambiguous is usually too precise to find. Dropping back to the
    # leading name keeps a real photograph of the right subject instead of
    # falling through to stock footage of nobody in particular.
    exact = bool(results)
    if not results:
        broader = " ".join(subject.split()[:2])
        if broader and broader != subject:
            results = _search(broader, limit)

    if not results:
        return []

    # Flagged so the caller can tell a photograph of this occasion from a
    # generic portrait of the person, and spend its still budget on the former.
    for result in results:
        result["exact"] = exact

    with ThreadPoolExecutor(max_workers=min(len(results), 4)) as executor:
        return list(executor.map(_download, results))


def format_credit(image):
    """A one-line credit for the video description. Commons licences are
    commercial-use but attribution-bearing, so this is a requirement, not a
    courtesy."""
    parts = [image.get("title") or "Image"]
    if image.get("artist"):
        parts.append(f"by {image['artist']}")
    if image.get("license"):
        parts.append(f"({image['license']})")
    return " ".join(parts) + " via Wikimedia Commons"
