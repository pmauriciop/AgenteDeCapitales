"""
bot/handlers/messages.py
─────────────────────────
Handler de mensajes de texto libre.
Usa NLP para detectar intención y parsear transacciones.
"""

import logging
from datetime import date

from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

from ai.nlp import classify_intent, parse_transaction
from database.repositories import UserRepo, TransactionRepo
from database.models import Transaction
from services.transaction_service import TransactionService
from services.budget_service import BudgetService
from services.analyst_service import AnalystService
from bot.keyboards import main_menu, confirm_transaction_keyboard

logger = logging.getLogger(__name__)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Procesa mensajes de texto:
    1. Mapea botones del menú principal.
    2. Si no es un botón, usa NLP para detectar la intención.
    """
    text = update.message.text.strip()
    user = update.effective_user

    # ── Botones del menú principal ────────────────────────
    menu_routes = {
        "💸 Gasto":       _trigger_expense,
        "💰 Ingreso":     _trigger_income,
        "📊 Resumen":     _show_summary,
        "💼 Presupuestos": _show_budgets,
        "📋 Historial":   _show_history,
        "🔁 Recurrentes": _show_recurring,
        "📄 Reporte PDF": _request_report,
        "❓ Ayuda":       _show_help,
    }

    if text in menu_routes:
        await menu_routes[text](update, context)
        return

    # ── NLP: intentar parsear transacción ─────────────────
    await update.message.chat.send_action("typing")

    intent = await classify_intent(text)
    logger.info("Intent detectado: %s para user %s", intent, user.id)

    if intent in ("add_expense", "add_income"):
        parsed = await parse_transaction(text)
        if parsed:
            await _save_and_confirm(update, context, parsed)
            return

    if intent == "get_summary":
        await _show_summary(update, context)
        return

    if intent == "get_budget":
        await _show_budgets(update, context)
        return

    if intent == "list_transactions":
        await _show_history(update, context)
        return

    if intent == "get_report":
        await _request_report(update, context)
        return

    if intent == "help":
        await _show_help(update, context)
        return

    # ── Analista IA: preguntas sobre los datos del usuario ─
    is_question = await AnalystService.is_analyst_question(text)
    if is_question:
        await _answer_with_analyst(update, context, text)
        return

    # ── Fallback ──────────────────────────────────────────
    await update.message.reply_text(
        "🤔 No entendí tu mensaje. Podés:\n"
        "• Escribir algo como \"Gasté $200 en el colectivo\"\n"
        "• Hacer preguntas como \"¿cuánto gasté este mes?\" o \"proyectá mis gastos\"\n"
        "• Usar los botones del menú\n"
        "• Enviar un mensaje de voz o foto de ticket",
        reply_markup=main_menu(),
    )


async def _answer_with_analyst(update: Update, context: ContextTypes.DEFAULT_TYPE, question: str) -> None:
    """Consulta al analista IA con el contexto financiero completo del usuario."""
    db_user, _ = UserRepo.get_or_create(
        telegram_id=update.effective_user.id,
        name=update.effective_user.full_name,
    )
    await update.message.chat.send_action("typing")
    answer = await AnalystService.answer(
        user_id=db_user.id,
        user_name=update.effective_user.full_name,
        question=question,
    )
    await update.message.reply_text(answer, reply_markup=main_menu())


async def _save_and_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE, parsed: dict) -> None:
    """Guarda la transacción y muestra confirmación."""
    db_user, _ = UserRepo.get_or_create(
        telegram_id=update.effective_user.id,
        name=update.effective_user.full_name,
    )

    tx = TransactionService.add_from_parsed(db_user.id, parsed)

    # Verificar alertas de presupuesto
    alert_msg = ""
    if tx.type == "expense":
        status = BudgetService.check_overspent(db_user.id, tx.category)
        if status and status["percentage"] >= 80:
            pct = status["percentage"]
            alert_msg = (
                f"\n\n⚠️ *Alerta de presupuesto:* estás al *{pct:.0f}%* "
                f"en _{tx.category}_ este mes."
            )

    tipo = "Ingreso" if tx.type == "income" else "Gasto"
    emoji = "💰" if tx.type == "income" else "💸"
    sign = "+" if tx.type == "income" else "-"

    msg = (
        f"{emoji} *{tipo} registrado*\n\n"
        f"• Monto: `{sign}${tx.amount:,.2f}`\n"
        f"• Categoría: _{tx.category.capitalize()}_\n"
        f"• Descripción: _{tx.description}_\n"
        f"• Fecha: `{tx.date}`"
        f"{alert_msg}"
    )

    await update.message.reply_text(
        msg,
        parse_mode="Markdown",
        reply_markup=confirm_transaction_keyboard(tx.id),
    )


# ── Triggers de secciones ────────────────────────────────

async def _trigger_expense(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["pending_type"] = "expense"
    await update.message.reply_text(
        "💸 *Registrar gasto*\n\nEscribime el monto o describí el gasto, por ejemplo:\n"
        "_\"Gasté $1.200 en el supermercado\"_\n\n"
        "O escribí solo el monto y te pregunto el resto:",
        parse_mode="Markdown",
    )


async def _trigger_income(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["pending_type"] = "income"
    await update.message.reply_text(
        "💰 *Registrar ingreso*\n\nEscribime el monto o describí el ingreso, por ejemplo:\n"
        "_\"Cobré $80.000 de sueldo\"_",
        parse_mode="Markdown",
    )


async def _show_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db_user, _ = UserRepo.get_or_create(
        telegram_id=update.effective_user.id,
        name=update.effective_user.full_name,
    )
    month = date.today().strftime("%Y-%m")
    summary = TransactionService.get_monthly_summary(db_user.id, month)
    msg = TransactionService.format_summary_message(summary)
    await update.message.reply_text(msg, parse_mode="Markdown")


async def _show_budgets(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db_user, _ = UserRepo.get_or_create(
        telegram_id=update.effective_user.id,
        name=update.effective_user.full_name,
    )
    month = date.today().strftime("%Y-%m")
    statuses = BudgetService.get_status(db_user.id, month)
    msg = BudgetService.format_budget_status(statuses, month)
    await update.message.reply_text(msg, parse_mode="Markdown")


async def _show_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db_user, _ = UserRepo.get_or_create(
        telegram_id=update.effective_user.id,
        name=update.effective_user.full_name,
    )
    txs = TransactionService.list_recent(db_user.id)
    msg = TransactionService.format_transaction_list(txs)
    await update.message.reply_text(msg, parse_mode="Markdown")


async def _show_recurring(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from services.recurring_service import RecurringService
    db_user, _ = UserRepo.get_or_create(
        telegram_id=update.effective_user.id,
        name=update.effective_user.full_name,
    )
    recs = RecurringService.list_active(db_user.id)
    msg = RecurringService.format_recurring_list(recs)
    await update.message.reply_text(msg, parse_mode="Markdown")


async def _request_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📄 Generando tu reporte PDF… ⏳",
        parse_mode="Markdown",
    )
    from reports.pdf_generator import generate_monthly_report
    from telegram import InputFile
    import os

    db_user, _ = UserRepo.get_or_create(
        telegram_id=update.effective_user.id,
        name=update.effective_user.full_name,
    )
    month = date.today().strftime("%Y-%m")
    pdf_path = await generate_monthly_report(
        user_id=db_user.id,
        month=month,
        user_name=update.effective_user.full_name,
    )
    with open(pdf_path, "rb") as f:
        await update.message.reply_document(
            document=f,
            filename=f"reporte_{month}.pdf",
            caption=f"📄 Reporte financiero de *{month}*",
            parse_mode="Markdown",
        )
    os.unlink(pdf_path)


async def _show_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from bot.handlers.start import HELP_TEXT
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown", reply_markup=main_menu())


message_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)
