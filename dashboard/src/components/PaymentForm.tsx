import { useEffect, useRef, useState } from "react";
import {
  createPayment, fetchInvoices, Invoice, ocrInvoiceUpload, PaymentCreate,
} from "../api/client";
import { useToast } from "../hooks/useToast";
import CustomerPicker from "./CustomerPicker";
import FormField from "./FormField";
import SupplierPicker from "./SupplierPicker";

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
  const [supplier, setSupplier] = useState<{ supplier_id: number | null; supplier_name: string }>({
    supplier_id: null, supplier_name: "",
  });
  const [customer, setCustomer] = useState<{ customer_id: number | null; customer_name: string }>({
    customer_id: null, customer_name: "",
  });
  const [ref, setRef] = useState("");
  const [note, setNote] = useState("");
  const [openInvoices, setOpenInvoices] = useState<Invoice[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [imagePath, setImagePath] = useState<string | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [ocrBusy, setOcrBusy] = useState(false);
  const fileInput = useRef<HTMLInputElement | null>(null);

  const onUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    setOcrBusy(true);
    setImagePreview(URL.createObjectURL(file));
    try {
      const result = await ocrInvoiceUpload(file);
      if (result.image_path) setImagePath(result.image_path);

      if (result.type === "payment_slip") {
        if (result.amount != null) setAmount(String(result.amount));
        if (result.payment_mode) setMode(result.payment_mode);
        if (result.payment_date) setDate(result.payment_date);
        if (result.transaction_ref) setRef(result.transaction_ref);
        if (result.note && !note) setNote(result.note);
        toast.push({
          kind: "success",
          title: "Payment slip read",
          body: `Confidence: ${result.confidence}. Review before saving.`,
        });
      } else if (result.type === "invoice") {
        // Treat invoice photos as outflow against the matching invoice.
        setDirection("outflow");
        if (result.total_amount != null) setAmount(String(result.total_amount));
        if (result.invoice_date) setDate(result.invoice_date);
        // Try to match against the loaded open invoices by invoice_number.
        if (result.invoice_number) {
          const match = openInvoices.find(
            (i) => i.invoice_number.trim().toLowerCase() === result.invoice_number!.trim().toLowerCase()
          );
          if (match) setInvoiceId(match.id);
        }
        toast.push({
          kind: "success",
          title: "Invoice read",
          body: result.invoice_number
            ? `Invoice #${result.invoice_number} — review then save.`
            : "Review the prefilled fields.",
        });
      } else {
        toast.push({
          kind: "error",
          title: "Couldn't read",
          body: "Try a clearer photo.",
        });
      }
    } catch (err) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.push({ kind: "error", title: "OCR failed", body: msg ?? "Try a clearer photo." });
    } finally {
      setOcrBusy(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  };

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
      supplier_id: direction === "outflow" ? supplier.supplier_id : null,
      customer_id: direction === "inflow" ? customer.customer_id : null,
      transaction_ref: ref.trim() || null,
      image_path: imagePath,
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
      <div className="ocr-upload">
        <input
          type="file" accept="image/*" ref={fileInput} style={{ display: "none" }}
          onChange={onUpload} disabled={ocrBusy || submitting}
        />
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => fileInput.current?.click()}
          disabled={ocrBusy || submitting}
        >
          {ocrBusy ? "Reading…" : "📎 Upload receipt or invoice"}
        </button>
        {imagePreview && (
          <div className="ocr-preview">
            <img src={imagePreview} alt="Receipt preview" />
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={() => {
                setImagePreview(null);
                setImagePath(null);
              }}
            >Remove</button>
          </div>
        )}
      </div>

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
        <>
          <FormField label="To vendor" hint="payment is booked against the vendor's running balance">
            <SupplierPicker value={supplier} onChange={setSupplier} />
          </FormField>
          {supplier.supplier_id != null && openInvoices.some((i) => i.supplier_id === supplier.supplier_id) && (
            <FormField label="Specific invoice" hint="optional — only set if this payment is for one bill">
              <select
                className="form-select"
                value={invoiceId ?? ""}
                onChange={(e) => setInvoiceId(e.target.value ? Number(e.target.value) : null)}
              >
                <option value="">— Apply to vendor balance —</option>
                {openInvoices
                  .filter((i) => i.supplier_id === supplier.supplier_id)
                  .map((inv) => {
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
        </>
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
