"""
bot/handlers/voice.py
──────────────────────
Handler para mensajes de voz.
Descarga el archivo OGG de Telegram, lo transcribe con Whisper
y luego lo procesa como texto libre.
"""

import logging
import os
import tempfile

from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

from ai.transcriber import transcribe_audio
from ai.nlp import parse_transaction
from database.repositories import UserRepo
from services.transaction_service import TransactionService
from services.budget_service import BudgetService
from bot.keyboards import confirm_transaction_keyboard, main_menu

logger = logging.getLogger(__name__)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Procesa mensajes de voz: transcribe → parsea → guarda."""
    await update.message.reply_text("🎤 Transcribiendo tu audio… ⏳")

    voice = update.message.voice or update.message.audio
    if not voice:
        await update.message.reply_text("❌ No pude procesar el audio.")
        return

    # Descargar el archivo
    file = await context.bot.get_file(voice.file_id)
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        await file.download_to_drive(tmp_path)

        # Transcribir
        text = await transcribe_audio(tmp_path)
        logger.info("Transcripción: %s", text)

        await update.message.reply_text(f"🎙️ Entendí: _{text}_", parse_mode="Markdown")

        # Parsear como transacción
        parsed = await parse_transaction(text)
        if not parsed:
            await update.message.reply_text(
                "🤔 No detecté una transacción en tu mensaje de voz.\n"
                "Intentá con algo como: _\"Gasté doscientos pesos en el colectivo\"_",
                parse_mode="Markdown",
            )
            return

        # Guardar y confirmar
        db_user, _ = UserRepo.get_or_create(
            telegram_id=update.effective_user.id,
            name=update.effective_user.full_name,
        )
        tx = TransactionService.add_from_parsed(db_user.id, parsed)

        # Alertas de presupuesto
        alert_msg = ""
        if tx.type == "expense":
            status = BudgetService.check_overspent(db_user.id, tx.category)
            if status and status["percentage"] >= 80:
                alert_msg = (
                    f"\n\n⚠️ *Alerta:* estás al *{status['percentage']:.0f}%* "
                    f"del presupuesto en _{tx.category}_."
                )

        tipo = "Ingreso" if tx.type == "income" else "Gasto"
        emoji = "💰" if tx.type == "income" else "💸"
        sign = "+" if tx.type == "income" else "-"

        msg = (
            f"{emoji} *{tipo} registrado por voz*\n\n"
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

    except Exception as e:
        logger.error("Error procesando voz: %s", e)
        await update.message.reply_text(
            "❌ Ocurrió un error al procesar tu audio. Por favor intentá de nuevo.",
            reply_markup=main_menu(),
        )
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


voice_handler = MessageHandler(filters.VOICE | filters.AUDIO, handle_voice)
