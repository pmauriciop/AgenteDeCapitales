"""
tests/test_analyst_service.py
──────────────────────────────
Tests para services/analyst_service.py.

Mockeamos:
  - TransactionRepo.*   → devuelve datos de prueba sin tocar Supabase
  - RecurringRepo.*     → idem
  - BudgetRepo.*        → idem
  - ai.analyst.answer_financial_question → evita llamada real a Groq
  - ai.analyst.detect_analyst_intent     → idem
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from database.models import Transaction, RecurringTransaction, Budget


# ─────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────

USER_ID = "user-analyst-uuid"
USER_NAME = "Carlos"


def _make_tx(
    *,
    tx_id="t1",
    amount=1000.0,
    tx_type="expense",
    category="alimentacion",
    description="Super",
    tx_date="2026-03-01",
    installment_current=None,
    installment_total=None,
    installments_remaining=None,
) -> Transaction:
    return Transaction(
        id=tx_id,
        user_id=USER_ID,
        amount=amount,
        type=tx_type,
        category=category,
        description=description,
        date=date.fromisoformat(tx_date),
        installment_current=installment_current,
        installment_total=installment_total,
        installments_remaining=installments_remaining,
    )


def _make_recurring(description="Netflix", amount=1200.0) -> RecurringTransaction:
    return RecurringTransaction(
        id="r1",
        user_id=USER_ID,
        amount=amount,
        category="entretenimiento",
        description=description,
        frequency="monthly",
        next_date=date(2026, 3, 15),
    )


# ─────────────────────────────────────────────
#  is_analyst_question
# ─────────────────────────────────────────────

class TestIsAnalystQuestion:
    @pytest.mark.asyncio
    async def test_returns_true_when_analyst_intent(self):
        from services.analyst_service import AnalystService

        with patch("services.analyst_service.detect_analyst_intent",
                   new=AsyncMock(return_value=True)):
            result = await AnalystService.is_analyst_question("¿cuánto gasté este mes?")

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_for_command(self):
        from services.analyst_service import AnalystService

        with patch("services.analyst_service.detect_analyst_intent",
                   new=AsyncMock(return_value=False)):
            result = await AnalystService.is_analyst_question("gasté 500 en taxi")

        assert result is False


# ─────────────────────────────────────────────
#  answer — armado del contexto
# ─────────────────────────────────────────────

class TestAnalystServiceAnswer:
    """
    Testea que AnalystService.answer():
    1. Llama a los repos correctos
    2. Arma el contexto con las claves esperadas
    3. Pasa el contexto a answer_financial_question
    4. Retorna la respuesta del LLM
    """

    def _patch_all_repos(self, txs_month=None, txs_all=None, recurring=None,
                         monthly_totals=None, budget_status=None):
        """Devuelve un dict de patches con valores por defecto."""
        return {
            "TransactionRepo.get_monthly_totals": MagicMock(
                return_value=monthly_totals or []
            ),
            "TransactionRepo.list_by_month": MagicMock(
                return_value=txs_month or []
            ),
            "RecurringRepo.list_active": MagicMock(
                return_value=recurring or []
            ),
            "BudgetRepo.get_budget_status": MagicMock(
                return_value=budget_status or []
            ),
            "TransactionRepo.list_all": MagicMock(
                return_value=txs_all or []
            ),
        }

    @pytest.mark.asyncio
    async def test_returns_llm_response(self):
        from services.analyst_service import AnalystService

        patches = self._patch_all_repos()

        with (
            patch("services.analyst_service.TransactionRepo.get_monthly_totals",
                  patches["TransactionRepo.get_monthly_totals"]),
            patch("services.analyst_service.TransactionRepo.list_by_month",
                  patches["TransactionRepo.list_by_month"]),
            patch("services.analyst_service.RecurringRepo.list_active",
                  patches["RecurringRepo.list_active"]),
            patch("services.analyst_service.BudgetRepo.get_budget_status",
                  patches["BudgetRepo.get_budget_status"]),
            patch("services.analyst_service.TransactionRepo.list_all",
                  patches["TransactionRepo.list_all"]),
            patch("services.analyst_service.answer_financial_question",
                  new=AsyncMock(return_value="Gastaste $1000 este mes.")),
        ):
            result = await AnalystService.answer(
                user_id=USER_ID,
                user_name=USER_NAME,
                question="¿cuánto gasté?",
            )

        assert result == "Gastaste $1000 este mes."

    @pytest.mark.asyncio
    async def test_context_contains_required_keys(self):
        from services.analyst_service import AnalystService

        captured_context = {}

        async def fake_answer(question, context):
            captured_context.update(context)
            return "ok"

        with (
            patch("services.analyst_service.TransactionRepo.get_monthly_totals",
                  MagicMock(return_value=[])),
            patch("services.analyst_service.TransactionRepo.list_by_month",
                  MagicMock(return_value=[])),
            patch("services.analyst_service.RecurringRepo.list_active",
                  MagicMock(return_value=[])),
            patch("services.analyst_service.BudgetRepo.get_budget_status",
                  MagicMock(return_value=[])),
            patch("services.analyst_service.TransactionRepo.list_all",
                  MagicMock(return_value=[])),
            patch("services.analyst_service.answer_financial_question",
                  new=AsyncMock(side_effect=fake_answer)),
        ):
            await AnalystService.answer(USER_ID, USER_NAME, "test")

        expected_keys = {
            "user_name", "today", "current_month",
            "monthly_totals_last_6_months", "current_month_transactions",
            "all_transactions", "installments_active",
            "recurring_subscriptions", "budget_status",
        }
        assert expected_keys.issubset(set(captured_context.keys()))

    @pytest.mark.asyncio
    async def test_context_user_name_correct(self):
        from services.analyst_service import AnalystService

        captured = {}

        async def fake_answer(question, context):
            captured.update(context)
            return "ok"

        with (
            patch("services.analyst_service.TransactionRepo.get_monthly_totals",
                  MagicMock(return_value=[])),
            patch("services.analyst_service.TransactionRepo.list_by_month",
                  MagicMock(return_value=[])),
            patch("services.analyst_service.RecurringRepo.list_active",
                  MagicMock(return_value=[])),
            patch("services.analyst_service.BudgetRepo.get_budget_status",
                  MagicMock(return_value=[])),
            patch("services.analyst_service.TransactionRepo.list_all",
                  MagicMock(return_value=[])),
            patch("services.analyst_service.answer_financial_question",
                  new=AsyncMock(side_effect=fake_answer)),
        ):
            await AnalystService.answer(USER_ID, "Valentina", "test")

        assert captured["user_name"] == "Valentina"

    @pytest.mark.asyncio
    async def test_installments_active_filtered_correctly(self):
        """Solo cuotas con installment_total Y installments_remaining > 0."""
        from services.analyst_service import AnalystService

        txs_all = [
            _make_tx(tx_id="t1", description="Con cuotas restantes",
                     installment_total=6, installments_remaining=3),
            _make_tx(tx_id="t2", description="Cuotas terminadas",
                     installment_total=6, installments_remaining=0),
            _make_tx(tx_id="t3", description="Sin cuotas"),
        ]
        captured = {}

        async def fake_answer(question, context):
            captured.update(context)
            return "ok"

        with (
            patch("services.analyst_service.TransactionRepo.get_monthly_totals",
                  MagicMock(return_value=[])),
            patch("services.analyst_service.TransactionRepo.list_by_month",
                  MagicMock(return_value=[])),
            patch("services.analyst_service.RecurringRepo.list_active",
                  MagicMock(return_value=[])),
            patch("services.analyst_service.BudgetRepo.get_budget_status",
                  MagicMock(return_value=[])),
            patch("services.analyst_service.TransactionRepo.list_all",
                  MagicMock(return_value=txs_all)),
            patch("services.analyst_service.answer_financial_question",
                  new=AsyncMock(side_effect=fake_answer)),
        ):
            await AnalystService.answer(USER_ID, USER_NAME, "test")

        active = captured["installments_active"]
        assert len(active) == 1
        assert active[0]["description"] == "Con cuotas restantes"

    @pytest.mark.asyncio
    async def test_recurring_serialized_correctly(self):
        from services.analyst_service import AnalystService

        rec = _make_recurring(description="Spotify", amount=500.0)
        captured = {}

        async def fake_answer(question, context):
            captured.update(context)
            return "ok"

        with (
            patch("services.analyst_service.TransactionRepo.get_monthly_totals",
                  MagicMock(return_value=[])),
            patch("services.analyst_service.TransactionRepo.list_by_month",
                  MagicMock(return_value=[])),
            patch("services.analyst_service.RecurringRepo.list_active",
                  MagicMock(return_value=[rec])),
            patch("services.analyst_service.BudgetRepo.get_budget_status",
                  MagicMock(return_value=[])),
            patch("services.analyst_service.TransactionRepo.list_all",
                  MagicMock(return_value=[])),
            patch("services.analyst_service.answer_financial_question",
                  new=AsyncMock(side_effect=fake_answer)),
        ):
            await AnalystService.answer(USER_ID, USER_NAME, "test")

        recurring = captured["recurring_subscriptions"]
        assert len(recurring) == 1
        assert recurring[0]["description"] == "Spotify"
        assert recurring[0]["amount"] == 500.0
        assert recurring[0]["frequency"] == "monthly"

    @pytest.mark.asyncio
    async def test_monthly_totals_passed_through(self):
        from services.analyst_service import AnalystService

        totals = [
            {"month": "2026-01", "income": 50000.0, "expense": 30000.0, "balance": 20000.0},
            {"month": "2026-02", "income": 50000.0, "expense": 35000.0, "balance": 15000.0},
        ]
        captured = {}

        async def fake_answer(question, context):
            captured.update(context)
            return "ok"

        with (
            patch("services.analyst_service.TransactionRepo.get_monthly_totals",
                  MagicMock(return_value=totals)),
            patch("services.analyst_service.TransactionRepo.list_by_month",
                  MagicMock(return_value=[])),
            patch("services.analyst_service.RecurringRepo.list_active",
                  MagicMock(return_value=[])),
            patch("services.analyst_service.BudgetRepo.get_budget_status",
                  MagicMock(return_value=[])),
            patch("services.analyst_service.TransactionRepo.list_all",
                  MagicMock(return_value=[])),
            patch("services.analyst_service.answer_financial_question",
                  new=AsyncMock(side_effect=fake_answer)),
        ):
            await AnalystService.answer(USER_ID, USER_NAME, "test")

        assert len(captured["monthly_totals_last_6_months"]) == 2
        assert captured["monthly_totals_last_6_months"][0]["month"] == "2026-01"
