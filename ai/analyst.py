"""
ai/analyst.py
─────────────
Analista financiero con IA.

Dado un mensaje en lenguaje natural del usuario y su contexto financiero
completo (transacciones, recurrentes, presupuestos), usa Groq para
razonar y responder preguntas como:

  - "¿Cuántas cuotas me quedan?"
  - "¿En qué estoy gastando más?"
  - "Haceme una proyección para el próximo trimestre"
  - "¿Cuándo voy a poder ahorrar $50.000?"
  - "Comparame este mes con el anterior"
  - "¿Cuánto gasto en promedio por semana?"

El LLM recibe todos los datos estructurados y los analiza libre de restricciones.
"""

import json
import logging
from datetime import date

from groq import AsyncGroq
from config import GROQ_API_KEY, GROQ_MODEL

logger = logging.getLogger(__name__)

_client = AsyncGroq(api_key=GROQ_API_KEY)


async def answer_financial_question(
    question: str,
    context: dict,
) -> str:
    """
    Responde una pregunta financiera en lenguaje natural.

    Args:
        question:  La pregunta del usuario tal cual la escribió.
        context:   Dict con todos los datos financieros del usuario:
                   - monthly_totals: list[dict]  → histórico mensual
                   - current_month_txs: list[dict] → transacciones del mes
                   - recurring: list[dict]        → suscripciones/recurrentes
                   - budget_status: list[dict]    → presupuestos actuales
                   - user_name: str

    Returns:
        Respuesta en texto plano (sin Markdown especial), lista para Telegram.
    """
    today = date.today().isoformat()

    system_prompt = f"""Eres un asesor financiero personal experto trabajando con datos REALES del usuario.
Hoy es {today}. El usuario se llama {context.get('user_name', 'el usuario')}.

Tu rol: analizar los datos financieros que te proporciono y responder la pregunta con precisión,
razonando paso a paso cuando sea necesario.

CAPACIDADES:
- Calcular cuotas pendientes de compras en cuotas (identificalas por descripción, ej: "cuota 3/12")
- Proyectar gastos futuros basándote en el promedio histórico
- Identificar tendencias de gasto/ingreso mes a mes
- Responder comparativas entre períodos
- Estimar fechas de ahorro para metas
- Detectar gastos inusuales o categorías problemáticas
- Analizar la salud financiera general

DATOS DEL USUARIO:
{json.dumps(context, ensure_ascii=False, indent=2, default=str)}

INSTRUCCIONES DE RESPUESTA:
- Sé conciso pero completo. Máximo 300 palabras.
- Usa números concretos de los datos. No inventes cifras.
- Usa emojis para hacer la respuesta más legible.
- Si hay cuotas, lista cada una con cuántas quedan y el monto.
- Si hacés proyecciones, explicá el método (promedio de N meses).
- Si la pregunta no puede responderse con los datos disponibles, decilo claramente.
- Respondé en español argentino.
- NO uses bloques de código ni tablas complejas. Sé conversacional.
- NO uses caracteres especiales de Markdown como *, _, `, [ ] que rompen Telegram.
  Solo podés usar emojis y texto plano."""

    try:
        response = await _client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ],
            temperature=0.3,
            max_tokens=600,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error("Error en analyst: %s", e)
        return "❌ No pude analizar tus datos en este momento. Intentá de nuevo en unos segundos."


async def detect_analyst_intent(text: str) -> bool:
    """
    Detecta si el mensaje del usuario es una pregunta/consulta analítica
    sobre sus finanzas (vs. registrar una transacción o comando simple).

    Returns True si debe ir al analista.
    """
    system_prompt = """Determiná si el mensaje del usuario es una PREGUNTA ANALÍTICA sobre sus finanzas.

Ejemplos de PREGUNTA ANALÍTICA (responder true):
- "¿cuántas cuotas me quedan?"
- "haceme una proyección de gastos"
- "en qué gasto más?"
- "comparame este mes con el anterior"
- "¿cuándo puedo ahorrar 100000 pesos?"
- "¿cuánto gasté en promedio por semana?"
- "¿cómo van mis finanzas?"
- "¿me alcanza el sueldo?"
- "analizá mis gastos"
- "¿en qué categoría me paso más?"

Ejemplos que NO son analíticas (responder false):
- "gasté 500 en taxi" (registrar gasto)
- "cobré el sueldo" (registrar ingreso)
- "quiero ver el resumen" (comando de menú)
- "ayuda" (comando)
- "hola" (saludo)

Respondé ÚNICAMENTE con: true o false"""

    try:
        response = await _client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            temperature=0,
            max_tokens=5,
        )
        result = response.choices[0].message.content.strip().lower()
        return result == "true"
    except Exception:
        return False
