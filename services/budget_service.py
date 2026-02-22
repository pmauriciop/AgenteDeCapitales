"""
services/budget_service.py
───────────────────────────
Lógica de negocio para gestión de presupuestos mensuales.
Permite definir límites por categoría y consultar el estado de gasto.
"""

from __future__ import annotations
from datetime import date

from database.models import Budget
from database.repositories import BudgetRepo


class BudgetService:
    """Gestiona presupuestos y alertas de gasto."""

    # ── Creación / actualización ──────────────────────────

    @classmethod
    def set_budget(
        cls,
        user_id: str,
        category: str,
        limit_amount: float,
        month: str | None = None,
    ) -> Budget:
        """
        Define o actualiza el presupuesto de una categoría.

        Args:
            user_id:      UUID del usuario.
            category:     Nombre de la categoría.
            limit_amount: Monto máximo en el mes.
            month:        "YYYY-MM". Si es None usa el mes actual.
        """
        if not month:
            month = date.today().strftime("%Y-%m")
        return BudgetRepo.set_budget(user_id, category, abs(limit_amount), month)

    # ── Consultas ─────────────────────────────────────────

    @classmethod
    def get_status(cls, user_id: str, month: str | None = None) -> list[dict]:
        """
        Retorna el estado de todos los presupuestos del mes:
        [{"category", "limit", "spent", "remaining", "percentage"}, ...]
        """
        if not month:
            month = date.today().strftime("%Y-%m")
        return BudgetRepo.get_budget_status(user_id, month)

    @classmethod
    def check_overspent(cls, user_id: str, category: str, month: str | None = None) -> dict | None:
        """
        Verifica si una categoría ha superado su presupuesto.

        Returns:
            dict con estado si hay presupuesto definido, None si no.
        """
        if not month:
            month = date.today().strftime("%Y-%m")
        statuses = cls.get_status(user_id, month)
        for s in statuses:
            if s["category"] == category:
                return s
        return None

    # ── Alertas ───────────────────────────────────────────

    @classmethod
    def get_alerts(cls, user_id: str, month: str | None = None) -> list[str]:
        """
        Retorna lista de alertas para categorías que superaron el 80% del presupuesto.
        """
        statuses = cls.get_status(user_id, month)
        alerts = []
        for s in statuses:
            pct = s["percentage"]
            cat = s["category"].capitalize()
            if pct >= 100:
                alerts.append(
                    f"🚨 *{cat}*: superaste el presupuesto ({pct:.0f}% usado — "
                    f"${s['spent']:,.2f} de ${s['limit']:,.2f})"
                )
            elif pct >= 80:
                alerts.append(
                    f"⚠️ *{cat}*: estás al {pct:.0f}% del presupuesto "
                    f"(${s['remaining']:,.2f} restantes)"
                )
        return alerts

    # ── Formato para Telegram ─────────────────────────────

    @staticmethod
    def format_budget_status(statuses: list[dict], month: str) -> str:
        """Formatea el estado de presupuestos para Telegram."""
        if not statuses:
            return (
                f"📭 No tenés presupuestos definidos para *{month}*.\n"
                "Usá /presupuesto para crear uno."
            )

        lines = [f"💼 *Presupuestos — {month}*\n"]
        for s in statuses:
            pct = s["percentage"]
            bar = BudgetService._progress_bar(pct)
            emoji = "🚨" if pct >= 100 else ("⚠️" if pct >= 80 else "✅")
            lines.append(
                f"{emoji} *{s['category'].capitalize()}*\n"
                f"   {bar} {pct:.0f}%\n"
                f"   Gastado: `${s['spent']:,.2f}` / `${s['limit']:,.2f}`"
            )
        return "\n\n".join(lines)

    @staticmethod
    def _progress_bar(percentage: float, length: int = 10) -> str:
        """Genera una barra de progreso ASCII."""
        filled = min(int(percentage / 100 * length), length)
        return "█" * filled + "░" * (length - filled)
