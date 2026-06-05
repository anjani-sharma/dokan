import { useEffect, useState, Fragment } from "react";
import StatusBadge from "../components/StatusBadge";
import Modal from "../components/Modal";
import InvoiceForm from "../components/InvoiceForm";
import FormField from "../components/FormField";
import ProductPicker from "../components/ProductPicker";
import {
  addInvoiceItem, deleteInvoice, deleteInvoiceItem, fetchDuplicateInvoiceClusters,
  fetchInvoices, fmt, Invoice, InvoiceItemCreate, updateInvoice, updateInvoiceItem,
} from "../api/client";
import { useToast } from "../hooks/useToast";

const STATUS_FILTERS = ["all", "unpaid", "partial", "paid"];

export default function Invoices() {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [filter, setFilter] = useState("all");
  const [expanded, setExpanded] = useState<number | null>(null);
  const [editing, setEditing] = useState<Invoice | null>(null);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [dupClusters, setDupClusters] = useState<Invoice[][] | null>(null);
  const [dupLoading, setDupLoading] = useState(false);

  const toast = useToast();

  const openDuplicatesModal = async () => {
    setDupLoading(true);
    try {
      const clusters = await fetchDuplicateInvoiceClusters();
      setDupClusters(clusters);
    } catch (e: unknown) {
      const msg = (e as { message?: string })?.message ?? "Could not load duplicates";
      toast.push({ kind: "error", title: "Could not load duplicates", body: msg });
    } finally {
      setDupLoading(false);
    }
  };

  const deleteFromCluster = async (id: number) => {
    if (!confirm("Delete this invoice? Its stock movements will be reversed.")) return;
    try {
      await deleteInvoice(id);
      setDupClusters(prev =>
        prev?.map(g => g.filter(i => i.id !== id)).filter(g => g.length > 1) ?? null
      );
      load(filter);
      toast.push({ kind: "success", title: `Invoice #${id} deleted` });
    } catch (e: unknown) {
      const msg = (e as { message?: string })?.message ?? "Delete failed";
      toast.push({ kind: "error", title: "Delete failed", body: msg });
    }
  };

  const load = (f: string) => {
    setLoading(true);
    fetchInvoices(f === "all" ? undefined : f)
      .then(setInvoices)
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(filter); }, [filter]);

  useEffect(() => {
    const onChanged = () => load(filter);
    window.addEventListener("ananta:data-changed", onChanged);
    return () => window.removeEventListener("ananta:data-changed", onChanged);
  }, [filter]);

  const toggle = (id: number) => setExpanded(prev => prev === id ? null : id);

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Purchase Invoices</h1>
          <div className="page-subtitle">Bills you owe to suppliers.</div>
        </div>
        <div className="header-actions">
          <div className="filter-group">
            {STATUS_FILTERS.map(s => (
              <button
                key={s}
                className={`filter-btn ${filter === s ? "active" : ""}`}
                onClick={() => setFilter(s)}
              >
                {s.charAt(0).toUpperCase() + s.slice(1)}
              </button>
            ))}
          </div>
          <button className="btn btn-secondary" onClick={openDuplicatesModal} disabled={dupLoading}>
            {dupLoading ? "Scanning…" : "Find duplicates"}
          </button>
          <button className="btn btn-primary" onClick={() => setShowForm(true)}>+ New invoice</button>
        </div>
      </div>

      {dupClusters !== null && (
        <Modal open onClose={() => setDupClusters(null)} title="Duplicate invoices" wide>
          {dupClusters.length === 0 ? (
            <div style={{ padding: 16 }}>
              No duplicates found — every (supplier, date, total) combination is unique.
            </div>
          ) : (
            <div style={{ maxHeight: 600, overflowY: "auto" }}>
              <div style={{ marginBottom: 12, fontSize: 13, color: "#555" }}>
                {dupClusters.length} cluster{dupClusters.length === 1 ? "" : "s"} of invoices share
                the same supplier, date, and total. Keep one row per cluster, delete the rest —
                stock movements are reversed automatically.
              </div>
              {dupClusters.map((group, gi) => (
                <div key={gi} style={{ border: "1px solid #ddd", borderRadius: 6, padding: 12, marginBottom: 12 }}>
                  <div style={{ marginBottom: 8, fontSize: 13, fontWeight: 500 }}>
                    {group[0].invoice_date} · {fmt(group[0].total_amount)} · supplier #{group[0].supplier_id}
                  </div>
                  <table className="data-table" style={{ fontSize: 13 }}>
                    <thead>
                      <tr>
                        <th>Invoice #</th>
                        <th>Items</th>
                        <th style={{ textAlign: "right" }}>Total</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {group.map(inv => (
                        <tr key={inv.id}>
                          <td>{inv.invoice_number}</td>
                          <td>{inv.items?.length ?? 0}</td>
                          <td style={{ textAlign: "right" }}>{fmt(inv.total_amount)}</td>
                          <td style={{ textAlign: "right" }}>
                            <button
                              className="btn btn-small btn-secondary"
                              onClick={() => deleteFromCluster(inv.id)}
                            >
                              Delete
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ))}
            </div>
          )}
        </Modal>
      )}

      <Modal open={showForm} onClose={() => setShowForm(false)} title="Record a purchase invoice" wide>
        <InvoiceForm
          onCancel={() => setShowForm(false)}
          onSaved={() => { setShowForm(false); load(filter); }}
        />
      </Modal>

      {editing && (
        <Modal open onClose={() => setEditing(null)} title={`Edit invoice #${editing.invoice_number}`} wide>
          <InvoiceEditForm
            invoice={editing}
            onClose={() => setEditing(null)}
            onChanged={(updated) => {
              setEditing(updated);
              load(filter);
            }}
            onDeleted={() => { setEditing(null); load(filter); }}
          />
        </Modal>
      )}

      {loading ? (
        <div className="page-loading">Loading invoices…</div>
      ) : invoices.length === 0 ? (
        <div className="empty-state">No invoices found.</div>
      ) : (
        <div className="table-card">
          <table className="data-table">
            <thead>
              <tr>
                <th>Invoice #</th>
                <th>Date</th>
                <th>Total</th>
                <th>Paid</th>
                <th>Outstanding</th>
                <th>Status</th>
                <th></th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {invoices.map(inv => (
                <Fragment key={inv.id}>
                  <tr className="clickable-row" onClick={() => toggle(inv.id)}>
                    <td><strong>#{inv.invoice_number}</strong></td>
                    <td>{inv.invoice_date}</td>
                    <td>{fmt(inv.total_amount)}</td>
                    <td className="text-green">{fmt(inv.paid_amount)}</td>
                    <td className={inv.total_amount - inv.paid_amount > 0 ? "text-red" : ""}>
                      {fmt(inv.total_amount - inv.paid_amount)}
                    </td>
                    <td><StatusBadge status={inv.status} /></td>
                    <td style={{ textAlign: "right" }}>
                      <button
                        className="btn btn-ghost btn-sm"
                        onClick={(e) => { e.stopPropagation(); setEditing(inv); }}
                      >Edit</button>
                    </td>
                    <td className="expand-icon">{expanded === inv.id ? "▲" : "▼"}</td>
                  </tr>
                  {expanded === inv.id && (
                    <tr className="detail-row">
                      <td colSpan={8}>
                        <div className="detail-panel">
                          {inv.notes && <p className="detail-notes">Notes: {inv.notes}</p>}
                          {inv.items.length === 0 ? (
                            <p className="text-muted">No line items recorded.</p>
                          ) : (
                            <table className="data-table inner-table">
                              <thead>
                                <tr>
                                  <th>Product</th>
                                  <th>Qty</th>
                                  <th>Unit Cost</th>
                                  <th>Line Total</th>
                                </tr>
                              </thead>
                              <tbody>
                                {inv.items.map(item => (
                                  <tr key={item.id}>
                                    <td>{item.product_name_raw ?? `Product #${item.id}`}</td>
                                    <td>{item.qty}</td>
                                    <td>{fmt(item.unit_cost)}</td>
                                    <td>{fmt(item.qty * item.unit_cost)}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Invoice edit form ──────────────────────────────────────────────────────
//
// Lets the user fix the invoice header (number, date, totals, paid, notes)
// and add / edit / remove individual line items. Every line-item operation
// hits a dedicated endpoint so stock movements stay accurate.

function InvoiceEditForm({
  invoice, onClose, onChanged, onDeleted,
}: {
  invoice: Invoice;
  onClose: () => void;
  onChanged: (updated: Invoice) => void;
  onDeleted: () => void;
}) {
  const toast = useToast();
  const [invNumber, setInvNumber] = useState(invoice.invoice_number);
  const [invDate, setInvDate] = useState(invoice.invoice_date);
  const [total, setTotal] = useState(String(invoice.total_amount));
  const [paid, setPaid] = useState(String(invoice.paid_amount));
  const [notes, setNotes] = useState(invoice.notes ?? "");
  const [savingHeader, setSavingHeader] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const saveHeader = async () => {
    setError(null);
    setSavingHeader(true);
    try {
      const updated = await updateInvoice(invoice.id, {
        invoice_number: invNumber.trim(),
        invoice_date: invDate,
        total_amount: Number(total) || 0,
        paid_amount: Number(paid) || 0,
        notes: notes.trim() || null,
      });
      toast.push({ kind: "success", title: "Invoice updated" });
      onChanged(updated);
    } catch (err) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg ?? "Could not save header changes.");
    } finally {
      setSavingHeader(false);
    }
  };

  const removeInvoice = async () => {
    if (!confirm("Delete this invoice? Stock movements will be reversed.")) return;
    try {
      await deleteInvoice(invoice.id);
      toast.push({ kind: "success", title: "Invoice deleted" });
      onDeleted();
    } catch {
      toast.push({ kind: "error", title: "Delete failed" });
    }
  };

  return (
    <div className="form-grid">
      <div className="form-grid form-grid-2">
        <FormField label="Invoice number">
          <input className="form-input" value={invNumber} onChange={(e) => setInvNumber(e.target.value)} />
        </FormField>
        <FormField label="Date">
          <input type="date" className="form-input" value={invDate} onChange={(e) => setInvDate(e.target.value)} />
        </FormField>
      </div>
      <div className="form-grid form-grid-2">
        <FormField label="Total amount" hint="₹">
          <input
            type="number" step="0.01" min="0" className="form-input"
            value={total} onChange={(e) => setTotal(e.target.value)}
          />
        </FormField>
        <FormField label="Paid amount" hint="₹">
          <input
            type="number" step="0.01" min="0" className="form-input"
            value={paid} onChange={(e) => setPaid(e.target.value)}
          />
        </FormField>
      </div>
      <FormField label="Notes">
        <textarea className="form-textarea" value={notes} onChange={(e) => setNotes(e.target.value)} />
      </FormField>
      {error && <div className="form-error">{error}</div>}
      <div className="form-actions" style={{ justifyContent: "space-between" }}>
        <button type="button" className="btn btn-ghost text-red" onClick={removeInvoice}>
          Delete invoice
        </button>
        <div style={{ display: "flex", gap: 8 }}>
          <button type="button" className="btn btn-ghost" onClick={onClose}>Close</button>
          <button type="button" className="btn btn-primary" onClick={saveHeader} disabled={savingHeader}>
            {savingHeader ? "Saving…" : "Save header"}
          </button>
        </div>
      </div>

      <hr style={{ border: "none", borderTop: "1px solid var(--divider)", margin: "12px 0" }} />

      <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>Line items</h3>
      <ItemsEditor invoiceId={invoice.id} items={invoice.items} onChanged={onChanged} />
    </div>
  );
}

// Inline editor for the invoice's items. Each row tracks its own draft state;
// changes are sent on Save (per row). New items use the same picker so users
// can scan a barcode to attach a product.

function ItemsEditor({
  invoiceId, items, onChanged,
}: {
  invoiceId: number;
  items: Invoice["items"];
  onChanged: (updated: Invoice) => void;
}) {
  const toast = useToast();
  const [newItem, setNewItem] = useState<{
    product_id: number | null; product_name: string; qty: string; unit_cost: string;
  }>({ product_id: null, product_name: "", qty: "", unit_cost: "" });

  const addRow = async () => {
    if (!newItem.product_name.trim()) {
      toast.push({ kind: "error", title: "Pick a product" });
      return;
    }
    const body: InvoiceItemCreate = {
      product_id: newItem.product_id,
      product_name_raw: newItem.product_name.trim(),
      qty: Number(newItem.qty) || 0,
      unit_cost: Number(newItem.unit_cost) || 0,
    };
    try {
      const updated = await addInvoiceItem(invoiceId, body);
      toast.push({ kind: "success", title: "Item added" });
      setNewItem({ product_id: null, product_name: "", qty: "", unit_cost: "" });
      onChanged(updated);
    } catch {
      toast.push({ kind: "error", title: "Could not add item" });
    }
  };

  return (
    <div className="line-items-list">
      {items.map((it) => (
        <ItemRow key={it.id} invoiceId={invoiceId} item={it} onChanged={onChanged} />
      ))}

      <div className="line-item-row" style={{ marginTop: 6 }}>
        <ProductPicker
          value={{ product_id: newItem.product_id, product_name: newItem.product_name }}
          onChange={(v) =>
            setNewItem((p) => ({
              ...p,
              product_id: v.product_id,
              product_name: v.product_name,
              unit_cost: v.cost_price && !p.unit_cost ? String(v.cost_price) : p.unit_cost,
            }))
          }
        />
        <input
          className="form-input" type="number" step="0.001" min="0"
          value={newItem.qty} onChange={(e) => setNewItem({ ...newItem, qty: e.target.value })}
          placeholder="Qty"
        />
        <input
          className="form-input" type="number" step="0.01" min="0"
          value={newItem.unit_cost} onChange={(e) => setNewItem({ ...newItem, unit_cost: e.target.value })}
          placeholder="Unit cost"
        />
        <button type="button" className="btn btn-primary btn-sm" onClick={addRow}>Add</button>
      </div>
    </div>
  );
}

function ItemRow({
  invoiceId, item, onChanged,
}: {
  invoiceId: number;
  item: Invoice["items"][number];
  onChanged: (updated: Invoice) => void;
}) {
  const toast = useToast();
  const [name, setName] = useState(item.product_name_raw ?? "");
  const [qty, setQty] = useState(String(item.qty));
  const [cost, setCost] = useState(String(item.unit_cost));
  const [busy, setBusy] = useState(false);

  const save = async () => {
    setBusy(true);
    try {
      const updated = await updateInvoiceItem(invoiceId, item.id, {
        product_id: null,
        product_name_raw: name.trim() || null,
        qty: Number(qty) || 0,
        unit_cost: Number(cost) || 0,
      });
      toast.push({ kind: "success", title: "Item updated" });
      onChanged(updated);
    } catch {
      toast.push({ kind: "error", title: "Update failed" });
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!confirm("Remove this item? Stock will be adjusted.")) return;
    setBusy(true);
    try {
      const updated = await deleteInvoiceItem(invoiceId, item.id);
      toast.push({ kind: "success", title: "Item removed" });
      onChanged(updated);
    } catch {
      toast.push({ kind: "error", title: "Remove failed" });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="line-item-row">
      <input
        className="form-input" value={name}
        onChange={(e) => setName(e.target.value)} placeholder="Product name"
      />
      <input
        className="form-input" type="number" step="0.001" min="0"
        value={qty} onChange={(e) => setQty(e.target.value)} placeholder="Qty"
      />
      <input
        className="form-input" type="number" step="0.01" min="0"
        value={cost} onChange={(e) => setCost(e.target.value)} placeholder="Unit cost"
      />
      <button type="button" className="btn btn-ghost btn-sm" onClick={save} disabled={busy}>Save</button>
      <button type="button" className="line-item-remove" onClick={remove} disabled={busy} aria-label="Remove">×</button>
    </div>
  );
}
