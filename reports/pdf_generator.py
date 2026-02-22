"""
reports/pdf_generator.py
─────────────────────────
Genera reportes PDF mensuales con resumen financiero,
gráficos de categorías y tabla de transacciones.

Dependencias:
    - reportlab (PDF generation)
    - matplotlib (charts)

Uso:
    from reports.pdf_generator import generate_monthly_report

    path = await generate_monthly_report(user_id="uuid", month="2026-02")
    # retorna la ruta al PDF generado en /tmp/
"""

from __future__ import annotations
import io
import os
import tempfile
from datetime import date
from pathlib import Path
from typing import Optional

# ReportLab
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image as RLImage,
    HRFlowable,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# Matplotlib para gráficos
import matplotlib
matplotlib.use("Agg")  # sin GUI
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from database.repositories import TransactionRepo, BudgetRepo


# ─────────────────────────────────────────────
#  Paleta de colores
# ─────────────────────────────────────────────

PRIMARY = colors.HexColor("#1a56db")
SUCCESS = colors.HexColor("#057a55")
DANGER = colors.HexColor("#e02424")
WARNING = colors.HexColor("#c27803")
LIGHT_BG = colors.HexColor("#f9fafb")
BORDER = colors.HexColor("#e5e7eb")
TEXT = colors.HexColor("#111827")
TEXT_MUTED = colors.HexColor("#6b7280")


# ─────────────────────────────────────────────
#  generate_monthly_report
# ─────────────────────────────────────────────

async def generate_monthly_report(
    user_id: str,
    month: Optional[str] = None,
    user_name: str = "Usuario",
) -> str:
    """
    Genera un reporte PDF mensual y retorna la ruta del archivo.

    Args:
        user_id:   UUID del usuario en Supabase.
        month:     "YYYY-MM". Si es None usa el mes actual.
        user_name: Nombre del usuario para personalizar el reporte.

    Returns:
        Ruta absoluta al archivo PDF generado.
    """
    if not month:
        month = date.today().strftime("%Y-%m")

    # ── Obtener datos ──────────────────────────────────
    summary = TransactionRepo.get_summary(user_id, month)
    budgets = BudgetRepo.get_budget_status(user_id, month)
    transactions = summary.pop("transactions")

    income = summary["income"]
    expense = summary["expense"]
    balance = summary["balance"]

    # Breakdown por categoría
    category_totals: dict[str, float] = {}
    for tx in transactions:
        if tx.type == "expense":
            category_totals[tx.category] = category_totals.get(tx.category, 0) + tx.amount

    # ── Crear PDF ──────────────────────────────────────
    tmp_file = tempfile.NamedTemporaryFile(
        suffix=".pdf",
        prefix=f"reporte_{month}_",
        delete=False,
    )
    tmp_path = tmp_file.name
    tmp_file.close()

    doc = SimpleDocTemplate(
        tmp_path,
        pagesize=A4,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    story = []

    # ── Header ────────────────────────────────────────
    story.extend(_build_header(styles, user_name, month))
    story.append(Spacer(1, 0.4 * cm))

    # ── KPI cards ─────────────────────────────────────
    story.extend(_build_kpi_table(income, expense, balance))
    story.append(Spacer(1, 0.6 * cm))

    # ── Gráfico de torta (gastos por categoría) ───────
    if category_totals:
        chart_path = _build_pie_chart(category_totals, month)
        story.append(RLImage(chart_path, width=12 * cm, height=8 * cm))
        story.append(Spacer(1, 0.4 * cm))

    # ── Tabla de presupuestos ──────────────────────────
    if budgets:
        story.extend(_build_budget_table(styles, budgets))
        story.append(Spacer(1, 0.4 * cm))

    # ── Tabla de transacciones ─────────────────────────
    story.extend(_build_transactions_table(styles, transactions))

    # ── Footer ────────────────────────────────────────
    story.append(Spacer(1, 0.5 * cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
    generated_on = date.today().strftime("%d/%m/%Y")
    footer_style = ParagraphStyle("footer", parent=styles["Normal"],
                                  fontSize=8, textColor=TEXT_MUTED, alignment=TA_CENTER)
    story.append(Paragraph(f"Reporte generado el {generated_on} · AgenteDeCapitales", footer_style))

    doc.build(story)

    # Limpiar chart temporal
    if category_totals:
        os.unlink(chart_path)

    return tmp_path


# ─────────────────────────────────────────────
#  Helpers de construcción
# ─────────────────────────────────────────────

def _build_header(styles, user_name: str, month: str) -> list:
    """Header del reporte."""
    title_style = ParagraphStyle(
        "title",
        parent=styles["Title"],
        fontSize=20,
        textColor=PRIMARY,
        spaceAfter=4,
        alignment=TA_CENTER,
    )
    sub_style = ParagraphStyle(
        "subtitle",
        parent=styles["Normal"],
        fontSize=11,
        textColor=TEXT_MUTED,
        alignment=TA_CENTER,
    )
    year, m = month.split("-")
    month_names = {
        "01": "Enero", "02": "Febrero", "03": "Marzo",
        "04": "Abril", "05": "Mayo", "06": "Junio",
        "07": "Julio", "08": "Agosto", "09": "Septiembre",
        "10": "Octubre", "11": "Noviembre", "12": "Diciembre",
    }
    month_label = f"{month_names.get(m, m)} {year}"
    return [
        Paragraph("📊 Reporte Financiero Mensual", title_style),
        Paragraph(f"{user_name} · {month_label}", sub_style),
        HRFlowable(width="100%", thickness=1, color=PRIMARY),
    ]


def _build_kpi_table(income: float, expense: float, balance: float) -> list:
    """Tabla de KPIs principales."""
    balance_color = SUCCESS if balance >= 0 else DANGER
    sign = "+" if balance >= 0 else ""

    data = [
        [
            _kpi_cell("💰 Ingresos", f"${income:,.2f}", SUCCESS),
            _kpi_cell("💸 Gastos", f"${expense:,.2f}", DANGER),
            _kpi_cell("📈 Balance", f"{sign}${balance:,.2f}", balance_color),
        ]
    ]
    table = Table(data, colWidths=["33%", "33%", "34%"])
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BG),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [LIGHT_BG]),
        ("ROUNDEDCORNERS", [4]),
    ]))
    return [table]


