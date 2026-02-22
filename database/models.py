"""
database/models.py
──────────────────
Modelos de datos (dataclasses) que representan las tablas de Supabase.
Sirven como contratos entre capas, sin ORM pesado.

Tablas esperadas en Supabase:
  - users            (id, telegram_id, name, created_at)
  - transactions     (id, user_id, amount, category, description,
                      type, date, created_at)
  - budgets          (id, user_id, category, limit_amount, month,
                      created_at)
  - recurring        (id, user_id, amount, category, description,
                      frequency, next_date, active)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal, Optional


# ─────────────────────────────────────────────
#  Users
# ─────────────────────────────────────────────

@dataclass
class User:
    telegram_id: int
    name: str
    id: Optional[str] = None
    created_at: Optional[datetime] = None

    @classmethod
    def from_dict(cls, data: dict) -> "User":
        return cls(
            id=data.get("id"),
            telegram_id=int(data["telegram_id"]),
            name=data["name"],
            created_at=data.get("created_at"),
        )

    def to_dict(self) -> dict:
        return {
            "telegram_id": self.telegram_id,
            "name": self.name,
        }


# ─────────────────────────────────────────────
#  Transactions
# ─────────────────────────────────────────────

TransactionType = Literal["income", "expense"]


@dataclass
class Transaction:
    user_id: str
    amount: float                        # siempre positivo
    category: str
    description: str
    type: TransactionType                # "income" | "expense"
    date: date
    id: Optional[str] = None
    created_at: Optional[datetime] = None

    @classmethod
    def from_dict(cls, data: dict) -> "Transaction":
        raw_date = data["date"]
        parsed_date = (
            date.fromisoformat(raw_date) if isinstance(raw_date, str) else raw_date
        )
        return cls(
            id=data.get("id"),
            user_id=data["user_id"],
            amount=float(data["amount"]),
            category=data["category"],
            description=data.get("description", ""),
            type=data["type"],
            date=parsed_date,
            created_at=data.get("created_at"),
        )

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "amount": self.amount,
            "category": self.category,
            "description": self.description,
            "type": self.type,
            "date": self.date.isoformat(),
        }


# ─────────────────────────────────────────────
#  Budgets
# ─────────────────────────────────────────────

@dataclass
class Budget:
    user_id: str
    category: str
    limit_amount: float
    month: str                           # formato "YYYY-MM"
    id: Optional[str] = None
    created_at: Optional[datetime] = None

    @classmethod
    def from_dict(cls, data: dict) -> "Budget":
        return cls(
            id=data.get("id"),
            user_id=data["user_id"],
            category=data["category"],
            limit_amount=float(data["limit_amount"]),
            month=data["month"],
            created_at=data.get("created_at"),
        )

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "category": self.category,
            "limit_amount": self.limit_amount,
            "month": self.month,
        }


# ─────────────────────────────────────────────
#  Recurring transactions
# ─────────────────────────────────────────────

Frequency = Literal["daily", "weekly", "monthly", "yearly"]


@dataclass
class RecurringTransaction:
    user_id: str
    amount: float
    category: str
    description: str
    frequency: Frequency
    next_date: date
    active: bool = True
    id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "RecurringTransaction":
        raw_date = data["next_date"]
        parsed_date = (
            date.fromisoformat(raw_date) if isinstance(raw_date, str) else raw_date
        )
        return cls(
            id=data.get("id"),
            user_id=data["user_id"],
            amount=float(data["amount"]),
            category=data["category"],
            description=data.get("description", ""),
            frequency=data["frequency"],
            next_date=parsed_date,
            active=data.get("active", True),
        )

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "amount": self.amount,
            "category": self.category,
            "description": self.description,
            "frequency": self.frequency,
            "next_date": self.next_date.isoformat(),
            "active": self.active,
        }
