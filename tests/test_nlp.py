"""
tests/test_nlp.py
──────────────────
Tests unitarios para ai/nlp.py
Se mockea la API de OpenAI para no hacer llamadas reales.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


def _make_openai_response(content: str):
    """Crea un mock de respuesta de OpenAI."""
    choice = MagicMock()
    choice.message.content = content
    response = MagicMock()
    response.choices = [choice]
    return response


class TestParseTransaction:
    @pytest.mark.asyncio
    @patch("ai.nlp._client")
    async def test_parse_expense(self, mock_client):
        """Parsea correctamente un gasto."""
        mock_client.chat.completions.create = AsyncMock(
            return_value=_make_openai_response(
                '{"amount": 500.0, "type": "expense", "category": "alimentación", '
                '"description": "supermercado", "date": "2026-02-21"}'
            )
        )

        from ai.nlp import parse_transaction
        result = await parse_transaction("gasté 500 en el super")

        assert result is not None
        assert result["amount"] == 500.0
        assert result["type"] == "expense"
        assert result["category"] == "alimentación"

    @pytest.mark.asyncio
    @patch("ai.nlp._client")
    async def test_parse_income(self, mock_client):
        """Parsea correctamente un ingreso."""
        mock_client.chat.completions.create = AsyncMock(
            return_value=_make_openai_response(
                '{"amount": 150000.0, "type": "income", "category": "salario", '
                '"description": "sueldo mensual", "date": "2026-02-21"}'
            )
        )

        from ai.nlp import parse_transaction
        result = await parse_transaction("cobré el sueldo, 150000 pesos")

        assert result is not None
        assert result["type"] == "income"
        assert result["amount"] == 150000.0

    @pytest.mark.asyncio
    @patch("ai.nlp._client")
    async def test_parse_returns_none_for_non_transaction(self, mock_client):
        """Retorna None cuando el mensaje no es una transacción."""
        mock_client.chat.completions.create = AsyncMock(
            return_value=_make_openai_response("null")
        )

        from ai.nlp import parse_transaction
        result = await parse_transaction("hola, ¿cómo estás?")
        assert result is None

    @pytest.mark.asyncio
    @patch("ai.nlp._client")
    async def test_parse_normalizes_negative_amount(self, mock_client):
        """El monto siempre debe ser positivo."""
        mock_client.chat.completions.create = AsyncMock(
            return_value=_make_openai_response(
                '{"amount": -200.0, "type": "expense", "category": "transporte", '
                '"description": "colectivo", "date": "2026-02-21"}'
            )
        )

        from ai.nlp import parse_transaction
        result = await parse_transaction("pagué el colectivo 200")
        assert result["amount"] == 200.0  # abs() aplicado

    @pytest.mark.asyncio
    @patch("ai.nlp._client")
    async def test_parse_handles_invalid_json(self, mock_client):
        """Retorna None si el modelo devuelve JSON inválido."""
        mock_client.chat.completions.create = AsyncMock(
            return_value=_make_openai_response("esto no es json válido")
        )

        from ai.nlp import parse_transaction
        result = await parse_transaction("algo raro")
        assert result is None


class TestClassifyIntent:
    @pytest.mark.asyncio
    @patch("ai.nlp._client")
    async def test_classify_expense_intent(self, mock_client):
        mock_client.chat.completions.create = AsyncMock(
            return_value=_make_openai_response("add_expense")
        )

        from ai.nlp import classify_intent
        result = await classify_intent("gasté 500 en el super")
        assert result == "add_expense"

    @pytest.mark.asyncio
    @patch("ai.nlp._client")
    async def test_classify_unknown_fallback(self, mock_client):
        """Intenciones no reconocidas caen en 'unknown'."""
        mock_client.chat.completions.create = AsyncMock(
            return_value=_make_openai_response("algo_que_no_existe")
        )

        from ai.nlp import classify_intent
        result = await classify_intent("texto aleatorio sin sentido")
        assert result == "unknown"

    @pytest.mark.asyncio
    @patch("ai.nlp._client")
    async def test_classify_get_summary(self, mock_client):
        mock_client.chat.completions.create = AsyncMock(
            return_value=_make_openai_response("get_summary")
        )

        from ai.nlp import classify_intent
        result = await classify_intent("¿cuánto gasté este mes?")
        assert result == "get_summary"
