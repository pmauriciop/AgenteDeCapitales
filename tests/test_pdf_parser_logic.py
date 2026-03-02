"""
tests/test_pdf_parser_logic.py
────────────────────────────────
Tests para la lógica de extracción estructurada de ai/pdf_parser.py.

No se testea la parte de LLM (Groq). Se testean:
  - _parse_date_es()
  - _parse_amount()
  - _parse_transaction_line()
  - extract_structured_transactions()
  - extract_upcoming_installments()
  - parse_pdf_transactions() — llamada completa con mock de Groq
"""

from __future__ import annotations

import json
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ─────────────────────────────────────────────
#  _parse_date_es
# ─────────────────────────────────────────────

class TestParseDateEs:
    def _parse(self, s):
        from ai.pdf_parser import _parse_date_es
        return _parse_date_es(s)

    def test_dd_mm_yy(self):
        assert self._parse("15-10-24") == "2024-10-15"

    def test_dd_Mmm_yy(self):
        assert self._parse("23-Nov-25") == "2025-11-23"

    def test_dd_Mmm_yy_lower(self):
        assert self._parse("05-ene-26") == "2026-01-05"

    def test_dd_slash_mm_slash_yyyy(self):
        assert self._parse("20/01/2026") == "2026-01-20"

    def test_invalid_returns_none(self):
        assert self._parse("no-es-fecha") is None

    def test_invalid_date_values(self):
        # día 32 no existe
        assert self._parse("32-01-26") is None

    def test_two_digit_year_adjusted(self):
        result = self._parse("01-mar-99")
        assert result == "2099-03-01"


# ─────────────────────────────────────────────
#  _parse_amount
# ─────────────────────────────────────────────

class TestParseAmount:
    def _parse(self, s):
        from ai.pdf_parser import _parse_amount
        return _parse_amount(s)

    def test_punto_miles_coma_decimal(self):
        assert self._parse("3.423,50") == pytest.approx(3423.50)

    def test_solo_coma_decimal(self):
        assert self._parse("1234,56") == pytest.approx(1234.56)

    def test_solo_punto_decimal(self):
        assert self._parse("1234.56") == pytest.approx(1234.56)

    def test_sin_decimales(self):
        assert self._parse("1500") == pytest.approx(1500.0)

    def test_con_simbolo_pesos(self):
        assert self._parse("$5.000,00") == pytest.approx(5000.0)

    def test_negativo_retorna_positivo(self):
        assert self._parse("-200,00") == pytest.approx(200.0)

    def test_invalido_retorna_cero(self):
        assert self._parse("abc") == 0.0

    def test_monto_grande(self):
        assert self._parse("149.999,08") == pytest.approx(149999.08)


# ─────────────────────────────────────────────
#  _parse_transaction_line
# ─────────────────────────────────────────────

class TestParseTransactionLine:
    def _parse(self, line):
        from ai.pdf_parser import _parse_transaction_line
        return _parse_transaction_line(line, "2026-03-02")

    def test_linea_con_cuota(self):
        line = "15-10-24 * MERPAGO*IVMACOGLOBALGROUP 12/12 664719 3.423,50"
        tx = self._parse(line)
        assert tx is not None
        assert tx["amount"] == pytest.approx(3423.50)
        assert tx["date"] == "2024-10-15"
        assert tx["installment_current"] == 12
        assert tx["installment_total"] == 12
        assert tx["installments_remaining"] == 0

    def test_linea_cuota_parcial(self):
        line = "23-Nov-25 * MERPAGO*LACOSTEOUTLET 03/06 001298 10.000,00"
        tx = self._parse(line)
        assert tx is not None
        assert tx["installment_current"] == 3
        assert tx["installment_total"] == 6
        assert tx["installments_remaining"] == 3

    def test_linea_sin_cuota(self):
        line = "20-01-26 K DISNEY PLUS 052084 18.399,00"
        tx = self._parse(line)
        assert tx is not None
        assert tx["installment_current"] is None
        assert tx["installment_total"] is None
        assert tx["amount"] == pytest.approx(18399.0)
        assert "DISNEY" in tx["description"]

    def test_linea_sin_fecha_retorna_none(self):
        line = "TOTAL A PAGAR $50.000,00"
        assert self._parse(line) is None

    def test_linea_vacia_retorna_none(self):
        assert self._parse("") is None

    def test_monto_cero_retorna_none(self):
        line = "15-01-26 * COMERCIO 123456 0,00"
        assert self._parse(line) is None

    def test_prefijo_K_removido(self):
        line = "10-02-26 K SUPERMERCADO DISCO 999999 2.500,00"
        tx = self._parse(line)
        assert tx is not None
        assert "K " not in tx["description"]

    def test_descripcion_truncada_a_80_chars(self):
        long_desc = "A" * 90
        line = f"10-02-26 * {long_desc} 999999 100,00"
        tx = self._parse(line)
        assert tx is not None
        assert len(tx["description"]) <= 80

    def test_cuota_1_de_1_no_se_toma(self):
        # 1/1 no es "en cuotas", es pago único
        line = "10-02-26 * TIENDA ABC 1/1 123456 500,00"
        tx = self._parse(line)
        assert tx is not None
        assert tx["installment_total"] is None


