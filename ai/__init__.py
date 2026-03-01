"""
ai/__init__.py
──────────────
Expone los componentes del módulo de inteligencia artificial.

Los imports son lazy (se resuelven al momento de uso) para que los tests
puedan hacer mock del cliente Groq antes de que el módulo lo instancie.
"""

# No importar nada a nivel de módulo: los módulos de IA instancian clientes
# externos (Groq, Supabase) al importarse, lo que rompe los mocks en tests.
# Los consumidores deben importar directamente desde el submódulo:
#   from ai.nlp import parse_transaction
#   from ai.ocr import parse_receipt
#   etc.

__all__ = [
    "parse_transaction",
    "classify_intent",
    "transcribe_audio",
    "extract_text_from_image",
    "parse_receipt",
    "parse_pdf_transactions",
    "summarize_pdf_statement",
]
