"""
File storage service.

If Cloudflare R2 credentials are set → uploads to R2, returns public URL.
If not set → saves to local disk, returns local path.
"""
import os
import uuid
from datetime import date


def _r2_configured() -> bool:
    """Read R2 config directly from env vars — works regardless of which settings module is loaded."""
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


def upload_image(local_path: str, prefix: str = "invoices") -> str:
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
            Bucket=os.environ["R2_BUCKET_NAME"],
            Key=filename,
            Body=f,
            ContentType=content_type,
        )

    base = os.environ.get("R2_PUBLIC_URL", "").rstrip("/")
    return f"{base}/{filename}"


def upload_voice(local_path: str) -> str:
    if not _r2_configured():
        return local_path

    filename = f"voice/{date.today().isoformat()}/{uuid.uuid4().hex}.ogg"
    client   = _get_r2_client()
    with open(local_path, "rb") as f:
        client.put_object(
            Bucket=os.environ["R2_BUCKET_NAME"],
            Key=filename,
            Body=f,
            ContentType="audio/ogg",
        )

    base = os.environ.get("R2_PUBLIC_URL", "").rstrip("/")
    return f"{base}/{filename}"
