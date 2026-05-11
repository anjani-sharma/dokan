import { useState } from "react";
import { createCustomer, createSale, SaleCreate } from "../api/client";
import { useToast } from "../hooks/useToast";
import CustomerPicker from "./CustomerPicker";
import FormField from "./FormField";
import Modal from "./Modal";
import ProductPicker from "./ProductPicker";

const today = () => new Date().toISOString().slice(0, 10);

interface SaleFormProps {
  onSaved: () => void;
  onCancel: () => void;
  defaultDate?: string;
}

export default function SaleForm({ onSaved, onCancel, defaultDate }: SaleFormProps) {
  const toast = useToast();
  const [date, setDate] = useState(defaultDate ?? today());
  const [product, setProduct] = useState<{ product_id: number | null; product_name: string }>({
    product_id: null, product_name: "",
  });
  const [customer, setCustomer] = useState<{ customer_id: number | null; customer_name: string }>({
    customer_id: null, customer_name: "",
  });
  const [qty, setQty] = useState("");
  const [price, setPrice] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showNewCustomer, setShowNewCustomer] = useState(false);
  // Point-of-sale payment state. Default to "full" — the common case is
  // a walk-in cash sale paid in full at the till.
  const [payKind, setPayKind] = useState<"full" | "partial" | "credit">("full");
  const [payMode, setPayMode] = useState<"cash" | "gpay" | "upi" | "bank_deposit" | "other">("cash");
  const [partialAmount, setPartialAmount] = useState("");

  const lineTotal = (Number(qty) || 0) * (Number(price) || 0);

  const onPickProduct = (v: { product_id: number | null; product_name: string; selling_price?: number }) => {
    setProduct({ product_id: v.product_id, product_name: v.product_name });
    if (v.selling_price && !price) setPrice(String(v.selling_price));
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!product.product_name.trim()) { setError("Pick a product or type its name."); return; }
    const qtyN = Number(qty);
    const priceN = Number(price);
    if (!qtyN || qtyN <= 0) { setError("Quantity must be greater than zero."); return; }
    if (priceN < 0) { setError("Price cannot be negative."); return; }

    let paymentAmount: number | null = null;
    if (payKind === "full") {
      paymentAmount = qtyN * priceN;
    } else if (payKind === "partial") {
      const pn = Number(partialAmount);
      if (!pn || pn <= 0) { setError("Enter the partial payment amount."); return; }
      if (pn > qtyN * priceN + 0.001) { setError("Partial payment can't exceed sale total."); return; }
      paymentAmount = pn;
    }

    const body: SaleCreate = {
      sale_date: date,
      product_id: product.product_id,
      customer_id: customer.customer_id,
      product_name_raw: product.product_name.trim(),
      qty_sold: qtyN,
      selling_price: priceN,
      source: "manual",
      raw_input: null,
      payment_amount: paymentAmount,
      payment_mode: paymentAmount ? payMode : null,
    };
    setSubmitting(true);
    try {
      await createSale(body);
      toast.push({ kind: "success", title: "Sale recorded", body: `${qtyN} × ${product.product_name}` });
      onSaved();
    } catch (err) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg ?? "Could not save sale.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={submit} className="form-grid">
      <div className="form-grid form-grid-2">
        <FormField label="Date">
          <input type="date" className="form-input" value={date} onChange={(e) => setDate(e.target.value)} required />
        </FormField>
        <FormField label="Quantity">
          <input
            type="number" step="0.001" min="0" className="form-input"
            value={qty} onChange={(e) => setQty(e.target.value)}
            placeholder="e.g. 5" required
          />
        </FormField>
      </div>
      <FormField label="Product">
        <ProductPicker value={product} onChange={onPickProduct} />
      </FormField>
      <FormField label="Selling price" hint="₹ per unit">
        <input
          type="number" step="0.01" min="0" className="form-input"
          value={price} onChange={(e) => setPrice(e.target.value)}
          placeholder="0.00"
        />
      </FormField>
      <FormField label="Customer" hint="optional — for credit / installment sales">
        <div style={{ display: "flex", gap: 8, alignItems: "stretch" }}>
          <div style={{ flex: 1 }}>
            <CustomerPicker value={customer} onChange={setCustomer} />
          </div>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => setShowNewCustomer(true)}
          >
            + New
          </button>
        </div>
      </FormField>

      <Modal
        open={showNewCustomer}
        onClose={() => setShowNewCustomer(false)}
        title="Add a new customer"
      >
        <NewCustomerInlineForm
          onCancel={() => setShowNewCustomer(false)}
          onCreated={(c) => {
            setCustomer({ customer_id: c.id, customer_name: c.name });
            setShowNewCustomer(false);
            toast.push({ kind: "success", title: "Customer added", body: c.name });
          }}
        />
      </Modal>
      <FormField label="Payment received" hint="record what changed hands at the till">
        <div className="filter-group">
          <button
            type="button"
            className={"filter-btn" + (payKind === "full" ? " active" : "")}
            onClick={() => setPayKind("full")}
          >Full ({lineTotal ? `₹${lineTotal.toFixed(2)}` : "—"})</button>
          <button
            type="button"
            className={"filter-btn" + (payKind === "partial" ? " active" : "")}
            onClick={() => setPayKind("partial")}
          >Partial</button>
          <button
            type="button"
            className={"filter-btn" + (payKind === "credit" ? " active" : "")}
            onClick={() => setPayKind("credit")}
          >On credit</button>
        </div>
      </FormField>

      {payKind !== "credit" && (
        <div className="form-grid form-grid-2">
          {payKind === "partial" && (
            <FormField label="Amount paid now" hint="₹">
              <input
                type="number" step="0.01" min="0" className="form-input"
                value={partialAmount} onChange={(e) => setPartialAmount(e.target.value)}
                placeholder="0.00"
              />
            </FormField>
          )}
          <FormField label="Payment mode">
            <select
              className="form-select" value={payMode}
              onChange={(e) => setPayMode(e.target.value as typeof payMode)}
            >
              <option value="cash">Cash</option>
              <option value="gpay">GPay</option>
              <option value="upi">UPI</option>
              <option value="bank_deposit">Bank deposit</option>
              <option value="other">Other</option>
            </select>
          </FormField>
        </div>
      )}

      {payKind === "credit" && customer.customer_id == null && (
        <div className="text-muted" style={{ fontSize: 12 }}>
          Tip: attach a customer above so the outstanding balance shows up on the Customers page.
        </div>
      )}

      {error && <div className="form-error">{error}</div>}
      <div className="form-actions">
        <button type="button" className="btn btn-ghost" onClick={onCancel} disabled={submitting}>Cancel</button>
        <button type="submit" className="btn btn-primary" disabled={submitting}>
          {submitting ? "Saving…" : "Save sale"}
        </button>
      </div>
    </form>
  );
}