# ─────────────────────────────────────────────
#  extract_structured_transactions
# ─────────────────────────────────────────────

class TestExtractStructuredTransactions:
    def _extract(self, text):
        from ai.pdf_parser import extract_structured_transactions
        return extract_structured_transactions({"text": text})

    PDF_DETALLE = """
DETALLE DEL CONSUMO

15-10-24 * MERPAGO*LACOSTE 03/06 001298 10.000,00
20-01-26 K DISNEY PLUS 052084 18.399,00
23-Nov-25 * SHELL SELECT 007777 3.200,00

TOTAL A PAGAR $31.599,00
"""

    def test_detecta_seccion_detalle(self):
        txs = self._extract(self.PDF_DETALLE)
        assert len(txs) == 3

    def test_cuotas_extraidas_correctamente(self):
        txs = self._extract(self.PDF_DETALLE)
        lacoste = next(t for t in txs if "LACOSTE" in t["description"])
        assert lacoste["installment_current"] == 3
        assert lacoste["installment_total"] == 6

    def test_sin_cuota_es_none(self):
        txs = self._extract(self.PDF_DETALLE)
        disney = next(t for t in txs if "DISNEY" in t["description"])
        assert disney["installment_current"] is None

    def test_total_a_pagar_no_incluido(self):
        txs = self._extract(self.PDF_DETALLE)
        descriptions = [t["description"].upper() for t in txs]
        assert not any("TOTAL" in d for d in descriptions)

    def test_texto_sin_seccion_detalle_usa_fallback(self):
        text = "15-10-24 * SUPERMERCADO ABC 123456 5.000,00"
        txs = self._extract(text)
        # Puede retornar 0 (sin sección DETALLE y sin match del fallback) o 1
        # La clave es que no tira excepción
        assert isinstance(txs, list)

    def test_texto_vacio_retorna_lista_vacia(self):
        txs = self._extract("")
        assert txs == []

    def test_impuestos_no_incluidos(self):
        text = """
DETALLE DEL CONSUMO

15-10-24 * SUPERMERCADO 123456 5.000,00
16-10-24 K IMPUESTO PAIS 111111 100,00
TOTAL A PAGAR $5.100,00
"""
        txs = self._extract(text)
        descriptions = [t["description"].upper() for t in txs]
        assert not any("IMPUESTO" in d for d in descriptions)


# ─────────────────────────────────────────────
#  extract_upcoming_installments
# ─────────────────────────────────────────────

class TestExtractUpcomingInstallments:
    def _extract(self, text):
        from ai.pdf_parser import extract_upcoming_installments
        return extract_upcoming_installments({"text": text})

    def test_extrae_cuotas_simples(self):
        text = "Cuotas a vencer: Marzo/26 $10.000,00  Abril/26 $10.000,00"
        result = self._extract(text)
        assert "2026-03" in result
        assert result["2026-03"] == pytest.approx(10000.0)
        assert "2026-04" in result

    def test_extrae_a_partir_de(self):
        text = "Cuotas a vencer: A partir de Septiembre/26 $56.663,00"
        result = self._extract(text)
        assert "2026-09+" in result
        assert result["2026-09+"] == pytest.approx(56663.0)

    def test_sin_cuotas_retorna_vacio(self):
        result = self._extract("Texto sin cuotas a vencer")
        assert result == {}

    def test_multiples_meses(self):
        text = (
            "Cuotas a vencer: Marzo/26 $5.000,00  Abril/26 $5.000,00  "
            "Mayo/26 $5.000,00"
        )
        result = self._extract(text)
        assert len(result) == 3

    def test_montos_correctos(self):
        text = "Cuotas a vencer: Marzo/26 $149.999,08"
        result = self._extract(text)
        assert result.get("2026-03") == pytest.approx(149999.08)


# ─────────────────────────────────────────────
#  parse_pdf_transactions (integración con mock Groq)
# ─────────────────────────────────────────────

