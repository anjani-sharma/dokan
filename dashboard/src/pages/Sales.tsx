import { useEffect, useState } from "react";
import { deleteSale, fetchSales, fmt, SaleRow, updateSale } from "../api/client";
import { useToast } from "../hooks/useToast";
import FormField from "../components/FormField";
import Modal from "../components/Modal";
import SaleForm from "../components/SaleForm";

const today = () => new Date().toISOString().slice(0, 10);

export default function Sales() {
  const toast = useToast();
  const [date, setDate] = useState(today());
  const [sales, setSales] = useState<SaleRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<SaleRow | null>(null);

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
                    <button className="btn btn-ghost btn-sm" onClick={() => setEditing(s)}>Edit</button>
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

      {editing && (
        <Modal open onClose={() => setEditing(null)} title="Edit sale">
          <SaleEditForm
            sale={editing}
            onCancel={() => setEditing(null)}
            onSaved={() => { setEditing(null); load(date); }}
          />
        </Modal>
      )}
    </div>
  );
}

// ── Sale row edit form ─────────────────────────────────────────────────────
//
// Quick-correct form — adjusts qty, unit price, and the raw product name.
// Stock is reconciled on the backend via record_stock_movement("adjustment").

function SaleEditForm({
  sale, onSaved, onCancel,
}: {
  sale: SaleRow;
  onSaved: () => void;
  onCancel: () => void;
}) {
  const toast = useToast();
  const [name, setName] = useState(sale.product_name_raw ?? "");
  const [qty, setQty] = useState(String(sale.qty_sold));
  const [price, setPrice] = useState(String(sale.selling_price));
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const q = Number(qty);
    if (!q || q <= 0) { setError("Quantity must be > 0."); return; }
    setSubmitting(true);
    try {
      await updateSale(sale.id, {
        qty_sold: q,
        selling_price: Number(price) || 0,
        product_name_raw: name.trim() || null,
      });
      toast.push({ kind: "success", title: "Sale updated" });
      onSaved();
    } catch (err) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg ?? "Could not update.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={submit} className="form-grid">
      <FormField label="Product name">
        <input className="form-input" value={name} onChange={(e) => setName(e.target.value)} />
      </FormField>
      <div className="form-grid form-grid-2">
        <FormField label="Quantity">
          <input
            type="number" step="0.001" min="0" className="form-input"
            value={qty} onChange={(e) => setQty(e.target.value)} required
          />
        </FormField>
        <FormField label="Selling price" hint="₹ per unit">
          <input
            type="number" step="0.01" min="0" className="form-input"
            value={price} onChange={(e) => setPrice(e.target.value)}
          />
        </FormField>
      </div>
      {error && <div className="form-error">{error}</div>}
      <div className="form-actions">
        <button type="button" className="btn btn-ghost" onClick={onCancel} disabled={submitting}>Cancel</button>
        <button type="submit" className="btn btn-primary" disabled={submitting}>
          {submitting ? "Saving…" : "Save"}
        </button>
      </div>
    </form>
  );
}
