const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export async function fetchSummary() {
  const res = await fetch(`${BASE}/api/summary`);
  if (!res.ok) throw new Error("Error al obtener resumen");
  return res.json();
}

export async function fetchTransactions() {
  const res = await fetch(`${BASE}/api/transactions`);
  if (!res.ok) throw new Error("Error al obtener transacciones");
  return res.json();
}
