import { useState } from "react";
import { createSale, SaleCreate } from "../api/client";
import { useToast } from "../hooks/useToast";
import CustomerPicker from "./CustomerPicker";
import FormField from "./FormField";
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

    const body: SaleCreate = {
      sale_date: date,
      product_id: product.product_id,
      customer_id: customer.customer_id,
      product_name_raw: product.product_name.trim(),
      qty_sold: qtyN,
      selling_price: priceN,
      source: "manual",
      raw_input: null,
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
        <CustomerPicker value={customer} onChange={setCustomer} />
      </FormField>
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
