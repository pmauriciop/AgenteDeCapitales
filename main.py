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
from config import LOG_LEVEL, ENV
from bot.app import create_app


def setup_logging() -> None:
    """Configura el sistema de logging."""
    level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    logging.basicConfig(
        level=level,
        format=fmt,
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )
    # Reducir verbosidad de librerías externas
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)


def main() -> None:
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("🚀 Iniciando Agente de Capitales (ENV=%s)...", ENV)

    app = create_app()

    logger.info("✅ Bot en línea. Escuchando mensajes...")
    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=["message", "callback_query", "edited_message"],
    )


if __name__ == "__main__":
    main()
