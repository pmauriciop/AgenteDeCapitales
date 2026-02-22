"""
bot/__init__.py
────────────────
Módulo principal del bot de Telegram.
"""

from .app import create_app

__all__ = ["create_app"]
