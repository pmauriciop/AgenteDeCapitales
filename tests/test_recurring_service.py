"""
tests/test_recurring_service.py
────────────────────────────────
Tests unitarios para services/recurring_service.py
"""

import pytest
from datetime import date
from unittest.mock import MagicMock, patch

from database.models import RecurringTransaction
from services.recurring_service import RecurringService


def _make_rec(**kwargs) -> RecurringTransaction:
    defaults = dict(
        id="rec-1",
        user_id="user-uuid",
        amount=800.0,
        category="servicios",
        description="Netflix",
        frequency="monthly",
        next_date=date(2026, 2, 1),
        active=True,
    )
    defaults.update(kwargs)
    return RecurringTransaction(**defaults)


class TestCalculateNextDate:
    def test_daily(self):
        d = date(2026, 2, 21)
        result = RecurringService._calculate_next_date(d, "daily")
        assert result == date(2026, 2, 22)

    def test_weekly(self):
        d = date(2026, 2, 21)
        result = RecurringService._calculate_next_date(d, "weekly")
        assert result == date(2026, 2, 28)

    def test_monthly(self):
        d = date(2026, 2, 21)
        result = RecurringService._calculate_next_date(d, "monthly")
        assert result == date(2026, 3, 21)

    def test_yearly(self):
        d = date(2026, 2, 21)
        result = RecurringService._calculate_next_date(d, "yearly")
        assert result == date(2027, 2, 21)

    def test_monthly_end_of_month(self):
        """Enero 31 + 1 mes = Febrero 28 (sin overflow)."""
        d = date(2026, 1, 31)
        result = RecurringService._calculate_next_date(d, "monthly")
        assert result == date(2026, 2, 28)


class TestFormatRecurringList:
    def test_empty_list(self):
        msg = RecurringService.format_recurring_list([])
        assert "No tenés" in msg

    def test_with_items(self):
        recs = [
            _make_rec(description="Netflix", amount=800.0, frequency="monthly"),
            _make_rec(id="rec-2", description="Alquiler", amount=50000.0, frequency="monthly"),
        ]
        msg = RecurringService.format_recurring_list(recs)
        assert "Netflix" in msg
        assert "Alquiler" in msg
        assert "800.00" in msg
        assert "50,000.00" in msg
        assert "Mensual" in msg


class TestProcessDue:
    @patch("services.recurring_service.RecurringRepo")
    @patch("services.recurring_service.TransactionRepo")
    def test_processes_due_transactions(self, mock_tx_repo, mock_rec_repo):
        """Transacciones cuya next_date <= hoy deben procesarse."""
        rec = _make_rec(next_date=date(2026, 2, 15))  # ya pasó
        mock_rec_repo.list_active.return_value = [rec]

        from database.models import Transaction
        saved_tx = Transaction(
            id="tx-auto-1",
            user_id="user-uuid",
            amount=800.0,
            category="servicios",
            description="[Auto] Netflix",
            type="expense",
            date=date(2026, 2, 15),
        )
        mock_tx_repo.create.return_value = saved_tx

        result = RecurringService.process_due("user-uuid")

        assert len(result) == 1
        assert result[0].description == "[Auto] Netflix"
        mock_tx_repo.create.assert_called_once()
        mock_rec_repo.update_next_date.assert_called_once()

    @patch("services.recurring_service.RecurringRepo")
    @patch("services.recurring_service.TransactionRepo")
    def test_skips_future_transactions(self, mock_tx_repo, mock_rec_repo):
        """Transacciones futuras no deben procesarse."""
        rec = _make_rec(next_date=date(2026, 12, 31))  # claramente en el futuro
        mock_rec_repo.list_active.return_value = [rec]

        result = RecurringService.process_due("user-uuid")

        assert len(result) == 0
        mock_tx_repo.create.assert_not_called()
