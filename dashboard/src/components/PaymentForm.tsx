import { useEffect, useState } from "react";
import { createPayment, fetchInvoices, Invoice, PaymentCreate } from "../api/client";
import { useToast } from "../hooks/useToast";
import CustomerPicker from "./CustomerPicker";
import FormField from "./FormField";

const today = () => new Date().toISOString().slice(0, 10);

const MODES = [
  { value: "cash",          label: "Cash" },
  { value: "gpay",          label: "GPay" },
  { value: "upi",           label: "UPI" },
  { value: "bank_deposit",  label: "Bank deposit" },
  { value: "other",         label: "Other" },
];

interface PaymentFormProps {
  onSaved: () => void;
  onCancel: () => void;
  defaultDirection?: "inflow" | "outflow";
}

export default function PaymentForm({ onSaved, onCancel, defaultDirection }: PaymentFormProps) {
  const toast = useToast();
  const [direction, setDirection] = useState<"inflow" | "outflow">(defaultDirection ?? "outflow");
  const [date, setDate] = useState(today());
  const [amount, setAmount] = useState("");
  const [mode, setMode] = useState("gpay");
  const [invoiceId, setInvoiceId] = useState<number | null>(null);
  const [customer, setCustomer] = useState<{ customer_id: number | null; customer_name: string }>({
    customer_id: null, customer_name: "",
  });
  const [ref, setRef] = useState("");
  const [note, setNote] = useState("");
  const [openInvoices, setOpenInvoices] = useState<Invoice[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load unpaid + partial invoices when direction = outflow.
  useEffect(() => {
    if (direction !== "outflow") { setOpenInvoices([]); setInvoiceId(null); return; }
    Promise.all([fetchInvoices("unpaid"), fetchInvoices("partial")])
      .then(([u, p]) => setOpenInvoices([...u, ...p]))
      .catch(() => setOpenInvoices([]));
  }, [direction]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const amt = Number(amount);
    if (!amt || amt <= 0) { setError("Amount must be greater than zero."); return; }

    const body: PaymentCreate = {
      payment_date: date,
      amount: amt,
      payment_mode: mode,
      direction,
      purchase_invoice_id: direction === "outflow" ? invoiceId : null,
      customer_id: direction === "inflow" ? customer.customer_id : null,
      transaction_ref: ref.trim() || null,
      image_path: null,
      note: note.trim() || null,
    };

    setSubmitting(true);
    try {
      await createPayment(body);
      toast.push({
        kind: "success",
        title: direction === "inflow" ? "Payment received" : "Payment made",
        body: `₹${amt.toFixed(2)} · ${mode}`,
      });
      onSaved();
    } catch (err) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg ?? "Could not save payment.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={submit} className="form-grid">
      <FormField label="Direction">
        <div className="filter-group">
          <button
            type="button"
            className={"filter-btn" + (direction === "inflow" ? " active" : "")}
            onClick={() => setDirection("inflow")}
          >↙ Received</button>
          <button
            type="button"
            className={"filter-btn" + (direction === "outflow" ? " active" : "")}
            onClick={() => setDirection("outflow")}
          >↗ Paid out</button>
        </div>
      </FormField>

      <div className="form-grid form-grid-2">
        <FormField label="Date">
          <input type="date" className="form-input" value={date} onChange={(e) => setDate(e.target.value)} required />
        </FormField>
        <FormField label="Amount" hint="₹">
          <input
            type="number" step="0.01" min="0" className="form-input"
            value={amount} onChange={(e) => setAmount(e.target.value)}
            placeholder="0.00" required
          />
        </FormField>
      </div>

      <FormField label="Mode">
        <select className="form-select" value={mode} onChange={(e) => setMode(e.target.value)}>
          {MODES.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
        </select>
      </FormField>

      {direction === "outflow" && (
        <FormField label="Against invoice" hint="optional — updates the invoice's paid status">
          <select
            className="form-select"
            value={invoiceId ?? ""}
            onChange={(e) => setInvoiceId(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">— None —</option>
            {openInvoices.map((inv) => {
              const outstanding = inv.total_amount - inv.paid_amount;
              return (
                <option key={inv.id} value={inv.id}>
                  #{inv.invoice_number} · {inv.invoice_date} · outstanding ₹{outstanding.toFixed(2)}
                </option>
              );
            })}
          </select>
        </FormField>
      )}

      {direction === "inflow" && (
        <FormField label="From customer" hint="optional — leave blank for walk-in cash sale">
          <CustomerPicker value={customer} onChange={setCustomer} />
        </FormField>
      )}

      <FormField label="Transaction reference" hint="optional — UPI ref, cheque #, etc.">
        <input
          className="form-input" value={ref} onChange={(e) => setRef(e.target.value)}
          placeholder="optional"
        />
      </FormField>

      <FormField label="Note">
        <textarea
          className="form-textarea" value={note}
          onChange={(e) => setNote(e.target.value)} placeholder="optional"
        />
      </FormField>

      {error && <div className="form-error">{error}</div>}
      <div className="form-actions">
        <button type="button" className="btn btn-ghost" onClick={onCancel} disabled={submitting}>Cancel</button>
        <button type="submit" className="btn btn-primary" disabled={submitting}>
          {submitting ? "Saving…" : "Save payment"}
        </button>
      </div>
    </form>
  );
}
