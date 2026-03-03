import { useEffect, useState } from "react";
import { fetchSummary, fetchTransactions } from "./api";
import StatsRow from "./components/StatsRow";
import CategoryChart from "./components/CategoryChart";
import MonthlyChart from "./components/MonthlyChart";
import InstallmentsPanel from "./components/InstallmentsPanel";
import TransactionsTable from "./components/TransactionsTable";
import "./App.css";

export default function App() {
  const [summary, setSummary] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([fetchSummary(), fetchTransactions()])
      .then(([s, t]) => { setSummary(s); setTransactions(t); })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="centered"><div className="spinner" /><p>Cargando datos...</p></div>
  );
  if (error) return (
    <div className="centered error-box">
      <p>Error al conectar con la API</p>
      <code>{error}</code>
      <p className="muted">Asegurate de que la API corra:<br /><code>python dashboard_api.py</code></p>
    </div>
  );

  return (
    <div className="app">
      <header className="app-header">
        <h1>Agente de Capitales</h1>
        <span className="header-sub">Dashboard financiero personal</span>
      </header>
      <main className="app-main">
        <StatsRow summary={summary} />
        <div className="charts-grid">
          <MonthlyChart data={summary?.monthly} />
          <CategoryChart data={summary?.by_category} />
        </div>
        <InstallmentsPanel data={summary?.installments_active} />
        <TransactionsTable data={transactions} />
      </main>
    </div>
  );
}
