"""
ai/pdf_parser.py
─────────────────
Extracción de datos financieros desde PDFs bancarios argentinos.

Estrategia en dos pasos:
  1. Extracción estructurada (Python):
     - Parsea línea a línea la sección "DETALLE DEL CONSUMO"
     - Detecta la columna CUOTA (formato NN/NN) de compras en cuotas
     - Extrae "cuotas a vencer" del pie del resumen
  2. Enriquecimiento con LLM (Groq):
     - Categoriza y normaliza. Fallback total para bancos no reconocidos.

Formatos soportados con detección de cuotas:
  - Visa / Mastercard Banco Galicia
  - Cualquier resumen con columna CUOTA en formato NN/NN

Uso:
    from ai.pdf_parser import parse_pdf_transactions, summarize_pdf_statement
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date
from pathlib import Path
from typing import Any

import pdfplumber
from groq import AsyncGroq
from config import GROQ_API_KEY, GROQ_MODEL

logger = logging.getLogger(__name__)

_client = AsyncGroq(api_key=GROQ_API_KEY)

MAX_TEXT_CHARS = 12000


def extract_full_content(pdf_path: str | Path) -> dict[str, Any]:
    """Extrae texto completo de todas las páginas."""
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF no encontrado: {pdf_path}")
    pages_data = []
    all_text_parts = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages):
            page_text = page.extract_text() or ""
            page_tables = page.extract_tables() or []
            all_text_parts.append(page_text.strip())
            pages_data.append({"page": i + 1, "text": page_text, "tables": page_tables})
    return {"text": "\n\n".join(all_text_parts), "pages": pages_data}


def extract_text_from_pdf(pdf_path: str | Path) -> str:
    """Extrae texto plano (compatibilidad con código existente)."""
    return extract_full_content(pdf_path)["text"]


# ── Helpers de parseo ────────────────────────────────────────

_MESES_ES = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
    "jan": 1, "apr": 4, "aug": 8, "dec": 12,
}

_MESES_ES_FULL = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}


def _parse_date_es(date_str: str) -> str | None:
    """Convierte '15-Oct-24', '15-10-24', '15/10/2024' -> 'YYYY-MM-DD'."""
    parts = re.split(r"[-/]", date_str.strip())
    if len(parts) != 3:
        return None
    day, mon, year = parts
    if mon.isdigit():
        month = int(mon)
    else:
        month = _MESES_ES.get(mon[:3].lower())
    if not month:
        return None
    day, year = int(day), int(year)
    if year < 100:
        year += 2000
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def _parse_amount(s: str) -> float:
    """Convierte '3.423,50' (formato argentino) -> 3423.50."""
    s = s.replace("$", "").replace(" ", "").strip()
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return abs(float(s))
    except ValueError:
        return 0.0


# ── Parser estructurado: DETALLE DEL CONSUMO ────────────────

def extract_structured_transactions(content: dict) -> list[dict]:
    """
    Parsea línea a línea la sección DETALLE DEL CONSUMO.
    Detecta columna CUOTA (NN/NN) en cada línea si existe.
    """
    lines = content["text"].splitlines()
    results = []
    in_detalle = False
    today_str = date.today().isoformat()

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if re.search(r"DETALLE\s+DEL\s+CONSUMO", line, re.IGNORECASE):
            in_detalle = True
            continue
        if in_detalle and re.search(
            r"TOTAL\s+A\s+PAGAR|IMPUESTO\s+DE\s+SELLOS|INTERESES\s+FINANCIACION"
            r"|DB\s+IVA|PERCEPCION\s+ING|Plan\s+V:|Cuotas\s+a\s+vencer"
            r"|TARJETA\s+\d{4}\s+Total",
            line, re.IGNORECASE
        ):
            in_detalle = False
            continue
        # Ignorar líneas que son claramente cargos financieros aunque tengan fecha
        if in_detalle and re.search(
            r"IMPUESTO|INTERES|IVA\s+\d|PERCEPCION|COMISION|CARGO\s+FINANCIERO",
            line, re.IGNORECASE
        ):
            continue
        if not in_detalle:
            continue
        tx = _parse_transaction_line(line, today_str)
        if tx:
            results.append(tx)

    if not results:
        results = _fallback_regex_parse(content["text"], today_str)
    return results


def _parse_transaction_line(line: str, today_str: str) -> dict | None:
    """
    Parsea una línea de consumo. Formatos soportados:
      "15-10-24 * MERPAGO*IVMACOGLOBALGROUP 12/12 664719 3.423,50"  (dd-mm-yy)
      "23-Nov-25 * MERPAGO*LACOSTEOUTLET 03/06 001298 10.000,00"    (dd-Mmm-yy)
      "20-01-26 K DISNEY PLUS 052084 18.399,00"                     (sin cuota)
    """
    date_match = re.match(r"^(\d{2}-\w{2,3}-\d{2,4})", line)
    if not date_match:
        return None
    tx_date = _parse_date_es(date_match.group(1))
    if not tx_date:
        return None

    rest = line[date_match.end():].strip()
    # Quitar prefijo de tipo de tarjeta (* = adicional, K = titular)
    rest = re.sub(r"^[*K]\s+", "", rest)

    # Cuota NN/NN (solo si ambos son <= 99 y es un patrón de cuotas real)
    cuota_match = re.search(r"\b(\d{1,2})/(\d{2})\b", rest)
    installment_current = installment_total = remaining = None
    if cuota_match:
        c = int(cuota_match.group(1))
        t = int(cuota_match.group(2))
        # Validar: current <= total y total > 1 (para no confundir con comprobantes)
        if 1 <= c <= t and t > 1:
            installment_current = c
            installment_total = t
            remaining = t - c
            rest = (rest[:cuota_match.start()] + rest[cuota_match.end():]).strip()

    # Monto al final (formato argentino: 1.234,56 o 1234,56 o 1234.56)
    amount_match = re.search(r"([\d.,]+)\s*$", rest)
    if not amount_match:
        return None
    amount = _parse_amount(amount_match.group(1))
    if amount <= 0:
        return None

    # Descripción: eliminar comprobante (4+ dígitos al final) y limpiar
    desc_raw = rest[:amount_match.start()].strip()
    desc_raw = re.sub(r"\s+\d{4,}\s*$", "", desc_raw).strip()
    description = desc_raw[:80] or "Sin descripcion"

    return {
        "date": tx_date, "description": description, "amount": amount,
        "type": "expense",
        "installment_current": installment_current,
        "installment_total": installment_total,
        "installments_remaining": remaining,
    }


def _fallback_regex_parse(text: str, today_str: str) -> list[dict]:
    """Regex flexible para formatos bancarios no reconocidos."""
    results = []
    for m in re.finditer(
        r"(\d{2}[-/]\w{2,3}[-/]\d{2,4})\s+.{3,50}\s+([\d.,]+)\s*$",
        text, re.MULTILINE
    ):
        tx_date = _parse_date_es(m.group(1))
        amount = _parse_amount(m.group(2))
        if tx_date and amount > 0:
            desc = re.sub(r"\d{2}[-/]\w{2,3}[-/]\d{2,4}|[\d.,]+\s*$", "", m.group(0)).strip()[:80]
            results.append({
                "date": tx_date, "description": desc, "amount": amount,
                "type": "expense",
                "installment_current": None, "installment_total": None,
                "installments_remaining": None,
            })
    return results


def extract_upcoming_installments(content: dict) -> dict[str, float]:
    """
    Extrae cuotas a vencer del pie del resumen Galicia/Visa.
      "Marzo/26 $149.999,08  Abril/26 $149.999,08 ..."
      "A partir de Setiembre/26 $56.663,00"
    Returns: {"2026-03": 149999.08, ...}
    """
    text = content["text"]
    upcoming: dict[str, float] = {}

    vencer_match = re.search(
        r"Cuotas\s+a\s+vencer\s*:(.*?)(?:\n\n|\Z)",
        text, re.DOTALL | re.IGNORECASE
    )
    if not vencer_match:
        return upcoming

    block = vencer_match.group(1)
    months_found = re.findall(r"(\w+)/(\d{2,4})", block)
    amounts_found = re.findall(r"\$\s*([\d.,]+)", block)

    for i, (month_name, year_str) in enumerate(months_found):
        month_num = _MESES_ES_FULL.get(month_name.lower())
        if not month_num:
            continue
        year = int(year_str)
        if year < 100:
            year += 2000
        key = f"{year}-{month_num:02d}"
        if i < len(amounts_found):
            upcoming[key] = _parse_amount(amounts_found[i])

    partir_match = re.search(
        r"A\s+partir\s+de\s+(\w+)/(\d{2,4})\s+\$([\d.,]+)",
        block, re.IGNORECASE
    )
    if partir_match:
        month_num = _MESES_ES_FULL.get(partir_match.group(1).lower())
        if month_num:
            year = int(partir_match.group(2))
            if year < 100:
                year += 2000
            upcoming[f"{year}-{month_num:02d}+"] = _parse_amount(partir_match.group(3))

    return upcoming


# ── Funciones públicas principales ──────────────────────────

async def parse_pdf_transactions(
    pdf_path: str | Path,
    content: dict | None = None,
) -> list[dict[str, Any]]:
    """
    Analiza un PDF financiero y extrae todas las transacciones.
    Acepta `content` ya extraído para evitar doble lectura del PDF.
    """
    today = date.today().isoformat()
    if content is None:
        content = extract_full_content(pdf_path)
    full_text = content["text"]

    if not full_text.strip():
        return []

    structured_txs = extract_structured_transactions(content)
    upcoming = extract_upcoming_installments(content)
    logger.info(
        "PDF pre-procesado: %d transacciones, %d meses cuotas a vencer",
        len(structured_txs), len(upcoming)
    )

    if not structured_txs:
        return await _llm_only_parse(full_text, today)

    return await _llm_enrich(structured_txs, today)


async def _llm_enrich(structured_txs: list[dict], today: str) -> list[dict[str, Any]]:
    """Usa Groq solo para asignar categorías. Preserva datos de cuotas."""
    tx_list = [
        {"idx": i, "description": tx["description"], "amount": tx["amount"]}
        for i, tx in enumerate(structured_txs)
    ]

    system_prompt = f"""Eres un categorizador financiero experto en gastos argentinos. Hoy es {today}.