class TestParsePdfTransactions:
    """
    Testea el flujo completo: extracción estructurada → enriquecimiento LLM.
    El cliente Groq se mockea para no hacer llamadas reales.
    """

    PDF_TEXT_WITH_DETALLE = """
DETALLE DEL CONSUMO

15-10-24 * MERPAGO*LACOSTE 03/06 001298 10.000,00
20-01-26 K DISNEY PLUS 052084 18.399,00

TOTAL A PAGAR $28.399,00
"""

    def _make_groq_response(self, enrichment: list[dict]) -> MagicMock:
        """Mock de respuesta de Groq que devuelve el JSON de categorías."""
        msg = MagicMock()
        msg.content = json.dumps(enrichment)
        choice = MagicMock()
        choice.message = msg
        resp = MagicMock()
        resp.choices = [choice]
        return resp

    @pytest.mark.asyncio
    async def test_parse_returns_transactions(self):
        from ai.pdf_parser import parse_pdf_transactions

        enrichment = [
            {"idx": 0, "category": "ropa", "type": "expense"},
            {"idx": 1, "category": "entretenimiento", "type": "expense"},
        ]
        groq_resp = self._make_groq_response(enrichment)

        with patch("ai.pdf_parser._client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=groq_resp)
            result = await parse_pdf_transactions(
                "fake.pdf",
                content={"text": self.PDF_TEXT_WITH_DETALLE, "pages": []},
            )

        assert len(result) == 2
        lacoste = next(t for t in result if "LACOSTE" in t["description"])
        disney = next(t for t in result if "DISNEY" in t["description"])
        assert lacoste["category"] == "ropa"
        assert lacoste["installment_current"] == 3
        assert lacoste["installment_total"] == 6
        assert disney["category"] == "entretenimiento"
        assert disney["installment_current"] is None

    @pytest.mark.asyncio
    async def test_parse_preserves_installment_data(self):
        from ai.pdf_parser import parse_pdf_transactions

        enrichment = [{"idx": 0, "category": "otros", "type": "expense"}]
        groq_resp = self._make_groq_response(enrichment)

        pdf_text = """
DETALLE DEL CONSUMO

23-Nov-25 * TIENDA ABC 01/12 999999 5.000,00

TOTAL A PAGAR $5.000,00
"""
        with patch("ai.pdf_parser._client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=groq_resp)
            result = await parse_pdf_transactions(
                "fake.pdf",
                content={"text": pdf_text, "pages": []},
            )

        assert len(result) == 1
        tx = result[0]
        assert tx["installment_current"] == 1
        assert tx["installment_total"] == 12
        assert tx["installments_remaining"] == 11

    @pytest.mark.asyncio
    async def test_parse_empty_pdf_returns_empty(self):
        from ai.pdf_parser import parse_pdf_transactions

        result = await parse_pdf_transactions(
            "fake.pdf",
            content={"text": "", "pages": []},
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_llm_fallback_used_when_no_structured(self):
        """Si no hay sección DETALLE DEL CONSUMO, usa el LLM completo (_llm_only_parse)."""
        from ai.pdf_parser import parse_pdf_transactions

        llm_transactions = [
            {
                "amount": 500.0, "type": "expense", "category": "alimentacion",
                "description": "Super Vea", "date": "2026-03-01",
                "installment_current": None, "installment_total": None,
                "installments_remaining": None,
            }
        ]
        msg = MagicMock()
        msg.content = json.dumps(llm_transactions)
        choice = MagicMock()
        choice.message = msg
        resp = MagicMock()
        resp.choices = [choice]

        pdf_text = "Resumen de cuenta\nFecha: 2026-03\nSaldo: $500"

        with patch("ai.pdf_parser._client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=resp)
            result = await parse_pdf_transactions(
                "fake.pdf",
                content={"text": pdf_text, "pages": []},
            )

        assert len(result) == 1
        assert result[0]["description"] == "Super Vea"

    @pytest.mark.asyncio
    async def test_groq_invalid_json_returns_empty(self):
        """Si Groq devuelve JSON inválido en el fallback, retorna []."""
        from ai.pdf_parser import parse_pdf_transactions

        msg = MagicMock()
        msg.content = "esto no es json"
        choice = MagicMock()
        choice.message = msg
        resp = MagicMock()
        resp.choices = [choice]

        pdf_text = "Resumen sin sección DETALLE"

        with patch("ai.pdf_parser._client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=resp)
            result = await parse_pdf_transactions(
                "fake.pdf",
                content={"text": pdf_text, "pages": []},
            )

        assert result == []
