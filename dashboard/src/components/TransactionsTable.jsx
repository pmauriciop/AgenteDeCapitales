import Card from "./Card";

const fmt = (v) => `$${Number(v).toLocaleString("es-AR", { minimumFractionDigits: 2 })}`;

const TYPE_LABEL = { expense: "Gasto", income: "Ingreso" };
const TYPE_CLASS = { expense: "badge-expense", income: "badge-income" };

export default function TransactionsTable({ data }) {
  if (!data || data.length === 0) return null;
  const sorted = [...data].sort((a, b) => b.date.localeCompare(a.date));
  return (
    <Card title={`Todas las transacciones (${data.length})`}>
      <div className="table-wrapper">
        <table className="tx-table">
          <thead>
            <tr>
              <th>Fecha</th>
              <th>Descripción</th>
              <th>Categoría</th>
              <th>Tipo</th>
              <th>Cuota</th>
              <th>Monto</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((tx) => (
              <tr key={tx.id}>
                <td>{tx.date}</td>
                <td>{tx.description}</td>
                <td><span className="badge badge-cat">{tx.category}</span></td>
                <td><span className={`badge ${TYPE_CLASS[tx.type]}`}>{TYPE_LABEL[tx.type]}</span></td>
                <td>
                  {tx.installment_total
                    ? `${tx.installment_current}/${tx.installment_total}`
                    : "—"}
                </td>
                <td className={tx.type === "expense" ? "amount-expense" : "amount-income"}>
                  {tx.type === "expense" ? "-" : "+"}{fmt(tx.amount)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
