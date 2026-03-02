"""
ai/ocr.py
─────────
Extracción de texto e información financiera desde imágenes
(tickets, facturas, recibos) usando Groq Vision.

Flujo en dos pasos (privacy-first):
  1. extract_text_from_image():
     Manda la imagen al LLM de visión y extrae SOLO texto crudo.
     La imagen viaja al LLM una única vez, con instrucción de transcribir
     únicamente el contenido visible sin incluir metadatos de la imagen.

  2. _parse_text_to_receipt():
     Recibe solo texto plano (sin imagen) y extrae los campos financieros.
     En este paso NO se envía ningún dato visual a servicios externos.

De esta forma, el número de tarjeta, CBU, nombre del titular, etc. que
pudieran aparecer en la imagen solo se exponen en el paso 1 (inevitable
para leer la imagen), pero el paso de análisis estructurado trabaja
exclusivamente con texto, minimizando la superficie de exposición.

Uso:
    from ai.ocr import parse_receipt

    data = await parse_receipt(image_path="/tmp/ticket.jpg")
    # data = {"amount": 450.0, "category": "alimentación", ...}
"""

import base64
import json
import logging
import re
from pathlib import Path
from typing import Any

from groq import AsyncGroq

from config import GROQ_API_KEY

logger = logging.getLogger(__name__)

_client = AsyncGroq(api_key=GROQ_API_KEY)

# Modelo de Groq con soporte de visión (solo se usa en el paso 1)
_VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

# ── Patrones de datos sensibles a eliminar del texto extraído ─────────────

_RE_CARD_NUMBER  = re.compile(r"\b(?:\d[ -]?){15}\d\b|\b\d{4}[\s\-]\d{4}[\s\-]\d{4}[\s\-]\d{4}\b")
_RE_CUIT         = re.compile(r"\b\d{2}-\d{8}-\d\b")
_RE_CBU          = re.compile(r"\b\d{22}\b")
_RE_EMAIL        = re.compile(r"\b[\w.+-]+@[\w.-]+\.\w{2,}\b")
_RE_DNI          = re.compile(r"(?i)\b(dni|d\.n\.i\.?)[:\s#]*\d{7,8}\b")
_RE_CARD_PARTIAL = re.compile(r"(?i)(tarjeta|nro\.?\s*tarjeta|card\s*n[°º]?\.?)[:\s#]*[\dX*]{4,}")


def _sanitize_ocr_text(text: str) -> str:
    """
    Elimina datos sensibles del texto extraído de una imagen antes
    de enviarlo al LLM de análisis (paso 2).

    Quita: números de tarjeta, CUIT, CBU, emails, DNI.
    Conserva: monto total, nombre del comercio, fecha, items.
    """
    text = _RE_CARD_NUMBER.sub("[TARJETA ELIMINADA]", text)
    text = _RE_CARD_PARTIAL.sub(r"\1: [TARJETA ELIMINADA]", text)
    text = _RE_CUIT.sub("[CUIT ELIMINADO]", text)
    text = _RE_CBU.sub("[CBU ELIMINADO]", text)
    text = _RE_EMAIL.sub("[EMAIL ELIMINADO]", text)
    text = _RE_DNI.sub(r"\1: [DNI ELIMINADO]", text)
    return text


