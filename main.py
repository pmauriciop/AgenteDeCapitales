"""
main.py
────────
Punto de entrada del Agente de Capitales.
Inicializa el logging, crea la aplicación y lanza el polling.

Uso:
    python main.py
"""

import logging
import sys
import warnings
from config import LOG_LEVEL, ENV
from bot.app import create_app

# Suprimir PTBUserWarning de ConversationHandler (comportamiento esperado para
# handlers mixtos MessageHandler + CallbackQueryHandler)
warnings.filterwarnings("ignore", category=UserWarning, module="telegram")


def setup_logging() -> None:
    """Configura el sistema de logging."""
    level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    formatter = logging.Formatter(fmt)

    # Handler a archivo (siempre funciona, sin problemas de encoding)
    file_handler = logging.FileHandler("bot.log", encoding="utf-8", mode="a")
    file_handler.setFormatter(formatter)

    # Handler a consola — usamos reconfigure si está disponible (Python 3.7+)
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
