"""
bot/handlers/report.py
───────────────────────
Handler para generación y envío del reporte PDF mensual.
"""

import os
from datetime import date

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from bot.keyboards import main_menu
from database.repositories import UserRepo
from reports.pdf_generator import generate_monthly_report


async def send_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /reporte — genera y envía el PDF del mes actual."""
    db_user, _ = UserRepo.get_or_create(
        telegram_id=update.effective_user.id,
        name=update.effective_user.full_name,
    )

    month = date.today().strftime("%Y-%m")

    # Si se pasa el mes como argumento: /reporte 2026-01
    if context.args:
        arg = context.args[0]
        if len(arg) == 7 and arg[4] == "-":
            month = arg

    await update.message.reply_text(
        f"📄 Generando reporte de *{month}*… ⏳\n"
        "Esto puede tardar unos segundos.",
        parse_mode="Markdown",
    )

    try:
        pdf_path = await generate_monthly_report(
            user_id=db_user.id,
            month=month,
            user_name=update.effective_user.full_name,
        )

        with open(pdf_path, "rb") as f:
            await update.message.reply_document(
                document=f,
                filename=f"reporte_financiero_{month}.pdf",
                caption=(
                    f"📊 *Reporte financiero — {month}*\n"
                    f"Generado el {date.today().strftime('%d/%m/%Y')}"
                ),
                parse_mode="Markdown",
                reply_markup=main_menu(),
            )

        os.unlink(pdf_path)

    except Exception as e:
        await update.message.reply_text(
            f"❌ Error generando el reporte: {e}",
            reply_markup=main_menu(),
        )


report_handler = CommandHandler("reporte", send_report)
