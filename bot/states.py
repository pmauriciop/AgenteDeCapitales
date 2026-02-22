"""
bot/states.py
──────────────
Estados de la conversación (ConversationHandler).
Mantiene todos los estados en un único lugar para evitar colisiones.
"""

# ── Registro de gasto manual ──────────────────
EXPENSE_AMOUNT = "EXPENSE_AMOUNT"
EXPENSE_CATEGORY = "EXPENSE_CATEGORY"
EXPENSE_DESCRIPTION = "EXPENSE_DESCRIPTION"

# ── Registro de ingreso manual ────────────────
INCOME_AMOUNT = "INCOME_AMOUNT"
INCOME_CATEGORY = "INCOME_CATEGORY"
INCOME_DESCRIPTION = "INCOME_DESCRIPTION"

# ── Presupuesto ───────────────────────────────
BUDGET_CATEGORY = "BUDGET_CATEGORY"
BUDGET_AMOUNT = "BUDGET_AMOUNT"

# ── Recurrentes ───────────────────────────────
RECURRING_DESCRIPTION = "RECURRING_DESCRIPTION"
RECURRING_AMOUNT = "RECURRING_AMOUNT"
RECURRING_CATEGORY = "RECURRING_CATEGORY"
RECURRING_FREQUENCY = "RECURRING_FREQUENCY"

# ── Eliminar transacción ──────────────────────
DELETE_TX_ID = "DELETE_TX_ID"
