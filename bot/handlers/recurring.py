"""
bot/handlers/recurring.py
──────────────────────────
ConversationHandler para gestión de transacciones recurrentes:
  /recurrentes      — listar recurrentes activas
  /recurrente_nuevo — crear nueva recurrente
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

from bot.keyboards import (
    expense_categories_keyboard,
    frequency_keyboard,
    main_menu,
)
from bot.states import (
    RECURRING_AMOUNT,
    RECURRING_CATEGORY,
    RECURRING_DESCRIPTION,
    RECURRING_FREQUENCY,
)
from database.repositories import UserRepo
from services.recurring_service import RecurringService

# ── Listar recurrentes ────────────────────────────────────

async def list_recurring(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db_user, _ = UserRepo.get_or_create(
        telegram_id=update.effective_user.id,
        name=update.effective_user.full_name,
    )
    recs = RecurringService.list_active(db_user.id)
    msg = RecurringService.format_recurring_list(recs)
    await update.effective_message.reply_text(msg, parse_mode="Markdown")


async def recurring_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.data.startswith("deactivate_rec:"):
        rec_id = query.data.split(":", 1)[1]
        success = RecurringService.deactivate(rec_id)
        msg = "✅ Recurrente cancelada." if success else "❌ No se pudo cancelar."
        await query.edit_message_text(msg)


# ── ConversationHandler: crear recurrente ─────────────────

async def start_new_recurring(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    await update.message.reply_text(
        "🔁 *Nueva transacción recurrente*\n\n"
        "¿Cómo se llama? (ej: Netflix, Alquiler, Sueldo):",
        parse_mode="Markdown",
    )
    return RECURRING_DESCRIPTION


async def get_recurring_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    context.user_data["rec_description"] = update.message.text.strip()
    await update.message.reply_text("💰 ¿Cuál es el monto?")
    return RECURRING_AMOUNT


async def get_recurring_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    text = update.message.text.replace(",", ".").replace("$", "").strip()
    try:
        amount = float(text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Monto inválido. Ingresá un número positivo:")
        return RECURRING_AMOUNT

    context.user_data["rec_amount"] = amount
    await update.message.reply_text(
        "📂 ¿En qué categoría entra?",
        reply_markup=expense_categories_keyboard(),
    )
    return RECURRING_CATEGORY


async def get_recurring_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    query = update.callback_query
    await query.answer()

    if query.data == "cancel":
        await query.edit_message_text("❌ Operación cancelada.")
        return ConversationHandler.END

    category = query.data.split(":", 1)[1]
    context.user_data["rec_category"] = category
    await query.edit_message_text(
        f"✅ Categoría: _{category.capitalize()}_\n\n⏰ ¿Con qué frecuencia se repite?",
        parse_mode="Markdown",
        reply_markup=frequency_keyboard(),
    )
    return RECURRING_FREQUENCY


async def get_recurring_frequency(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "cancel":
        await query.edit_message_text("❌ Operación cancelada.")
        return ConversationHandler.END

    frequency = query.data.split(":", 1)[1]

    db_user, _ = UserRepo.get_or_create(
        telegram_id=update.effective_user.id,
        name=update.effective_user.full_name,
    )

    rec = RecurringService.add(
        user_id=db_user.id,
        amount=context.user_data["rec_amount"],
        category=context.user_data["rec_category"],
        description=context.user_data["rec_description"],
        frequency=frequency,
        start_date=date.today(),
    )

    freq_labels = {
        "daily": "Diaria", "weekly": "Semanal",
        "monthly": "Mensual", "yearly": "Anual",
    }

    await query.edit_message_text(
        f"✅ *Recurrente creada*\n\n"
        f"• Nombre: _{rec.description}_\n"
        f"• Monto: `${rec.amount:,.2f}`\n"
        f"• Categoría: _{rec.category.capitalize()}_\n"
        f"• Frecuencia: _{freq_labels.get(frequency, frequency)}_\n"
        f"• Primera ejecución: `{rec.next_date}`",
        parse_mode="Markdown",
    )

    context.user_data.clear()
    return ConversationHandler.END


async def cancel_recurring(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ Operación cancelada.", reply_markup=main_menu())
    context.user_data.clear()
    return ConversationHandler.END


recurring_conversation = ConversationHandler(
    entry_points=[CommandHandler("recurrente_nuevo", start_new_recurring)],
    states={
        RECURRING_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_recurring_description)],
        RECURRING_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_recurring_amount)],
        RECURRING_CATEGORY: [CallbackQueryHandler(get_recurring_category, pattern=r"^(cat_expense:|cancel)")],
        RECURRING_FREQUENCY: [CallbackQueryHandler(get_recurring_frequency, pattern=r"^(freq:|cancel)")],
    },
    fallbacks=[CommandHandler("cancelar", cancel_recurring)],
)

recurring_callback = CallbackQueryHandler(recurring_callback_handler, pattern=r"^deactivate_rec:")
