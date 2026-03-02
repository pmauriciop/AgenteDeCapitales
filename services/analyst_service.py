"""
services/analyst_service.py
────────────────────────────
Servicio que recopila el contexto financiero completo del usuario
y lo pasa al analista de IA para responder preguntas.
"""

from __future__ import annotations

from datetime import date

from ai.analyst import answer_financial_question, detect_analyst_intent
from database.repositories import (
    BudgetRepo,
    RecurringRepo,
    TransactionRepo,
)


class AnalystService:
    """Orquesta la recopilación de datos y la consulta al analista de IA."""

    @classmethod
    async def is_analyst_question(cls, text: str) -> bool:
        """Detecta si el texto es una pregunta analítica."""
        return await detect_analyst_intent(text)

    @classmethod
    async def answer(cls, user_id: str, user_name: str, question: str) -> str:
        """
        Recopila todos los datos del usuario y genera una respuesta inteligente.

        Args:
            user_id:   UUID del usuario en Supabase.
            user_name: Nombre del usuario (para personalización).
            question:  Pregunta en lenguaje natural.

        Returns:
            Respuesta del analista en texto plano.
        """
        today = date.today()
        current_month = today.strftime("%Y-%m")

        # ── 1. Histórico de últimos 6 meses ──────────────
        monthly_totals = TransactionRepo.get_monthly_totals(user_id, n_months=6)

        # ── 2. Transacciones del mes actual (detalle) ────
        current_txs_raw = TransactionRepo.list_by_month(user_id, current_month)
        current_month_txs = [
            {
                "date": str(tx.date),
                "type": tx.type,
                "category": tx.category,
                "description": tx.description,
                "amount": tx.amount,
            }
            for tx in current_txs_raw
        ]

        # ── 3. Recurrentes activas ────────────────────────
        recurrentes_raw = RecurringRepo.list_active(user_id)
        recurring = [
            {
                "description": r.description,
                "amount": r.amount,
                "category": r.category,
                "frequency": r.frequency,
                "next_date": str(r.next_date),
            }
            for r in recurrentes_raw
        ]

        # ── 4. Estado de presupuestos del mes actual ─────
        budget_status_raw = BudgetRepo.get_budget_status(user_id, current_month)

        # ── 5. Todas las transacciones con cuotas activas ──
        # Busca en TODA la historia, no solo 6 meses
        all_txs_raw = TransactionRepo.list_all(user_id)
        all_transactions = [
            {
                "date": str(tx.date),
                "type": tx.type,
                "category": tx.category,
                "description": tx.description,
                "amount": tx.amount,
                "installment_current": tx.installment_current,
                "installment_total": tx.installment_total,
                "installments_remaining": tx.installments_remaining,
            }
            for tx in all_txs_raw
        ]

        # Cuotas activas (tienen installment_total y installments_remaining > 0)
        installments_active = [
            t for t in all_transactions
            if t.get("installment_total") and (t.get("installments_remaining") or 0) > 0
        ]

        # ── Armar contexto completo ───────────────────────
        context = {
            "user_name": user_name,
            "today": str(today),
            "current_month": current_month,
            "monthly_totals_last_6_months": monthly_totals,
            "current_month_transactions": current_month_txs,
            "all_transactions": all_transactions,
            "installments_active": installments_active,
            "recurring_subscriptions": recurring,
            "budget_status": budget_status_raw,
        }

        return await answer_financial_question(question, context)
