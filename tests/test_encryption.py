"""
tests/test_encryption.py
─────────────────────────
Tests unitarios para database/encryption.py
"""

import pytest
from unittest.mock import patch

# Mockeamos ENCRYPTION_KEY antes de importar el módulo
FAKE_KEY = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="

# Generamos una clave Fernet válida para los tests
from cryptography.fernet import Fernet
VALID_KEY = Fernet.generate_key().decode()


@pytest.fixture(autouse=True)
def patch_config(monkeypatch):
    """Inyecta una clave de encriptación válida para tests."""
    monkeypatch.setenv("ENCRYPTION_KEY", VALID_KEY)
    # Re-importar para que tome la nueva clave
    import importlib
    import database.encryption as enc_module
    enc_module._fernet = Fernet(VALID_KEY.encode())
    return enc_module


def test_encrypt_returns_string():
    from database.encryption import encrypt
    result = encrypt("hola mundo")
    assert isinstance(result, str)
    assert result != "hola mundo"


def test_decrypt_roundtrip():
    from database.encryption import encrypt, decrypt
    original = "dato sensible: $1.500"
    encrypted = encrypt(original)
    decrypted = decrypt(encrypted)
    assert decrypted == original


def test_encrypt_different_each_time():
    """Fernet agrega un nonce, por lo que cada cifrado es diferente."""
    from database.encryption import encrypt
    text = "mismo texto"
    assert encrypt(text) != encrypt(text)


def test_encrypt_requires_string():
    from database.encryption import encrypt
    with pytest.raises(TypeError):
        encrypt(12345)


def test_decrypt_requires_string():
    from database.encryption import decrypt
    with pytest.raises(TypeError):
        decrypt(99.9)


def test_decrypt_invalid_token():
    from database.encryption import decrypt
    from cryptography.fernet import InvalidToken
    with pytest.raises(InvalidToken):
        decrypt("token_invalido_total")
