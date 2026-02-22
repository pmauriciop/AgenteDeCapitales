"""
bot/handlers/pdf.py
────────────────────
Handler para archivos PDF enviados al bot.
Procesa resúmenes de tarjeta de crédito y otros documentos financieros.

Flujo:
  1. El usuario envía un PDF como documento.
  2. Se extrae el texto con pdfplumber.
  3. GPT identifica todas las transacciones en el documento.
  4. Se muestran al usuario para confirmación antes de guardar.
  5. Con un botón, el usuario importa todas o descarta.
"""

import logging
import os
import tempfile

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, CallbackQueryHandler, filters

from ai.pdf_parser import parse_pdf_transactions, summarize_pdf_statement
from database.repositories import UserRepo
from services.transaction_service import TransactionService
from bot.keyboards import main_menu

logger = logging.getLogger(__name__)


async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Procesa un PDF enviado como documento."""
    document = update.message.document

    # Solo procesar PDFs
    if not document or not (
        document.mime_type == "application/pdf"
        or (document.file_name or "").lower().endswith(".pdf")
    ):
        return

    await update.message.reply_text(
        "📄 Analizando el documento PDF… ⏳\n"
        "Esto puede tardar unos segundos."
    )

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        # Descargar PDF
        file = await context.bot.get_file(document.file_id)
        await file.download_to_drive(tmp_path)

        # Extraer resumen general
        summary_text = await summarize_pdf_statement(tmp_path)
        await update.message.reply_text(
            f"📋 *Resumen del documento:*\n\n{summary_text}",
            parse_mode="Markdown",
        )

        # Extraer transacciones
        transactions = await parse_pdf_transactions(tmp_path)

        if not transactions:
            await update.message.reply_text(
                "🤔 No encontré transacciones en este PDF.\n"
                "Asegurate de que sea un resumen de tarjeta o extracto bancario.",
                reply_markup=main_menu(),
            )
            return

        # Guardar transacciones pendientes en user_data
        context.user_data["pending_pdf_txs"] = transactions
        count = len(transactions)
        total_expense = sum(t["amount"] for t in transactions if t["type"] == "expense")
        total_income = sum(t["amount"] for t in transactions if t["type"] == "income")

        # Mostrar preview de las primeras 5
        preview_lines = [f"💾 *Encontré {count} transacciones:*\n"]
        for tx in transactions[:5]:
            emoji = "💰" if tx["type"] == "income" else "💸"
            sign = "+" if tx["type"] == "income" else "-"
            preview_lines.append(
                f"{emoji} `{tx['date']}` {tx['description'][:30]} — "
                f"`{sign}${tx['amount']:,.2f}`"
            )
        if count > 5:
            preview_lines.append(f"_...y {count - 5} más_")

        preview_lines.append(f"\n💸 Total gastos: `${total_expense:,.2f}`")
        if total_income > 0:
            preview_lines.append(f"💰 Total ingresos: `${total_income:,.2f}`")

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    f"✅ Importar todas ({count})",
                    callback_data="pdf_import_all",
                ),
                InlineKeyboardButton("❌ Cancelar", callback_data="pdf_cancel"),
            ]
        ])

        await update.message.reply_text(
            "\n".join(preview_lines),
            parse_mode="Markdown",
            reply_markup=keyboard,
        )

    except Exception as e:
        logger.error("Error procesando PDF: %s", e)
        await update.message.reply_text(
            "❌ Hubo un error al procesar el PDF. Verificá que sea un documento válido.",
            reply_markup=main_menu(),
        )
    finally:
        os.unlink(tmp_path)


async def handle_pdf_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Procesa la confirmación/cancelación de importación del PDF."""
    query = update.callback_query
    await query.answer()

    if query.data == "pdf_cancel":
        context.user_data.pop("pending_pdf_txs", None)
        await query.edit_message_text("❌ Importación cancelada.")
        return

    if query.data == "pdf_import_all":
        transactions = context.user_data.pop("pending_pdf_txs", [])
        if not transactions:
            await query.edit_message_text("❌ No hay transacciones pendientes.")
            return

        db_user, _ = UserRepo.get_or_create(
            telegram_id=update.effective_user.id,
            name=update.effective_user.full_name,
        )

        saved_count = 0
        errors = 0
        for tx_data in transactions:
            try:
                TransactionService.add_from_parsed(db_user.id, tx_data)
                saved_count += 1
            except Exception as e:
                logger.error("Error guardando TX del PDF: %s", e)
                errors += 1

        msg = f"✅ *Importación completada*\n\n• Guardadas: `{saved_count}`"
        if errors:
            msg += f"\n• Errores: `{errors}`"

        await query.edit_message_text(msg, parse_mode="Markdown")


# ── Handlers exportables ──────────────────────────────────

pdf_handler = MessageHandler(
    filters.Document.MimeType("application/pdf") | filters.Document.FileExtension("pdf"),
    handle_pdf,
)

pdf_callback_handler = CallbackQueryHandler(
    handle_pdf_callback,
    pattern=r"^pdf_(import_all|cancel)$",
)
