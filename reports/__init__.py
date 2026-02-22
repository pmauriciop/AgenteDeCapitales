"""
reports/__init__.py
────────────────────
Módulo de generación de reportes financieros.
"""

from .pdf_generator import generate_monthly_report

__all__ = ["generate_monthly_report"]