// ── Inline create-customer panel used by the Sales flow ────────────────────

function NewCustomerInlineForm({
  onCreated,
  onCancel,
}: {
  onCreated: (c: { id: number; name: string }) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!name.trim()) { setError("Name is required."); return; }
    setSubmitting(true);
    try {
      const created = await createCustomer({
        name: name.trim(),
        phone: phone.trim() || null,
        address: address.trim() || null,
      });
      onCreated({ id: created.id, name: created.name });
    } catch (err) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg ?? "Could not create customer.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={submit} className="form-grid">
      <FormField label="Name">
        <input
          className="form-input" value={name} autoFocus required
          onChange={(e) => setName(e.target.value)}
        />
      </FormField>
      <div className="form-grid form-grid-2">
        <FormField label="Phone">
          <input
            className="form-input" value={phone}
            onChange={(e) => setPhone(e.target.value)} placeholder="optional"
          />
        </FormField>
        <FormField label="Address">
          <input
            className="form-input" value={address}
            onChange={(e) => setAddress(e.target.value)} placeholder="optional"
          />
        </FormField>
      </div>
      {error && <div className="form-error">{error}</div>}
      <div className="form-actions">
        <button type="button" className="btn btn-ghost" onClick={onCancel} disabled={submitting}>Cancel</button>
        <button type="submit" className="btn btn-primary" disabled={submitting}>
          {submitting ? "Adding…" : "Add customer"}
        </button>
      </div>
    </form>
  );
}
