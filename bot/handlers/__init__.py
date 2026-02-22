"""
bot/handlers/__init__.py
─────────────────────────
Exporta todos los handlers registrables en la aplicación.
"""

from .start import start_handler
from .messages import message_handler
from .voice import voice_handler
from .photo import photo_handler
from .pdf import pdf_handler, pdf_callback_handler
from .expense import expense_conversation
from .income import income_conversation
from .summary import summary_handler, summary_callback
from .budget import budget_conversation, budget_callback
from .recurring import recurring_conversation, recurring_callback
from .report import report_handler
from .callbacks import generic_callback_handler

__all__ = [
    "start_handler",
    "message_handler",
    "voice_handler",
    "photo_handler",
    "pdf_handler",
    "pdf_callback_handler",
    "expense_conversation",
    "income_conversation",
    "summary_handler",
    "summary_callback",
    "budget_conversation",
    "budget_callback",
    "recurring_conversation",
    "recurring_callback",
    "report_handler",
    "generic_callback_handler",
]
