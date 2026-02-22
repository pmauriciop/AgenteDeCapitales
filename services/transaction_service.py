"""
services/transaction_service.py
────────────────────────────────
Lógica de negocio para gestión de transacciones.
Orquesta NLP → validación → persistencia en DB.
"""

from __future__ import annotations
from datetime import date
from typing import Any

from database.models import Transaction
from database.repositories import TransactionRepo, UserRepo


class TransactionService:
    """Gestiona el ciclo de vida de las transacciones financieras."""

    # ── Creación ──────────────────────────────────────────

    @classmethod
    def add_from_parsed(cls, user_id: str, parsed: dict[str, Any]) -> Transaction:
        """
        Crea una transacción a partir del dict retornado por el NLP.

        Args:
            user_id: UUID del usuario en Supabase.
            parsed:  dict con amount, type, category, description, date.

        Returns:
            Transaction persistida en DB.
        """
        tx = Transaction(
            user_id=user_id,
            amount=float(parsed["amount"]),
            category=parsed.get("category", "otros"),
            description=parsed.get("description", ""),
            type=parsed["type"],
            date=date.fromisoformat(parsed["date"]),
        )
        return TransactionRepo.create(tx)

    @classmethod
    def add_manual(
        cls,
        user_id: str,
        amount: float,
        tx_type: str,
        category: str,
        description: str,
        tx_date: date | None = None,
    ) -> Transaction:
        """
        Crea una transacción con datos explícitos (sin NLP).
        Útil para los handlers de teclado del bot.
        """
        tx = Transaction(
            user_id=user_id,
            amount=abs(amount),
            category=category,
            description=description,
            type=tx_type,
            date=tx_date or date.today(),
        )
        return TransactionRepo.create(tx)

    # ── Consultas ─────────────────────────────────────────

    @classmethod
    def get_monthly_summary(cls, user_id: str, month: str | None = None) -> dict:
        """
        Retorna resumen del mes (ingresos, gastos, balance, breakdown).

        Args:
            user_id: UUID del usuario.
            month:   "YYYY-MM". Si es None usa el mes actual.
        """
        if not month:
            month = date.today().strftime("%Y-%m")

        summary = TransactionRepo.get_summary(user_id, month)

        # Breakdown por categoría
        category_breakdown: dict[str, float] = {}
        for tx in summary["transactions"]:
            if tx.type == "expense":
                category_breakdown[tx.category] = (
                    category_breakdown.get(tx.category, 0) + tx.amount
                )

        summary["breakdown"] = dict(
            sorted(category_breakdown.items(), key=lambda x: x[1], reverse=True)
        )
        summary.pop("transactions")  # no serializar la lista completa en el resumen
        return summary

    @classmethod
    def list_recent(cls, user_id: str, month: str | None = None, limit: int = 10) -> list[Transaction]:
        """Lista las últimas N transacciones del mes."""
        if not month:
            month = date.today().strftime("%Y-%m")
        txs = TransactionRepo.list_by_month(user_id, month)
        return txs[:limit]

    # ── Eliminación ───────────────────────────────────────

    @classmethod
    def delete(cls, transaction_id: str) -> bool:
        """Elimina una transacción por ID."""
        return TransactionRepo.delete(transaction_id)

    # ── Formato para Telegram ─────────────────────────────

    @staticmethod
    def format_summary_message(summary: dict) -> str:
        """Formatea el resumen mensual como mensaje de Telegram (Markdown)."""
        month = summary["month"]
        income = summary["income"]
        expense = summary["expense"]
        balance = summary["balance"]
        breakdown = summary.get("breakdown", {})

        emoji_balance = "📈" if balance >= 0 else "📉"
        sign = "+" if balance >= 0 else "-"
        abs_balance = abs(balance)

        lines = [
            f"📊 *Resumen de {month}*\n",
            f"💰 Ingresos:  `${income:,.2f}`",
            f"💸 Gastos:    `${expense:,.2f}`",
            f"{emoji_balance} Balance:   `{sign}${abs_balance:,.2f}`",
        ]

        if breakdown:
            lines.append("\n📂 *Gastos por categoría:*")
            for cat, amount in breakdown.items():
                lines.append(f"  • {cat.capitalize()}: `${amount:,.2f}`")

        return "\n".join(lines)

    @staticmethod
    def format_transaction_list(txs: list[Transaction]) -> str:
        """Formatea una lista de transacciones para Telegram."""
        if not txs:
            return "📭 No hay transacciones registradas."

        lines = ["📋 *Últimas transacciones:*\n"]
        for tx in txs:
            emoji = "💰" if tx.type == "income" else "💸"
            sign = "+" if tx.type == "income" else "-"
            lines.append(
                f"{emoji} `{tx.date}` — {tx.category}\n"
                f"   {sign}${tx.amount:,.2f} · {tx.description}\n"
                f"   `ID: {tx.id}`"
            )
        return "\n".join(lines)
