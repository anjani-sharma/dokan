import { useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { fetchPayments, fmt, Payment } from "../api/client";
import StatusBadge from "../components/StatusBadge";

const MODE_FILTERS = ["all", "gpay", "bank_deposit", "cash", "upi", "other"];
const DIR_FILTERS  = ["all", "inflow", "outflow"];

function groupByMode(payments: Payment[], direction: "inflow" | "outflow") {
  const totals: Record<string, number> = {};
  for (const p of payments) {
    if (p.direction !== direction) continue;
    totals[p.payment_mode] = (totals[p.payment_mode] ?? 0) + p.amount;
  }
  return Object.entries(totals).map(([mode, amount]) => ({ mode, amount }));
}

export default function Payments() {
  const [payments, setPayments]   = useState<Payment[]>([]);
  const [modeFilter, setMode]     = useState("all");
  const [dirFilter,  setDir]      = useState("all");
  const [loading, setLoading]     = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchPayments({
      payment_mode: modeFilter !== "all" ? modeFilter : undefined,
      direction:    dirFilter  !== "all" ? dirFilter  : undefined,
    })
      .then(setPayments)
      .finally(() => setLoading(false));
  }, [modeFilter, dirFilter]);

  const totalIn  = payments.filter(p => p.direction === "inflow") .reduce((s, p) => s + p.amount, 0);
  const totalOut = payments.filter(p => p.direction === "outflow").reduce((s, p) => s + p.amount, 0);
  const net      = totalIn - totalOut;

  const inflowByMode  = groupByMode(payments, "inflow");
  const outflowByMode = groupByMode(payments, "outflow");

  return (
    <div className="page">
      <div className="page-header">
        <h1>Payments</h1>
        <div className="filter-row">
          <div className="filter-group">
            {DIR_FILTERS.map(d => (
              <button
                key={d}
                className={`filter-btn ${dirFilter === d ? "active" : ""}`}
                onClick={() => setDir(d)}
              >
                {d === "inflow" ? "↙ Received" : d === "outflow" ? "↗ Made" : "All"}
              </button>
            ))}
          </div>
          <div className="filter-group">
            {MODE_FILTERS.map(m => (
              <button
                key={m}
                className={`filter-btn ${modeFilter === m ? "active" : ""}`}
                onClick={() => setMode(m)}
              >
                {m === "all" ? "All Modes" : m === "bank_deposit" ? "Bank" : m.toUpperCase()}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Summary strip */}
      <div className="kpi-grid kpi-grid-3">
        <div className="kpi-card kpi-green">
          <div className="kpi-label">Received</div>
          <div className="kpi-value">{fmt(totalIn)}</div>
        </div>
        <div className="kpi-card kpi-red">
          <div className="kpi-label">Paid Out</div>
          <div className="kpi-value">{fmt(totalOut)}</div>
        </div>
        <div className={`kpi-card ${net >= 0 ? "kpi-blue" : "kpi-orange"}`}>
          <div className="kpi-label">Net</div>
          <div className="kpi-value">{fmt(net)}</div>
        </div>
      </div>

      {/* Mode breakdown charts */}
      {payments.length > 0 && (
        <div className="charts-grid charts-grid-2">
          <div className="chart-card">
            <h2>Received by Mode</h2>
            {inflowByMode.length === 0 ? (
              <div className="empty-state">No inflows in selection</div>
            ) : (
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={inflowByMode} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="mode" tick={{ fontSize: 12 }} />
                  <YAxis tickFormatter={v => `₹${v}`} tick={{ fontSize: 11 }} />
                  <Tooltip formatter={(v) => fmt(Number(v ?? 0))} />
                  <Bar dataKey="amount" fill="#10b981" name="Received" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
          <div className="chart-card">
            <h2>Paid Out by Mode</h2>
            {outflowByMode.length === 0 ? (
              <div className="empty-state">No outflows in selection</div>
            ) : (
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={outflowByMode} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="mode" tick={{ fontSize: 12 }} />
                  <YAxis tickFormatter={v => `₹${v}`} tick={{ fontSize: 11 }} />
                  <Tooltip formatter={(v) => fmt(Number(v ?? 0))} />
                  <Bar dataKey="amount" fill="#ef4444" name="Paid Out" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      )}

      {/* Payments table */}
      {loading ? (
        <div className="page-loading">Loading payments…</div>
      ) : payments.length === 0 ? (
        <div className="empty-state">No payments found.</div>
      ) : (
        <div className="table-card">
          <table className="data-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Direction</th>
                <th>Mode</th>
                <th>Amount</th>
                <th>Reference</th>
                <th>Invoice</th>
                <th>Note</th>
              </tr>
            </thead>
            <tbody>
              {payments.map(p => (
                <tr key={p.id}>
                  <td>{p.payment_date}</td>
                  <td><StatusBadge status={p.direction} /></td>
                  <td>
                    <span className="mode-chip">
                      {p.payment_mode === "gpay" ? "GPay"
                        : p.payment_mode === "bank_deposit" ? "Bank"
                        : p.payment_mode.toUpperCase()}
                    </span>
                  </td>
                  <td className={p.direction === "inflow" ? "text-green bold" : "text-red bold"}>
                    {p.direction === "inflow" ? "+" : "−"}{fmt(p.amount)}
                  </td>
                  <td className="text-muted">{p.transaction_ref ?? "—"}</td>
                  <td className="text-muted">
                    {p.purchase_invoice_id ? `#${p.purchase_invoice_id}` : "—"}
                  </td>
                  <td className="text-muted">{p.note ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
