"""File storage helpers — uploads to Cloudflare R2 if configured, else local disk.

Mirror of `bot/services/storage.py`. The bot keeps its own copy because it
ships as a standalone container that doesn't have `src.shared` on its
import path. Keep the two in sync if you edit either.
"""
import os
import uuid
from datetime import date


def _r2_configured() -> bool:
    return all([
        os.environ.get("R2_ACCOUNT_ID"),
        os.environ.get("R2_ACCESS_KEY_ID"),
        os.environ.get("R2_SECRET_ACCESS_KEY"),
        os.environ.get("R2_BUCKET_NAME"),
    ])


def _get_r2_client():
    import boto3
    return boto3.client(
        "s3",
        endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )


_CONTENT_TYPES = {
    "jpg":  "image/jpeg",
    "jpeg": "image/jpeg",
    "png":  "image/png",
    "webp": "image/webp",
    "pdf":  "application/pdf",
}


def upload_image(local_path: str, prefix: str = "invoices") -> str:
    """Upload to R2 (if configured) and return the public URL, else return `local_path`."""
    if not _r2_configured():
        return local_path

    ext = local_path.rsplit(".", 1)[-1].lower()
    filename = f"{prefix}/{date.today().isoformat()}/{uuid.uuid4().hex}.{ext}"
    content_type = _CONTENT_TYPES.get(ext, "application/octet-stream")

    client = _get_r2_client()
    with open(local_path, "rb") as f:
        client.put_object(
            Bucket=os.environ["R2_BUCKET_NAME"],
            Key=filename,
            Body=f,
            ContentType=content_type,
        )

    base = os.environ.get("R2_PUBLIC_URL", "").rstrip("/")
    return f"{base}/{filename}"


def fetch_bytes(path_or_url: str) -> bytes:
    """Read the source file regardless of whether it's a local path or R2 URL."""
    if path_or_url.startswith(("http://", "https://")):
        import httpx
        r = httpx.get(path_or_url, timeout=30.0)
        r.raise_for_status()
        return r.content
    with open(path_or_url, "rb") as f:
        return f.read()
