import { useEffect, useRef, useState } from "react";
import { CustomerSummary, fetchCustomers, upsertCustomer } from "../api/client";

interface CustomerPickerProps {
  value: { customer_id: number | null; customer_name: string };
  onChange: (v: { customer_id: number | null; customer_name: string }) => void;
  placeholder?: string;
}

export default function CustomerPicker({ value, onChange, placeholder }: CustomerPickerProps) {
  const [all, setAll] = useState<CustomerSummary[]>([]);
  const [query, setQuery] = useState(value.customer_name);
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(0);
  const [creating, setCreating] = useState(false);
  const wrap = useRef<HTMLDivElement | null>(null);

  useEffect(() => { fetchCustomers().then(setAll).catch(() => setAll([])); }, []);
  useEffect(() => { setQuery(value.customer_name); }, [value.customer_name]);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (wrap.current && !wrap.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const filtered = query.trim()
    ? all.filter((c) => c.name.toLowerCase().includes(query.trim().toLowerCase()))
    : all;

  const pick = (c: CustomerSummary) => {
    onChange({ customer_id: c.id, customer_name: c.name });
    setQuery(c.name);
    setOpen(false);
  };

  const createNew = async () => {
    if (!query.trim() || creating) return;
    setCreating(true);
    try {
      const c = await upsertCustomer({ name: query.trim() });
      const summary: CustomerSummary = {
        id: c.id, name: c.name, phone: c.phone,
        total_sales: 0, total_received: 0, balance: 0, last_activity: null,
        oldest_due_date: null, days_overdue: null,
      };
      setAll((prev) => prev.some((x) => x.id === c.id) ? prev : [...prev, summary]);
      pick(summary);
    } finally {
      setCreating(false);
    }
  };

  const clearChoice = () => {
    setQuery("");
    onChange({ customer_id: null, customer_name: "" });
    setOpen(false);
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") { setHighlight((h) => Math.min(h + 1, filtered.length)); e.preventDefault(); }
    else if (e.key === "ArrowUp") { setHighlight((h) => Math.max(h - 1, 0)); e.preventDefault(); }
    else if (e.key === "Enter") {
      e.preventDefault();
      if (highlight < filtered.length) pick(filtered[highlight]);
      else void createNew();
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
          if (value.customer_id && e.target.value !== value.customer_name) {
            onChange({ customer_id: null, customer_name: e.target.value });
          }
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKeyDown}
        placeholder={placeholder ?? "Walk-in customer (optional)…"}
      />
      {open && (
        <div className="picker-menu">
          {value.customer_id && (
            <div className="picker-item" onClick={clearChoice} style={{ color: "var(--text-muted)" }}>
              ✕ Clear — walk-in / no customer
            </div>
          )}
          {filtered.length === 0 && !query.trim() && <div className="picker-empty">No customers yet</div>}
          {filtered.map((c, i) => (
            <div
              key={c.id}
              className={"picker-item" + (i === highlight ? " highlight" : "")}
              onClick={() => pick(c)}
              onMouseEnter={() => setHighlight(i)}
            >
              <div className="bold">{c.name}</div>
              <div className="text-muted" style={{ fontSize: 11 }}>
                {c.phone ?? "no phone"} · balance ₹{c.balance.toFixed(2)}
              </div>
            </div>
          ))}
          {query.trim() && !filtered.some((c) => c.name.toLowerCase() === query.trim().toLowerCase()) && (
            <div
              className={"picker-item picker-item-create" + (highlight === filtered.length ? " highlight" : "")}
              onClick={createNew}
              onMouseEnter={() => setHighlight(filtered.length)}
            >
              + Create customer "{query.trim()}"
            </div>
          )}
        </div>
      )}
    </div>
  );
}
