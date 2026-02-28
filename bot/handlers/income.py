"""
bot/handlers/income.py
───────────────────────
ConversationHandler para registro manual de ingresos.
Flujo: monto → categoría → descripción → guardar
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
from bot.keyboards import income_categories_keyboard, main_menu
from bot.states import (
    INCOME_AMOUNT,
    INCOME_CATEGORY,
    INCOME_DESCRIPTION,
)


async def start_income(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    await update.message.reply_text(
        "💰 *Nuevo ingreso*\n\n¿Cuánto recibiste? Ingresá el monto:",
        parse_mode="Markdown",
    )
    return INCOME_AMOUNT


async def get_income_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    text = update.message.text.replace(",", ".").replace("$", "").strip()
    try:
        amount = float(text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Monto inválido. Ingresá un número positivo:")
        return INCOME_AMOUNT

    context.user_data["income_amount"] = amount
    await update.message.reply_text(
        "📂 ¿Cuál es la categoría de este ingreso?",
        reply_markup=income_categories_keyboard(),
    )
    return INCOME_CATEGORY


async def get_income_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    query = update.callback_query
    await query.answer()

    if query.data == "cancel":
        await query.edit_message_text("❌ Registro cancelado.")
        return ConversationHandler.END

    category = query.data.split(":", 1)[1]
    context.user_data["income_category"] = category
    await query.edit_message_text(
        f"✅ Categoría: _{category.capitalize()}_\n\n"
        "📝 Agregá una descripción (o /skip para omitir):",
        parse_mode="Markdown",
    )
    return INCOME_DESCRIPTION


async def get_income_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    description = update.message.text
    if description.lower() == "/skip":
        description = ""

    db_user, _ = UserRepo.get_or_create(
        telegram_id=update.effective_user.id,
        name=update.effective_user.full_name,
    )

    tx = TransactionService.add_manual(
        user_id=db_user.id,
        amount=context.user_data["income_amount"],
        tx_type="income",
        category=context.user_data["income_category"],
        description=description,
        tx_date=date.today(),
    )

    await update.message.reply_text(
        f"✅ *Ingreso registrado*\n\n"
        f"• Monto: `+${tx.amount:,.2f}`\n"
        f"• Categoría: _{tx.category.capitalize()}_\n"
        f"• Descripción: _{tx.description or 'Sin descripción'}_\n"
        f"• Fecha: `{tx.date}`",
        parse_mode="Markdown",
        reply_markup=main_menu(),
    )

    context.user_data.clear()
    return ConversationHandler.END


async def cancel_income(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ Registro cancelado.", reply_markup=main_menu())
    context.user_data.clear()
    return ConversationHandler.END


income_conversation = ConversationHandler(
    entry_points=[CommandHandler("ingreso", start_income)],
    states={
        INCOME_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_income_amount)],
        INCOME_CATEGORY: [CallbackQueryHandler(get_income_category, pattern=r"^(cat_income:|cancel)")],
        INCOME_DESCRIPTION: [MessageHandler(filters.TEXT, get_income_description)],
    },
    fallbacks=[CommandHandler("cancelar", cancel_income)],
)
