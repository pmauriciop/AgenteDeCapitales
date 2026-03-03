import Card from "./Card";

const fmt = (v) => `$${Number(v).toLocaleString("es-AR", { minimumFractionDigits: 2 })}`;

const CAT_COLORS = {
  hogar: "#22d3ee", tecnologia: "#6366f1", ropa: "#f59e0b",
  alimentacion: "#10b981", transporte: "#8b5cf6", entretenimiento: "#fb923c", otros: "#94a3b8",
};

export default function InstallmentsPanel({ data }) {
  if (!data || data.length === 0)
    return <Card title="Cuotas activas"><p className="muted">Sin cuotas pendientes</p></Card>;

  const totalMensual = data.reduce((sum, t) => sum + t.amount, 0);

  return (
    <Card title="Cuotas activas">
      <p className="installments-total">Total mensual: <strong>{fmt(totalMensual)}</strong></p>
      <div className="installments-list">
        {data.map((t, i) => {
          const pct = Math.round(((t.installment_total - t.installments_remaining) / t.installment_total) * 100);
          const color = CAT_COLORS[t.category] || "#94a3b8";
          return (
            <div key={i} className="installment-item">
              <div className="installment-header">
                <span className="installment-desc">{t.description}</span>
                <span className="installment-amount">{fmt(t.amount)}/mes</span>
              </div>
              <div className="installment-meta">
                <span>Cuota {t.installment_current}/{t.installment_total} — restan {t.installments_remaining}</span>
                <span className="installment-cat" style={{ color }}>{t.category}</span>
              </div>
              <div className="progress-bar-bg">
                <div className="progress-bar-fill" style={{ width: `${pct}%`, background: color }} />
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