def _encode_image(image_path: str | Path) -> str:
    """Codifica una imagen en base64 para enviar a la API."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _get_mime_type(path: Path) -> str:
    ext = path.suffix.lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    return mime_map.get(ext, "image/jpeg")


async def extract_text_from_image(image_path: str | Path) -> str:
    """
    PASO 1: Extrae el texto visible en una imagen usando el LLM de visión.

    La imagen viaja al LLM solo aquí. El texto resultante pasa por
    _sanitize_ocr_text() antes de cualquier uso posterior.

    Args:
        image_path: Ruta a la imagen (jpg, png, webp).

    Returns:
        Texto crudo extraído y sanitizado de la imagen.
    """
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Imagen no encontrada: {image_path}")

    b64 = _encode_image(path)
    mime = _get_mime_type(path)

    response = await _client.chat.completions.create(
        model=_VISION_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Extrae TODO el texto visible en esta imagen, tal como aparece. "
                            "No interpretes, solo transcribe. "
                            "No incluyas descripción de la imagen ni metadatos."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime};base64,{b64}",
                        },
                    },
                ],
            }
        ],
        max_tokens=1000,
    )

    raw_text = response.choices[0].message.content.strip()
    # Sanitizar el texto antes de retornarlo
    return _sanitize_ocr_text(raw_text)


async def _parse_text_to_receipt(text: str, today: str) -> dict[str, Any] | None:
    """
    PASO 2: Extrae datos financieros estructurados a partir de texto plano.

    NO recibe ni envía ninguna imagen. Solo trabaja con el texto ya
    extraído y sanitizado del paso 1.

    Args:
        text:  Texto extraído del ticket (ya sanitizado).
        today: Fecha de hoy en formato ISO.

    Returns:
        dict con amount, category, description, date, type.
        None si el texto no corresponde a un recibo válido.
    """
    system_prompt = f"""Analiza el texto de un ticket o recibo y extrae la información financiera.
Hoy es {today}.

Responde ÚNICAMENTE con un JSON válido:
{{
  "amount": <monto total como número positivo>,
  "category": "<categoría del gasto>",
  "description": "<nombre del negocio o descripción breve, máximo 60 caracteres>",
  "date": "<YYYY-MM-DD, usa hoy si no se ve la fecha>"
}}

Categorías disponibles: alimentación, transporte, entretenimiento, salud, educación, hogar, ropa, tecnología, servicios, otros

Reglas:
- El campo "amount" debe ser el TOTAL del ticket, no un subtotal.
- El campo "description" debe ser solo el nombre del negocio o tipo de compra, sin datos personales.
- Si el texto no corresponde a un ticket o no se puede determinar el monto, responde exactamente: null"""

    response = await _client.chat.completions.create(
        model="llama-3.3-70b-versatile",  # Modelo de texto, sin visión
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Texto del ticket:\n\n{text}"},
        ],
        max_tokens=300,
        temperature=0,
    )

    raw = response.choices[0].message.content.strip()
    if raw.lower() == "null":
        return None

    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()

    try:
        data = json.loads(raw)
        data["amount"] = abs(float(data["amount"]))
        if not data.get("date"):
            data["date"] = today
        data["type"] = "expense"
        return data
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


async def parse_receipt(image_path: str | Path) -> dict[str, Any] | None:
    """
    Analiza una imagen de ticket/factura y extrae los datos financieros.

    Flujo privacy-first en dos pasos:
      1. extract_text_from_image(): imagen -> texto (LLM visión, imagen expuesta)
      2. _parse_text_to_receipt(): texto -> JSON (LLM texto, sin imagen)

    Args:
        image_path: Ruta a la imagen del recibo.

    Returns:
        dict con: amount, category, description, date, type.
        None si no se puede parsear.
    """
    from datetime import date
    today = date.today().isoformat()

    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Imagen no encontrada: {image_path}")

    # Paso 1: imagen -> texto (única vez que la imagen viaja a un LLM externo)
    logger.info("OCR paso 1: extrayendo texto de imagen %s", path.name)
    extracted_text = await extract_text_from_image(image_path)

    if not extracted_text.strip():
        logger.warning("OCR paso 1: no se pudo extraer texto de la imagen")
        return None

    logger.info(
        "OCR paso 1 OK: %d caracteres extraídos (imagen no reenviada en paso 2)",
        len(extracted_text),
    )

    # Paso 2: texto -> datos estructurados (sin imagen, sin datos sensibles)
    return await _parse_text_to_receipt(extracted_text, today)
