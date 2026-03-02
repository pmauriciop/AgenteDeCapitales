"""
tests/test_repositories.py
───────────────────────────
Tests para database/repositories.py usando mocks de Supabase.

Estrategia: parchamos `database.repositories.get_client` para devolver
un cliente fake que no toca la red. Cada método del fake implementa
exactamente la cadena de llamadas que usa el repo real
(.table().select()...execute()).
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, call, patch

import pytest

from database.encryption import encrypt
from database.models import (
    Budget,
    RecurringTransaction,
    Transaction,
    User,
)

# ─────────────────────────────────────────────
#  Helpers de fixtures
# ─────────────────────────────────────────────

USER_ID = "user-uuid-1234"
NOW_DATE = date(2026, 3, 2)


def _make_tx_row(
    *,
    tx_id="tx-uuid-1",
    amount=1500.0,
    tx_type="expense",
    category="alimentacion",
    description="Super",
    tx_date="2026-03-02",
    installment_current=None,
    installment_total=None,
    installments_remaining=None,
) -> dict:
    """Fila de Supabase con descripción cifrada."""
    return {
        "id": tx_id,
        "user_id": USER_ID,
        "amount": amount,
        "type": tx_type,
        "category": category,
        "description": encrypt(description),
        "date": tx_date,
        "created_at": None,
        "installment_current": installment_current,
        "installment_total": installment_total,
        "installments_remaining": installments_remaining,
    }


def _make_budget_row(
    *,
    budget_id="budget-uuid-1",
    category="alimentacion",
    limit_amount=5000.0,
    month="2026-03",
) -> dict:
    return {
        "id": budget_id,
        "user_id": USER_ID,
        "category": category,
        "limit_amount": limit_amount,
        "month": month,
        "created_at": None,
    }


def _make_recurring_row(
    *,
    rec_id="rec-uuid-1",
    amount=1200.0,
    category="servicios",
    description="Netflix",
    frequency="monthly",
    next_date="2026-03-15",
    active=True,
) -> dict:
    return {
        "id": rec_id,
        "user_id": USER_ID,
        "amount": amount,
        "category": category,
        "description": encrypt(description),
        "frequency": frequency,
        "next_date": next_date,
        "active": active,
    }


def _chain_mock(final_data) -> MagicMock:
    """
    Construye un mock de cliente Supabase que soporta la cadena:
      .table().select/insert/update/delete().[eq/gte/lt/order]*().execute()

    Para `maybe_single()` (usado por UserRepo.get_by_telegram_id), la cadena es:
      .table().select().eq().maybe_single().execute()  → result.data = dict | None
    """
    # Resultado para execute() normal (list-based, INSERT/UPDATE/DELETE/SELECT)
    execute_result = MagicMock()
    execute_result.data = final_data

    # Resultado para maybe_single().execute() (dict-based, o None)
    maybe_execute_result = MagicMock()
    # Si final_data es un dict (o None), úsalo; si es lista, toma el primer elemento
    if isinstance(final_data, list):
        maybe_execute_result.data = final_data[0] if final_data else None
    else:
        maybe_execute_result.data = final_data

    maybe_node = MagicMock()
    maybe_node.execute.return_value = maybe_execute_result

    # Nodo terminal: cualquier llamada devuelve execute_result
    terminal = MagicMock()
    terminal.execute.return_value = execute_result
    terminal.eq.return_value = terminal
    terminal.gte.return_value = terminal
    terminal.lt.return_value = terminal
    terminal.order.return_value = terminal
    terminal.maybe_single.return_value = maybe_node

    table_mock = MagicMock()
    table_mock.select.return_value = terminal
    table_mock.insert.return_value = terminal
    table_mock.update.return_value = terminal
    table_mock.delete.return_value = terminal

    client_mock = MagicMock()
    client_mock.table.return_value = table_mock
    return client_mock


# ─────────────────────────────────────────────
#  UserRepo
# ─────────────────────────────────────────────

class TestUserRepo:
    def test_get_by_telegram_id_found(self):
        from database.repositories import UserRepo

        row = {"id": "u1", "telegram_id": 999, "name": "Juan", "created_at": None}
        client = _chain_mock(row)  # maybe_single devuelve directo el resultado

        with patch("database.repositories.get_client", return_value=client):
            user = UserRepo.get_by_telegram_id(999)

        assert user is not None
        assert user.telegram_id == 999
        assert user.name == "Juan"

    def test_get_by_telegram_id_not_found(self):
        from database.repositories import UserRepo

        client = _chain_mock(None)
        with patch("database.repositories.get_client", return_value=client):
            user = UserRepo.get_by_telegram_id(0)

        assert user is None

    def test_create_user(self):
        from database.repositories import UserRepo

        row = {"id": "u2", "telegram_id": 42, "name": "Maria", "created_at": None}
        client = _chain_mock([row])

        with patch("database.repositories.get_client", return_value=client):
            user = UserRepo.create(telegram_id=42, name="Maria")

        assert user.id == "u2"
        assert user.name == "Maria"

    def test_get_or_create_existing(self):
        from database.repositories import UserRepo

        row = {"id": "u3", "telegram_id": 77, "name": "Pedro", "created_at": None}
        client = _chain_mock(row)

        with patch("database.repositories.get_client", return_value=client):
            user, created = UserRepo.get_or_create(telegram_id=77, name="Pedro")

        assert created is False
        assert user.telegram_id == 77

    def test_get_or_create_new(self):
        from database.repositories import UserRepo

        created_row = {"id": "u4", "telegram_id": 88, "name": "Ana", "created_at": None}

        call_count = 0

        def fake_get_client():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Primera llamada: get_by_telegram_id → not found
                return _chain_mock(None)
            # Segunda llamada: create
            return _chain_mock([created_row])

        with patch("database.repositories.get_client", side_effect=fake_get_client):
            user, created = UserRepo.get_or_create(telegram_id=88, name="Ana")

        assert created is True
        assert user.name == "Ana"


# ─────────────────────────────────────────────
#  TransactionRepo
# ─────────────────────────────────────────────

class TestTransactionRepoCreate:
    def test_create_encrypts_description(self):
        from database.encryption import decrypt
        from database.repositories import TransactionRepo

        row = _make_tx_row(description="Almuerzo")
        client = _chain_mock([row])

        tx = Transaction(
            user_id=USER_ID, amount=500.0, category="alimentacion",
            description="Almuerzo", type="expense", date=NOW_DATE,
        )

        with patch("database.repositories.get_client", return_value=client):
            result = TransactionRepo.create(tx)

        assert result.description == "Almuerzo"  # desencriptada al volver
        assert result.amount == 1500.0           # la que devuelve el mock

    def test_create_returns_transaction_object(self):
        from database.repositories import TransactionRepo

        row = _make_tx_row()
        client = _chain_mock([row])

        tx = Transaction(
            user_id=USER_ID, amount=1500.0, category="alimentacion",
            description="Super", type="expense", date=NOW_DATE,
        )

        with patch("database.repositories.get_client", return_value=client):
            result = TransactionRepo.create(tx)

        assert isinstance(result, Transaction)
        assert result.type == "expense"
        assert result.category == "alimentacion"


class TestTransactionRepoFindDuplicate:
    def test_finds_existing_duplicate(self):
        from database.repositories import TransactionRepo

        row = _make_tx_row(description="Super", amount=1500.0, tx_type="expense")
        client = _chain_mock([row])

        with patch("database.repositories.get_client", return_value=client):
            result = TransactionRepo.find_duplicate(
                user_id=USER_ID,
                tx_date=NOW_DATE,
                amount=1500.0,
                description="Super",
                tx_type="expense",
            )

        assert result is not None
        assert result.description == "Super"

    def test_no_match_different_description(self):
        from database.repositories import TransactionRepo

        row = _make_tx_row(description="Super", amount=1500.0)
        client = _chain_mock([row])

        with patch("database.repositories.get_client", return_value=client):
            result = TransactionRepo.find_duplicate(
                user_id=USER_ID,
                tx_date=NOW_DATE,
                amount=1500.0,
                description="Otra cosa",
                tx_type="expense",
            )

        assert result is None

    def test_no_match_empty_results(self):
        from database.repositories import TransactionRepo

        client = _chain_mock([])

        with patch("database.repositories.get_client", return_value=client):
            result = TransactionRepo.find_duplicate(
                user_id=USER_ID,
                tx_date=NOW_DATE,
                amount=999.0,
                description="X",
                tx_type="expense",
            )

        assert result is None


class TestTransactionRepoListByMonth:
    def test_returns_transactions_for_month(self):
        from database.repositories import TransactionRepo

        rows = [
            _make_tx_row(tx_id="t1", description="Super", tx_date="2026-03-01"),
            _make_tx_row(tx_id="t2", description="Nafta", tx_date="2026-03-15"),
        ]
        client = _chain_mock(rows)

        with patch("database.repositories.get_client", return_value=client):
            txs = TransactionRepo.list_by_month(USER_ID, "2026-03")

        assert len(txs) == 2
        assert all(isinstance(t, Transaction) for t in txs)
        assert txs[0].description == "Super"
        assert txs[1].description == "Nafta"

    def test_returns_empty_for_no_data(self):
        from database.repositories import TransactionRepo

        client = _chain_mock([])

        with patch("database.repositories.get_client", return_value=client):
            txs = TransactionRepo.list_by_month(USER_ID, "2026-01")

        assert txs == []


class TestTransactionRepoGetSummary:
    def test_summary_totals(self):
        from database.repositories import TransactionRepo

        rows = [
            _make_tx_row(tx_id="t1", amount=3000.0, tx_type="income",
                         category="salario", description="Sueldo"),
            _make_tx_row(tx_id="t2", amount=1000.0, tx_type="expense",
                         category="alimentacion", description="Super"),
            _make_tx_row(tx_id="t3", amount=500.0, tx_type="expense",
                         category="transporte", description="Nafta"),
        ]
        client = _chain_mock(rows)

        with patch("database.repositories.get_client", return_value=client):
            summary = TransactionRepo.get_summary(USER_ID, "2026-03")

        assert summary["income"] == pytest.approx(3000.0)
        assert summary["expense"] == pytest.approx(1500.0)
        assert summary["balance"] == pytest.approx(1500.0)
        assert len(summary["transactions"]) == 3

    def test_summary_all_expenses_negative_balance(self):
        from database.repositories import TransactionRepo

        rows = [
            _make_tx_row(tx_id="t1", amount=2000.0, tx_type="expense",
                         description="Alquiler"),
        ]
        client = _chain_mock(rows)

        with patch("database.repositories.get_client", return_value=client):
            summary = TransactionRepo.get_summary(USER_ID, "2026-03")

        assert summary["income"] == 0.0
        assert summary["balance"] == pytest.approx(-2000.0)


class TestTransactionRepoGetMonthlyTotals:
    def test_groups_by_month(self):
        from database.repositories import TransactionRepo

        rows = [
            _make_tx_row(tx_id="t1", amount=1000.0, tx_type="expense",
                         description="A", tx_date="2026-01-10"),
            _make_tx_row(tx_id="t2", amount=2000.0, tx_type="income",
                         category="salario", description="B", tx_date="2026-01-15"),
            _make_tx_row(tx_id="t3", amount=500.0, tx_type="expense",
                         description="C", tx_date="2026-02-05"),
        ]
        client = _chain_mock(rows)

        with patch("database.repositories.get_client", return_value=client):
            totals = TransactionRepo.get_monthly_totals(USER_ID, n_months=6)

        months = {t["month"]: t for t in totals}
        assert "2026-01" in months
        assert months["2026-01"]["income"] == pytest.approx(2000.0)
        assert months["2026-01"]["expense"] == pytest.approx(1000.0)
        assert months["2026-01"]["balance"] == pytest.approx(1000.0)
        assert months["2026-02"]["expense"] == pytest.approx(500.0)

    def test_returns_sorted(self):
        from database.repositories import TransactionRepo

        rows = [
            _make_tx_row(tx_id="t1", description="A", tx_date="2026-02-01"),
            _make_tx_row(tx_id="t2", description="B", tx_date="2026-01-01"),
        ]
        client = _chain_mock(rows)

        with patch("database.repositories.get_client", return_value=client):
            totals = TransactionRepo.get_monthly_totals(USER_ID, n_months=6)

        months = [t["month"] for t in totals]
        assert months == sorted(months)


# ─────────────────────────────────────────────
#  BudgetRepo
# ─────────────────────────────────────────────

class TestBudgetRepo:
    def test_list_by_month_returns_budgets(self):
        from database.repositories import BudgetRepo

        rows = [_make_budget_row(category="alimentacion", limit_amount=5000.0)]
        client = _chain_mock(rows)

        with patch("database.repositories.get_client", return_value=client):
            budgets = BudgetRepo.list_by_month(USER_ID, "2026-03")

        assert len(budgets) == 1
        assert isinstance(budgets[0], Budget)
        assert budgets[0].category == "alimentacion"
        assert budgets[0].limit_amount == 5000.0

    def test_get_budget_status_calculates_percentage(self):
        from database.repositories import BudgetRepo, TransactionRepo

        budget_rows = [_make_budget_row(limit_amount=4000.0)]
        tx_rows = [
            _make_tx_row(amount=1000.0, tx_type="expense", description="A"),
            _make_tx_row(amount=1000.0, tx_type="expense", description="B"),
        ]

        call_count = 0

        def fake_get_client():
            nonlocal call_count
            call_count += 1
            # 1ª llamada: list_by_month (budgets)
            # 2ª llamada: list_by_category (transactions)
            if call_count == 1:
                return _chain_mock(budget_rows)
            return _chain_mock(tx_rows)

        with patch("database.repositories.get_client", side_effect=fake_get_client):
            status = BudgetRepo.get_budget_status(USER_ID, "2026-03")

        assert len(status) == 1
        s = status[0]
        assert s["limit"] == 4000.0
        assert s["spent"] == pytest.approx(2000.0)
        assert s["remaining"] == pytest.approx(2000.0)
        assert s["percentage"] == pytest.approx(50.0)

    def test_get_budget_status_empty(self):
        from database.repositories import BudgetRepo

        client = _chain_mock([])

        with patch("database.repositories.get_client", return_value=client):
            status = BudgetRepo.get_budget_status(USER_ID, "2026-03")

        assert status == []


# ─────────────────────────────────────────────
#  RecurringRepo
# ─────────────────────────────────────────────

class TestRecurringRepo:
    def test_list_active_decrypts_description(self):
        from database.repositories import RecurringRepo

        rows = [_make_recurring_row(description="Netflix")]
        client = _chain_mock(rows)

        with patch("database.repositories.get_client", return_value=client):
            recs = RecurringRepo.list_active(USER_ID)

        assert len(recs) == 1
        assert isinstance(recs[0], RecurringTransaction)
        assert recs[0].description == "Netflix"

    def test_deactivate_returns_true(self):
        from database.repositories import RecurringRepo

        client = _chain_mock([{"id": "rec-1"}])

        with patch("database.repositories.get_client", return_value=client):
            result = RecurringRepo.deactivate("rec-1")

        assert result is True

    def test_deactivate_not_found_returns_false(self):
        from database.repositories import RecurringRepo

        client = _chain_mock([])

        with patch("database.repositories.get_client", return_value=client):
            result = RecurringRepo.deactivate("nonexistent")

        assert result is False

    def test_create_encrypts_description(self):
        from database.encryption import decrypt
        from database.repositories import RecurringRepo

        row = _make_recurring_row(description="Spotify")
        client = _chain_mock([row])

        rec = RecurringTransaction(
            user_id=USER_ID, amount=500.0, category="entretenimiento",
            description="Spotify", frequency="monthly",
            next_date=date(2026, 3, 15),
        )

        with patch("database.repositories.get_client", return_value=client):
            result = RecurringRepo.create(rec)

        assert result.description == "Spotify"  # desencriptada al volver
