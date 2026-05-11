import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Bar, BarChart, CartesianGrid, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import KpiCard from "../components/KpiCard";
import {
  AnalyticsKpi, AnalyticsPayload,
  fetchAnalytics, fmt, triggerDailyReport, triggerWeeklyReport,
} from "../api/client";
import { useToast } from "../hooks/useToast";

export default function Dashboard() {
  const toast = useToast();
  const [data, setData] = useState<AnalyticsPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState<"daily" | "weekly" | null>(null);

  useEffect(() => {
    fetchAnalytics().then(setData).finally(() => setLoading(false));
  }, []);

  const handleSend = async (kind: "daily" | "weekly") => {
    setSending(kind);
    try {
      kind === "daily" ? await triggerDailyReport() : await triggerWeeklyReport();
      toast.push({ kind: "success", title: `${kind === "daily" ? "Daily" : "Weekly"} report sent`, body: "Telegram delivered." });
    } catch {
      toast.push({ kind: "error", title: "Send failed", body: "Check backend connection." });
    } finally {
      setSending(null);
    }
  };

  if (loading || !data) return <div className="page-loading">Loading dashboard…</div>;

  // Build short labels for trend chart (day-of-month, every 5 days)
  const trendData = data.sales_trend_30d.map((t, i) => ({
    date: t.date,
    label: i % 5 === 0 || i === data.sales_trend_30d.length - 1
      ? new Date(t.date).toLocaleDateString("en-IN", { day: "numeric", month: "short" })
      : "",
    sales: t.total,
  }));

  const topProducts = data.sales_by_product_30d.map((p) => ({
    ...p,
    short: p.name.length > 16 ? p.name.slice(0, 16) + "…" : p.name,
  }));

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Overview</h1>
          <div className="page-subtitle">Your shop at a glance — last 30 days.</div>
        </div>
        <div className="header-actions">
          <button className="btn btn-ghost btn-sm" onClick={() => handleSend("daily")} disabled={sending !== null}>
            {sending === "daily" ? "Sending…" : "📤 Daily report"}
          </button>
          <button className="btn btn-ghost btn-sm" onClick={() => handleSend("weekly")} disabled={sending !== null}>
            {sending === "weekly" ? "Sending…" : "📤 Weekly report"}
          </button>
        </div>
      </div>

      {/* KPI strip — today / week / month */}
      <KpiBlock label="Today"     kpi={data.kpis.today} />
      <KpiBlock label="This week" kpi={data.kpis.week} />
      <KpiBlock label="Last 30 days" kpi={data.kpis.month} extra={
        <KpiCard
          label="Stock value on hand"
          value={fmt(data.stock_value_on_hand)}
          sub="cost basis"
          accent="blue"
        />
      } />

      {/* Sales trend (30 days) */}
      <div className="chart-card">
        <h2>Sales — last 30 days</h2>
        {trendData.every((d) => d.sales === 0) ? (
          <div className="empty-state">No sales in the last 30 days.</div>
        ) : (
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={trendData} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="label" tick={{ fontSize: 11 }} interval={0} />
              <YAxis tickFormatter={(v) => fmt(Number(v ?? 0))} tick={{ fontSize: 11 }} width={80} />
              <Tooltip
                formatter={(v) => fmt(Number(v ?? 0))}
                labelFormatter={(_, payload) => payload?.[0]?.payload?.date ?? ""}
              />
              <Line type="monotone" dataKey="sales" stroke="#4f46e5" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Top products + outstanding lists */}
      <div className="charts-grid charts-grid-2">
        <div className="chart-card">
          <h2>Top products — last 30 days</h2>
          {topProducts.length === 0 ? (
            <div className="empty-state">No sales yet.</div>
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart
                layout="vertical"
                data={topProducts}
                margin={{ top: 8, right: 16, left: 8, bottom: 8 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis type="number" tickFormatter={(v) => `₹${v}`} tick={{ fontSize: 11 }} />
                <YAxis dataKey="short" type="category" width={130} tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v) => fmt(Number(v ?? 0))} />
                <Bar dataKey="revenue" fill="#4f46e5" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        <PartyList
          title="Customers who owe you"
          empty="No customer dues — nice."
          rows={data.customers_outstanding}
          linkBase="/customers"
          variant="red"
        />
      </div>

      <div className="charts-grid charts-grid-2">
        <PartyList
          title="Suppliers you owe"
          empty="All caught up with suppliers."
          rows={data.suppliers_outstanding}
          linkBase="/suppliers"
          variant="orange"
        />

        <div className="chart-card">
          <h2>Low stock</h2>
          {data.low_stock.length === 0 ? (
            <div className="empty-state">All products above reorder level.</div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Product</th>
                  <th>On hand</th>
                  <th>Reorder at</th>
                </tr>
              </thead>
              <tbody>
                {data.low_stock.slice(0, 10).map((p) => (
                  <tr key={p.id} className="row-warning">
                    <td><strong>{p.name}</strong></td>
                    <td className="text-red bold">{p.stock_qty} {p.unit ?? ""}</td>
                    <td className="text-muted">{p.reorder_level} {p.unit ?? ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}

// ── KPI strip per window ──────────────────────────────────────────────────

function KpiBlock({ label, kpi, extra }: { label: string; kpi: AnalyticsKpi; extra?: React.ReactNode }) {
  return (
    <div>
      <div className="kpi-block-label">{label}</div>
      <div className="kpi-grid">
        <KpiCard label="Sales"    value={fmt(kpi.sales)}    accent="indigo" />
        <KpiCard label="Received" value={fmt(kpi.received)} accent="green" />
        <KpiCard label="Paid out" value={fmt(kpi.paid_out)} accent="red" />
        <KpiCard
          label="Net cash"
          value={fmt(kpi.net)}
          accent={kpi.net >= 0 ? "green" : "orange"}
        />
        {extra}
      </div>
    </div>
  );
}

// ── Outstanding list (customers / suppliers) ──────────────────────────────

function PartyList({
  title, empty, rows, linkBase, variant,
}: {
  title: string;
  empty: string;
  rows: { id: number; name: string; phone: string | null; balance: number; last_activity: string | null }[];
  linkBase: string;
  variant: "red" | "orange";
}) {
  return (
    <div className="chart-card">
      <h2>{title}</h2>
      {rows.length === 0 ? (
        <div className="empty-state">{empty}</div>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Last activity</th>
              <th style={{ textAlign: "right" }}>Balance</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="clickable-row">
                <td>
                  <Link to={linkBase} style={{ color: "inherit", textDecoration: "none" }}>
                    <strong>{r.name}</strong>
                    {r.phone && <span className="text-muted" style={{ marginLeft: 8, fontSize: 11 }}>{r.phone}</span>}
                  </Link>
                </td>
                <td className="text-muted">{r.last_activity ?? "—"}</td>
                <td className={`text-${variant} bold`} style={{ textAlign: "right" }}>{fmt(r.balance)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
