import { useEffect, useState } from "react";
import {
  fetchInvoices, fetchSupplierLedger, fetchSupplierSummaries, fmt,
  Invoice, SupplierLedger, SupplierSummary, updateSupplier, upsertSupplier,
} from "../api/client";
import { useToast } from "../hooks/useToast";
import FormField from "../components/FormField";
import InvoiceForm from "../components/InvoiceForm";
import Modal from "../components/Modal";
import PaymentForm from "../components/PaymentForm";

export default function Suppliers() {
  const toast = useToast();
  const [suppliers, setSuppliers] = useState<SupplierSummary[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<number | null>(null);
  const [showNew, setShowNew] = useState(false);
  const [showBills, setShowBills] = useState(false);

  const load = () => {
    setLoading(true);
    fetchSupplierSummaries()
      .then(setSuppliers)
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const filtered = query.trim()
    ? suppliers.filter((s) => s.name.toLowerCase().includes(query.trim().toLowerCase()))
    : suppliers;

  const totalDue = suppliers.reduce((s, x) => s + Math.max(x.balance, 0), 0);
  const suppliersOwedTo = suppliers.filter((s) => s.balance > 0).length;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Suppliers</h1>
          <div className="page-subtitle">Track what you owe to vendors.</div>
        </div>
        <div className="header-actions">
          <input
            className="search-input" placeholder="Search by name…"
            value={query} onChange={(e) => setQuery(e.target.value)}
          />
          <button className="btn btn-secondary" onClick={() => setShowBills(true)}>Bills due</button>
          <button className="btn btn-primary" onClick={() => setShowNew(true)}>+ New vendor</button>
        </div>
      </div>

      <div className="kpi-grid kpi-grid-3">
        <div className="kpi-card kpi-indigo">
          <div className="kpi-label">Suppliers</div>
          <div className="kpi-value">{suppliers.length}</div>
        </div>
        <div className="kpi-card kpi-orange">
          <div className="kpi-label">With outstanding</div>
          <div className="kpi-value">{suppliersOwedTo}</div>
        </div>
        <div className="kpi-card kpi-red">
          <div className="kpi-label">Total due</div>
          <div className="kpi-value">{fmt(totalDue)}</div>
        </div>
      </div>

      {loading ? (
        <div className="page-loading">Loading suppliers…</div>
      ) : filtered.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">🏭</div>
          <div className="empty-state-title">{query ? "No matches" : "No suppliers yet"}</div>
          <div>{query ? "Try a different search." : "Create one above, or it'll be added the first time you save an invoice."}</div>
        </div>
      ) : (
        <div className="table-card">
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Phone</th>
                <th>Invoiced</th>
                <th>Paid</th>
                <th>Due</th>
                <th>Last activity</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((s) => {
                const due = s.balance > 0;
                return (
                  <tr key={s.id} className="clickable-row" onClick={() => setSelected(s.id)}>
                    <td><strong>{s.name}</strong></td>
                    <td className="text-muted">{s.phone ?? "—"}</td>
                    <td>{fmt(s.total_invoiced)}</td>
                    <td className="text-green">{fmt(s.total_paid)}</td>
                    <td className={due ? "text-red bold" : "text-muted"}>{fmt(s.balance)}</td>
                    <td className="text-muted">{s.last_activity ?? "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {selected != null && (
        <SupplierDetail id={selected} onClose={() => setSelected(null)} onChanged={load} />
      )}

      <Modal open={showNew} onClose={() => setShowNew(false)} title="New vendor">
        <SupplierCreateForm
          onCancel={() => setShowNew(false)}
          onSaved={() => {
            setShowNew(false);
            toast.push({ kind: "success", title: "Vendor added" });
            load();
          }}
        />
      </Modal>

      <Modal open={showBills} onClose={() => setShowBills(false)} title="Bills due across all vendors" wide>
        <BillsDuePanel onPickVendor={(id) => { setShowBills(false); setSelected(id); }} />
      </Modal>
    </div>
  );
}

// ── Cross-vendor unpaid bills list ─────────────────────────────────────────
//
// Quick filter so the user can answer "what bills should I pay this week?"
// without needing to know the vendor name first. Pulls unpaid + partial
// invoices in one go and groups by vendor.

function BillsDuePanel({ onPickVendor }: { onPickVendor: (vendorId: number) => void }) {
  const [bills, setBills] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [vendors, setVendors] = useState<Map<number, string>>(new Map());

  useEffect(() => {
    setLoading(true);
    Promise.all([
      fetchInvoices("unpaid"),
      fetchInvoices("partial"),
      fetchSupplierSummaries(),
    ])
      .then(([u, p, s]) => {
        const all = [...u, ...p].sort((a, b) => a.invoice_date.localeCompare(b.invoice_date));
        setBills(all);
        setVendors(new Map(s.map((x) => [x.id, x.name])));
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="page-loading">Loading bills…</div>;
  if (bills.length === 0) return <div className="empty-state">No unpaid bills. You're all caught up.</div>;

  const total = bills.reduce((s, b) => s + (b.total_amount - b.paid_amount), 0);

  return (
    <>
      <div className="kpi-grid kpi-grid-3" style={{ marginBottom: 16 }}>
        <div className="kpi-card kpi-orange">
          <div className="kpi-label">Bills due</div>
          <div className="kpi-value">{bills.length}</div>
        </div>
        <div className="kpi-card kpi-red">
          <div className="kpi-label">Total outstanding</div>
          <div className="kpi-value">{fmt(total)}</div>
        </div>
        <div className="kpi-card kpi-indigo">
          <div className="kpi-label">Vendors involved</div>
          <div className="kpi-value">{new Set(bills.map((b) => b.supplier_id)).size}</div>
        </div>
      </div>
      <div className="table-card">
        <table className="data-table">
          <thead>
            <tr>
              <th>Invoice #</th>
              <th>Vendor</th>
              <th>Date</th>
              <th>Total</th>
              <th>Paid</th>
              <th>Outstanding</th>
            </tr>
          </thead>
          <tbody>
            {bills.map((b) => (
              <tr
                key={b.id} className="clickable-row"
                onClick={() => onPickVendor(b.supplier_id)}
              >
                <td><strong>#{b.invoice_number}</strong></td>
                <td>{vendors.get(b.supplier_id) ?? `#${b.supplier_id}`}</td>
                <td>{b.invoice_date}</td>
                <td>{fmt(b.total_amount)}</td>
                <td className="text-green">{fmt(b.paid_amount)}</td>
                <td className="text-red bold">{fmt(b.total_amount - b.paid_amount)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

// ── Detail (ledger) ────────────────────────────────────────────────────────

function SupplierDetail({ id, onClose, onChanged }: { id: number; onClose: () => void; onChanged: () => void }) {
  const toast = useToast();
  const [ledger, setLedger] = useState<SupplierLedger | null>(null);
  const [loading, setLoading] = useState(true);
  const [showPayment, setShowPayment] = useState(false);
  const [showInvoice, setShowInvoice] = useState(false);
  const [editing, setEditing] = useState(false);

  const load = () => {
    setLoading(true);
    fetchSupplierLedger(id).then(setLedger).finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [id]);

  return (
    <Modal open onClose={onClose} title={ledger?.supplier_name ?? "Supplier"} wide>
      {loading || !ledger ? (
        <div className="page-loading">Loading ledger…</div>
      ) : (
        <>
          <div className="kpi-grid kpi-grid-3" style={{ marginBottom: 20 }}>
            <div className="kpi-card kpi-blue">
              <div className="kpi-label">Invoiced</div>
              <div className="kpi-value">{fmt(ledger.total_invoiced)}</div>
            </div>
            <div className="kpi-card kpi-green">
              <div className="kpi-label">Paid</div>
              <div className="kpi-value">{fmt(ledger.total_paid)}</div>
            </div>
            <div className={"kpi-card " + (ledger.balance > 0 ? "kpi-red" : "kpi-green")}>
              <div className="kpi-label">{ledger.balance > 0 ? "You owe" : "Settled"}</div>
              <div className="kpi-value">{fmt(Math.abs(ledger.balance))}</div>
            </div>
          </div>

          <div className="filter-row" style={{ marginBottom: 16, justifyContent: "space-between" }}>
            <div className="text-muted" style={{ fontSize: 12 }}>
              {ledger.phone ? `📞 ${ledger.phone}` : "No phone on file"}
              {ledger.address && <span> · 📍 {ledger.address}</span>}
            </div>
            <div className="filter-group">
              <button className="btn btn-ghost btn-sm" onClick={() => setEditing(true)}>Edit details</button>
              <button className="btn btn-secondary btn-sm" onClick={() => setShowInvoice(true)}>+ New invoice</button>
              <button className="btn btn-primary btn-sm" onClick={() => setShowPayment(true)}>+ Record payment</button>
            </div>
          </div>

          {ledger.entries.length === 0 ? (
            <div className="empty-state">No invoices yet. Save one and it'll appear here.</div>
          ) : (
            <div className="table-card">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Type</th>
                    <th>Description</th>
                    <th>Invoiced</th>
                    <th>Paid</th>
                    <th>Balance</th>
                  </tr>
                </thead>
                <tbody>
                  {ledger.entries.map((e, i) => (
                    <tr key={`${e.entry_type}-${e.source_id}-${i}`}>
                      <td>{e.entry_date}</td>
                      <td>
                        <span className={"badge " + (e.entry_type === "invoice" ? "badge-blue" : "badge-green")}>
                          {e.entry_type}
                        </span>
                      </td>
                      <td>{e.description}</td>
                      <td className="text-red">{e.debit > 0 ? fmt(e.debit) : ""}</td>
                      <td className="text-green">{e.credit > 0 ? fmt(e.credit) : ""}</td>
                      <td className="bold">{fmt(e.running_balance)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {showPayment && (
            <Modal open onClose={() => setShowPayment(false)} title="Record outflow payment">
              <PaymentForm
                defaultDirection="outflow"
                onCancel={() => setShowPayment(false)}
                onSaved={() => {
                  setShowPayment(false);
                  toast.push({ kind: "success", title: "Payment recorded" });
                  load();
                  onChanged();
                }}
              />
            </Modal>
          )}

          {showInvoice && (
            <Modal open onClose={() => setShowInvoice(false)} title={`New invoice for ${ledger.supplier_name}`} wide>
              <InvoiceForm
                defaultSupplier={{ supplier_id: id, supplier_name: ledger.supplier_name }}
                onCancel={() => setShowInvoice(false)}
                onSaved={() => {
                  setShowInvoice(false);
                  toast.push({ kind: "success", title: "Invoice saved" });
                  load();
                  onChanged();
                }}
              />
            </Modal>
          )}

          {editing && (
            <Modal open onClose={() => setEditing(false)} title="Edit supplier">
              <SupplierEditForm
                initial={{ id, name: ledger.supplier_name, phone: ledger.phone, address: ledger.address }}
                onCancel={() => setEditing(false)}
                onSaved={() => {
                  setEditing(false);
                  toast.push({ kind: "success", title: "Supplier updated" });
                  load();
                  onChanged();
                }}
              />
            </Modal>
          )}
        </>
      )}
    </Modal>
  );
}

// ── Create / edit forms ────────────────────────────────────────────────────

function SupplierCreateForm({ onSaved, onCancel }: { onSaved: () => void; onCancel: () => void }) {
  const [name, setName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!name.trim()) { setError("Name is required."); return; }
    setSubmitting(true);
    try {
      await upsertSupplier(name.trim());
      onSaved();
    } catch (err) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg ?? "Could not save.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={submit} className="form-grid">
      <FormField label="Name">
        <input className="form-input" value={name} onChange={(e) => setName(e.target.value)} required autoFocus />
      </FormField>
      {error && <div className="form-error">{error}</div>}
      <div className="form-actions">
        <button type="button" className="btn btn-ghost" onClick={onCancel} disabled={submitting}>Cancel</button>
        <button type="submit" className="btn btn-primary" disabled={submitting}>
          {submitting ? "Saving…" : "Create supplier"}
        </button>
      </div>
    </form>
  );
}

function SupplierEditForm({
  initial, onSaved, onCancel,
}: {
  initial: { id: number; name: string; phone: string | null; address: string | null };
  onSaved: () => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState(initial.name);
  const [phone, setPhone] = useState(initial.phone ?? "");
  const [address, setAddress] = useState(initial.address ?? "");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!name.trim()) { setError("Name is required."); return; }
    setSubmitting(true);
    try {
      await updateSupplier(initial.id, {
        name: name.trim(),
        phone: phone.trim() || null,
        address: address.trim() || null,
      });
      onSaved();
    } catch (err) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg ?? "Could not save.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={submit} className="form-grid">
      <FormField label="Name">
        <input className="form-input" value={name} onChange={(e) => setName(e.target.value)} required autoFocus />
      </FormField>
      <FormField label="Phone">
        <input className="form-input" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="optional" />
      </FormField>
      <FormField label="Address">
        <input className="form-input" value={address} onChange={(e) => setAddress(e.target.value)} placeholder="optional" />
      </FormField>
      {error && <div className="form-error">{error}</div>}
      <div className="form-actions">
        <button type="button" className="btn btn-ghost" onClick={onCancel} disabled={submitting}>Cancel</button>
        <button type="submit" className="btn btn-primary" disabled={submitting}>
          {submitting ? "Saving…" : "Save changes"}
        </button>
      </div>
    </form>
  );
}
