import Card from "./Card";

const fmt = (v) => `$${Number(v).toLocaleString("es-AR", { minimumFractionDigits: 2 })}`;

export default function StatsRow({ summary }) {
  if (!summary) return null;
  const { total_income, total_expense, balance } = summary;
  return (
    <div className="stats-row">
      <Card className="stat-card stat-income">
        <div className="stat-label">Ingresos totales</div>
        <div className="stat-value">{fmt(total_income)}</div>
      </Card>
      <Card className="stat-card stat-expense">
        <div className="stat-label">Gastos totales</div>
        <div className="stat-value">{fmt(total_expense)}</div>
      </Card>
      <Card className={`stat-card ${balance >= 0 ? "stat-income" : "stat-expense"}`}>
        <div className="stat-label">Balance</div>
        <div className="stat-value">{fmt(balance)}</div>
      </Card>
    </div>
  );
}
