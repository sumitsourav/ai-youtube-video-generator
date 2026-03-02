# app/services/video_fetch_service.py

import requests
import os
from app.config import IMAGE_DIR, PEXELS_API_KEY
from app.utils.file_utils import temp_filename

def fetch_videos(query, limit=5):
    url = "https://api.pexels.com/videos/search"

    headers = {
        "Authorization": PEXELS_API_KEY
    }

    params = {
        "query": query,
        "per_page": limit,
        "orientation": "landscape"
    }

    response = requests.get(url, headers=headers, params=params)

    if response.status_code != 200:
        print("Pexels Video API Error:", response.status_code)
        return []

    data = response.json()

    video_paths = []

    for video in data.get("videos", []):
        # pick medium quality video
        video_url = video["video_files"][0]["link"]

        video_data = requests.get(video_url).content
        filename = os.path.join(IMAGE_DIR, temp_filename("mp4"))

        with open(filename, "wb") as f:
            f.write(video_data)

        video_paths.append(filename)

    return video_paths