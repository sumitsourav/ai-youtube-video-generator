# app/services/video_fetch_service.py

import os
from concurrent.futures import ThreadPoolExecutor

import requests
from app.config import IMAGE_DIR, PEXELS_API_KEY
from app.utils.file_utils import temp_filename

SEARCH_URL = "https://api.pexels.com/videos/search"


def _smallest_file(video):
    # Output is always scaled to a fixed size downstream, so there's no
    # benefit to downloading a larger source than necessary - just slower.
    return min(video["video_files"], key=lambda vf: vf.get("width", 0) * vf.get("height", 0))


def _download_one(video_url):
    video_data = requests.get(video_url, timeout=30).content
    filename = os.path.join(IMAGE_DIR, temp_filename("mp4"))
    with open(filename, "wb") as f:
        f.write(video_data)
    return filename


def _search_one(query, per_query_limit):
    headers = {"Authorization": PEXELS_API_KEY}
    params = {"query": query, "per_page": per_query_limit, "orientation": "landscape"}
    response = requests.get(SEARCH_URL, headers=headers, params=params, timeout=15)

    if response.status_code != 200:
        print("Pexels Video API Error:", response.status_code, "for query:", query)
        return []

    videos = response.json().get("videos", [])
    return [_smallest_file(video)["link"] for video in videos]


def fetch_beat_clips(phrases, clips_per_beat=2):
    """Download clips per beat, keeping them grouped by the beat they belong to.

    Returns a list parallel to `phrases`, each entry a list of local paths.

    A beat whose search returns nothing gets clips borrowed from its
    neighbours rather than a clip fetched for some unrelated phrase. Pexels
    answers every query with something, so an unmatched phrase used to pull in
    whatever it happened to return - a forest under a line about cricket.
    Re-showing footage that fits reads as deliberate; unrelated footage reads
    as broken.
    """
    with ThreadPoolExecutor(max_workers=min(len(phrases), 8)) as executor:
        url_groups = list(
            executor.map(lambda phrase: _search_one(phrase, clips_per_beat), phrases)
        )

    # Dedupe across beats so two beats that resolved to similar phrases don't
    # show the identical clip back to back.
    seen = set()
    for group_index, urls in enumerate(url_groups):
        kept = []
        for url in urls:
            if url not in seen:
                seen.add(url)
                kept.append(url)
        url_groups[group_index] = kept

    flat = [(i, url) for i, urls in enumerate(url_groups) for url in urls]
    if not flat:
        return [[] for _ in phrases]

    with ThreadPoolExecutor(max_workers=min(len(flat), 8)) as executor:
        paths = list(executor.map(lambda item: _download_one(item[1]), flat))

    grouped = [[] for _ in phrases]
    for (beat_index, _), path in zip(flat, paths):
        grouped[beat_index].append(path)

    return _fill_empty_beats(grouped)


def _fill_empty_beats(grouped):
    """Borrow from the nearest beat that found something. Nearest is used on
    purpose - adjacent beats are adjacent in the narrative, so their footage is
    the closest thing to relevant that's on hand."""
    have = [i for i, clips in enumerate(grouped) if clips]
    if not have:
        return grouped

    for i, clips in enumerate(grouped):
        if not clips:
            nearest = min(have, key=lambda j: abs(j - i))
            grouped[i] = list(grouped[nearest])
    return grouped


def fetch_videos(queries, limit=10):
    """queries: a single search string, or a list of them (e.g. several
    concrete visual keywords for one topic) - results are pooled and deduped
    across all of them, up to `limit` total clips."""
    if isinstance(queries, str):
        queries = [queries]

    per_query_limit = max(1, -(-limit // len(queries)))  # ceil division

    video_urls = []
    seen = set()
    for query in queries:
        for url in _search_one(query, per_query_limit):
            if url not in seen:
                seen.add(url)
                video_urls.append(url)
    video_urls = video_urls[:limit]

    if not video_urls:
        return []

    with ThreadPoolExecutor(max_workers=min(len(video_urls), 8)) as executor:
        return list(executor.map(_download_one, video_urls))
