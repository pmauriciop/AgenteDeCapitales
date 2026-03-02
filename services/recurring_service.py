"""
services/recurring_service.py
──────────────────────────────
Lógica de negocio para transacciones recurrentes.
Crea suscripciones (Netflix, alquiler, salario, etc.) y las
procesa automáticamente cuando llega su fecha.
"""

from __future__ import annotations

from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from database.models import RecurringTransaction, Transaction
from database.repositories import RecurringRepo, TransactionRepo


class RecurringService:
    """Gestiona transacciones periódicas y su procesamiento automático."""

    # ── Creación ──────────────────────────────────────────

    @classmethod
    def add(
        cls,
        user_id: str,
        amount: float,
        category: str,
        description: str,
        frequency: str,
        start_date: date | None = None,
    ) -> RecurringTransaction:
        """
        Registra una nueva transacción recurrente.

        Args:
            frequency: "daily" | "weekly" | "monthly" | "yearly"
        """
        rec = RecurringTransaction(
            user_id=user_id,
            amount=abs(amount),
            category=category,
            description=description,
            frequency=frequency,
            next_date=start_date or date.today(),
        )
        return RecurringRepo.create(rec)

    # ── Procesamiento automático ──────────────────────────

    @classmethod
    def process_due(cls, user_id: str) -> list[Transaction]:
        """
        Procesa todas las recurrentes cuya next_date <= hoy.
        Crea las transacciones correspondientes y actualiza la próxima fecha.

        Returns:
            Lista de transacciones creadas.
        """
        today = date.today()
        active = RecurringRepo.list_active(user_id)
        created: list[Transaction] = []

        for rec in active:
            if rec.next_date <= today:
                # Crear la transacción
                tx = Transaction(
                    user_id=user_id,
                    amount=rec.amount,
                    category=rec.category,
                    description=f"[Auto] {rec.description}",
                    type="expense",
                    date=rec.next_date,
                )
                saved_tx = TransactionRepo.create(tx)
                created.append(saved_tx)

                # Calcular próxima fecha
                next_date = cls._calculate_next_date(rec.next_date, rec.frequency)
                RecurringRepo.update_next_date(rec.id, next_date)

        return created

    @classmethod
    def list_active(cls, user_id: str) -> list[RecurringTransaction]:
        """Lista todas las recurrentes activas del usuario."""
        return RecurringRepo.list_active(user_id)

    @classmethod
    def deactivate(cls, recurring_id: str) -> bool:
        """Desactiva (cancela) una recurrente."""
        return RecurringRepo.deactivate(recurring_id)

    # ── Helpers ───────────────────────────────────────────

    @staticmethod
    def _calculate_next_date(current: date, frequency: str) -> date:
        """Calcula la próxima fecha de ejecución según la frecuencia."""
        if frequency == "daily":
            return current + timedelta(days=1)
        elif frequency == "weekly":
            return current + timedelta(weeks=1)
        elif frequency == "monthly":
            return current + relativedelta(months=1)
        elif frequency == "yearly":
            return current + relativedelta(years=1)
        else:
            return current + relativedelta(months=1)

    # ── Formato para Telegram ─────────────────────────────

    FREQ_LABELS = {
        "daily": "Diaria",
        "weekly": "Semanal",
        "monthly": "Mensual",
        "yearly": "Anual",
    }

    @classmethod
    def format_recurring_list(cls, recs: list[RecurringTransaction]) -> str:
        """Formatea la lista de recurrentes para Telegram."""
        if not recs:
            return "📭 No tenés transacciones recurrentes activas."

        lines = ["🔁 *Transacciones recurrentes:*\n"]
        for rec in recs:
            freq_label = cls.FREQ_LABELS.get(rec.frequency, rec.frequency)
            lines.append(
                f"• *{rec.description}*\n"
                f"  💰 `${rec.amount:,.2f}` · {freq_label}\n"
                f"  📅 Próxima: `{rec.next_date}`\n"
                f"  `ID: {rec.id}`"
            )
        return "\n\n".join(lines)
