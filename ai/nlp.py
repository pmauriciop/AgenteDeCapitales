"""
ai/nlp.py
─────────
Procesamiento de lenguaje natural con Groq (Llama 3.3 70B).
Extrae transacciones y clasifica intenciones del usuario
a partir de texto libre (mensajes de Telegram).
"""

import json
import re
from datetime import date
from typing import Any

from groq import AsyncGroq

from config import GROQ_API_KEY, GROQ_MODEL

_client = AsyncGroq(api_key=GROQ_API_KEY)

# ─────────────────────────────────────────────
#  Categorías disponibles
# ─────────────────────────────────────────────

EXPENSE_CATEGORIES = [
    "alimentación",
    "transporte",
    "entretenimiento",
    "salud",
    "educación",
    "hogar",
    "ropa",
    "tecnología",
    "servicios",
    "otros",
]

INCOME_CATEGORIES = [
    "salario",
    "freelance",
    "inversiones",
    "ventas",
    "otros_ingresos",
]

# ─────────────────────────────────────────────
#  Intenciones soportadas
# ─────────────────────────────────────────────

INTENTS = [
    "add_expense",       # registrar un gasto
    "add_income",        # registrar un ingreso
    "get_summary",       # ver resumen / balance
    "get_budget",        # ver presupuesto
    "set_budget",        # definir presupuesto
    "list_transactions", # listar transacciones
    "delete_transaction",# borrar transacción
    "add_recurring",     # agregar recurrente
    "list_recurring",    # ver recurrentes
    "get_report",        # pedir reporte
    "help",              # ayuda
    "unknown",           # no entendido
]


# ─────────────────────────────────────────────
#  parse_transaction
# ─────────────────────────────────────────────

async def parse_transaction(text: str) -> dict[str, Any] | None:
    """
    Extrae los datos de una transacción a partir de texto libre.

    Args:
        text: Mensaje del usuario en lenguaje natural.

    Returns:
        dict con claves:
            - amount      (float, positivo)
            - type        ("income" | "expense")
            - category    (str)
            - description (str)
            - date        (str ISO "YYYY-MM-DD", hoy si no se menciona)
        None si no se detecta transacción.
    """
    today = date.today().isoformat()

    system_prompt = f"""Eres un asistente financiero. Extrae los datos de la transacción del mensaje del usuario.
Hoy es {today}.

Responde ÚNICAMENTE con un JSON válido con esta estructura exacta:
{{
  "amount": <número positivo>,
  "type": "income" | "expense",
  "category": "<categoría>",
  "description": "<descripción breve>",
  "date": "<YYYY-MM-DD>"
}}

Categorías de gastos: {", ".join(EXPENSE_CATEGORIES)}
Categorías de ingresos: {", ".join(INCOME_CATEGORIES)}

Si el mensaje NO describe una transacción, responde exactamente: null
No incluyas explicaciones ni texto adicional."""

    response = await _client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
        temperature=0,
        max_tokens=200,
    )

    raw = response.choices[0].message.content.strip()
    # Limpiar bloques de código markdown si el modelo los devuelve
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()

    if raw.lower() == "null":
        return None

    try:
        data = json.loads(raw)
        data["amount"] = abs(float(data["amount"]))
        if data["type"] not in ("income", "expense"):
            data["type"] = "expense"
        if not data.get("date"):
            data["date"] = today
        return data
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


# ─────────────────────────────────────────────
#  classify_intent
# ─────────────────────────────────────────────

async def classify_intent(text: str) -> str:
    """
    Clasifica la intención del mensaje del usuario.

    Returns:
        Una de las intenciones definidas en INTENTS.
    """
    system_prompt = f"""Clasifica la intención del mensaje del usuario en una de estas categorías:
{chr(10).join(f"- {i}" for i in INTENTS)}

Responde ÚNICAMENTE con el nombre exacto de la intención (sin comillas ni explicación)."""

    response = await _client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
        temperature=0,
        max_tokens=30,
    )

    intent = response.choices[0].message.content.strip().lower()
    return intent if intent in INTENTS else "unknown"


# ─────────────────────────────────────────────
#  generate_financial_advice
# ─────────────────────────────────────────────

async def generate_financial_advice(summary: dict) -> str:
    """
    Genera un consejo financiero personalizado basado en el resumen del mes.

    Args:
        summary: dict con income, expense, balance y breakdown por categoría.

    Returns:
        Texto con consejos en español, formateado para Telegram.
    """
    system_prompt = """Eres un asesor financiero personal amigable y conciso.
Analiza el resumen financiero del usuario y da 2-3 consejos prácticos y personalizados.
Usa emojis y formato Markdown compatible con Telegram.
Sé positivo pero honesto. Máximo 150 palabras."""

    user_message = f"Mi resumen financiero del mes:\n{json.dumps(summary, ensure_ascii=False, indent=2)}"

    response = await _client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0.7,
        max_tokens=300,
    )

    return response.choices[0].message.content.strip()