def _kpi_cell(label: str, value: str, color) -> str:
    """Celda HTML para KPI."""
    return f'<font color="{color.hexval() if hasattr(color, "hexval") else "#000"}" size="14"><b>{value}</b></font><br/><font size="9" color="#6b7280">{label}</font>'


def _build_pie_chart(category_totals: dict[str, float], month: str) -> str:
    """Genera gráfico de torta y retorna la ruta del archivo temporal."""
    labels = list(category_totals.keys())
    values = list(category_totals.values())

    fig, ax = plt.subplots(figsize=(6, 4), facecolor="white")
    palette = plt.cm.Set3.colors
    wedge_colors = [palette[i % len(palette)] for i in range(len(labels))]

    wedges, texts, autotexts = ax.pie(
        values,
        labels=None,
        colors=wedge_colors,
        autopct="%1.1f%%",
        startangle=90,
        pctdistance=0.8,
    )
    for at in autotexts:
        at.set_fontsize(8)

    legend_labels = [f"{l.capitalize()} (${v:,.0f})" for l, v in zip(labels, values)]
    ax.legend(
        wedges,
        legend_labels,
        title="Categorías",
        loc="center left",
        bbox_to_anchor=(1, 0, 0.5, 1),
        fontsize=7,
    )
    ax.set_title(f"Distribución de gastos · {month}", fontsize=11, pad=10)
    plt.tight_layout()

    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    plt.savefig(tmp.name, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return tmp.name


def _build_budget_table(styles, budgets: list[dict]) -> list:
    """Tabla de estado de presupuestos."""
    heading_style = ParagraphStyle(
        "heading", parent=styles["Heading2"], fontSize=12, textColor=PRIMARY, spaceBefore=6
    )
    elements = [Paragraph("💼 Presupuestos", heading_style), Spacer(1, 0.2 * cm)]

    header = ["Categoría", "Presupuesto", "Gastado", "Restante", "%"]
    rows = [header]
    for b in budgets:
        pct = b["percentage"]
        pct_color = "red" if pct >= 100 else ("orange" if pct >= 80 else "green")
        rows.append([
            b["category"].capitalize(),
            f"${b['limit']:,.2f}",
            f"${b['spent']:,.2f}",
            f"${b['remaining']:,.2f}",
            f'<font color="{pct_color}"><b>{pct:.0f}%</b></font>',
        ])

    table = Table(rows, colWidths=[4 * cm, 3.5 * cm, 3.5 * cm, 3.5 * cm, 2 * cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_BG]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    elements.append(table)
    return elements


def _build_transactions_table(styles, transactions: list) -> list:
    """Tabla de transacciones del mes."""
    heading_style = ParagraphStyle(
        "heading2", parent=styles["Heading2"], fontSize=12, textColor=PRIMARY, spaceBefore=6
    )
    elements = [Paragraph("📋 Transacciones del mes", heading_style), Spacer(1, 0.2 * cm)]

    if not transactions:
        no_data_style = ParagraphStyle("nodata", parent=styles["Normal"],
                                        textColor=TEXT_MUTED, fontSize=9)
        elements.append(Paragraph("No hay transacciones registradas.", no_data_style))
        return elements

    header = ["Fecha", "Tipo", "Categoría", "Descripción", "Monto"]
    rows = [header]
    for tx in transactions[:50]:  # máximo 50 filas
        tipo = "Ingreso" if tx.type == "income" else "Gasto"
        color = "green" if tx.type == "income" else "red"
        sign = "+" if tx.type == "income" else "-"
        rows.append([
            str(tx.date),
            f'<font color="{color}">{tipo}</font>',
            tx.category.capitalize(),
            tx.description[:35] + ("…" if len(tx.description) > 35 else ""),
            f'<font color="{color}"><b>{sign}${tx.amount:,.2f}</b></font>',
        ])

    table = Table(rows, colWidths=[2.5 * cm, 2 * cm, 3 * cm, 6.5 * cm, 2.5 * cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (4, 0), (4, -1), "RIGHT"),
        ("ALIGN", (0, 0), (3, -1), "LEFT"),
        ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_BG]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(table)
    return elements
