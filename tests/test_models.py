"""
tests/test_models.py
─────────────────────
Tests unitarios para database/models.py
"""

from datetime import date, datetime

import pytest

from database.models import Budget, RecurringTransaction, Transaction, User


class TestUser:
    def test_from_dict(self):
        data = {"id": "uuid-1", "telegram_id": "123456", "name": "Juan", "created_at": None}
        user = User.from_dict(data)
        assert user.telegram_id == 123456
        assert user.name == "Juan"
        assert user.id == "uuid-1"

    def test_to_dict(self):
        user = User(telegram_id=999, name="María")
        d = user.to_dict()
        assert d["telegram_id"] == 999
        assert d["name"] == "María"
        assert "id" not in d  # no se persiste el id en insert


class TestTransaction:
    def test_from_dict(self):
        data = {
            "id": "tx-1",
            "user_id": "user-uuid",
            "amount": "1500.50",
            "category": "alimentación",
            "description": "supermercado",
            "type": "expense",
            "date": "2026-02-15",
        }
        tx = Transaction.from_dict(data)
        assert tx.amount == 1500.50
        assert tx.date == date(2026, 2, 15)
        assert tx.type == "expense"

    def test_to_dict(self):
        tx = Transaction(
            user_id="u1",
            amount=500.0,
            category="transporte",
            description="colectivo",
            type="expense",
            date=date(2026, 2, 21),
        )
        d = tx.to_dict()
        assert d["date"] == "2026-02-21"
        assert d["amount"] == 500.0
        assert "id" not in d


class TestBudget:
    def test_from_dict(self):
        data = {
            "id": "b-1",
            "user_id": "u-1",
            "category": "alimentación",
            "limit_amount": "10000",
            "month": "2026-02",
        }
        budget = Budget.from_dict(data)
        assert budget.limit_amount == 10000.0
        assert budget.month == "2026-02"

    def test_to_dict(self):
        budget = Budget(user_id="u1", category="hogar", limit_amount=5000.0, month="2026-02")
        d = budget.to_dict()
        assert d["limit_amount"] == 5000.0
        assert "id" not in d


class TestRecurringTransaction:
    def test_from_dict(self):
        data = {
            "id": "r-1",
            "user_id": "u-1",
            "amount": "800",
            "category": "servicios",
            "description": "Netflix",
            "frequency": "monthly",
            "next_date": "2026-03-01",
            "active": True,
        }
        rec = RecurringTransaction.from_dict(data)
        assert rec.amount == 800.0
        assert rec.frequency == "monthly"
        assert rec.next_date == date(2026, 3, 1)

    def test_to_dict(self):
        rec = RecurringTransaction(
            user_id="u1",
            amount=800.0,
            category="servicios",
            description="Netflix",
            frequency="monthly",
            next_date=date(2026, 3, 1),
        )
        d = rec.to_dict()
        assert d["next_date"] == "2026-03-01"
        assert d["active"] is True
