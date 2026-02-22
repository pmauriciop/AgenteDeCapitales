"""
ai/pdf_parser.py
─────────────────
Extracción de datos financieros desde archivos PDF
(resúmenes de tarjeta de crédito, facturas, recibos digitales).

Flujo:
  1. Extrae el texto del PDF con pdfplumber.
  2. Envía el texto a GPT para estructurar los datos.
  3. Retorna lista de transacciones detectadas.

Uso:
    from ai.pdf_parser import parse_pdf_transactions

    txs = await parse_pdf_transactions("/tmp/resumen_tarjeta.pdf")
    # txs = [{"amount": 500.0, "category": "...", ...}, ...]
"""

from __future__ import annotations
import json
from datetime import date
from pathlib import Path
from typing import Any

import pdfplumber
from openai import AsyncOpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL

_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

MAX_TEXT_CHARS = 8000  # límite para no exceder el contexto del modelo


def extract_text_from_pdf(pdf_path: str | Path) -> str:
    """
    Extrae todo el texto de un PDF usando pdfplumber.

    Args:
        pdf_path: Ruta al archivo PDF.

    Returns:
        Texto plano concatenado de todas las páginas.
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF no encontrado: {pdf_path}")

    text_parts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text.strip())

    return "\n\n".join(text_parts)


async def parse_pdf_transactions(
    pdf_path: str | Path,
) -> list[dict[str, Any]]:
    """
    Analiza un PDF financiero y extrae todas las transacciones detectadas.

    Args:
        pdf_path: Ruta al PDF (resumen de tarjeta, factura, etc.).

    Returns:
        Lista de dicts, cada uno con:
            - amount      (float, positivo)
            - type        ("income" | "expense")
            - category    (str)
            - description (str)
            - date        (str ISO "YYYY-MM-DD")
        Lista vacía si no se detectan transacciones.
    """
    today = date.today().isoformat()

    # Extraer texto del PDF
    raw_text = extract_text_from_pdf(pdf_path)

    if not raw_text.strip():
        return []

    # Truncar si es demasiado largo
    if len(raw_text) > MAX_TEXT_CHARS:
        raw_text = raw_text[:MAX_TEXT_CHARS] + "\n[... texto truncado ...]"

    system_prompt = f"""Eres un asistente financiero experto. Analizas documentos financieros en texto plano.
Hoy es {today}.

Extrae TODAS las transacciones que encuentres en el documento.
Responde ÚNICAMENTE con un array JSON válido:
[
  {{
    "amount": <número positivo>,
    "type": "income" | "expense",
    "category": "<categoría>",
    "description": "<descripción breve del comercio o concepto>",
    "date": "<YYYY-MM-DD, usá hoy si no hay fecha>"
  }},
  ...
]

Categorías disponibles:
- Gastos: alimentación, transporte, entretenimiento, salud, educación, hogar, ropa, tecnología, servicios, otros
- Ingresos: salario, freelance, inversiones, ventas, otros_ingresos

Reglas:
- Los débitos/cargos/compras son "expense"
- Los créditos/pagos/acreditaciones son "income"
- Si el documento no contiene transacciones, retorná: []
- No incluyas texto fuera del JSON."""

    response = await _client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Documento:\n\n{raw_text}"},
        ],
        temperature=0,
        max_tokens=2000,
    )

    raw = response.choices[0].message.content.strip()

    # Limpiar posibles bloques de código markdown
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        transactions = json.loads(raw)
        if not isinstance(transactions, list):
            return []

        # Validar y normalizar cada transacción
        result = []
        for tx in transactions:
            try:
                result.append({
                    "amount": abs(float(tx["amount"])),
                    "type": tx.get("type", "expense"),
                    "category": tx.get("category", "otros"),
                    "description": tx.get("description", "")[:100],
                    "date": tx.get("date", today),
                })
            except (KeyError, ValueError):
                continue

        return result

    except json.JSONDecodeError:
        return []


async def summarize_pdf_statement(pdf_path: str | Path) -> str:
    """
    Genera un resumen en lenguaje natural de un estado de cuenta o resumen de tarjeta.

    Returns:
        Texto con resumen formateado para Telegram.
    """
    raw_text = extract_text_from_pdf(pdf_path)

    if not raw_text.strip():
        return "❌ No se pudo extraer texto del PDF."

    if len(raw_text) > MAX_TEXT_CHARS:
        raw_text = raw_text[:MAX_TEXT_CHARS] + "\n[... texto truncado ...]"

    response = await _client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "Eres un asesor financiero. Resume el siguiente documento financiero "
                    "de forma clara y concisa para el usuario. Incluye: totales, principales "
                    "gastos, y cualquier dato relevante. Usa emojis y Markdown para Telegram. "
                    "Máximo 200 palabras."
                ),
            },
            {"role": "user", "content": raw_text},
        ],
        temperature=0.3,
        max_tokens=400,
    )

    return response.choices[0].message.content.strip()
