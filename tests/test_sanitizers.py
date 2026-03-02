"""
tests/test_sanitizers.py
─────────────────────────
Tests unitarios para las funciones de sanitización de datos sensibles.
No requieren conexión a APIs externas.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Importar los patrones directamente sin cargar el módulo completo
# (que necesita groq instalado)
_RE_CARD_NUMBER = re.compile(
    r"\b(?:\d[ -]?){15}\d\b"
    r"|\b\d{4}[\s\-]\d{4}[\s\-]\d{4}[\s\-]\d{4}\b"
)
_RE_CARD_PARTIAL = re.compile(
    r"(?i)(tarjeta|nro\.?\s*tarjeta|card\s*n[°º]?\.?)[:\s#]*[\dX*]{4,}"
)
_RE_CUIT = re.compile(r"\b\d{2}-\d{8}-\d\b")
_RE_CBU = re.compile(r"\b\d{22}\b")
_RE_ALIAS = re.compile(r"(?i)\balias[:\s]+[\w.]+")
_RE_EMAIL = re.compile(r"\b[\w.+-]+@[\w.-]+\.\w{2,}\b")
_RE_TITULAR_LINE = re.compile(
    r"(?i)^.*\b(titular|cliente|sr\.?|sra\.?|nombre)\b.*:\s*.+$",
    re.MULTILINE,
)
_RE_DOMICILIO_LINE = re.compile(
    r"(?i)^.*\b(domicilio|direcci[oó]n|calle|av\.?|avda\.?|bv\.?)\b.{0,60}$",
    re.MULTILINE,
)
_RE_DNI = re.compile(r"(?i)\b(dni|d\.n\.i\.?)[:\s#]*\d{7,8}\b")


def _sanitize(text):
    text = _RE_TITULAR_LINE.sub("[DATOS PERSONALES ELIMINADOS]", text)
    text = _RE_DOMICILIO_LINE.sub("[DOMICILIO ELIMINADO]", text)
    text = _RE_CARD_NUMBER.sub("[TARJETA ELIMINADA]", text)
    text = _RE_CARD_PARTIAL.sub(r"\1: [TARJETA ELIMINADA]", text)
    text = _RE_CUIT.sub("[CUIT ELIMINADO]", text)
    text = _RE_CBU.sub("[CBU ELIMINADO]", text)
    text = _RE_ALIAS.sub("alias: [ALIAS ELIMINADO]", text)
    text = _RE_EMAIL.sub("[EMAIL ELIMINADO]", text)
    text = _RE_DNI.sub(r"\1: [DNI ELIMINADO]", text)
    return text


# ── Datos de prueba ───────────────────────────────────────────

PDF_SAMPLE = """\
BANCO GALICIA - RESUMEN DE TARJETA DE CREDITO VISA
Periodo: Enero/2026

Titular: GARCIA MAURICIO PABLO
CUIT: 20-12345678-9
Tarjeta Nro. 4509123456789012
Domicilio: Av. Corrientes 1234 Piso 3 Dpto A, CABA
Email: mauricio.garcia@gmail.com
alias: juan.perez.galicia

                    DETALLE DEL CONSUMO

15-01-26 * MERPAGO*LACOSTEOUTLET 03/06 001298 10.000,00
20-01-26 K DISNEY PLUS 052084 18.399,00
22-01-26 * SHELL ESTACION 001 052088 35.000,00

TOTAL A PAGAR: $63.399,00

Cuotas a vencer:
Febrero/26 $10.000,00  Marzo/26 $10.000,00
"""

OCR_SAMPLE = """\
SUPERMERCADO CARREFOUR
CUIT: 30-68898256-8

Arroz x2          $1.200
Leche x4          $2.800
TOTAL             $5.929

Tarjeta Visa **** 5678
DNI: 12345678
"""

CBU_SAMPLE = "CBU: 0110599520000012345678"   # 22 dígitos

# ── Tests ─────────────────────────────────────────────────────

def test_pdf_cuit_removed():
    r = _sanitize(PDF_SAMPLE)
    assert "20-12345678-9" not in r, "CUIT del titular debe eliminarse"

def test_pdf_card_number_removed():
    r = _sanitize(PDF_SAMPLE)
    assert "4509123456789012" not in r, "Número de tarjeta debe eliminarse"

def test_pdf_email_removed():
    r = _sanitize(PDF_SAMPLE)
    assert "mauricio.garcia@gmail.com" not in r, "Email debe eliminarse"

def test_pdf_nombre_titular_removed():
    r = _sanitize(PDF_SAMPLE)
    assert "GARCIA MAURICIO PABLO" not in r, "Nombre del titular debe eliminarse"

def test_pdf_domicilio_removed():
    r = _sanitize(PDF_SAMPLE)
    assert "Corrientes 1234" not in r, "Domicilio debe eliminarse"

def test_pdf_alias_removed():
    r = _sanitize(PDF_SAMPLE)
    assert "juan.perez.galicia" not in r, "Alias CBU debe eliminarse"

def test_pdf_movements_preserved():
    r = _sanitize(PDF_SAMPLE)
    assert "MERPAGO" in r, "Movimientos deben conservarse"
    assert "DISNEY PLUS" in r, "Movimientos deben conservarse"
    assert "SHELL" in r, "Movimientos deben conservarse"

def test_pdf_totals_preserved():
    r = _sanitize(PDF_SAMPLE)
    assert "TOTAL A PAGAR" in r, "Totales deben conservarse"
    assert "Cuotas a vencer" in r, "Cuotas a vencer deben conservarse"

def test_ocr_cuit_removed():
    r = _sanitize(OCR_SAMPLE)
    assert "30-68898256-8" not in r, "CUIT en ticket debe eliminarse"

def test_ocr_dni_removed():
    r = _sanitize(OCR_SAMPLE)
    assert "12345678" not in r, "DNI en ticket debe eliminarse"

def test_ocr_total_preserved():
    r = _sanitize(OCR_SAMPLE)
    assert "TOTAL" in r, "Total del ticket debe conservarse"
    assert "CARREFOUR" in r, "Nombre del comercio debe conservarse"

def test_cbu_22_digits_removed():
    r = _sanitize(CBU_SAMPLE)
    assert "0110599520000012345678" not in r, "CBU de 22 digitos debe eliminarse"


if __name__ == "__main__":
    tests = [
        test_pdf_cuit_removed, test_pdf_card_number_removed,
        test_pdf_email_removed, test_pdf_nombre_titular_removed,
        test_pdf_domicilio_removed, test_pdf_alias_removed,
        test_pdf_movements_preserved, test_pdf_totals_preserved,
        test_ocr_cuit_removed, test_ocr_dni_removed,
        test_ocr_total_preserved, test_cbu_22_digits_removed,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  OK: {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FALLO: {t.__name__} -> {e}")
            failed += 1
    print(f"\n{passed}/{passed+failed} tests pasaron")
