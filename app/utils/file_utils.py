# app/utils/file_utils.py

import os
import uuid

def ensure_dirs(paths):
    for path in paths:
        os.makedirs(path, exist_ok=True)

def temp_filename(ext):
    return f"{uuid.uuid4()}.{ext}"