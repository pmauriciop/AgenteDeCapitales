"""
tests/conftest.py
──────────────────
Configuración global de pytest.
Las variables de entorno se inyectan aquí ANTES de que
cualquier módulo del proyecto sea importado.
"""

import os
from cryptography.fernet import Fernet

# ── Generar clave Fernet válida para todos los tests ─────
VALID_FERNET_KEY = Fernet.generate_key().decode()

# ── Inyectar variables de entorno mínimas ─────────────────
#    Se hace a nivel de módulo para que estén disponibles
#    antes de la primera importación de config.py
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "1234567890:AAFakeTokenForTestingPurposesOnly")
os.environ.setdefault("OPENAI_API_KEY", "sk-fake-openai-key-for-testing")
os.environ.setdefault("OPENAI_MODEL", "gpt-4o-mini")
os.environ.setdefault("SUPABASE_URL", "https://fake.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "fake-supabase-key")
os.environ.setdefault("ENCRYPTION_KEY", VALID_FERNET_KEY)
os.environ.setdefault("ENV", "test")
os.environ.setdefault("LOG_LEVEL", "WARNING")

import pytest


@pytest.fixture(autouse=True)
def patch_fernet_key():
    """
    Asegura que el módulo de encriptación use la clave de test,
    incluso si ya fue importado anteriormente.
    """
    import database.encryption as enc_module
    enc_module._fernet = Fernet(VALID_FERNET_KEY.encode())
    yield
