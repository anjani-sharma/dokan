import { useEffect, useState } from "react";
import { fetchProducts, fetchStockMovements, fmt, Product, StockMovement } from "../api/client";
import StatusBadge from "../components/StatusBadge";

export default function Stock() {
  const [products, setProducts] = useState<Product[]>([]);
  const [movements, setMovements] = useState<StockMovement[]>([]);
  const [selectedProduct, setSelectedProduct] = useState<number | null>(null);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([fetchProducts(), fetchStockMovements()])
      .then(([p, m]) => { setProducts(p); setMovements(m); })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (selectedProduct !== null) {
      fetchStockMovements(selectedProduct).then(setMovements);
    } else {
      fetchStockMovements().then(setMovements);
    }
  }, [selectedProduct]);

  const filtered = products.filter(p =>
    p.name.toLowerCase().includes(search.toLowerCase()) ||
    p.sku.toLowerCase().includes(search.toLowerCase())
  );

  const isLow = (p: Product) => p.reorder_level > 0 && p.stock_qty <= p.reorder_level;

  if (loading) return <div className="page-loading">Loading stock…</div>;

  return (
    <div className="page">
      <div className="page-header">
        <h1>Stock</h1>
        <input
          className="search-input"
          placeholder="Search products…"
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
              </tr>
            </thead>
            <tbody>
              {filtered.map(p => (
                <tr
                  key={p.id}
                  className={`clickable-row ${isLow(p) ? "row-warning" : ""} ${selectedProduct === p.id ? "row-selected" : ""}`}
                  onClick={() => setSelectedProduct(prev => prev === p.id ? null : p.id)}
                >
                  <td className="text-muted">{p.sku}</td>
                  <td><strong>{p.name}</strong></td>
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
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr><td colSpan={8} className="empty-state">No products found.</td></tr>
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
    </div>
  );
}
