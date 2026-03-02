"""
tests/test_budget_service.py
─────────────────────────────
Tests unitarios para services/budget_service.py
"""

from unittest.mock import patch

import pytest

from services.budget_service import BudgetService


class TestBudgetServiceFormat:
    def test_progress_bar_empty(self):
        bar = BudgetService._progress_bar(0)
        assert bar == "░" * 10

    def test_progress_bar_full(self):
        bar = BudgetService._progress_bar(100)
        assert bar == "█" * 10

    def test_progress_bar_half(self):
        bar = BudgetService._progress_bar(50)
        assert bar == "█████░░░░░"

    def test_progress_bar_over_100(self):
        bar = BudgetService._progress_bar(150)
        assert bar == "█" * 10  # no supera el límite

    def test_format_budget_status_empty(self):
        msg = BudgetService.format_budget_status([], "2026-02")
        assert "No tenés presupuestos" in msg

    def test_format_budget_status_with_data(self):
        statuses = [
            {"category": "alimentación", "limit": 10000.0, "spent": 8500.0, "remaining": 1500.0, "percentage": 85.0},
            {"category": "transporte", "limit": 3000.0, "spent": 500.0, "remaining": 2500.0, "percentage": 16.7},
        ]
        msg = BudgetService.format_budget_status(statuses, "2026-02")
        assert "Alimentación" in msg
        assert "85%" in msg
        assert "⚠️" in msg  # 85% → alerta
        assert "✅" in msg  # 16.7% → ok

    def test_get_alerts_overspent(self):
        with patch.object(BudgetService, "get_status") as mock_get:
            mock_get.return_value = [
                {"category": "alimentación", "limit": 10000.0, "spent": 11000.0,
                 "remaining": -1000.0, "percentage": 110.0},
            ]
            alerts = BudgetService.get_alerts("user-id", "2026-02")
            assert len(alerts) == 1
            assert "🚨" in alerts[0]

    def test_get_alerts_warning(self):
        with patch.object(BudgetService, "get_status") as mock_get:
            mock_get.return_value = [
                {"category": "hogar", "limit": 5000.0, "spent": 4200.0,
                 "remaining": 800.0, "percentage": 84.0},
            ]
            alerts = BudgetService.get_alerts("user-id", "2026-02")
            assert len(alerts) == 1
            assert "⚠️" in alerts[0]

    def test_get_alerts_no_alerts_when_low(self):
        with patch.object(BudgetService, "get_status") as mock_get:
            mock_get.return_value = [
                {"category": "ropa", "limit": 5000.0, "spent": 1000.0,
                 "remaining": 4000.0, "percentage": 20.0},
            ]
            alerts = BudgetService.get_alerts("user-id", "2026-02")
            assert len(alerts) == 0
