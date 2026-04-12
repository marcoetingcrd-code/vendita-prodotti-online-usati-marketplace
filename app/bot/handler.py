"""Telegram Bot setup — webhook mode for production, polling for development."""

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from app.config import TELEGRAM_BOT_TOKEN, BASE_URL
from app.bot.commands import (
    cmd_start, cmd_help, cmd_nuovo, cmd_lista, cmd_venduto,
    cmd_prezzo, cmd_stats, handle_photo, handle_callback, handle_text,
)

_app: Application | None = None


def create_bot_app() -> Application:
    """Crea e configura l'applicazione Telegram Bot."""
    global _app

    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN non configurato in .env")

    builder = Application.builder().token(TELEGRAM_BOT_TOKEN)
    app = builder.build()

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("nuovo", cmd_nuovo))
    app.add_handler(CommandHandler("lista", cmd_lista))
    app.add_handler(CommandHandler("venduto", cmd_venduto))
    app.add_handler(CommandHandler("prezzo", cmd_prezzo))
    app.add_handler(CommandHandler("stats", cmd_stats))

    # Photos
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # Inline keyboard callbacks
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Text messages (for conversational flows)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    _app = app
    return app


def get_bot_app() -> Application | None:
    return _app
