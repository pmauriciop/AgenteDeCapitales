"""
bot/handlers/callbacks.py
──────────────────────────
Handler genérico para callbacks de botones inline que no
están cubiertos por los ConversationHandlers específicos.

Patrones manejados:
  - confirm_tx:<id>  → confirmar que la transacción ya fue guardada
  - delete_tx:<id>   → eliminar una transacción
  - cancel           → cancelar operación genérica
"""

from telegram import Update
from telegram.ext import CallbackQueryHandler, ContextTypes

from services.transaction_service import TransactionService


async def handle_generic_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data

    # ── Confirmar transacción (ya guardada, solo feedback) ──
    if data.startswith("confirm_tx:"):
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("✅ Transacción confirmada y guardada.")
        return

    # ── Eliminar transacción ──────────────────────────────
    if data.startswith("delete_tx:"):
        tx_id = data.split(":", 1)[1]
        success = TransactionService.delete(tx_id)
        if success:
            await query.edit_message_text("🗑️ Transacción eliminada.")
        else:
            await query.edit_message_text("❌ No se encontró la transacción.")
        return

    # ── Cancelar ──────────────────────────────────────────
    if data == "cancel":
        await query.edit_message_text("❌ Operación cancelada.")
        return


generic_callback_handler = CallbackQueryHandler(
    handle_generic_callback,
    pattern=r"^(confirm_tx:|delete_tx:|cancel$)",
)
