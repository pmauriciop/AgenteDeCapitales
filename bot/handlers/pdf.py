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

import asyncio
import logging
import os
import tempfile

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import RetryAfter
from telegram.ext import CallbackQueryHandler, ContextTypes, MessageHandler, filters

from ai.pdf_parser import extract_full_content, parse_pdf_transactions, summarize_pdf_statement
from bot.keyboards import main_menu
from database.repositories import UserRepo
from services.transaction_service import TransactionService

logger = logging.getLogger(__name__)


async def _send_safe(message, text: str, **kwargs) -> None:
    """Envía un mensaje respetando el flood control de Telegram (hasta 3 reintentos)."""
    for attempt in range(3):
        try:
            await message.reply_text(text, **kwargs)
            return
        except RetryAfter as e:
            wait = e.retry_after + 2
            logger.warning("Flood control (intento %d): esperando %ds...", attempt + 1, wait)
            await asyncio.sleep(wait)
        except Exception as e:
            logger.error("Error enviando mensaje (intento %d): %s - %s", attempt + 1, type(e).__name__, e)
            await asyncio.sleep(2)
    logger.error("No se pudo enviar el mensaje después de 3 intentos")


async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Procesa un PDF enviado como documento."""
    document = update.message.document

    # Solo procesar PDFs
    if not document or not (
        document.mime_type == "application/pdf"
        or (document.file_name or "").lower().endswith(".pdf")
    ):
        return

    await _send_safe(
        update.message,
        "📄 Analizando el documento PDF… ⏳\n"
        "Esto puede tardar unos segundos."
    )

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        # Descargar PDF
        logger.info("Descargando PDF...")
        file = await context.bot.get_file(document.file_id)
        await file.download_to_drive(tmp_path)
        logger.info("PDF descargado en %s", tmp_path)

        # Extraer contenido una sola vez (evita doble lectura)
        content = extract_full_content(tmp_path)
        logger.info("Contenido extraído, enviando a Groq...")

        # Resumen y transacciones en paralelo
        try:
            summary_text, transactions = await asyncio.gather(
                summarize_pdf_statement(tmp_path, content=content),
                parse_pdf_transactions(tmp_path, content=content),
            )
        except Exception as groq_err:
            logger.error("Error en Groq: %s", groq_err, exc_info=True)
            await _send_safe(
                update.message,
                "❌ Error al analizar el PDF con IA. Intentá de nuevo.",
                reply_markup=main_menu(),
            )
            return

        logger.info("Groq respondió: %d transacciones", len(transactions))

        # Enviar resumen en texto plano
        logger.info("Enviando resumen al usuario...")
        await _send_safe(update.message, f"📋 Resumen del documento:\n\n{summary_text}")
        logger.info("Resumen enviado OK")

        if not transactions:
            await _send_safe(
                update.message,
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
        preview_lines = [f"Encontre {count} transacciones:\n"]
        for tx in transactions[:5]:
            emoji = "+" if tx["type"] == "income" else "-"
            desc = tx['description'][:30]
            date_str = str(tx['date'])
            amount_str = f"{emoji}${tx['amount']:,.2f}"
            cuota_str = ""
            if tx.get("installment_total"):
                rem = tx.get("installments_remaining", "?")
                cuota_str = f" [cuota {tx['installment_current']}/{tx['installment_total']}, restan {rem}]"
            preview_lines.append(f"{date_str}  {desc}{cuota_str}  {amount_str}")
        if count > 5:
            preview_lines.append(f"...y {count - 5} mas")

        preview_lines.append(f"\nTotal gastos: ${total_expense:,.2f}")
        if total_income > 0:
            preview_lines.append(f"Total ingresos: ${total_income:,.2f}")

        preview_text = "\n".join(preview_lines)
        logger.info("Preview construido (%d chars)", len(preview_text))

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    f"Importar todas ({count})",
                    callback_data="pdf_import_all",
                ),
                InlineKeyboardButton("Cancelar", callback_data="pdf_cancel"),
            ]
        ])

        logger.info("Enviando preview al usuario...")
        try:
            await _send_safe(
                update.message,
                preview_text,
                reply_markup=keyboard,
            )
            logger.info("Preview enviado OK")
        except Exception as preview_err:
            logger.error("CRASH EN PREVIEW SEND: %s - %s", type(preview_err).__name__, preview_err, exc_info=True)

    except Exception as e:
        logger.error("Error procesando PDF: %s", e, exc_info=True)
        try:
            await _send_safe(
                update.message,
                "❌ Hubo un error al procesar el PDF. Verificá que sea un documento válido.",
                reply_markup=main_menu(),
            )
        except Exception:
            pass
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


async def handle_pdf_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Procesa la confirmación/cancelación de importación del PDF."""
    try:
        query = update.callback_query
        logger.info("Callback recibido: %s", query.data)
        await query.answer()
        logger.info("query.answer() OK")

        if query.data == "pdf_cancel":
            context.user_data.pop("pending_pdf_txs", None)
            await query.edit_message_text("Importacion cancelada.")
            return

        if query.data == "pdf_import_all":
            transactions = context.user_data.pop("pending_pdf_txs", [])
            logger.info("Transacciones pendientes: %d", len(transactions))

            if not transactions:
                await query.edit_message_text("No hay transacciones pendientes.")
                return

            logger.info("Obteniendo usuario de DB...")
            db_user, _ = UserRepo.get_or_create(
                telegram_id=update.effective_user.id,
                name=update.effective_user.full_name,
            )
            logger.info("Usuario OK: %s", db_user.id)

            saved_count = 0
            skipped_count = 0
            errors = 0
            for tx_data in transactions:
                try:
                    _, created = TransactionService.add_from_parsed(db_user.id, tx_data)
                    if created:
                        saved_count += 1
                    else:
                        skipped_count += 1
                except Exception as e:
                    logger.error("Error guardando TX del PDF: %s - %s", type(e).__name__, e, exc_info=True)
                    errors += 1

            logger.info("Guardado: %d nuevas, %d duplicadas, %d errores", saved_count, skipped_count, errors)
            msg = f"Importacion completada\n\nNuevas: {saved_count}"
            if skipped_count:
                msg += f"\nYa existian: {skipped_count}"
            if errors:
                msg += f"\nErrores: {errors}"

            await query.edit_message_text(msg)
            logger.info("Callback completado OK")

    except Exception as e:
        logger.error("CRASH EN CALLBACK: %s - %s", type(e).__name__, e, exc_info=True)
        try:
            await update.callback_query.edit_message_text("Error al procesar. Intenta de nuevo.")
        except Exception:
            pass


# ── Handlers exportables ──────────────────────────────────

pdf_handler = MessageHandler(
    filters.Document.MimeType("application/pdf") | filters.Document.FileExtension("pdf"),
    handle_pdf,
)

pdf_callback_handler = CallbackQueryHandler(
    handle_pdf_callback,
    pattern=r"^pdf_(import_all|cancel)$",
)
