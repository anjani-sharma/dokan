import { useEffect, useState } from "react";
import {
  BarChart, Bar, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import KpiCard from "../components/KpiCard";
import {
  fetchDailyReport, fetchWeeklyReport, fetchOutstanding,
  triggerDailyReport, triggerWeeklyReport,
  fmt, DailyReport, WeeklyReport, OutstandingData,
} from "../api/client";

// Build last-7-days labels for the bar chart
function last7Days() {
  const days = [];
  for (let i = 6; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    days.push(d.toISOString().slice(0, 10));
  }
  return days;
}

const DAY_LABELS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

export default function Dashboard() {
  const [daily, setDaily] = useState<DailyReport | null>(null);
  const [weekly, setWeekly] = useState<WeeklyReport | null>(null);
  const [outstanding, setOutstanding] = useState<OutstandingData | null>(null);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState<"daily" | "weekly" | null>(null);

  useEffect(() => {
    Promise.all([fetchDailyReport(), fetchWeeklyReport(), fetchOutstanding()])
      .then(([d, w, o]) => { setDaily(d); setWeekly(w); setOutstanding(o); })
      .finally(() => setLoading(false));
  }, []);

  // Merge weekly sales into per-day chart data
  const chartData = last7Days().map((dateStr) => {
    const label = DAY_LABELS[new Date(dateStr).getDay()];
    const dayTotal = weekly
      ? (weekly as any).__sales_by_day?.[dateStr] ?? 0
      : 0;
    return { day: label, date: dateStr, sales: dayTotal };
  });

  // Today's sales for bar chart
  const todaySalesData = daily?.sales.slice(0, 8).map(s => ({
    name: s.product_name.length > 14 ? s.product_name.slice(0, 14) + "…" : s.product_name,
    revenue: s.line_total,
    qty: s.qty_sold,
  })) ?? [];

  const handleSend = async (type: "daily" | "weekly") => {
    setSending(type);
    try {
      type === "daily" ? await triggerDailyReport() : await triggerWeeklyReport();
      alert(`${type === "daily" ? "Daily" : "Weekly"} report sent to Telegram!`);
    } catch {
      alert("Failed to send report. Check backend connection.");
    } finally {
      setSending(null);
    }
  };

  if (loading) return <div className="page-loading">Loading dashboard…</div>;

  const profit = daily ? daily.total_sales - daily.paid_out : 0;

  return (
    <div className="page">
      <div className="page-header">
        <h1>Overview</h1>
        <div className="header-actions">
          <button
            className="btn btn-secondary"
            onClick={() => handleSend("daily")}
            disabled={sending !== null}
          >
            {sending === "daily" ? "Sending…" : "📤 Send Daily Report"}
          </button>
          <button
            className="btn btn-secondary"
            onClick={() => handleSend("weekly")}
            disabled={sending !== null}
          >
            {sending === "weekly" ? "Sending…" : "📤 Send Weekly Report"}
          </button>
        </div>
      </div>

      {/* KPI cards */}
      <div className="kpi-grid">
        <KpiCard
          label="Today's Sales"
          value={fmt(daily?.total_sales ?? 0)}
          sub={`${daily?.sales_count ?? 0} items sold · ${daily?.date ?? ""}`}
          accent="blue"
        />
        <KpiCard
          label="Today's Received"
          value={fmt(daily?.received ?? 0)}
          accent="green"
        />
        <KpiCard
          label="Today's Paid Out"
          value={fmt(daily?.paid_out ?? 0)}
          accent="red"
        />
        <KpiCard
          label="This Week Paid Out"
          value={fmt(weekly?.paid_out ?? 0)}
          sub="all payments this week"
          accent="red"
        />
        <KpiCard
          label="This Week Received"
          value={fmt(weekly?.received ?? 0)}
          sub="all inflows this week"
          accent="green"
        />
        <KpiCard
          label="Outstanding Payables"
          value={fmt(outstanding?.total_outstanding ?? 0)}
          sub={`${outstanding?.invoices.length ?? 0} invoices pending`}
          accent="orange"
        />
        <KpiCard
          label="This Week's Sales"
          value={fmt(weekly?.total_sales ?? 0)}
          sub={`${weekly?.sales_count ?? 0} transactions`}
          accent="blue"
        />
        <KpiCard
          label="Low Stock Items"
          value={String(daily?.low_stock_count ?? 0)}
          sub={daily?.low_stock_count ? "Need restocking" : "All good"}
          accent={daily?.low_stock_count ? "orange" : "green"}
        />
      </div>

      <div className="charts-grid">
        {/* Today's sales by product */}
        <div className="chart-card">
          <h2>Today's Sales by Product</h2>
          {todaySalesData.length === 0 ? (
            <div className="empty-state">No sales recorded today</div>
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={todaySalesData} margin={{ top: 8, right: 16, left: 0, bottom: 32 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} angle={-30} textAnchor="end" />
                <YAxis tickFormatter={v => `₹${v}`} tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v) => fmt(Number(v ?? 0))} />
                <Bar dataKey="revenue" fill="#4f46e5" name="Revenue" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Weekly top items by revenue */}
        <div className="chart-card">
          <h2>Top Items This Week (Revenue)</h2>
          {(weekly?.top_by_revenue ?? []).length === 0 ? (
            <div className="empty-state">No weekly data yet</div>
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart
                data={weekly!.top_by_revenue.map(t => ({
                  name: t.name.length > 14 ? t.name.slice(0, 14) + "…" : t.name,
                  revenue: t.revenue,
                }))}
                margin={{ top: 8, right: 16, left: 0, bottom: 32 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} angle={-30} textAnchor="end" />
                <YAxis tickFormatter={v => `₹${v}`} tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v) => fmt(Number(v ?? 0))} />
                <Bar dataKey="revenue" fill="#10b981" name="Revenue" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Weekly top items by qty */}
        <div className="chart-card">
          <h2>Top Items This Week (Quantity)</h2>
          {(weekly?.top_by_qty ?? []).length === 0 ? (
            <div className="empty-state">No weekly data yet</div>
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart
                layout="vertical"
                data={weekly!.top_by_qty.map(t => ({
                  name: t.name.length > 18 ? t.name.slice(0, 18) + "…" : t.name,
                  qty: t.qty,
                }))}
                margin={{ top: 8, right: 32, left: 8, bottom: 8 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis type="number" tick={{ fontSize: 11 }} />
                <YAxis dataKey="name" type="category" width={130} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="qty" fill="#f59e0b" name="Units Sold" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Outstanding invoices summary */}
        <div className="chart-card">
          <h2>Outstanding Invoices</h2>
          {(outstanding?.invoices ?? []).length === 0 ? (
            <div className="empty-state">✅ No outstanding payables</div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Invoice</th>
                  <th>Date</th>
                  <th>Total</th>
                  <th>Due</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {outstanding!.invoices.slice(0, 6).map(inv => (
                  <tr key={inv.id}>
                    <td>#{inv.invoice_number}</td>
                    <td>{inv.invoice_date}</td>
                    <td>{fmt(inv.total_amount)}</td>
                    <td className="text-red">{fmt(inv.outstanding)}</td>
                    <td>
                      <span className={`badge badge-${inv.status === "unpaid" ? "red" : "orange"}`}>
                        {inv.status}
                      </span>
                    </td>
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
