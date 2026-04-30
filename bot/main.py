import logging

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters,
)

from handlers.voice import handle_voice, handle_voice_price_reply
from handlers.photo import handle_photo, handle_photo_callback, handle_photo_edit_text
from handlers.text import handle_start, handle_report, handle_weekly, handle_outstanding, handle_text
from settings import settings

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)


async def _smart_text_handler(update: Update, context) -> None:
    """
    Routes text messages:
      1. If user is correcting a photo OCR result → photo edit handler
      2. Otherwise → normal text/sales handler
    """
    # Priority: photo correction > voice price reply > normal text
    if await handle_photo_edit_text(update, context):
        return
    if await handle_voice_price_reply(update, context):
        return
    await handle_text(update, context)


def main() -> None:
    app = Application.builder().token(settings.telegram_bot_token).build()

    # Commands
    app.add_handler(CommandHandler("start",       handle_start))
    app.add_handler(CommandHandler("help",        handle_start))
    app.add_handler(CommandHandler("report",      handle_report))
    app.add_handler(CommandHandler("weekly",      handle_weekly))
    app.add_handler(CommandHandler("outstanding", handle_outstanding))

    # Media
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # Inline button callbacks (photo confirmation)
    app.add_handler(CallbackQueryHandler(handle_photo_callback, pattern=r"^(save|edit|cancel):"))

    # Text — routes through smart dispatcher
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _smart_text_handler))

    print("Bot started. Polling for updates…")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
