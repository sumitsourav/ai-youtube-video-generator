import requests
import os
from app.config import IMAGE_DIR, PEXELS_API_KEY
from app.utils.file_utils import temp_filename

def fetch_images(query, limit=6):
    url = "https://api.pexels.com/v1/search"

    headers = {
        "Authorization": PEXELS_API_KEY
    }

    params = {
        "query": query,
        "per_page": limit,
        "orientation": "portrait"  # better for shorts
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)

        # 🔥 Check response status
        if response.status_code != 200:
            print("Pexels API Error:", response.status_code)
            return []

        # 🔥 Safe JSON parsing
        data = response.json()

        if "photos" not in data or not data["photos"]:
            print("No images found for:", query)
            return []

        image_paths = []

        for photo in data["photos"]:
            img_url = photo["src"]["large"]

            img_data = requests.get(img_url, timeout=10).content
            filename = os.path.join(IMAGE_DIR, temp_filename("jpg"))

            with open(filename, "wb") as f:
                f.write(img_data)

            image_paths.append(filename)

        return image_paths

    except Exception as e:
        print("Error fetching images:", e)
        return []