Asigna categoria y tipo a cada transaccion.

Categorias gastos: alimentacion, transporte, entretenimiento, salud, educacion, hogar, ropa, tecnologia, servicios, otros
Categorias ingresos: salario, freelance, inversiones, ventas, otros_ingresos

Reglas:
- Comercios/consumos -> "expense"
- "SU PAGO", "TRANSFERENCIA", pagos -> "income"
- Impuestos, intereses, comisiones -> "expense" + "servicios"
- Supermercados, restaurantes, bares -> "alimentacion"
- Nafta, combustible, SHELL -> "transporte"
- Disney Plus, Netflix, Spotify -> "entretenimiento"
- Lacoste, Grimoldi, Zara, Adidas -> "ropa"
- Electronica, instrumentos musicales -> "tecnologia"
- MercadoPago sin contexto -> "otros"

Responde UNICAMENTE con JSON array:
[{{"idx": <numero>, "category": "<categoria>", "type": "income"|"expense"}}]"""

    response = await _client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(tx_list, ensure_ascii=False)},
        ],
        temperature=0,
        max_tokens=1500,
    )

    raw = re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "", response.choices[0].message.content.strip(),
        flags=re.MULTILINE
    ).strip()

    try:
        enrich_map = {e["idx"]: e for e in json.loads(raw) if "idx" in e}
    except (json.JSONDecodeError, TypeError):
        enrich_map = {}

    return [
        {
            "amount": tx["amount"],
            "type": enrich_map.get(i, {}).get("type", "expense"),
            "category": enrich_map.get(i, {}).get("category", "otros"),
            "description": tx["description"],
            "date": tx["date"],
            "installment_current": tx.get("installment_current"),
            "installment_total": tx.get("installment_total"),
            "installments_remaining": tx.get("installments_remaining"),
        }
        for i, tx in enumerate(structured_txs)
    ]


async def _llm_only_parse(raw_text: str, today: str) -> list[dict[str, Any]]:
    """Fallback completo por LLM para formatos bancarios no reconocidos."""
    if len(raw_text) > MAX_TEXT_CHARS:
        raw_text = raw_text[:MAX_TEXT_CHARS] + "\n[... truncado ...]"

    system_prompt = f"""Eres un experto en documentos bancarios argentinos. Hoy es {today}.

