import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { AnalyticsPayload, fetchAnalytics, fmt } from "../api/client";
import {
  IconAlert, IconBuilding, IconCalendar, IconCart, IconCash, IconCreditCard,
  IconFile, IconPhone, IconTrend, IconUsers,
} from "../components/Icons";

const TODAY_HEADER = () => {
  const d = new Date();
  return d.toLocaleDateString("en-IN", {
    weekday: "long", month: "long", day: "numeric", year: "numeric",
  });
};

export default function Dashboard() {
  const [data, setData] = useState<AnalyticsPayload | null>(null);
  const [loading, setLoading] = useState(true);

  const load = () => fetchAnalytics().then(setData).finally(() => setLoading(false));
  useEffect(() => {
    load();
    const onChanged = () => { load(); };
    window.addEventListener("ananta:data-changed", onChanged);
    window.addEventListener("focus", onChanged);
    return () => {
      window.removeEventListener("ananta:data-changed", onChanged);
      window.removeEventListener("focus", onChanged);
    };
  }, []);

  if (loading || !data) return <div className="page-loading">Loading…</div>;

  const trendData = data.sales_trend_30d.map((t, i) => ({
    date: t.date,
    label: i % 5 === 0 || i === data.sales_trend_30d.length - 1
      ? new Date(t.date).toLocaleDateString("en-IN", { day: "numeric", month: "short" })
      : "",
    sales: t.total,
  }));

  const cashTotal = data.cash_drawer.cash + data.cash_drawer.upi + data.cash_drawer.card + data.cash_drawer.other;
  const customersOwedTotal = data.customers_outstanding.reduce((s, c) => s + c.balance, 0);
  const vendorsOwedTotal = data.suppliers_outstanding.reduce((s, v) => s + v.balance, 0);

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Dashboard</h1>
          <div className="page-subtitle">{TODAY_HEADER()}</div>
        </div>
        <div className="header-actions">
          <button className="btn btn-ghost btn-sm" onClick={load}>Refresh</button>
        </div>
      </div>

      {/* ── KPI strip ───────────────────────────────────────────────── */}
      <div className="kpi-grid kpi-grid-5">
        <div className="kpi-card">
          <div className="kpi-icon kpi-icon-brand"><IconCart /></div>
          <div className="kpi-label">Today's Sales</div>
          <div className="kpi-value">{fmt(data.kpis.today.sales)}</div>
          <div className="kpi-sub">today</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-icon kpi-icon-green"><IconTrend /></div>
          <div className="kpi-label">Month Sales</div>
          <div className="kpi-value">{fmt(data.kpis.month.sales)}</div>
          <div className="kpi-sub">last 30 days</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-icon kpi-icon-orange"><IconCalendar /></div>
          <div className="kpi-label">Customers Owe You</div>
          <div className="kpi-value">{fmt(customersOwedTotal)}</div>
          <div className="kpi-sub">{data.customers_outstanding.length} customer{data.customers_outstanding.length === 1 ? "" : "s"}</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-icon kpi-icon-red"><IconBuilding /></div>
          <div className="kpi-label">You Owe Vendors</div>
          <div className="kpi-value">{fmt(vendorsOwedTotal)}</div>
          <div className="kpi-sub">{data.suppliers_outstanding.length} vendor{data.suppliers_outstanding.length === 1 ? "" : "s"}</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-icon kpi-icon-red"><IconAlert /></div>
          <div className="kpi-label">Low Stock</div>
          <div className="kpi-value">{data.low_stock.length}</div>
          <div className="kpi-sub">products to restock</div>
        </div>
      </div>

      {/* ── Trend + Outstanding ─────────────────────────────────────── */}
      <div className="charts-grid charts-grid-2">
        <div className="chart-card">
          <h2>Sales — Last 30 Days</h2>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={trendData} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="label" tick={{ fontSize: 11 }} interval={0} />
              <YAxis tickFormatter={(v) => `₹${v}`} tick={{ fontSize: 11 }} width={60} />
              <Tooltip
                formatter={(v) => fmt(Number(v ?? 0))}
                labelFormatter={(_, payload) => payload?.[0]?.payload?.date ?? ""}
              />
              <Line type="monotone" dataKey="sales" stroke="var(--brand)" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-card">
          <h2>Top Customer Balances</h2>
          {data.customers_outstanding.length === 0 ? (
            <div className="empty-state">No outstanding balances</div>
          ) : (
            <div className="activity-list">
              {data.customers_outstanding.slice(0, 5).map((c) => (
                <Link
                  key={c.id} to="/customers"
                  className="activity-row" style={{ textDecoration: "none", color: "inherit" }}
                >
                  <div className="activity-icon kpi-icon-orange"><IconUsers size={14} /></div>
                  <div className="activity-body">
                    <div className="activity-title">{c.name}</div>
                    {c.phone && <div className="activity-sub"><IconPhone size={10} style={{ verticalAlign: -1, marginRight: 3 }} />{c.phone}</div>}
                  </div>
                  <div className="activity-amount text-red">{fmt(c.balance)}</div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="charts-grid charts-grid-2">
        <div className="chart-card">
          <h2>Top Vendor Balances</h2>
          {data.suppliers_outstanding.length === 0 ? (
            <div className="empty-state">No vendor dues</div>
          ) : (
            <div className="activity-list">
              {data.suppliers_outstanding.slice(0, 5).map((v) => (
                <Link
                  key={v.id} to="/suppliers"
                  className="activity-row" style={{ textDecoration: "none", color: "inherit" }}
                >
                  <div className="activity-icon kpi-icon-red"><IconBuilding size={14} /></div>
                  <div className="activity-body">
                    <div className="activity-title">{v.name}</div>
                    {v.phone && <div className="activity-sub"><IconPhone size={10} style={{ verticalAlign: -1, marginRight: 3 }} />{v.phone}</div>}
                  </div>
                  <div className="activity-amount text-red">{fmt(v.balance)}</div>
                </Link>
              ))}
            </div>
          )}
        </div>
        <div className="chart-card">
          <h2>Low Stock</h2>
          {data.low_stock.length === 0 ? (
            <div className="empty-state">Nothing low — all stocked up.</div>
          ) : (
            <div className="activity-list">
              {data.low_stock.slice(0, 5).map((p) => (
                <Link
                  key={p.id} to="/stock"
                  className="activity-row" style={{ textDecoration: "none", color: "inherit" }}
                >
                  <div className="activity-icon kpi-icon-orange"><IconAlert size={14} /></div>
                  <div className="activity-body">
                    <div className="activity-title">{p.name}</div>
                    <div className="activity-sub">on hand {p.stock_qty}{p.unit ? " " + p.unit : ""} · reorder at {p.reorder_level}</div>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── Cash drawer + Recent activity ───────────────────────────── */}
      <div className="charts-grid charts-grid-2">
        <div className="chart-card">
          <div className="card-head">
            <div className="card-title">
              <IconCash className="icon" /> Today's Cash Drawer
            </div>
            <div className="card-meta">{data.cash_drawer.count} transactions</div>
          </div>
          <div className="cash-drawer">
            <CashRow kind="cash"   label="Cash"   amount={data.cash_drawer.cash}  icon={<IconCash size={14} />} />
            <CashRow kind="upi"    label="UPI"    amount={data.cash_drawer.upi}   icon={<IconPhone size={14} />} />
            <CashRow kind="card"   label="Card"   amount={data.cash_drawer.card}  icon={<IconCreditCard size={14} />} />
            <CashRow kind="credit" label="Credit" amount={data.cash_drawer.other} icon={<IconUsers size={14} />} />
            <div className="cash-total">
              <span>Total</span>
              <span>{fmt(cashTotal)}</span>
            </div>
          </div>
        </div>

        <div className="chart-card">
          <div className="card-head">
            <div className="card-title">
              <IconFile className="icon" /> Recent Activity
            </div>
          </div>
          {data.recent_activity.length === 0 ? (
            <div className="empty-state">No recent activity</div>
          ) : (
            <div className="activity-list">
              {data.recent_activity.map((e, i) => (
                <div key={i} className="activity-row">
                  <div className={"activity-icon " + (e.kind === "sale" ? "kpi-icon-brand" : "kpi-icon-green")}>
                    {e.kind === "sale" ? <IconCart size={14} /> : <IconCash size={14} />}
                  </div>
                  <div className="activity-body">
                    <div className="activity-title">{e.title}</div>
                    <div className="activity-sub">{formatActivityDate(e.date)}</div>
                  </div>
                  <div className={"activity-amount " + (e.kind === "sale" ? "text-brand" : "text-green")}>
                    {fmt(e.amount)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function CashRow({
  kind, label, amount, icon,
}: {
  kind: "cash" | "upi" | "card" | "credit";
  label: string;
  amount: number;
  icon: React.ReactNode;
}) {
  return (
    <div className={"cash-row " + kind}>
      <div className="label-side">
        <span className="icon-wrap">{icon}</span>
        {label}
      </div>
      <span className="amount">{fmt(amount)}</span>
    </div>
  );
}

function formatActivityDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("en-IN", {
    month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
  });
}
