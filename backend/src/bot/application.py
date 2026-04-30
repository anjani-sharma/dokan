"""
Telegram bot wired into FastAPI via webhooks.

Instead of a separate polling process, Telegram pushes every message
to POST /bot/webhook. FastAPI processes it and replies.

One Render service = backend API + bot. Free tier compatible.
"""
import logging
import os
import sys

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters,
)

from src.settings import settings

logger = logging.getLogger(__name__)

# Add bot directory to path so handlers can import their services
BOT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "bot")
if os.path.exists(BOT_DIR):
    sys.path.insert(0, os.path.abspath(BOT_DIR))


_application: Application | None = None


async def get_application() -> Application:
    """Build and return the singleton bot Application."""
    global _application
    if _application is not None:
        return _application

    if not settings.telegram_bot_token:
        logger.warning("TELEGRAM_BOT_TOKEN not set — bot disabled")
        return None

    from handlers.voice import handle_voice, handle_voice_price_reply
    from handlers.photo import handle_photo, handle_photo_callback, handle_photo_edit_text
    from handlers.text import (
        handle_start, handle_report, handle_weekly,
        handle_outstanding, handle_text,
    )

    async def _smart_text(update: Update, context):
        if await handle_photo_edit_text(update, context):
            return
        if await handle_voice_price_reply(update, context):
            return
        await handle_text(update, context)

    app = Application.builder().token(settings.telegram_bot_token).build()

    app.add_handler(CommandHandler("start",       handle_start))
    app.add_handler(CommandHandler("help",        handle_start))
    app.add_handler(CommandHandler("report",      handle_report))
    app.add_handler(CommandHandler("weekly",      handle_weekly))
    app.add_handler(CommandHandler("outstanding", handle_outstanding))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(handle_photo_callback, pattern=r"^(save|edit|cancel):"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _smart_text))

    await app.initialize()
    _application = app
    return _application


async def register_webhook(base_url: str) -> None:
    """Tell Telegram where to send updates."""
    app = await get_application()
    if app is None:
        return
    webhook_url = f"{base_url.rstrip('/')}/bot/webhook"
    await app.bot.set_webhook(
        url=webhook_url,
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=True,
    )
    logger.info(f"Webhook registered: {webhook_url}")


async def shutdown_bot() -> None:
    global _application
    if _application:
        await _application.shutdown()
        _application = None
