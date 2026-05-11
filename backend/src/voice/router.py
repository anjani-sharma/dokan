"""Voice-to-intent endpoint for the in-app mic flow.

Accepts a short audio blob from the dashboard (or anywhere), transcribes it
with Whisper, and runs the existing bot NLP service to classify the intent
(sale vs payment vs unknown) and extract fields. Does NOT write to the DB —
the dashboard renders a prefilled form for the user to confirm and save.
"""

import logging
import os
import sys
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from src.dependencies import require_token
from src.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter()


def _import_bot():
    """Add bot/ to sys.path and import transcriber + nlp lazily.
    Same trick as the OCR endpoint; keeps bot/ optional for environments
    that don't bundle it."""
    bot_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "bot")
    bot_dir = os.path.abspath(bot_dir)
    if os.path.exists(bot_dir) and bot_dir not in sys.path:
        sys.path.insert(0, bot_dir)
    from services.transcriber import transcribe  # noqa: WPS433
    from services.nlp import extract_voice_intent  # noqa: WPS433
    return transcribe, extract_voice_intent


@router.post("/process", dependencies=[Depends(require_token)])
async def process_voice(file: UploadFile = File(...)):
    """Transcribe + classify a voice note. Returns:

    {
      "transcript": "...",
      "intent": "sale" | "payment_in" | "payment_out" | "unknown",
      "confidence": "high" | "medium" | "low",
      "sale": {...} | null,
      "payment": {...} | null,
      "note": "short summary"
    }
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No audio uploaded")

    ext = (file.filename.rsplit(".", 1)[-1] or "webm").lower()
    if ext not in ("webm", "ogg", "oga", "mp3", "m4a", "wav", "mp4"):
        raise HTTPException(status_code=400, detail=f"Unsupported audio format: {ext}")

    images_dir = settings.images_dir  # repurposed scratch dir; cleared on cold start
    os.makedirs(images_dir, exist_ok=True)
    local_path = os.path.join(images_dir, f"voice-{uuid.uuid4().hex}.{ext}")

    try:
        contents = await file.read()
        with open(local_path, "wb") as out:
            out.write(contents)

        transcribe, extract_voice_intent = _import_bot()
        transcript = transcribe(local_path)
        if not transcript or not transcript.strip():
            return {
                "transcript": "",
                "intent": "unknown",
                "confidence": "low",
                "sale": None,
                "payment": None,
                "note": "Couldn't hear anything — try again.",
            }

        intent = extract_voice_intent(transcript)
        return intent
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Voice processing failed")
        raise HTTPException(status_code=500, detail=f"Voice processing failed: {e}")
    finally:
        try:
            if os.path.exists(local_path):
                os.remove(local_path)
        except Exception:
            pass
