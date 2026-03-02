"""
ai/transcriber.py
─────────────────
Transcripción de mensajes de voz usando OpenAI Whisper.
Recibe la ruta a un archivo de audio (ogg, mp3, wav, etc.)
y retorna el texto transcripto.

Uso:
    from ai.transcriber import transcribe_audio

    text = await transcribe_audio("/tmp/voice_note.ogg")
"""

import os
import tempfile
from pathlib import Path

from groq import AsyncGroq

from config import GROQ_API_KEY

_client = AsyncGroq(api_key=GROQ_API_KEY)

SUPPORTED_FORMATS = {".ogg", ".mp3", ".wav", ".m4a", ".webm", ".flac"}


async def transcribe_audio(file_path: str | Path) -> str:
    """
    Transcribe un archivo de audio usando Whisper de OpenAI.

    Args:
        file_path: Ruta al archivo de audio descargado de Telegram.

    Returns:
        Texto transcripto en español.

    Raises:
        ValueError: Si el formato no es soportado.
        RuntimeError: Si la transcripción falla.
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"Archivo de audio no encontrado: {file_path}")

    if path.suffix.lower() not in SUPPORTED_FORMATS:
        raise ValueError(
            f"Formato no soportado: {path.suffix}. "
            f"Soportados: {', '.join(SUPPORTED_FORMATS)}"
        )

    with open(path, "rb") as audio_file:
        response = await _client.audio.transcriptions.create(
            model="whisper-large-v3-turbo",
            file=audio_file,
            language="es",
            response_format="text",
        )

    if not response:
        raise RuntimeError("Whisper retornó una transcripción vacía")

    return response.strip()


async def transcribe_audio_bytes(audio_bytes: bytes, extension: str = ".ogg") -> str:
    """
    Transcribe audio desde bytes (útil cuando se recibe directamente de Telegram).

    Args:
        audio_bytes: Contenido del archivo de audio en bytes.
        extension:   Extensión del archivo (con punto), por defecto ".ogg".

    Returns:
        Texto transcripto.
    """
    with tempfile.NamedTemporaryFile(suffix=extension, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        return await transcribe_audio(tmp_path)
    finally:
        os.unlink(tmp_path)
