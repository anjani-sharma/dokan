"""Bulk-import HTTP API.

Endpoints:
- POST /imports/upload   — multipart, N files + form field `kind`
- GET  /imports          — list (filter by status)
- GET  /imports/{id}     — one row
- POST /imports/{id}/commit   — post the (user-confirmed) extracted data
- POST /imports/{id}/discard  — drop the row, mark failed
"""
from __future__ import annotations

import csv
import io
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.dependencies import get_db, require_token
from src.imports.models import ImportJob
from src.imports.schemas import CommitResponse, ImportJobOut, UploadResponse
from src.imports.service import (
    commit_invoice_job,
    commit_payment_job,
    discard_job,
    queue_file,
    queue_payment_csv_rows,
)
from src.invoices.schemas import InvoiceCreate
from src.invoices.service import DuplicateInvoiceNumber
from src.payments.schemas import PaymentCreate

router = APIRouter()


@router.post("/upload", response_model=UploadResponse, dependencies=[Depends(require_token)])
async def upload(
    kind: str = Form(...),
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
):
    if kind not in ("invoice", "payment"):
        raise HTTPException(status_code=400, detail="kind must be 'invoice' or 'payment'")
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    job_ids: list[int] = []
    for f in files:
        try:
            contents = await f.read()
            job = await queue_file(
                db,
                kind=kind,
                filename=f.filename,
                content_type=f.content_type,
                contents=contents,
            )
            job_ids.append(job.id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    await db.commit()
    return UploadResponse(job_ids=job_ids, queued=len(job_ids))


@router.post("/upload/csv", response_model=UploadResponse, dependencies=[Depends(require_token)])
async def upload_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """CSV bulk-import for payments.

    Required columns: `date,amount,mode,direction`. Optional: `ref,note,
    supplier_name,customer_name`. Each row becomes a needs_review `ImportJob`.
    """
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="CSV file required")

    raw = (await file.read()).decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(raw))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV is empty or has no header row")

    required = {"date", "amount", "mode", "direction"}
    missing = required - {(h or "").strip().lower() for h in reader.fieldnames}
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"CSV missing required columns: {sorted(missing)}",
        )

    rows: list[dict] = []
    for r in reader:
        rows.append({(k or "").strip().lower(): (v or "").strip() for k, v in r.items()})
        rows[-1]["_source_filename"] = file.filename

    if not rows:
        raise HTTPException(status_code=400, detail="CSV had a header but no data rows")

    jobs = await queue_payment_csv_rows(db, rows)
    await db.commit()
    return UploadResponse(job_ids=[j.id for j in jobs], queued=len(jobs))


@router.get("", response_model=list[ImportJobOut])
async def list_jobs(
    status: str | None = None,
    kind: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(ImportJob).order_by(ImportJob.created_at.desc()).limit(200)
    if status:
        q = q.where(ImportJob.status == status)
    if kind:
        q = q.where(ImportJob.kind == kind)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/{job_id}", response_model=ImportJobOut)
async def get_job(job_id: int, db: AsyncSession = Depends(get_db)):
    job = await db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Import job not found")
    return job


@router.post(
    "/{job_id}/commit",
    response_model=CommitResponse,
    dependencies=[Depends(require_token)],
)
async def commit(
    job_id: int,
    body: dict[str, Any],
    db: AsyncSession = Depends(get_db),
):
    """Accept user-edited extracted data and post it through the regular
    invoice/payment create path. Body shape depends on `job.kind`."""
    job = await db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Import job not found")
    if job.status == "posted":
        raise HTTPException(status_code=409, detail="Already posted")

    if job.kind == "invoice":
        try:
            payload = InvoiceCreate.model_validate(body)
        except ValidationError as e:
            raise HTTPException(status_code=422, detail=e.errors())
        try:
            invoice_id = await commit_invoice_job(db, job, payload)
        except DuplicateInvoiceNumber:
            raise HTTPException(status_code=409, detail=f"Invoice {payload.invoice_number} already exists")
        return CommitResponse(job_id=job.id, status="posted", invoice_id=invoice_id)

    if job.kind == "payment":
        try:
            payload = PaymentCreate.model_validate(body)
        except ValidationError as e:
            raise HTTPException(status_code=422, detail=e.errors())
        payment_id = await commit_payment_job(db, job, payload)
        return CommitResponse(job_id=job.id, status="posted", payment_id=payment_id)

    raise HTTPException(status_code=400, detail=f"Unknown kind: {job.kind}")


@router.post("/{job_id}/discard", dependencies=[Depends(require_token)])
async def discard(job_id: int, db: AsyncSession = Depends(get_db)):
    job = await db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Import job not found")
    if job.status == "posted":
        raise HTTPException(status_code=409, detail="Cannot discard a posted job")
    await discard_job(db, job)
    return {"status": "discarded"}
