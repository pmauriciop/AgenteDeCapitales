"""
database/repositories.py
─────────────────────────
Capa de acceso a datos (Repository Pattern).
Cada clase encapsula las operaciones CRUD de una tabla de Supabase.

Uso:
    from database.repositories import UserRepo, TransactionRepo

    user = UserRepo.get_or_create(telegram_id=123456, name="Juan")
    txs  = TransactionRepo.list_by_month(user_id=user.id, month="2026-02")
"""

from __future__ import annotations
from datetime import date, datetime
from typing import Optional

from database.client import get_client
from database.models import User, Transaction, Budget, RecurringTransaction
from database.encryption import encrypt, decrypt


# ─────────────────────────────────────────────
#  UserRepo
# ─────────────────────────────────────────────

class UserRepo:
    TABLE = "users"

    @classmethod
    def get_by_telegram_id(cls, telegram_id: int) -> Optional[User]:
        db = get_client()
        result = (
            db.table(cls.TABLE)
            .select("*")
            .eq("telegram_id", telegram_id)
            .maybe_single()
            .execute()
        )
        if result is None or result.data is None:
            return None
        return User.from_dict(result.data)

    @classmethod
    def create(cls, telegram_id: int, name: str) -> User:
        db = get_client()
        user = User(telegram_id=telegram_id, name=name)
        result = db.table(cls.TABLE).insert(user.to_dict()).execute()
        return User.from_dict(result.data[0])

    @classmethod
    def get_or_create(cls, telegram_id: int, name: str) -> tuple[User, bool]:
        """
        Retorna (user, created).
        created=True si el usuario fue creado ahora.
        """
        user = cls.get_by_telegram_id(telegram_id)
        if user:
            return user, False
        return cls.create(telegram_id, name), True


# ─────────────────────────────────────────────
#  TransactionRepo
# ─────────────────────────────────────────────

class TransactionRepo:
    TABLE = "transactions"

    @classmethod
    def create(cls, tx: Transaction) -> Transaction:
        db = get_client()
        payload = tx.to_dict()
        # Encriptamos la descripción antes de guardar
        payload["description"] = encrypt(payload["description"])
        result = db.table(cls.TABLE).insert(payload).execute()
        return Transaction.from_dict(_decrypt_tx(result.data[0]))

    @classmethod
    def find_duplicate(
        cls,
        user_id: str,
        tx_date: "date",
        amount: float,
        description: str,
        tx_type: str,
    ) -> Optional[Transaction]:
        """
        Busca una transacción existente con el mismo user, fecha, monto y tipo.
        Compara descripción desencriptando los registros existentes.
        Retorna la Transaction si existe, None si no.
        """
        db = get_client()
        result = (
            db.table(cls.TABLE)
            .select("*")
            .eq("user_id", user_id)
            .eq("date", tx_date.isoformat())
            .eq("amount", amount)
            .eq("type", tx_type)
            .execute()
        )
        for row in result.data:
            try:
                existing_desc = decrypt(row["description"])
            except Exception:
                existing_desc = row["description"]
            if existing_desc == description:
                return Transaction.from_dict(_decrypt_tx(row))
        return None

    @classmethod
    def list_by_month(cls, user_id: str, month: str) -> list[Transaction]:
        """
        month: "YYYY-MM"
        """
        db = get_client()
        start = f"{month}-01"
        # último día calculado a partir del mes siguiente
        year, m = int(month[:4]), int(month[5:7])
        if m == 12:
            end = f"{year + 1}-01-01"
        else:
            end = f"{year}-{m + 1:02d}-01"

        result = (
            db.table(cls.TABLE)
            .select("*")
            .eq("user_id", user_id)
            .gte("date", start)
            .lt("date", end)
            .order("date", desc=True)
            .execute()
        )
        return [Transaction.from_dict(_decrypt_tx(row)) for row in result.data]

    @classmethod
    def list_by_category(
        cls, user_id: str, category: str, month: Optional[str] = None
    ) -> list[Transaction]:
        db = get_client()
        query = (
            db.table(cls.TABLE)
            .select("*")
            .eq("user_id", user_id)
            .eq("category", category)
        )
        if month:
            year, m = int(month[:4]), int(month[5:7])
            start = f"{month}-01"
            end = f"{year}-{m + 1:02d}-01" if m < 12 else f"{year + 1}-01-01"
            query = query.gte("date", start).lt("date", end)
        result = query.order("date", desc=True).execute()
        return [Transaction.from_dict(_decrypt_tx(row)) for row in result.data]

    @classmethod
    def delete(cls, transaction_id: str) -> bool:
        db = get_client()
        result = (
            db.table(cls.TABLE)
            .delete()
            .eq("id", transaction_id)
            .execute()
        )
        return len(result.data) > 0

    @classmethod
    def list_last_n_months(cls, user_id: str, n: int = 6) -> list[Transaction]:
        """Retorna todas las transacciones de los últimos N meses."""
        from datetime import date
        from dateutil.relativedelta import relativedelta
        today = date.today()
        start = (today - relativedelta(months=n)).replace(day=1)
        db = get_client()
        result = (
            db.table(cls.TABLE)
            .select("*")
            .eq("user_id", user_id)
            .gte("date", start.isoformat())
            .order("date", desc=False)
            .execute()
        )
        return [Transaction.from_dict(_decrypt_tx(row)) for row in result.data]

    @classmethod
    def get_monthly_totals(cls, user_id: str, n_months: int = 6) -> list[dict]:
        """
        Retorna totales de ingresos y gastos agrupados por mes
        para los últimos N meses.
        """
        txs = cls.list_last_n_months(user_id, n_months)
        months: dict[str, dict] = {}
        for tx in txs:
            key = tx.date.strftime("%Y-%m")
            if key not in months:
                months[key] = {"month": key, "income": 0.0, "expense": 0.0}
            months[key][tx.type] += tx.amount
        for m in months.values():
            m["balance"] = m["income"] - m["expense"]
        return sorted(months.values(), key=lambda x: x["month"])

    @classmethod
    def get_summary(cls, user_id: str, month: str) -> dict:
        """
        Retorna dict con totales de ingresos, gastos y balance del mes.
        """
        txs = cls.list_by_month(user_id, month)
        income = sum(t.amount for t in txs if t.type == "income")
        expense = sum(t.amount for t in txs if t.type == "expense")
        return {
            "month": month,
            "income": income,
            "expense": expense,
            "balance": income - expense,
            "transactions": txs,
        }


