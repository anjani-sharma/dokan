import { useEffect, useState } from "react";
import {
  CustomerCreate, CustomerLedger, CustomerSummary,
  createCustomer, fetchCustomerLedger, fetchCustomers, fmt, updateCustomer,
} from "../api/client";
import { useToast } from "../hooks/useToast";
import FormField from "../components/FormField";
import Modal from "../components/Modal";
import PaymentForm from "../components/PaymentForm";

export default function Customers() {
  const toast = useToast();
  const [customers, setCustomers] = useState<CustomerSummary[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<number | null>(null);
  const [showNew, setShowNew] = useState(false);

  const load = (q?: string) => {
    setLoading(true);
    fetchCustomers(q?.trim() || undefined)
      .then(setCustomers)
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  // Debounced search
  useEffect(() => {
    const t = setTimeout(() => load(query), 250);
    return () => clearTimeout(t);
  }, [query]);

  const totalOutstanding = customers.reduce((s, c) => s + Math.max(c.balance, 0), 0);
  const customersWithDues = customers.filter((c) => c.balance > 0).length;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Customers</h1>
          <div className="page-subtitle">Track who owes you what.</div>
        </div>
        <div className="header-actions">
          <input
            className="search-input" placeholder="Search by name…"
            value={query} onChange={(e) => setQuery(e.target.value)}
          />
          <button className="btn btn-primary" onClick={() => setShowNew(true)}>+ New customer</button>
        </div>
      </div>

      <div className="kpi-grid kpi-grid-3">
        <div className="kpi-card kpi-indigo">
          <div className="kpi-label">Customers</div>
          <div className="kpi-value">{customers.length}</div>
        </div>
        <div className="kpi-card kpi-orange">
          <div className="kpi-label">Owe you</div>
          <div className="kpi-value">{customersWithDues}</div>
          <div className="kpi-sub">{customers.length ? Math.round((customersWithDues / customers.length) * 100) : 0}% of customers</div>
        </div>
        <div className="kpi-card kpi-red">
          <div className="kpi-label">Total outstanding</div>
          <div className="kpi-value">{fmt(totalOutstanding)}</div>
        </div>
      </div>

      {loading ? (
        <div className="page-loading">Loading customers…</div>
      ) : customers.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">👥</div>
          <div className="empty-state-title">{query ? "No matches" : "No customers yet"}</div>
          <div>{query ? "Try a different search." : "Click “+ New customer” to add one, or attach one from a sale."}</div>
        </div>
      ) : (
        <div className="table-card">
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Phone</th>
                <th>Total sold</th>
                <th>Received</th>
                <th>Balance</th>
                <th>Last activity</th>
              </tr>
            </thead>
            <tbody>
              {customers.map((c) => {
                const owes = c.balance > 0;
                return (
                  <tr key={c.id} className="clickable-row" onClick={() => setSelected(c.id)}>
                    <td><strong>{c.name}</strong></td>
                    <td className="text-muted">{c.phone ?? "—"}</td>
                    <td>{fmt(c.total_sales)}</td>
                    <td className="text-green">{fmt(c.total_received)}</td>
                    <td className={owes ? "text-red bold" : c.balance < 0 ? "text-orange bold" : "text-muted"}>
                      {fmt(c.balance)}
                    </td>
                    <td className="text-muted">{c.last_activity ?? "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {selected != null && (
        <CustomerDetail id={selected} onClose={() => setSelected(null)} onChanged={() => load(query)} />
      )}

      <Modal open={showNew} onClose={() => setShowNew(false)} title="New customer">
        <CustomerForm
          onCancel={() => setShowNew(false)}
          onSaved={() => {
            setShowNew(false);
            toast.push({ kind: "success", title: "Customer added" });
            load(query);
          }}
        />
      </Modal>
    </div>
  );
}

// ── Detail drawer (ledger) ─────────────────────────────────────────────────

function CustomerDetail({ id, onClose, onChanged }: { id: number; onClose: () => void; onChanged: () => void }) {
  const toast = useToast();
  const [ledger, setLedger] = useState<CustomerLedger | null>(null);
  const [loading, setLoading] = useState(true);
  const [showPayment, setShowPayment] = useState(false);
  const [editing, setEditing] = useState(false);

  const load = () => {
    setLoading(true);
    fetchCustomerLedger(id).then(setLedger).finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [id]);

  return (
    <Modal open onClose={onClose} title={ledger?.customer.name ?? "Customer"} wide>
      {loading || !ledger ? (
        <div className="page-loading">Loading ledger…</div>
      ) : (
        <>
          <div className="kpi-grid kpi-grid-3" style={{ marginBottom: 20 }}>
            <div className="kpi-card kpi-blue">
              <div className="kpi-label">Total sold</div>
              <div className="kpi-value">{fmt(ledger.total_sales)}</div>
            </div>
            <div className="kpi-card kpi-green">
              <div className="kpi-label">Received</div>
              <div className="kpi-value">{fmt(ledger.total_received)}</div>
            </div>
            <div className={"kpi-card " + (ledger.balance > 0 ? "kpi-red" : ledger.balance < 0 ? "kpi-orange" : "kpi-green")}>
              <div className="kpi-label">{ledger.balance > 0 ? "Owes you" : ledger.balance < 0 ? "Credit" : "Settled"}</div>
              <div className="kpi-value">{fmt(Math.abs(ledger.balance))}</div>
            </div>
          </div>

          <div className="filter-row" style={{ marginBottom: 16, justifyContent: "space-between" }}>
            <div className="text-muted" style={{ fontSize: 12 }}>
              {ledger.customer.phone ? `📞 ${ledger.customer.phone}` : "No phone on file"}
              {ledger.customer.address && <span> · 📍 {ledger.customer.address}</span>}
            </div>
            <div className="filter-group">
              <button className="btn btn-ghost btn-sm" onClick={() => setEditing(true)}>Edit details</button>
              <button className="btn btn-primary btn-sm" onClick={() => setShowPayment(true)}>+ Record payment</button>
            </div>
          </div>

          {ledger.entries.length === 0 ? (
            <div className="empty-state">No transactions yet. Sales attached to this customer will appear here.</div>
          ) : (
            <div className="table-card">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Type</th>
                    <th>Description</th>
                    <th>Debit</th>
                    <th>Credit</th>
                    <th>Balance</th>
                  </tr>
                </thead>
                <tbody>
                  {ledger.entries.map((e, i) => (
                    <tr key={`${e.entry_type}-${e.source_id}-${i}`}>
                      <td>{e.entry_date}</td>
                      <td>
                        <span className={"badge " + (e.entry_type === "sale" ? "badge-blue" : "badge-green")}>
                          {e.entry_type}
                        </span>
                      </td>
                      <td>{e.description}{e.qty != null && <span className="text-muted"> · {e.qty} units</span>}</td>
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
            <Modal open onClose={() => setShowPayment(false)} title="Record inflow payment">
              <PaymentForm
                defaultDirection="inflow"
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

          {editing && (
            <Modal open onClose={() => setEditing(false)} title="Edit customer">
              <CustomerForm
                initial={ledger.customer}
                onCancel={() => setEditing(false)}
                onSaved={() => {
                  setEditing(false);
                  toast.push({ kind: "success", title: "Customer updated" });
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

// ── Create / edit form ─────────────────────────────────────────────────────

function CustomerForm({
  initial,
  onSaved,
  onCancel,
}: {
  initial?: { id: number; name: string; phone: string | null; address: string | null; notes: string | null };
  onSaved: () => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [phone, setPhone] = useState(initial?.phone ?? "");
  const [address, setAddress] = useState(initial?.address ?? "");
  const [notes, setNotes] = useState(initial?.notes ?? "");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!name.trim()) { setError("Name is required."); return; }
    const body: CustomerCreate = {
      name: name.trim(),
      phone: phone.trim() || null,
      address: address.trim() || null,
      notes: notes.trim() || null,
    };
    setSubmitting(true);
    try {
      if (initial) await updateCustomer(initial.id, body);
      else await createCustomer(body);
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
      <div className="form-grid form-grid-2">
        <FormField label="Phone">
          <input className="form-input" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="optional" />
        </FormField>
        <FormField label="Address">
          <input className="form-input" value={address} onChange={(e) => setAddress(e.target.value)} placeholder="optional" />
        </FormField>
      </div>
      <FormField label="Notes">
        <textarea className="form-textarea" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="optional" />
      </FormField>
      {error && <div className="form-error">{error}</div>}
      <div className="form-actions">
        <button type="button" className="btn btn-ghost" onClick={onCancel} disabled={submitting}>Cancel</button>
        <button type="submit" className="btn btn-primary" disabled={submitting}>
          {submitting ? "Saving…" : (initial ? "Save changes" : "Create customer")}
        </button>
      </div>
    </form>
  );
}
