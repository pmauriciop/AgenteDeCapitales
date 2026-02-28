"""
ai/ocr.py
─────────
Extracción de texto e información financiera desde imágenes
(tickets, facturas, recibos) usando OpenAI GPT-4o Vision.

Flujo:
  1. El usuario envía una foto del ticket al bot.
  2. extract_text_from_image() extrae el texto crudo.
  3. parse_receipt() interpreta el texto y retorna datos estructurados.

Uso:
    from ai.ocr import parse_receipt

    data = await parse_receipt(image_path="/tmp/ticket.jpg")
    # data = {"amount": 450.0, "category": "alimentación", ...}
"""

import base64
import json
from pathlib import Path
from typing import Any

from groq import AsyncGroq
from config import GROQ_API_KEY

_client = AsyncGroq(api_key=GROQ_API_KEY)

# Modelo de Groq con soporte de visión
_VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"


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
    Extrae el texto visible en una imagen usando GPT-4o Vision.

    Args:
        image_path: Ruta a la imagen (jpg, png, webp).

    Returns:
        Texto crudo extraído de la imagen.
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
                        "text": "Extrae TODO el texto visible en esta imagen, tal como aparece. No interpretes, solo transcribe.",
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

    return response.choices[0].message.content.strip()


async def parse_receipt(image_path: str | Path) -> dict[str, Any] | None:
    """
    Analiza una imagen de ticket/factura y extrae los datos financieros.

    Args:
        image_path: Ruta a la imagen del recibo.

    Returns:
        dict con:
            - amount      (float): monto total
            - category    (str):   categoría del gasto
            - description (str):   descripción del comercio/items
            - date        (str):   fecha ISO si se detecta, hoy si no
        None si no se puede parsear.
    """
    from datetime import date
    today = date.today().isoformat()

    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Imagen no encontrada: {image_path}")

    b64 = _encode_image(path)
    mime = _get_mime_type(path)

    system_prompt = f"""Analiza este ticket o recibo y extrae la información financiera.
Hoy es {today}.

Responde ÚNICAMENTE con un JSON válido:
{{
  "amount": <monto total como número positivo>,
  "category": "<categoría del gasto>",
  "description": "<nombre del negocio o descripción breve>",
  "date": "<YYYY-MM-DD, usa hoy si no se ve la fecha>"
}}

Categorías disponibles: alimentación, transporte, entretenimiento, salud, educación, hogar, ropa, tecnología, servicios, otros

Si la imagen no es un ticket o no se puede determinar el monto, responde exactamente: null"""

    response = await _client.chat.completions.create(
        model=_VISION_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": system_prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime};base64,{b64}",
                        },
                    },
                ],
            }
        ],
        max_tokens=300,
        temperature=0,
    )

    raw = response.choices[0].message.content.strip()

    if raw.lower() == "null":
        return None

    try:
        data = json.loads(raw)
        data["amount"] = abs(float(data["amount"]))
        if not data.get("date"):
            data["date"] = today
        data["type"] = "expense"
        return data
    except (json.JSONDecodeError, KeyError, ValueError):
        return None
