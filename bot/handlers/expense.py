"""
bot/handlers/expense.py
────────────────────────
ConversationHandler para registro manual de gastos paso a paso.
Flujo: monto → categoría → descripción → confirmar
"""

from datetime import date
import warnings
warnings.filterwarnings("ignore", message=".*per_message.*", category=UserWarning)
from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from database.repositories import UserRepo
from services.transaction_service import TransactionService
from bot.keyboards import expense_categories_keyboard, main_menu
from bot.states import (
    EXPENSE_AMOUNT,
    EXPENSE_CATEGORY,
    EXPENSE_DESCRIPTION,
)


async def start_expense(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    await update.message.reply_text(
        "💸 *Nuevo gasto*\n\n¿Cuánto gastaste? Ingresá el monto:",
        parse_mode="Markdown",
    )
    return EXPENSE_AMOUNT


async def get_expense_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    text = update.message.text.replace(",", ".").replace("$", "").strip()
    try:
        amount = float(text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Monto inválido. Ingresá un número positivo:")
        return EXPENSE_AMOUNT

    context.user_data["expense_amount"] = amount
    await update.message.reply_text(
        "📂 ¿En qué categoría entra este gasto?",
        reply_markup=expense_categories_keyboard(),
    )
    return EXPENSE_CATEGORY


async def get_expense_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    query = update.callback_query
    await query.answer()

    if query.data == "cancel":
        await query.edit_message_text("❌ Registro cancelado.")
        return ConversationHandler.END

    category = query.data.split(":", 1)[1]
    context.user_data["expense_category"] = category
    await query.edit_message_text(
        f"✅ Categoría: _{category.capitalize()}_\n\n"
        "📝 Agregá una descripción breve (o escribí /skip para omitir):",
        parse_mode="Markdown",
    )
    return EXPENSE_DESCRIPTION


async def get_expense_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    description = update.message.text
    if description.lower() == "/skip":
        description = ""

    db_user, _ = UserRepo.get_or_create(
        telegram_id=update.effective_user.id,
        name=update.effective_user.full_name,
    )

    tx = TransactionService.add_manual(
        user_id=db_user.id,
        amount=context.user_data["expense_amount"],
        tx_type="expense",
        category=context.user_data["expense_category"],
        description=description,
        tx_date=date.today(),
    )

    await update.message.reply_text(
        f"✅ *Gasto registrado*\n\n"
        f"• Monto: `$-{tx.amount:,.2f}`\n"
        f"• Categoría: _{tx.category.capitalize()}_\n"
        f"• Descripción: _{tx.description or 'Sin descripción'}_\n"
        f"• Fecha: `{tx.date}`",
        parse_mode="Markdown",
        reply_markup=main_menu(),
    )

    context.user_data.clear()
    return ConversationHandler.END


async def cancel_expense(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ Registro cancelado.", reply_markup=main_menu())
    context.user_data.clear()
    return ConversationHandler.END


expense_conversation = ConversationHandler(
    entry_points=[CommandHandler("gasto", start_expense)],
    states={
        EXPENSE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_expense_amount)],
        EXPENSE_CATEGORY: [CallbackQueryHandler(get_expense_category, pattern=r"^(cat_expense:|cancel)")],
        EXPENSE_DESCRIPTION: [MessageHandler(filters.TEXT, get_expense_description)],
    },
    fallbacks=[CommandHandler("cancelar", cancel_expense)],
)
