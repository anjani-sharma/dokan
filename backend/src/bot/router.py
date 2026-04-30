"""
POST /bot/webhook — receives all Telegram updates.
"""
import logging

from fastapi import APIRouter, Request, Response
from telegram import Update

from src.bot.application import get_application

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/webhook")
async def telegram_webhook(request: Request):
    """Telegram calls this endpoint for every message, photo, voice, button tap."""
    app = await get_application()
    if app is None:
        return Response(status_code=200)  # bot disabled, acknowledge silently

    try:
        data   = await request.json()
        update = Update.de_json(data, app.bot)
        await app.process_update(update)
    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)

    # Always return 200 — Telegram retries on any other status code
    return Response(status_code=200)


@router.get("/info")
async def bot_info():
    """Health check — returns bot username if configured."""
    app = await get_application()
    if app is None:
        return {"status": "disabled", "reason": "TELEGRAM_BOT_TOKEN not set"}
    me = await app.bot.get_me()
    wh = await app.bot.get_webhook_info()
    return {
        "status":  "active",
        "bot":     me.username,
        "webhook": wh.url,
        "pending": wh.pending_update_count,
    }
