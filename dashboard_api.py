"""
dashboard_api.py
─────────────────
Mini API FastAPI que sirve datos financieros desencriptados al dashboard web.
Corre en http://localhost:8000

Uso:
    python dashboard_api.py
"""

import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, '.')

from collections import defaultdict

from database.client import get_client
from database.encryption import decrypt

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def _decrypt_desc(desc: str) -> str:
    try:
        return decrypt(desc)
    except Exception:
        return desc


@app.get("/api/transactions")
def get_transactions():
    db = get_client()
    rows = db.table("transactions").select("*").order("date", desc=False).execute().data
    result = []
    for r in rows:
        result.append({
            "id": r["id"],
            "date": r["date"],
            "amount": float(r["amount"]),
            "type": r["type"],
            "category": r["category"],
            "description": _decrypt_desc(r["description"]),
            "installment_current": r.get("installment_current"),
            "installment_total": r.get("installment_total"),
            "installments_remaining": r.get("installments_remaining"),
        })
    return result


@app.get("/api/summary")
def get_summary():
    db = get_client()
    rows = db.table("transactions").select("*").execute().data

    # Totales generales
    total_expense = sum(float(r["amount"]) for r in rows if r["type"] == "expense")
    total_income  = sum(float(r["amount"]) for r in rows if r["type"] == "income")

    # Por categoria
    by_cat = defaultdict(float)
    for r in rows:
        if r["type"] == "expense":
            by_cat[r["category"]] += float(r["amount"])

    # Por mes
    by_month: dict = defaultdict(lambda: {"income": 0.0, "expense": 0.0})
    for r in rows:
        month = r["date"][:7]  # YYYY-MM
        by_month[month][r["type"]] += float(r["amount"])

    monthly = [
        {"month": k, "income": v["income"], "expense": v["expense"]}
        for k, v in sorted(by_month.items())
    ]

    # Cuotas activas
    installments = []
    for r in rows:
        if r.get("installment_total") and (r.get("installments_remaining") or 0) > 0:
            installments.append({
                "description": _decrypt_desc(r["description"]),
                "amount": float(r["amount"]),
                "installment_current": r["installment_current"],
                "installment_total": r["installment_total"],
                "installments_remaining": r["installments_remaining"],
                "category": r["category"],
            })

    return {
        "total_expense": total_expense,
        "total_income": total_income,
        "balance": total_income - total_expense,
        "by_category": [{"category": k, "amount": round(v, 2)} for k, v in sorted(by_cat.items(), key=lambda x: -x[1])],
        "monthly": monthly,
        "installments_active": installments,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
