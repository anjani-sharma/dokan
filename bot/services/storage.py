"""
File storage service.

If Cloudflare R2 credentials are set → uploads to R2, returns public URL.
If not set → saves to local disk, returns local path.

This means the same code works for:
  - Local dev (no R2 needed)
  - Free tier Render (R2 for permanent storage)
  - DigitalOcean server (local persistent volume)
"""
import os
import uuid
from datetime import date

from settings import settings


def _r2_configured() -> bool:
    return all([
        settings.r2_account_id,
        settings.r2_access_key_id,
        settings.r2_secret_access_key,
        settings.r2_bucket_name,
    ])


def _get_r2_client():
    import boto3
    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
    )


def upload_image(local_path: str, prefix: str = "invoices") -> str:
    """
    Upload an image file and return a permanent URL (R2) or local path.

    Args:
        local_path: path to the downloaded file
        prefix: R2 folder name — "invoices" or "payments"

    Returns:
        str: public URL if R2 configured, else local path
    """
    if not _r2_configured():
        return local_path  # local mode — path is enough

    ext      = local_path.rsplit(".", 1)[-1].lower()
    filename = f"{prefix}/{date.today().isoformat()}/{uuid.uuid4().hex}.{ext}"

    content_type = {
        "jpg": "image/jpeg", "jpeg": "image/jpeg",
        "png": "image/png",  "webp": "image/webp",
    }.get(ext, "image/jpeg")

    client = _get_r2_client()
    with open(local_path, "rb") as f:
        client.put_object(
            Bucket=settings.r2_bucket_name,
            Key=filename,
            Body=f,
            ContentType=content_type,
        )

    base = settings.r2_public_url.rstrip("/")
    return f"{base}/{filename}"


def upload_voice(local_path: str) -> str:
    """Upload a voice file and return URL or local path."""
    if not _r2_configured():
        return local_path

    filename = f"voice/{date.today().isoformat()}/{uuid.uuid4().hex}.ogg"
    client   = _get_r2_client()
    with open(local_path, "rb") as f:
        client.put_object(
            Bucket=settings.r2_bucket_name,
            Key=filename,
            Body=f,
            ContentType="audio/ogg",
        )

    base = settings.r2_public_url.rstrip("/")
    return f"{base}/{filename}"
