"""
bot/handlers/summary.py
────────────────────────
Handler para ver el resumen financiero mensual.
Soporta navegación entre meses con botones inline.
"""

from datetime import date

from telegram import Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from ai.nlp import generate_financial_advice
from bot.keyboards import month_selector_keyboard
from database.repositories import UserRepo
from services.budget_service import BudgetService
from services.transaction_service import TransactionService


async def show_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /resumen — muestra resumen del mes actual."""
    month = date.today().strftime("%Y-%m")
    await _send_summary(update, context, month, edit=False)


async def summary_month_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback de navegación entre meses."""
    query = update.callback_query
    await query.answer()
    month = query.data.split(":", 1)[1]
    await _send_summary(update, context, month, edit=True)


async def _send_summary(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    month: str,
    edit: bool,
) -> None:
    db_user, _ = UserRepo.get_or_create(
        telegram_id=update.effective_user.id,
        name=update.effective_user.full_name,
    )

    summary = TransactionService.get_monthly_summary(db_user.id, month)
    msg = TransactionService.format_summary_message(summary)

    # Alertas de presupuesto
    alerts = BudgetService.get_alerts(db_user.id, month)
    if alerts:
        msg += "\n\n" + "\n".join(alerts)

    keyboard = month_selector_keyboard(month)

    if edit and update.callback_query:
        await update.callback_query.edit_message_text(
            msg,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
    else:
        await update.effective_message.reply_text(
            msg,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )

        # Consejo financiero (solo en consulta fresca, no en navegación)
        if not edit and (summary["income"] > 0 or summary["expense"] > 0):
            await update.effective_message.reply_text("💡 Generando consejo financiero… ⏳")
            advice = await generate_financial_advice(summary)
            await update.effective_message.reply_text(
                f"💡 *Consejo del mes:*\n\n{advice}",
                parse_mode="Markdown",
            )


summary_handler = CommandHandler("resumen", show_summary)
summary_callback = CallbackQueryHandler(summary_month_callback, pattern=r"^month:")
