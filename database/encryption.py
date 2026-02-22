"""
database/encryption.py
──────────────────────
Utilidades para encriptar y desencriptar datos sensibles
usando Fernet (AES-128-CBC + HMAC-SHA256).

Uso:
    from database.encryption import encrypt, decrypt

    cifrado  = encrypt("dato sensible")
    original = decrypt(cifrado)
"""

from cryptography.fernet import Fernet
from config import ENCRYPTION_KEY


# Instancia única del motor de cifrado
_fernet = Fernet(ENCRYPTION_KEY.encode())


def encrypt(plain_text: str) -> str:
    """
    Encripta un texto plano y devuelve el resultado como string.

    Args:
        plain_text: Cadena a encriptar.

    Returns:
        Cadena encriptada en base64 (segura para guardar en DB).
    """
    if not isinstance(plain_text, str):
        raise TypeError("encrypt() espera un string")
    return _fernet.encrypt(plain_text.encode()).decode()


def decrypt(cipher_text: str) -> str:
    """
    Desencripta un texto previamente cifrado con encrypt().

    Args:
        cipher_text: Cadena encriptada.

    Returns:
        Texto original en claro.

    Raises:
        cryptography.fernet.InvalidToken: si el token es inválido o fue alterado.
    """
    if not isinstance(cipher_text, str):
        raise TypeError("decrypt() espera un string")
    return _fernet.decrypt(cipher_text.encode()).decode()