Extrae TODAS las transacciones. Atencion especial a:
- Columna CUOTA: "03/06" = cuota 3 de 6 -> installments_remaining = 3
- Fechas, comercios, pagos del titular

Responde UNICAMENTE con JSON array:
[{{"amount":<pos>,"type":"income"|"expense","category":"<cat>","description":"<desc>",
"date":"<YYYY-MM-DD>","installment_current":<n|null>,"installment_total":<n|null>,"installments_remaining":<n|null>}}]

Categorias: alimentacion, transporte, entretenimiento, salud, educacion, hogar, ropa, tecnologia, servicios, otros, salario, freelance, inversiones, ventas, otros_ingresos
Si no hay transacciones: []"""

    response = await _client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Documento:\n\n{raw_text}"},
        ],
        temperature=0,
        max_tokens=2500,
    )

    raw = re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "", response.choices[0].message.content.strip(),
        flags=re.MULTILINE
    ).strip()

    try:
        return [
            {
                "amount": abs(float(tx["amount"])),
                "type": tx.get("type", "expense"),
                "category": tx.get("category", "otros"),
                "description": str(tx.get("description", ""))[:100],
                "date": tx.get("date", today),
                "installment_current": tx.get("installment_current"),
                "installment_total": tx.get("installment_total"),
                "installments_remaining": tx.get("installments_remaining"),
            }
            for tx in json.loads(raw)
            if isinstance(tx, dict) and tx.get("amount")
        ]
    except (json.JSONDecodeError, KeyError, ValueError):
        return []


async def summarize_pdf_statement(pdf_path: str | Path, content: dict | None = None) -> str:
    """
    Genera un resumen inteligente incluyendo cuotas pendientes detectadas.
    Acepta `content` ya extraído para evitar doble lectura del PDF.
    """
    if content is None:
        content = extract_full_content(pdf_path)
    full_text = content["text"]

    if not full_text.strip():
        return "No se pudo extraer texto del PDF."

    upcoming = extract_upcoming_installments(content)
    upcoming_info = ""
    if upcoming:
        parts = [f"{m}: ${a:,.0f}" for m, a in upcoming.items()]
        upcoming_info = f"\n\nCuotas a vencer detectadas: {', '.join(parts)}"

    text_for_llm = full_text[:MAX_TEXT_CHARS] + upcoming_info

    response = await _client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "Eres un asesor financiero personal. Analizas resumenes bancarios argentinos.\n"
                    "Resume el documento incluyendo:\n"
                    "- Banco y tipo de documento\n"
                    "- Total a pagar\n"
                    "- Principales consumos\n"
                    "- Compras en cuotas: descripcion, cuota actual/total, cuantas quedan\n"
                    "- Cuotas a vencer por mes y sus montos\n"
                    "- Pagos realizados en el periodo\n"
                    "Texto plano, sin Markdown especial, con emojis. Maximo 300 palabras."
                ),
            },
            {"role": "user", "content": text_for_llm},
        ],
        temperature=0.2,
        max_tokens=600,
    )

    return response.choices[0].message.content.strip()
