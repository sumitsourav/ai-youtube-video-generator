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