# ─────────────────────────────────────────────
#  BudgetRepo
# ─────────────────────────────────────────────

class BudgetRepo:
    TABLE = "budgets"

    @classmethod
    def set_budget(cls, user_id: str, category: str, limit_amount: float, month: str) -> Budget:
        """Crea o actualiza el presupuesto de una categoría para un mes."""
        db = get_client()
        # Buscar si ya existe
        result = (
            db.table(cls.TABLE)
            .select("*")
            .eq("user_id", user_id)
            .eq("category", category)
            .eq("month", month)
            .execute()
        )
        budget = Budget(
            user_id=user_id,
            category=category,
            limit_amount=limit_amount,
            month=month,
        )
        if result.data:
            # actualizar
            updated = (
                db.table(cls.TABLE)
                .update({"limit_amount": limit_amount})
                .eq("id", result.data[0]["id"])
                .execute()
            )
            return Budget.from_dict(updated.data[0])
        else:
            inserted = db.table(cls.TABLE).insert(budget.to_dict()).execute()
            return Budget.from_dict(inserted.data[0])

    @classmethod
    def list_by_month(cls, user_id: str, month: str) -> list[Budget]:
        db = get_client()
        result = (
            db.table(cls.TABLE)
            .select("*")
            .eq("user_id", user_id)
            .eq("month", month)
            .execute()
        )
        return [Budget.from_dict(row) for row in result.data]

    @classmethod
    def get_budget_status(cls, user_id: str, month: str) -> list[dict]:
        """
        Retorna lista con estado de cada presupuesto:
        categoria, limite, gastado, restante, porcentaje.
        """
        budgets = cls.list_by_month(user_id, month)
        result = []
        for b in budgets:
            txs = TransactionRepo.list_by_category(user_id, b.category, month)
            spent = sum(t.amount for t in txs if t.type == "expense")
            result.append({
                "category": b.category,
                "limit": b.limit_amount,
                "spent": spent,
                "remaining": b.limit_amount - spent,
                "percentage": round((spent / b.limit_amount * 100) if b.limit_amount else 0, 1),
            })
        return result


# ─────────────────────────────────────────────
#  RecurringRepo
# ─────────────────────────────────────────────

class RecurringRepo:
    TABLE = "recurring"

    @classmethod
    def create(cls, rec: RecurringTransaction) -> RecurringTransaction:
        db = get_client()
        payload = rec.to_dict()
        payload["description"] = encrypt(payload["description"])
        result = db.table(cls.TABLE).insert(payload).execute()
        return RecurringTransaction.from_dict(_decrypt_rec(result.data[0]))

    @classmethod
    def list_active(cls, user_id: str) -> list[RecurringTransaction]:
        db = get_client()
        result = (
            db.table(cls.TABLE)
            .select("*")
            .eq("user_id", user_id)
            .eq("active", True)
            .order("next_date")
            .execute()
        )
        return [RecurringTransaction.from_dict(_decrypt_rec(row)) for row in result.data]

    @classmethod
    def deactivate(cls, recurring_id: str) -> bool:
        db = get_client()
        result = (
            db.table(cls.TABLE)
            .update({"active": False})
            .eq("id", recurring_id)
            .execute()
        )
        return len(result.data) > 0

    @classmethod
    def update_next_date(cls, recurring_id: str, next_date: date) -> None:
        db = get_client()
        db.table(cls.TABLE).update({"next_date": next_date.isoformat()}).eq("id", recurring_id).execute()


# ─────────────────────────────────────────────
#  Helpers privados
# ─────────────────────────────────────────────

def _decrypt_tx(row: dict) -> dict:
    """Desencripta descripción de una fila de transacciones."""
    if row.get("description"):
        try:
            row["description"] = decrypt(row["description"])
        except Exception:
            pass  # Si no está cifrado (datos legacy) lo dejamos tal cual
    return row


def _decrypt_rec(row: dict) -> dict:
    """Desencripta descripción de una fila de recurrentes."""
    if row.get("description"):
        try:
            row["description"] = decrypt(row["description"])
        except Exception:
            pass
    return row
