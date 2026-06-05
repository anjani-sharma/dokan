from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ImportJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    kind: str
    status: str
    source_path: str
    original_filename: str | None
    mime_type: str | None
    image_phash: str | None
    content_fingerprint: str | None
    extracted: dict[str, Any] | None
    dup_of_invoice_id: int | None
    dup_of_payment_id: int | None
    posted_invoice_id: int | None
    posted_payment_id: int | None
    error: str | None
    created_at: datetime
    updated_at: datetime


class UploadResponse(BaseModel):
    job_ids: list[int]
    queued: int


class CommitResponse(BaseModel):
    job_id: int
    status: str
    invoice_id: int | None = None
    payment_id: int | None = None
