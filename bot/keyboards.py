"""
bot/keyboards.py
─────────────────
Teclados personalizados de Telegram (InlineKeyboard y ReplyKeyboard).
Centralizados aquí para reutilización entre handlers.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton

from ai.nlp import EXPENSE_CATEGORIES, INCOME_CATEGORIES


# ─────────────────────────────────────────────
#  Menú principal
# ─────────────────────────────────────────────

def main_menu() -> ReplyKeyboardMarkup:
    keyboard = [
        ["💸 Gasto",       "💰 Ingreso"],
        ["📊 Resumen",     "💼 Presupuestos"],
        ["📋 Historial",   "🔁 Recurrentes"],
        ["📄 Reporte PDF", "❓ Ayuda"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, persistent=True)


# ─────────────────────────────────────────────
#  Selección de categorías
# ─────────────────────────────────────────────

def expense_categories_keyboard() -> InlineKeyboardMarkup:
    """Teclado inline con las categorías de gasto."""
    return _categories_keyboard(EXPENSE_CATEGORIES, prefix="cat_expense")


def income_categories_keyboard() -> InlineKeyboardMarkup:
    """Teclado inline con las categorías de ingreso."""
    return _categories_keyboard(INCOME_CATEGORIES, prefix="cat_income")


def _categories_keyboard(categories: list[str], prefix: str) -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for i, cat in enumerate(categories):
        row.append(InlineKeyboardButton(cat.capitalize(), callback_data=f"{prefix}:{cat}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("❌ Cancelar", callback_data="cancel")])
    return InlineKeyboardMarkup(buttons)


# ─────────────────────────────────────────────
#  Confirmación de transacción
# ─────────────────────────────────────────────

def confirm_transaction_keyboard(tx_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirmar", callback_data=f"confirm_tx:{tx_id}"),
            InlineKeyboardButton("🗑️ Eliminar", callback_data=f"delete_tx:{tx_id}"),
        ]
    ])


# ─────────────────────────────────────────────
#  Selección de mes
# ─────────────────────────────────────────────

def month_selector_keyboard(current_month: str) -> InlineKeyboardMarkup:
    """Teclado para navegar entre meses."""
    year, m = int(current_month[:4]), int(current_month[5:7])

    prev_m = m - 1 if m > 1 else 12
    prev_y = year if m > 1 else year - 1
    prev_month = f"{prev_y}-{prev_m:02d}"

    next_m = m + 1 if m < 12 else 1
    next_y = year if m < 12 else year + 1
    next_month = f"{next_y}-{next_m:02d}"

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("◀ Anterior", callback_data=f"month:{prev_month}"),
            InlineKeyboardButton("▶ Siguiente", callback_data=f"month:{next_month}"),
        ]
    ])


# ─────────────────────────────────────────────
#  Frecuencia de recurrentes
# ─────────────────────────────────────────────

def frequency_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Diaria", callback_data="freq:daily"),
            InlineKeyboardButton("Semanal", callback_data="freq:weekly"),
        ],
        [
            InlineKeyboardButton("Mensual", callback_data="freq:monthly"),
            InlineKeyboardButton("Anual", callback_data="freq:yearly"),
        ],
        [InlineKeyboardButton("❌ Cancelar", callback_data="cancel")],
    ])


# ─────────────────────────────────────────────
#  Cancelar
# ─────────────────────────────────────────────

def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancelar", callback_data="cancel")]])
