"""
bot/handlers/__init__.py
─────────────────────────
Exporta todos los handlers registrables en la aplicación.
"""

from .budget import budget_callback, budget_conversation
from .callbacks import generic_callback_handler
from .expense import expense_conversation
from .income import income_conversation
from .messages import message_handler
from .pdf import pdf_callback_handler, pdf_handler
from .photo import photo_handler
from .recurring import recurring_callback, recurring_conversation
from .report import report_handler
from .start import start_handler
from .summary import summary_callback, summary_handler
from .voice import voice_handler

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
