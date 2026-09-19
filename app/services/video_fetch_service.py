# app/services/video_fetch_service.py

import math
import os
import re
from concurrent.futures import ThreadPoolExecutor

import requests
from app.config import IMAGE_DIR, PEXELS_API_KEY
from app.services.image_fetch_service import fetch_archival_images
from app.utils.file_utils import temp_filename

SEARCH_URL = "https://api.pexels.com/videos/search"

# How many candidates to rank before picking. Costs one request either way -
# per_page is free - so this is only about having something to choose from.
_CANDIDATE_POOL = 15

# Kept on the same scale as the rarity weights: enough to break a tie in the
# subject's favour, not enough to outvote a candidate that matches the rest of
# the phrase.
_SUBJECT_BONUS = 1.0

_TRAILING_ID = re.compile(r"-\d+$")

# Words that appear in so many clip descriptions that matching on them says
# nothing about whether the footage is right.
_STOPWORDS = {
    "a", "an", "the", "of", "on", "in", "at", "with", "and", "for", "from",
    "over", "into", "view", "shot", "close", "up", "scene", "footage",
}


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


def _describes(video):
    """Pexels' `tags` field comes back empty, but the clip's page URL ends in a
    slug written from its description - "aerial-view-of-live-cricket-match-in-
    a-stadium-18148072" - which is the only thing in the response that says
    what the footage actually shows."""
    slug = video.get("url", "").rstrip("/").split("/")[-1]
    return _TRAILING_ID.sub("", slug).replace("-", " ").lower()


def _word_weights(words, described):
    """Weight each phrase word by how rare it is among the candidates.

    Counting matches equally lets a generic word decide the pick: "parchment
    scrolls stack" chose a clip of banked currency, because it matched
    "stack". Rarity within this one result set is the signal - when a search
    for "cricket trophy celebration" comes back as a wall of generic
    trophies, "trophy" is in nearly every candidate and tells us nothing,
    while "cricket" is in almost none and is the entire question. That is
    inverse document frequency, and the pool needed to compute it is already
    in hand.
    """
    total = len(described) or 1
    weights = {}
    for word in words:
        appearances = sum(1 for text in described if word in text)
        # A word in every candidate is worth nothing, never less than nothing.
        weights[word] = max(0.0, math.log(total / (1 + appearances)))
    return weights


def _relevance(video, words, weights):
    """Score one candidate against the phrase.

    The leading word keeps a flat bonus on top of its rarity weight. The
    prompt puts the subject there, and when a pool happens to be full of
    on-subject clips its rarity weight correctly drops to nothing - at which
    point the bonus is all that keeps the subject ahead of an incidental
    match.
    """
    described = _describes(video)
    if not words:
        return 0.0
    score = sum(weights.get(word, 0.0) for word in words if word in described)
    return score + (_SUBJECT_BONUS if words[0] in described else 0.0)


def _phrase_words(query):
    return [
        word
        for word in re.findall(r"[a-z]+", query.lower())
        if word not in _STOPWORDS and len(word) > 2
    ]


def _search_one(query, per_query_limit):
    headers = {"Authorization": PEXELS_API_KEY}
    # Ask for a pool rather than just what's needed. Pexels ranks loosely - it
    # will happily return thousands of results that ignore the qualifying word
    # - and measured across real generated phrases, 18% of beats got footage
    # matching nothing in their phrase while a better clip sat further down
    # this same response. Nothing extra is downloaded; only the winners are.
    params = {"query": query, "per_page": _CANDIDATE_POOL, "orientation": "landscape"}
    response = requests.get(SEARCH_URL, headers=headers, params=params, timeout=15)

    if response.status_code != 200:
        print("Pexels Video API Error:", response.status_code, "for query:", query)
        return []

    videos = response.json().get("videos", [])
    words = _phrase_words(query)
    weights = _word_weights(words, [_describes(video) for video in videos])
    ranked = sorted(videos, key=lambda v: _relevance(v, words, weights), reverse=True)
    return [_smallest_file(video)["link"] for video in ranked[:per_query_limit]]


def _cap_stills(images_by_index, beat_count):
    """Keep at most half the beats on photographs.

    Once the archival search falls back to the subject's name it finds a
    portrait for almost any beat, which turned a video into six photographs
    and no motion at all. Beats whose own occasion was found keep their
    stills; the rest give theirs up and take footage, so the archival material
    lands where it actually says something.
    """
    limit = max(1, beat_count // 2)
    if len(images_by_index) <= limit:
        return images_by_index

    ranked = sorted(
        images_by_index,
        key=lambda i: not images_by_index[i][0].get("exact", False),
    )
    return {i: images_by_index[i] for i in ranked[:limit]}


def fetch_beat_media(beats, per_beat=2):
    """Fill each beat with what suits it: an archival photograph where the beat
    is about a real, nameable subject, stock footage otherwise.

    Beat-aligned stock search fixed footage that ignored the narration, but it
    can't fix footage that doesn't exist - no stock library has clips of a
    particular cricketer or a particular treaty signing, so those beats got
    generic lookalikes. Commons does have photographs of the actual subject,
    so the beat's own ARCHIVAL line decides which source to ask.

    Mutates each beat, setting either "stills" (with credits) or "clips".
    """
    archival_indexes = [i for i, beat in enumerate(beats) if beat.get("archival")]

    images_by_index = {}
    if archival_indexes:
        with ThreadPoolExecutor(max_workers=min(len(archival_indexes), 6)) as executor:
            found = executor.map(
                lambda i: fetch_archival_images(beats[i]["archival"], per_beat),
                archival_indexes,
            )
            images_by_index = {i: images for i, images in zip(archival_indexes, found)}

    images_by_index = _cap_stills(images_by_index, len(beats))

    # A named subject Commons has never photographed falls back to stock rather
    # than leaving the beat with nothing.
    needs_footage = [i for i, _ in enumerate(beats) if not images_by_index.get(i)]
    clips_by_index = {}
    if needs_footage:
        groups = fetch_beat_clips([beats[i]["phrase"] for i in needs_footage], per_beat)
        clips_by_index = dict(zip(needs_footage, groups))

    for index, beat in enumerate(beats):
        beat["stills"] = images_by_index.get(index) or []
        beat["clips"] = clips_by_index.get(index) or []

    return beats


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
