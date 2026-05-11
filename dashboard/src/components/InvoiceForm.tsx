import { useRef, useState } from "react";
import {
  createInvoice, InvoiceCreate, InvoiceItemCreate, ocrInvoiceUpload, upsertSupplier,
} from "../api/client";
import { useToast } from "../hooks/useToast";
import FormField from "./FormField";
import ProductPicker from "./ProductPicker";
import SupplierPicker from "./SupplierPicker";

const today = () => new Date().toISOString().slice(0, 10);

interface InvoiceFormProps {
  onSaved: () => void;
  onCancel: () => void;
  defaultSupplier?: { supplier_id: number; supplier_name: string };
}

type DraftItem = {
  product_id: number | null;
  product_name: string;
  qty: string;
  unit_cost: string;
};

const emptyItem = (): DraftItem => ({ product_id: null, product_name: "", qty: "", unit_cost: "" });

export default function InvoiceForm({ onSaved, onCancel, defaultSupplier }: InvoiceFormProps) {
  const toast = useToast();
  const [invoiceNumber, setInvoiceNumber] = useState("");
  const [supplier, setSupplier] = useState<{ supplier_id: number | null; supplier_name: string }>(
    defaultSupplier ?? { supplier_id: null, supplier_name: "" }
  );
  const [invoiceDate, setInvoiceDate] = useState(today());
  const [totalAmount, setTotalAmount] = useState("");
  const [notes, setNotes] = useState("");
  const [items, setItems] = useState<DraftItem[]>([emptyItem()]);
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
      if (result.type !== "invoice") {
        toast.push({
          kind: "error",
          title: "Not an invoice",
          body: result.type === "payment_slip" ? "Looks like a payment slip — use the Payments page." : "Couldn't read this image.",
        });
        return;
      }
      // Prefill what we got. User confirms / edits in the form.
      if (result.invoice_number)    setInvoiceNumber(result.invoice_number);
      if (result.invoice_date)      setInvoiceDate(result.invoice_date);
      if (result.total_amount != null) setTotalAmount(String(result.total_amount));
      if (result.notes)             setNotes(result.notes);
      if (result.image_path)        setImagePath(result.image_path);

      if (result.items && result.items.length) {
        setItems(result.items.map((it) => ({
          product_id: null,
          product_name: it.product_name,
          qty: it.qty != null ? String(it.qty) : "",
          unit_cost: it.unit_cost != null ? String(it.unit_cost) : "",
        })));
      }

      // Auto-create / find the supplier if we got a name.
      if (result.supplier_name) {
        try {
          const s = await upsertSupplier(result.supplier_name);
          setSupplier({ supplier_id: s.id, supplier_name: s.name });
        } catch {
          setSupplier({ supplier_id: null, supplier_name: result.supplier_name });
        }
      }

      toast.push({
        kind: "success",
        title: "Fields extracted",
        body: `Confidence: ${result.confidence}. Please review before saving.`,
      });
    } catch (err) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.push({ kind: "error", title: "OCR failed", body: msg ?? "Try a clearer photo." });
    } finally {
      setOcrBusy(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  };

  const itemsTotal = items.reduce((s, it) => s + (Number(it.qty) || 0) * (Number(it.unit_cost) || 0), 0);

  const setItem = (idx: number, patch: Partial<DraftItem>) =>
    setItems((prev) => prev.map((it, i) => (i === idx ? { ...it, ...patch } : it)));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!invoiceNumber.trim()) { setError("Invoice number is required."); return; }
    if (!supplier.supplier_id) { setError("Pick or create a supplier."); return; }
    const total = Number(totalAmount);
    if (!total || total <= 0) { setError("Total amount must be greater than zero."); return; }

    const cleanItems: InvoiceItemCreate[] = items
      .filter((it) => it.product_name.trim() && Number(it.qty) > 0)
      .map((it) => ({
        product_id: it.product_id,
        product_name_raw: it.product_name.trim(),
        qty: Number(it.qty),
        unit_cost: Number(it.unit_cost) || 0,
      }));

    const body: InvoiceCreate = {
      invoice_number: invoiceNumber.trim(),
      supplier_id: supplier.supplier_id,
      invoice_date: invoiceDate,
      total_amount: total,
      notes: notes.trim() || null,
      image_path: imagePath,
      items: cleanItems,
    };

    setSubmitting(true);
    try {
      await createInvoice(body);
      toast.push({ kind: "success", title: "Invoice saved", body: `#${invoiceNumber}` });
      onSaved();
    } catch (err) {
      const e2 = err as { response?: { status?: number; data?: { detail?: string } } };
      if (e2.response?.status === 409) {
        setError(`Invoice ${invoiceNumber} already recorded.`);
        toast.push({ kind: "error", title: "Duplicate invoice", body: "Invoice number must be unique." });
      } else {
        setError(e2.response?.data?.detail ?? "Could not save invoice.");
      }
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
          {ocrBusy ? "Reading receipt…" : "📎 Upload receipt photo"}
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

      <div className="form-grid form-grid-2">
        <FormField label="Invoice number">
          <input
            className="form-input" value={invoiceNumber}
            onChange={(e) => setInvoiceNumber(e.target.value)}
            placeholder="e.g. INV-2026-042" required
          />
        </FormField>
        <FormField label="Invoice date">
          <input
            type="date" className="form-input" value={invoiceDate}
            onChange={(e) => setInvoiceDate(e.target.value)} required
          />
        </FormField>
      </div>
      <FormField label="Supplier">
        <SupplierPicker value={supplier} onChange={setSupplier} />
      </FormField>
      <FormField label="Total amount" hint="₹, on the invoice">
        <input
          type="number" step="0.01" min="0" className="form-input"
          value={totalAmount} onChange={(e) => setTotalAmount(e.target.value)}
          placeholder="0.00" required
        />
      </FormField>

      <FormField label="Line items" hint="optional — adds stock movements per product">
        <div className="line-items-list">
          {items.map((it, idx) => (
            <div key={idx} className="line-item-row">
              <ProductPicker
                value={{ product_id: it.product_id, product_name: it.product_name }}
                onChange={(v) => setItem(idx, {
                  product_id: v.product_id,
                  product_name: v.product_name,
                  unit_cost: v.cost_price && !it.unit_cost ? String(v.cost_price) : it.unit_cost,
                })}
              />
              <input
                className="form-input" type="number" step="0.001" min="0"
                value={it.qty} onChange={(e) => setItem(idx, { qty: e.target.value })}
                placeholder="Qty"
              />
              <input
                className="form-input" type="number" step="0.01" min="0"
                value={it.unit_cost} onChange={(e) => setItem(idx, { unit_cost: e.target.value })}
                placeholder="Unit cost"
              />
              <div className="text-muted" style={{ fontSize: 12, textAlign: "right" }}>
                ₹{((Number(it.qty) || 0) * (Number(it.unit_cost) || 0)).toFixed(2)}
              </div>
              <button
                type="button" className="line-item-remove" aria-label="Remove item"
                onClick={() => setItems((prev) => prev.filter((_, i) => i !== idx))}
                disabled={items.length === 1}
              >×</button>
            </div>
          ))}
          <button
            type="button" className="line-item-add"
            onClick={() => setItems((prev) => [...prev, emptyItem()])}
          >+ Add item</button>
        </div>
      </FormField>

      {itemsTotal > 0 && Math.abs(itemsTotal - Number(totalAmount)) > 0.01 && (
        <div className="text-muted" style={{ fontSize: 12 }}>
          Line items add up to ₹{itemsTotal.toFixed(2)} — does not match total above.
        </div>
      )}

      <FormField label="Notes">
        <textarea
          className="form-textarea" value={notes}
          onChange={(e) => setNotes(e.target.value)} placeholder="optional"
        />
      </FormField>

      {error && <div className="form-error">{error}</div>}
      <div className="form-actions">
        <button type="button" className="btn btn-ghost" onClick={onCancel} disabled={submitting}>Cancel</button>
        <button type="submit" className="btn btn-primary" disabled={submitting}>
          {submitting ? "Saving…" : "Save invoice"}
        </button>
      </div>
    </form>
  );
}
