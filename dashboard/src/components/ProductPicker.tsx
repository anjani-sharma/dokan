import { useEffect, useRef, useState } from "react";
import { Product, searchProducts } from "../api/client";

interface ProductPickerProps {
  value: { product_id: number | null; product_name: string };
  onChange: (v: { product_id: number | null; product_name: string; selling_price?: number; cost_price?: number }) => void;
  placeholder?: string;
}

export default function ProductPicker({ value, onChange, placeholder }: ProductPickerProps) {
  const [query, setQuery] = useState(value.product_name);
  const [results, setResults] = useState<Product[]>([]);
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(0);
  const timer = useRef<number | undefined>(undefined);
  const wrap = useRef<HTMLDivElement | null>(null);

  // Keep input in sync if parent resets value
  useEffect(() => { setQuery(value.product_name); }, [value.product_name]);

  // Debounced search
  useEffect(() => {
    if (!open) return;
    window.clearTimeout(timer.current);
    if (query.trim().length < 1) { setResults([]); return; }
    timer.current = window.setTimeout(() => {
      searchProducts(query.trim())
        .then(setResults)
        .catch(() => setResults([]));
    }, 200);
    return () => window.clearTimeout(timer.current);
  }, [query, open]);

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (wrap.current && !wrap.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const pick = (p: Product) => {
    onChange({
      product_id: p.id,
      product_name: p.name,
      selling_price: p.selling_price,
      cost_price: p.cost_price,
    });
    setQuery(p.name);
    setOpen(false);
  };

  const useFreeText = () => {
    onChange({ product_id: null, product_name: query.trim() });
    setOpen(false);
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") { setHighlight((h) => Math.min(h + 1, results.length)); e.preventDefault(); }
    else if (e.key === "ArrowUp") { setHighlight((h) => Math.max(h - 1, 0)); e.preventDefault(); }
    else if (e.key === "Enter") {
      e.preventDefault();
      if (highlight < results.length) pick(results[highlight]);
      else useFreeText();
    } else if (e.key === "Escape") setOpen(false);
  };

  return (
    <div className="picker" ref={wrap}>
      <input
        className="form-input"
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
          setHighlight(0);
          // If user clears, also clear the bound product_id
          if (value.product_id && e.target.value !== value.product_name) {
            onChange({ product_id: null, product_name: e.target.value });
          }
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKeyDown}
        placeholder={placeholder ?? "Search product…"}
      />
      {open && query.trim() && (
        <div className="picker-menu">
          {results.length === 0 && <div className="picker-empty">No matches</div>}
          {results.map((p, i) => (
            <div
              key={p.id}
              className={"picker-item" + (i === highlight ? " highlight" : "")}
              onClick={() => pick(p)}
              onMouseEnter={() => setHighlight(i)}
            >
              <div className="bold">{p.name}</div>
              <div className="text-muted" style={{ fontSize: 11 }}>
                {p.sku} · stock {p.stock_qty}{p.unit ? " " + p.unit : ""} · ₹{p.selling_price}
              </div>
            </div>
          ))}
          <div
            className={"picker-item picker-item-create" + (highlight === results.length ? " highlight" : "")}
            onClick={useFreeText}
            onMouseEnter={() => setHighlight(results.length)}
          >
            + Use "{query.trim()}" as-is (no catalog match)
          </div>
        </div>
      )}
    </div>
  );
}
