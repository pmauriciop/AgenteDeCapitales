"""
database/__init__.py
────────────────────
Expone los componentes principales del módulo de base de datos.
Se importa solo encryption para evitar errores en tests sin .env.
"""

from .encryption import decrypt, encrypt

__all__ = ["encrypt", "decrypt"]
