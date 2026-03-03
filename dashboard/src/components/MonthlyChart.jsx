import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer
} from "recharts";
import Card from "./Card";

const fmt = (v) => `$${Number(v).toLocaleString("es-AR", { minimumFractionDigits: 0 })}`;

export default function MonthlyChart({ data }) {
  if (!data || data.length === 0) return null;
  return (
    <Card title="Evolución mensual">
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={data} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#2d2d3a" />
          <XAxis dataKey="month" tick={{ fill: "#a1a1aa", fontSize: 12 }} />
          <YAxis tick={{ fill: "#a1a1aa", fontSize: 11 }} tickFormatter={(v) => `$${(v/1000).toFixed(0)}k`} />
          <Tooltip formatter={(v) => fmt(v)} contentStyle={{ background: "#1e1e2e", border: "1px solid #3f3f5a" }} />
          <Legend />
          <Bar dataKey="income" name="Ingresos" fill="#10b981" radius={[4,4,0,0]} />
          <Bar dataKey="expense" name="Gastos" fill="#f43f5e" radius={[4,4,0,0]} />
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );
}
