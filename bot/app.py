"""
bot/app.py
───────────
Construye y configura la aplicación de python-telegram-bot.
Registra todos los handlers en el orden correcto.
"""

import logging

from telegram import Update
from telegram.ext import Application, ContextTypes

from bot.handlers.budget import budget_callback, budget_conversation
from bot.handlers.callbacks import generic_callback_handler
from bot.handlers.expense import expense_conversation
from bot.handlers.income import income_conversation
from bot.handlers.messages import message_handler
from bot.handlers.pdf import pdf_callback_handler, pdf_handler
from bot.handlers.photo import photo_handler
from bot.handlers.recurring import recurring_callback, recurring_conversation
from bot.handlers.report import report_handler
from bot.handlers.start import help_handler, start_handler
from bot.handlers.summary import summary_callback, summary_handler
from bot.handlers.voice import voice_handler
from config import TELEGRAM_BOT_TOKEN

logger = logging.getLogger(__name__)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Captura cualquier excepción no manejada y responde al usuario sin caerse."""
    logger.error("Excepción no manejada:", exc_info=context.error)
    try:
        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text(
                "⚠️ Ocurrió un error inesperado. Por favor intentá de nuevo."
            )
    except Exception:
        pass


def create_app() -> Application:
    """
    Crea y configura la aplicación Telegram.

    Returns:
        Application lista para ejecutar.
    """
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # ── ConversationHandlers primero (prioridad más alta) ─
    app.add_handler(expense_conversation)
    app.add_handler(income_conversation)
    app.add_handler(budget_conversation)
    app.add_handler(recurring_conversation)

    # ── Comandos simples ──────────────────────────────────
    app.add_handler(start_handler)
    app.add_handler(help_handler)
    app.add_handler(summary_handler)
    app.add_handler(report_handler)

    # ── Callbacks inline ──────────────────────────────────
    app.add_handler(summary_callback)
    app.add_handler(budget_callback)
    app.add_handler(recurring_callback)
    app.add_handler(generic_callback_handler)

    # ── Media handlers ────────────────────────────────────
    app.add_handler(voice_handler)
    app.add_handler(photo_handler)
    app.add_handler(pdf_handler)

    # ── Callbacks de PDF ──────────────────────────────────
    app.add_handler(pdf_callback_handler)

    # ── Texto libre (NLP) — siempre al final ─────────────
    app.add_handler(message_handler)

    # ── Error handler global ──────────────────────────────
    app.add_error_handler(error_handler)

    logger.info("✅ Bot configurado con %d handlers", len(app.handlers))
    return app
