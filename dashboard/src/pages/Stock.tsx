import { useEffect, useState } from "react";
import {
  fetchProducts, fetchStockMovements, fmt, Product, ProductUpdate, StockMovement,
  updateProduct,
} from "../api/client";
import { useToast } from "../hooks/useToast";
import FormField from "../components/FormField";
import Modal from "../components/Modal";
import StatusBadge from "../components/StatusBadge";

export default function Stock() {
  const [products, setProducts] = useState<Product[]>([]);
  const [movements, setMovements] = useState<StockMovement[]>([]);
  const [selectedProduct, setSelectedProduct] = useState<number | null>(null);
  const [editing, setEditing] = useState<Product | null>(null);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  const refresh = () => {
    setLoading(true);
    Promise.all([fetchProducts(false), fetchStockMovements()])
      .then(([p, m]) => { setProducts(p); setMovements(m); })
      .finally(() => setLoading(false));
  };

  useEffect(() => { refresh(); }, []);

  useEffect(() => {
    if (selectedProduct !== null) {
      fetchStockMovements(selectedProduct).then(setMovements);
    } else {
      fetchStockMovements().then(setMovements);
    }
  }, [selectedProduct]);

  useEffect(() => {
    const onChanged = () => refresh();
    window.addEventListener("ananta:data-changed", onChanged);
    return () => window.removeEventListener("ananta:data-changed", onChanged);
  }, []);

  const filtered = products.filter(p =>
    p.name.toLowerCase().includes(search.toLowerCase()) ||
    p.sku.toLowerCase().includes(search.toLowerCase()) ||
    (p.barcode ?? "").toLowerCase().includes(search.toLowerCase())
  );

  const isLow = (p: Product) => p.reorder_level > 0 && p.stock_qty <= p.reorder_level;

  if (loading) return <div className="page-loading">Loading stock…</div>;

  return (
    <div className="page">
      <div className="page-header">
        <h1>Stock</h1>
        <input
          className="search-input"
          placeholder="Search by name, SKU, or barcode…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
      </div>

      <div className="stock-layout">
        {/* Product table */}
        <div className="table-card">
          <table className="data-table">
            <thead>
              <tr>
                <th>SKU</th>
                <th>Product</th>
                <th>Unit</th>
                <th>Stock</th>
                <th>Reorder At</th>
                <th>Cost Price</th>
                <th>Sell Price</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(p => (
                <tr
                  key={p.id}
                  className={`clickable-row ${isLow(p) ? "row-warning" : ""} ${selectedProduct === p.id ? "row-selected" : ""}`}
                  onClick={() => setSelectedProduct(prev => prev === p.id ? null : p.id)}
                >
                  <td className="text-muted">
                    {p.sku}
                    {p.barcode && <div style={{ fontSize: 10, color: "var(--text-dim)" }}>⌗ {p.barcode}</div>}
                  </td>
                  <td><strong>{p.name}</strong>{!p.is_active && <span className="badge badge-grey" style={{ marginLeft: 6 }}>inactive</span>}</td>
                  <td>{p.unit ?? "—"}</td>
                  <td className={isLow(p) ? "text-orange bold" : ""}>{p.stock_qty}</td>
                  <td>{p.reorder_level > 0 ? p.reorder_level : "—"}</td>
                  <td>{fmt(p.cost_price)}</td>
                  <td>{fmt(p.selling_price)}</td>
                  <td>
                    {isLow(p)
                      ? <span className="badge badge-orange">Low</span>
                      : <span className="badge badge-green">OK</span>
                    }
                  </td>
                  <td style={{ textAlign: "right" }}>
                    <button
                      className="btn btn-ghost btn-sm"
                      onClick={(e) => { e.stopPropagation(); setEditing(p); }}
                    >Edit</button>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr><td colSpan={9} className="empty-state">No products found.</td></tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Movement log */}
        <div className="table-card movements-card">
          <h2>
            {selectedProduct
              ? `Movements — ${products.find(p => p.id === selectedProduct)?.name}`
              : "Recent Stock Movements"}
          </h2>
          {selectedProduct && (
            <button className="btn btn-ghost" onClick={() => setSelectedProduct(null)}>
              ← Show all
            </button>
          )}
          <table className="data-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Type</th>
                <th>Qty Change</th>
                <th>Reference</th>
              </tr>
            </thead>
            <tbody>
              {movements.slice(0, 30).map(m => (
                <tr key={m.id}>
                  <td className="text-muted">{new Date(m.moved_at).toLocaleDateString("en-IN")}</td>
                  <td><StatusBadge status={m.movement_type} /></td>
                  <td className={m.qty_change >= 0 ? "text-green" : "text-red"}>
                    {m.qty_change >= 0 ? "+" : ""}{m.qty_change}
                  </td>
                  <td className="text-muted">{m.reference_type ?? "—"}</td>
                </tr>
              ))}
              {movements.length === 0 && (
                <tr><td colSpan={4} className="empty-state">No movements yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {editing && (
        <Modal open onClose={() => setEditing(null)} title={`Edit ${editing.name}`}>
          <ProductEditForm
            product={editing}
            onCancel={() => setEditing(null)}
            onSaved={() => { setEditing(null); refresh(); }}
          />
        </Modal>
      )}
    </div>
  );
}

// ── Product edit form ──────────────────────────────────────────────────────

function ProductEditForm({
  product, onSaved, onCancel,
}: {
  product: Product;
  onSaved: () => void;
  onCancel: () => void;
}) {
  const toast = useToast();
  const [sku, setSku] = useState(product.sku);
  const [barcode, setBarcode] = useState(product.barcode ?? "");
  const [name, setName] = useState(product.name);
  const [unit, setUnit] = useState(product.unit ?? "");
  const [cost, setCost] = useState(String(product.cost_price));
  const [price, setPrice] = useState(String(product.selling_price));
  const [stock, setStock] = useState(String(product.stock_qty));
  const [reorder, setReorder] = useState(String(product.reorder_level));
  const [active, setActive] = useState(product.is_active);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!name.trim()) { setError("Name is required."); return; }
    if (!sku.trim()) { setError("SKU is required."); return; }
    const body: ProductUpdate = {
      sku: sku.trim(),
      barcode: barcode.trim() || null,
      name: name.trim(),
      unit: unit.trim() || null,
      cost_price: Number(cost) || 0,
      selling_price: Number(price) || 0,
      stock_qty: Number(stock) || 0,
      reorder_level: Number(reorder) || 0,
      is_active: active,
    };
    setSubmitting(true);
    try {
      await updateProduct(product.id, body);
      toast.push({ kind: "success", title: "Product updated", body: name });
      onSaved();
    } catch (err) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg ?? "Could not update product.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={submit} className="form-grid">
      <div className="form-grid form-grid-2">
        <FormField label="SKU">
          <input className="form-input" value={sku} onChange={(e) => setSku(e.target.value)} required />
        </FormField>
        <FormField label="Barcode" hint="UPC/EAN — optional">
          <input
            className="form-input" value={barcode}
            onChange={(e) => setBarcode(e.target.value)}
            placeholder="Scan or type…"
          />
        </FormField>
      </div>
      <FormField label="Name">
        <input className="form-input" value={name} onChange={(e) => setName(e.target.value)} required />
      </FormField>
      <div className="form-grid form-grid-2">
        <FormField label="Unit">
          <input
            className="form-input" value={unit}
            onChange={(e) => setUnit(e.target.value)}
            placeholder="e.g. pcs, mtr, kg"
          />
        </FormField>
        <FormField label="Reorder level">
          <input
            type="number" step="0.001" min="0" className="form-input"
            value={reorder} onChange={(e) => setReorder(e.target.value)}
          />
        </FormField>
      </div>
      <div className="form-grid form-grid-2">
        <FormField label="Cost price" hint="₹">
          <input
            type="number" step="0.01" min="0" className="form-input"
            value={cost} onChange={(e) => setCost(e.target.value)}
          />
        </FormField>
        <FormField label="Selling price" hint="₹">
          <input
            type="number" step="0.01" min="0" className="form-input"
            value={price} onChange={(e) => setPrice(e.target.value)}
          />
        </FormField>
      </div>
      <FormField label="Stock on hand" hint="adjusts stock_qty directly — use for opening balances or corrections">
        <input
          type="number" step="0.001" min="0" className="form-input"
          value={stock} onChange={(e) => setStock(e.target.value)}
        />
      </FormField>
      <FormField label="Active">
        <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} />
          <span className="text-muted" style={{ fontSize: 12 }}>
            Inactive products are hidden from pickers and reports.
          </span>
        </label>
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
