# app/services/storage_service.py

import boto3
from botocore.config import Config

from app.config import B2_APPLICATION_KEY, B2_BUCKET_NAME, B2_ENDPOINT, B2_KEY_ID

_client = None


def is_configured() -> bool:
    return bool(B2_KEY_ID and B2_APPLICATION_KEY and B2_BUCKET_NAME and B2_ENDPOINT)


def _get_client():
    global _client
    if _client is None:
        _client = boto3.client(
            "s3",
            endpoint_url=B2_ENDPOINT,
            aws_access_key_id=B2_KEY_ID,
            aws_secret_access_key=B2_APPLICATION_KEY,
            config=Config(signature_version="s3v4"),
        )
    return _client


def upload_video(local_path: str, object_key: str):
    _get_client().upload_file(
        local_path,
        B2_BUCKET_NAME,
        object_key,
        ExtraArgs={"ContentType": "video/mp4"},
    )


def get_download_url(object_key: str, expires_in: int = 86400) -> str:
    return _get_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": B2_BUCKET_NAME, "Key": object_key},
        ExpiresIn=expires_in,
    )


def delete_video(object_key: str):
    _get_client().delete_object(Bucket=B2_BUCKET_NAME, Key=object_key)
