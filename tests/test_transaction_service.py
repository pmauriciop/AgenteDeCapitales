"""
tests/test_transaction_service.py
───────────────────────────────────
Tests unitarios para services/transaction_service.py
Usa mocks para no depender de Supabase.
"""

import pytest
from datetime import date
from unittest.mock import MagicMock, patch

from database.models import Transaction
from services.transaction_service import TransactionService


def _make_tx(**kwargs) -> Transaction:
    defaults = dict(
        id="tx-1",
        user_id="user-uuid",
        amount=1000.0,
        category="alimentación",
        description="supermercado",
        type="expense",
        date=date(2026, 2, 15),
    )
    defaults.update(kwargs)
    return Transaction(**defaults)


class TestTransactionServiceFormat:
    def test_format_summary_message_positive_balance(self):
        summary = {
            "month": "2026-02",
            "income": 50000.0,
            "expense": 30000.0,
            "balance": 20000.0,
            "breakdown": {"alimentación": 10000.0, "transporte": 5000.0},
        }
        msg = TransactionService.format_summary_message(summary)
        assert "2026-02" in msg
        assert "50,000.00" in msg
        assert "30,000.00" in msg
        assert "+$20,000.00" in msg
        assert "Alimentación" in msg

    def test_format_summary_message_negative_balance(self):
        summary = {
            "month": "2026-02",
            "income": 10000.0,
            "expense": 15000.0,
            "balance": -5000.0,
            "breakdown": {},
        }
        msg = TransactionService.format_summary_message(summary)
        assert "📉" in msg
        assert "-$5,000.00" in msg

    def test_format_transaction_list_empty(self):
        msg = TransactionService.format_transaction_list([])
        assert "No hay transacciones" in msg

    def test_format_transaction_list_with_items(self):
        txs = [_make_tx(type="expense"), _make_tx(id="tx-2", type="income", amount=5000.0)]
        msg = TransactionService.format_transaction_list(txs)
        assert "💸" in msg
        assert "💰" in msg
        assert "1,000.00" in msg
        assert "5,000.00" in msg


class TestTransactionServiceLogic:
    @patch("services.transaction_service.TransactionRepo")
    def test_add_from_parsed(self, mock_repo):
        mock_tx = _make_tx()
        mock_repo.create.return_value = mock_tx
        mock_repo.find_duplicate.return_value = None  # no hay duplicado

        parsed = {
            "amount": 1000.0,
            "type": "expense",
            "category": "alimentación",
            "description": "supermercado",
            "date": "2026-02-15",
        }
        tx, created = TransactionService.add_from_parsed("user-uuid", parsed)
        assert created is True
        assert tx.amount == 1000.0
        mock_repo.create.assert_called_once()

    @patch("services.transaction_service.TransactionRepo")
    def test_add_from_parsed_duplicate(self, mock_repo):
        """Si ya existe, retorna el existente con created=False."""
        existing = _make_tx()
        mock_repo.find_duplicate.return_value = existing

        parsed = {
            "amount": 1000.0,
            "type": "expense",
            "category": "alimentación",
            "description": "supermercado",
            "date": "2026-02-15",
        }
        tx, created = TransactionService.add_from_parsed("user-uuid", parsed)
        assert created is False
        assert tx.amount == 1000.0
        mock_repo.create.assert_not_called()

    @patch("services.transaction_service.TransactionRepo")
    def test_get_monthly_summary(self, mock_repo):
        mock_repo.get_summary.return_value = {
            "month": "2026-02",
            "income": 50000.0,
            "expense": 30000.0,
            "balance": 20000.0,
            "transactions": [
                _make_tx(category="alimentación", amount=10000.0),
                _make_tx(category="transporte", amount=5000.0),
            ],
        }

        result = TransactionService.get_monthly_summary("user-uuid", "2026-02")
        assert result["balance"] == 20000.0
        assert "alimentación" in result["breakdown"]
        assert "transactions" not in result
