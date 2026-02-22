"""
bot/handlers/start.py
──────────────────────
Handler del comando /start y /help.
Registra al usuario en la DB la primera vez y muestra el menú principal.
"""

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

from database.repositories import UserRepo
from bot.keyboards import main_menu


WELCOME_TEXT = """👋 ¡Hola, *{name}*! Soy tu *Agente de Capitales*.

Te ayudo a registrar y analizar tus finanzas personales de forma sencilla.

*¿Qué puedo hacer por vos?*
💸 Registrar gastos e ingresos (texto, voz o foto de ticket)
📊 Ver tu resumen mensual
💼 Gestionar presupuestos por categoría
🔁 Configurar gastos recurrentes
📄 Generar reportes PDF

*¿Cómo empezar?*
Solo escribime naturalmente, por ejemplo:
• _"Gasté $500 en el supermercado"_
• _"Cobré el sueldo, $150.000"_
• O usá los botones del menú 👇"""

HELP_TEXT = """🆘 *Comandos disponibles:*

/start — Menú principal
/resumen — Resumen del mes actual
/historial — Últimas transacciones
/presupuesto — Ver/configurar presupuestos
/recurrentes — Gestionar recurrentes
/reporte — Generar PDF mensual
/ayuda — Este mensaje

*También podés:*
🎤 Enviar un mensaje de voz
📷 Fotografiar un ticket o recibo
✍️ Escribir en lenguaje natural"""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    db_user, created = UserRepo.get_or_create(
        telegram_id=user.id,
        name=user.full_name,
    )

    greeting = WELCOME_TEXT.format(name=user.first_name)
    if not created:
        greeting = f"👋 ¡Bienvenido de vuelta, *{user.first_name}*!\n\nUsá el menú para gestionar tus finanzas 👇"

    await update.message.reply_text(
        greeting,
        parse_mode="Markdown",
        reply_markup=main_menu(),
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown", reply_markup=main_menu())


start_handler = CommandHandler(["start"], start)
help_handler = CommandHandler(["ayuda", "help"], help_cmd)
