"""
tests/test_dashboard_api.py
────────────────────────────
Tests para los endpoints de dashboard_api.py usando TestClient de FastAPI.

Mockeamos `database.client.get_client` para no tocar Supabase.
La encriptación usa la clave de test inyectada en conftest.py.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from database.encryption import encrypt

# ─────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────

def _enc(text: str) -> str:
    """Cifra un texto con la clave de test (inyectada por conftest)."""
    return encrypt(text)


def _make_tx_row(
    *,
    tx_id="t1",
    amount=1500.0,
    tx_type="expense",
    category="alimentacion",
    description="Super",
    tx_date="2026-03-02",
    installment_current=None,
    installment_total=None,
    installments_remaining=None,
) -> dict:
    return {
        "id": tx_id,
        "user_id": "user-uuid",
        "amount": str(amount),
        "type": tx_type,
        "category": category,
        "description": _enc(description),
        "date": tx_date,
        "created_at": None,
        "installment_current": installment_current,
        "installment_total": installment_total,
        "installments_remaining": installments_remaining,
    }


def _make_supabase_client(rows: list[dict]) -> MagicMock:
    """Supabase fake que devuelve `rows` para cualquier .table().select()...execute()."""
    execute_result = MagicMock()
    execute_result.data = rows

    terminal = MagicMock()
    terminal.execute.return_value = execute_result
    terminal.eq.return_value = terminal
    terminal.order.return_value = terminal

    table_mock = MagicMock()
    table_mock.select.return_value = terminal

    client = MagicMock()
    client.table.return_value = table_mock
    return client


@pytest.fixture
def client():
    """TestClient de FastAPI con Supabase mockeado."""
    from dashboard_api import app
    return TestClient(app)


# ─────────────────────────────────────────────
#  GET /api/transactions
# ─────────────────────────────────────────────

class TestGetTransactions:
    def test_returns_200(self, client):
        supabase = _make_supabase_client([])
        with patch("dashboard_api.get_client", return_value=supabase):
            resp = client.get("/api/transactions")
        assert resp.status_code == 200

    def test_returns_list(self, client):
        supabase = _make_supabase_client([])
        with patch("dashboard_api.get_client", return_value=supabase):
            resp = client.get("/api/transactions")
        assert isinstance(resp.json(), list)

    def test_decrypts_description(self, client):
        rows = [_make_tx_row(description="Almuerzo en Subway")]
        supabase = _make_supabase_client(rows)

        with patch("dashboard_api.get_client", return_value=supabase):
            resp = client.get("/api/transactions")

        data = resp.json()
        assert len(data) == 1
        assert data[0]["description"] == "Almuerzo en Subway"

    def test_returns_correct_fields(self, client):
        rows = [_make_tx_row(
            tx_id="abc-123",
            amount=2500.0,
            tx_type="expense",
            category="transporte",
            description="Nafta",
            tx_date="2026-03-01",
        )]
        supabase = _make_supabase_client(rows)

        with patch("dashboard_api.get_client", return_value=supabase):
            resp = client.get("/api/transactions")

        tx = resp.json()[0]
        assert tx["id"] == "abc-123"
        assert tx["amount"] == pytest.approx(2500.0)
        assert tx["type"] == "expense"
        assert tx["category"] == "transporte"
        assert tx["date"] == "2026-03-01"

    def test_installment_fields_present(self, client):
        rows = [_make_tx_row(
            description="Lacoste",
            installment_current=3,
            installment_total=6,
            installments_remaining=3,
        )]
        supabase = _make_supabase_client(rows)

        with patch("dashboard_api.get_client", return_value=supabase):
            resp = client.get("/api/transactions")

        tx = resp.json()[0]
        assert tx["installment_current"] == 3
        assert tx["installment_total"] == 6
        assert tx["installments_remaining"] == 3

    def test_multiple_transactions(self, client):
        rows = [
            _make_tx_row(tx_id="t1", description="A"),
            _make_tx_row(tx_id="t2", description="B"),
            _make_tx_row(tx_id="t3", description="C"),
        ]
        supabase = _make_supabase_client(rows)

        with patch("dashboard_api.get_client", return_value=supabase):
            resp = client.get("/api/transactions")

        assert len(resp.json()) == 3


# ─────────────────────────────────────────────
#  GET /api/summary
# ─────────────────────────────────────────────

class TestGetSummary:
    def test_returns_200(self, client):
        supabase = _make_supabase_client([])
        with patch("dashboard_api.get_client", return_value=supabase):
            resp = client.get("/api/summary")
        assert resp.status_code == 200

    def test_summary_keys_present(self, client):
        supabase = _make_supabase_client([])
        with patch("dashboard_api.get_client", return_value=supabase):
            resp = client.get("/api/summary")

        data = resp.json()
        for key in ("total_expense", "total_income", "balance",
                    "by_category", "monthly", "installments_active"):
            assert key in data, f"Falta clave: {key}"

    def test_totals_calculated_correctly(self, client):
        rows = [
            _make_tx_row(tx_id="t1", amount=5000.0, tx_type="income",
                         category="salario", description="Sueldo",
                         tx_date="2026-03-01"),
            _make_tx_row(tx_id="t2", amount=1000.0, tx_type="expense",
                         category="alimentacion", description="Super",
                         tx_date="2026-03-02"),
            _make_tx_row(tx_id="t3", amount=500.0, tx_type="expense",
                         category="transporte", description="Nafta",
                         tx_date="2026-03-03"),
        ]
        supabase = _make_supabase_client(rows)

        with patch("dashboard_api.get_client", return_value=supabase):
            resp = client.get("/api/summary")

        data = resp.json()
        assert data["total_income"] == pytest.approx(5000.0)
        assert data["total_expense"] == pytest.approx(1500.0)
        assert data["balance"] == pytest.approx(3500.0)

    def test_balance_negative_when_overspent(self, client):
        rows = [
            _make_tx_row(tx_id="t1", amount=3000.0, tx_type="expense",
                         description="Alquiler"),
            _make_tx_row(tx_id="t2", amount=1000.0, tx_type="income",
                         category="salario", description="Pago parcial"),
        ]
        supabase = _make_supabase_client(rows)

        with patch("dashboard_api.get_client", return_value=supabase):
            resp = client.get("/api/summary")

        data = resp.json()
        assert data["balance"] < 0

    def test_by_category_only_expenses(self, client):
        rows = [
            _make_tx_row(tx_id="t1", amount=2000.0, tx_type="expense",
                         category="alimentacion", description="Super"),
            _make_tx_row(tx_id="t2", amount=500.0, tx_type="expense",
                         category="transporte", description="Nafta"),
            _make_tx_row(tx_id="t3", amount=5000.0, tx_type="income",
                         category="salario", description="Sueldo"),
        ]
        supabase = _make_supabase_client(rows)

        with patch("dashboard_api.get_client", return_value=supabase):
            resp = client.get("/api/summary")

        cats = {item["category"]: item["amount"] for item in resp.json()["by_category"]}
        assert "alimentacion" in cats
        assert "transporte" in cats
        assert "salario" not in cats  # ingresos no deben aparecer en by_category

    def test_by_category_sorted_descending(self, client):
        rows = [
            _make_tx_row(tx_id="t1", amount=500.0, tx_type="expense",
                         category="transporte", description="Nafta"),
            _make_tx_row(tx_id="t2", amount=2000.0, tx_type="expense",
                         category="alimentacion", description="Super"),
        ]
        supabase = _make_supabase_client(rows)

        with patch("dashboard_api.get_client", return_value=supabase):
            resp = client.get("/api/summary")

        by_cat = resp.json()["by_category"]
        amounts = [item["amount"] for item in by_cat]
        assert amounts == sorted(amounts, reverse=True)

    def test_monthly_grouping(self, client):
        rows = [
            _make_tx_row(tx_id="t1", amount=1000.0, tx_type="expense",
                         description="A", tx_date="2026-01-10"),
            _make_tx_row(tx_id="t2", amount=2000.0, tx_type="income",
                         category="salario", description="B", tx_date="2026-01-15"),
            _make_tx_row(tx_id="t3", amount=500.0, tx_type="expense",
                         description="C", tx_date="2026-02-05"),
        ]
        supabase = _make_supabase_client(rows)

        with patch("dashboard_api.get_client", return_value=supabase):
            resp = client.get("/api/summary")

        monthly = {m["month"]: m for m in resp.json()["monthly"]}
        assert "2026-01" in monthly
        assert "2026-02" in monthly
        assert monthly["2026-01"]["income"] == pytest.approx(2000.0)
        assert monthly["2026-01"]["expense"] == pytest.approx(1000.0)
        assert monthly["2026-02"]["expense"] == pytest.approx(500.0)

    def test_monthly_sorted_chronologically(self, client):
        rows = [
            _make_tx_row(tx_id="t1", description="A", tx_date="2026-03-01"),
            _make_tx_row(tx_id="t2", description="B", tx_date="2026-01-01"),
            _make_tx_row(tx_id="t3", description="C", tx_date="2026-02-01"),
        ]
        supabase = _make_supabase_client(rows)

        with patch("dashboard_api.get_client", return_value=supabase):
            resp = client.get("/api/summary")

        months = [m["month"] for m in resp.json()["monthly"]]
        assert months == sorted(months)

    def test_installments_active_in_summary(self, client):
        rows = [
            _make_tx_row(
                tx_id="t1", description="Notebook cuotas",
                installment_current=2, installment_total=12,
                installments_remaining=10,
            ),
            _make_tx_row(
                tx_id="t2", description="Sin cuotas",
            ),
        ]
        supabase = _make_supabase_client(rows)

        with patch("dashboard_api.get_client", return_value=supabase):
            resp = client.get("/api/summary")

        active = resp.json()["installments_active"]
        assert len(active) == 1
        assert active[0]["description"] == "Notebook cuotas"
        assert active[0]["installments_remaining"] == 10

    def test_empty_db_returns_zeros(self, client):
        supabase = _make_supabase_client([])

        with patch("dashboard_api.get_client", return_value=supabase):
            resp = client.get("/api/summary")

        data = resp.json()
        assert data["total_income"] == 0.0
        assert data["total_expense"] == 0.0
        assert data["balance"] == 0.0
        assert data["by_category"] == []
        assert data["monthly"] == []
        assert data["installments_active"] == []
