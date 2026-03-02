"""
main.py
────────
Punto de entrada del Agente de Capitales.
Inicializa el logging, crea la aplicación y lanza el polling.

Uso:
    python main.py
"""

import logging
import logging.handlers
import sys
import warnings

from bot.app import create_app
from config import ENV, LOG_LEVEL

# Suprimir PTBUserWarning de ConversationHandler (comportamiento esperado para
# handlers mixtos MessageHandler + CallbackQueryHandler)
warnings.filterwarnings("ignore", category=UserWarning, module="telegram")


def setup_logging() -> None:
    """Configura el sistema de logging con rotación automática de archivos."""
    level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    formatter = logging.Formatter(fmt)

    # Handler a archivo con rotación: máx 5 MB por archivo, mantiene 3 backups
    # → bot.log, bot.log.1, bot.log.2  (máx ~15 MB en disco)
    file_handler = logging.handlers.RotatingFileHandler(
        "bot.log",
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    # Handler a consola
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(file_handler)
    root.addHandler(console_handler)

    # Reducir verbosidad de librerías externas
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)


def main() -> None:
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("🚀 Iniciando Agente de Capitales (ENV=%s)...", ENV)

    app = create_app()

    logger.info("✅ Bot en línea. Escuchando mensajes...")
    try:
        app.run_polling(
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query", "edited_message"],
        )
    except Exception as e:
        logger.critical("💥 Bot detenido por excepción inesperada: %s", e, exc_info=True)
        raise


if __name__ == "__main__":
    main()
