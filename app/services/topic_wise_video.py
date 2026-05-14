import requests
import os
from app.config import IMAGE_DIR, PEXELS_API_KEY

def topic_wise_video(topic):
    url = "https://api.pexels.com/videos/search"

    headers = {
        "Authorization": PEXELS_API_KEY
    }

    params = {
        "query": topic,
        "orientation": "portrait",
        "size": "medium"
    }

    response = requests.get(url, headers=headers, params=params)

    data = response.json()

    videos = data.get("videos", [])

    selected_videos = []

    for video in videos:
        if video.get("duration") <= 15:  # Filter for short videos (<= 15 seconds)
          for video_file in video.get("video_files", []):
            if video_file.get("quality") == "hd":
                video_url = video_file.get("link")
                selected_videos.append(video_url)


    return selected_videos