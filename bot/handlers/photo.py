"""
bot/handlers/photo.py
──────────────────────
Handler para fotos (tickets, facturas, recibos).
Descarga la imagen, la analiza con GPT-4o Vision
y registra el gasto detectado.
"""

import logging
import os
import tempfile

from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

from ai.ocr import parse_receipt
from bot.keyboards import confirm_transaction_keyboard, main_menu
from database.repositories import UserRepo
from services.budget_service import BudgetService
from services.transaction_service import TransactionService

logger = logging.getLogger(__name__)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Procesa fotos de tickets: OCR con Vision → guarda gasto."""
    await update.message.reply_text("📷 Analizando el ticket… ⏳")

    # Obtener la foto de mayor resolución
    photo = update.message.photo[-1] if update.message.photo else None
    document = update.message.document

    if not photo and not document:
        await update.message.reply_text("❌ No pude procesar la imagen.")
        return

    # Determinar extensión
    if document:
        ext = os.path.splitext(document.file_name or "img.jpg")[1] or ".jpg"
        file_obj = document
    else:
        ext = ".jpg"
        file_obj = photo

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp_path = tmp.name

    try:
        file = await context.bot.get_file(file_obj.file_id)
        await file.download_to_drive(tmp_path)

        # Analizar con OCR / Vision
        parsed = await parse_receipt(tmp_path)

        if not parsed:
            await update.message.reply_text(
                "🤔 No pude identificar datos financieros en esta imagen.\n"
                "Asegurate de que sea un ticket o recibo claro.",
                reply_markup=main_menu(),
            )
            return

        # Guardar transacción
        db_user, _ = UserRepo.get_or_create(
            telegram_id=update.effective_user.id,
            name=update.effective_user.full_name,
        )
        tx = TransactionService.add_from_parsed(db_user.id, parsed)

        # Alertas de presupuesto
        alert_msg = ""
        status = BudgetService.check_overspent(db_user.id, tx.category)
        if status and status["percentage"] >= 80:
            alert_msg = (
                f"\n\n⚠️ *Alerta:* estás al *{status['percentage']:.0f}%* "
                f"del presupuesto en _{tx.category}_."
            )

        msg = (
            f"🧾 *Ticket detectado*\n\n"
            f"• Monto: `${tx.amount:,.2f}`\n"
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

    except Exception as e:
        logger.error("Error procesando foto: %s", e)
        await update.message.reply_text(
            "❌ Error al procesar la imagen. Por favor intentá de nuevo.",
            reply_markup=main_menu(),
        )
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


photo_handler = MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_photo)
