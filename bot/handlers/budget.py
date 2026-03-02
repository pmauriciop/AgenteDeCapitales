"""
bot/handlers/budget.py
───────────────────────
Handlers para gestión de presupuestos:
  /presupuesto      — ver estado actual
  ConversationHandler — definir nuevo presupuesto
"""

import warnings
from datetime import date

warnings.filterwarnings("ignore", message=".*per_message.*", category=UserWarning)
from telegram import Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.keyboards import expense_categories_keyboard, main_menu
from bot.states import BUDGET_AMOUNT, BUDGET_CATEGORY
from database.repositories import UserRepo
from services.budget_service import BudgetService

# ── Ver presupuestos ──────────────────────────────────────

async def show_budget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db_user, _ = UserRepo.get_or_create(
        telegram_id=update.effective_user.id,
        name=update.effective_user.full_name,
    )
    month = date.today().strftime("%Y-%m")
    statuses = BudgetService.get_status(db_user.id, month)
    msg = BudgetService.format_budget_status(statuses, month)
    await update.effective_message.reply_text(msg, parse_mode="Markdown")


async def budget_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    # Reutilizar lógica de show_budget
    await show_budget(update, context)


# ── ConversationHandler: crear presupuesto ────────────────

async def start_set_budget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    await update.message.reply_text(
        "💼 *Definir presupuesto*\n\n¿Para qué categoría querés fijar un límite?",
        parse_mode="Markdown",
        reply_markup=expense_categories_keyboard(),
    )
    return BUDGET_CATEGORY


async def get_budget_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    query = update.callback_query
    await query.answer()

    if query.data == "cancel":
        await query.edit_message_text("❌ Operación cancelada.")
        return ConversationHandler.END

    category = query.data.split(":", 1)[1]
    context.user_data["budget_category"] = category
    month = date.today().strftime("%Y-%m")

    await query.edit_message_text(
        f"✅ Categoría: _{category.capitalize()}_\n\n"
        f"💰 ¿Cuál es el límite mensual para *{month}*? Ingresá el monto:",
        parse_mode="Markdown",
    )
    return BUDGET_AMOUNT


async def get_budget_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.replace(",", ".").replace("$", "").strip()
    try:
        amount = float(text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Monto inválido. Ingresá un número positivo:")
        return BUDGET_AMOUNT

    db_user, _ = UserRepo.get_or_create(
        telegram_id=update.effective_user.id,
        name=update.effective_user.full_name,
    )
    category = context.user_data["budget_category"]
    month = date.today().strftime("%Y-%m")

    budget = BudgetService.set_budget(db_user.id, category, amount, month)

    await update.message.reply_text(
        f"✅ *Presupuesto definido*\n\n"
        f"• Categoría: _{category.capitalize()}_\n"
        f"• Límite: `${budget.limit_amount:,.2f}`\n"
        f"• Mes: `{month}`",
        parse_mode="Markdown",
        reply_markup=main_menu(),
    )
    context.user_data.clear()
    return ConversationHandler.END


async def cancel_budget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ Operación cancelada.", reply_markup=main_menu())
    context.user_data.clear()
    return ConversationHandler.END


budget_conversation = ConversationHandler(
    entry_points=[CommandHandler("presupuesto_nuevo", start_set_budget)],
    states={
        BUDGET_CATEGORY: [CallbackQueryHandler(get_budget_category, pattern=r"^(cat_expense:|cancel)")],
        BUDGET_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_budget_amount)],
    },
    fallbacks=[CommandHandler("cancelar", cancel_budget)],
)

budget_callback = CallbackQueryHandler(budget_callback_handler, pattern=r"^budget:")
