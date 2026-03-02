"""
config.py
─────────
Carga y valida todas las variables de entorno del proyecto.
Centraliza la configuración para que ningún otro módulo
acceda directamente a os.environ.
"""

import os

from dotenv import load_dotenv

# Carga .env si existe (útil en desarrollo)
load_dotenv()


def _require(key: str) -> str:
    """Retorna el valor de una variable de entorno obligatoria."""
    value = os.getenv(key)
    if not value:
        raise EnvironmentError(
            f"Variable de entorno requerida no encontrada: '{key}'. "
            f"Revisa tu archivo .env"
        )
    return value


# ── Telegram ──────────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str = _require("TELEGRAM_BOT_TOKEN")

# ── OpenAI ────────────────────────────────────────────────
OPENAI_API_KEY: str = _require("OPENAI_API_KEY")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# ── Google Gemini ──────────────────────────────────────────
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# ── Groq ───────────────────────────────────────────────────
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# ── Supabase ──────────────────────────────────────────────
SUPABASE_URL: str = _require("SUPABASE_URL")
SUPABASE_KEY: str = _require("SUPABASE_KEY")
SUPABASE_SERVICE_KEY: str = os.getenv("SUPABASE_SERVICE_KEY", SUPABASE_KEY)

# ── Encriptación ──────────────────────────────────────────
ENCRYPTION_KEY: str = _require("ENCRYPTION_KEY")

# ── General ───────────────────────────────────────────────
ENV: str = os.getenv("ENV", "development")
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
