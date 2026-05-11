import { useEffect, useState } from "react";
import { deleteSale, fetchSales, fmt, SaleRow } from "../api/client";
import { useToast } from "../hooks/useToast";
import Modal from "../components/Modal";
import SaleForm from "../components/SaleForm";

const today = () => new Date().toISOString().slice(0, 10);

export default function Sales() {
  const toast = useToast();
  const [date, setDate] = useState(today());
  const [sales, setSales] = useState<SaleRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);

  const load = (d: string) => {
    setLoading(true);
    fetchSales(d).then(setSales).finally(() => setLoading(false));
  };

  useEffect(() => { load(date); }, [date]);

  useEffect(() => {
    const onChanged = () => load(date);
    window.addEventListener("ananta:data-changed", onChanged);
    return () => window.removeEventListener("ananta:data-changed", onChanged);
  }, [date]);

  const onDelete = async (id: number, name: string | null) => {
    if (!confirm(`Delete this sale${name ? ` (${name})` : ""}? Stock will be returned.`)) return;
    try {
      await deleteSale(id);
      toast.push({ kind: "success", title: "Sale deleted" });
      load(date);
    } catch {
      toast.push({ kind: "error", title: "Delete failed" });
    }
  };

  const total = sales.reduce((s, x) => s + x.line_total, 0);

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Sales</h1>
          <div className="page-subtitle">Record what went out the door today.</div>
        </div>
        <div className="header-actions">
          <input
            type="date" className="search-input" style={{ width: 160 }}
            value={date} onChange={(e) => setDate(e.target.value)}
          />
          <button className="btn btn-primary" onClick={() => setShowForm(true)}>+ New sale</button>
        </div>
      </div>

      <div className="kpi-grid kpi-grid-3">
        <div className="kpi-card kpi-indigo">
          <div className="kpi-label">Day total</div>
          <div className="kpi-value">{fmt(total)}</div>
          <div className="kpi-sub">{sales.length} {sales.length === 1 ? "sale" : "sales"}</div>
        </div>
      </div>

      {loading ? (
        <div className="page-loading">Loading sales…</div>
      ) : sales.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">📋</div>
          <div className="empty-state-title">No sales for {date}</div>
          <div>Use “+ New sale” to record one, or send a voice note to the bot.</div>
        </div>
      ) : (
        <div className="table-card">
          <table className="data-table">
            <thead>
              <tr>
                <th>Product</th>
                <th>Qty</th>
                <th>Unit price</th>
                <th>Line total</th>
                <th>Source</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {sales.map((s) => (
                <tr key={s.id}>
                  <td>
                    <strong>{s.product_name_raw ?? "—"}</strong>
                    {s.product_id == null && <span className="badge badge-grey" style={{ marginLeft: 8 }}>uncatalogued</span>}
                  </td>
                  <td>{s.qty_sold}</td>
                  <td>{fmt(s.selling_price)}</td>
                  <td className="bold">{fmt(s.line_total)}</td>
                  <td><span className="mode-chip">{s.source}</span></td>
                  <td style={{ textAlign: "right" }}>
                    <button className="btn btn-ghost btn-sm" onClick={() => onDelete(s.id, s.product_name_raw)}>
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal open={showForm} onClose={() => setShowForm(false)} title="Record a sale">
        <SaleForm
          defaultDate={date}
          onCancel={() => setShowForm(false)}
          onSaved={() => { setShowForm(false); load(date); }}
        />
      </Modal>
    </div>
  );
}
