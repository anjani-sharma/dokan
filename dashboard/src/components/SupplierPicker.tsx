import { useEffect, useRef, useState } from "react";
import { Supplier, fetchSuppliers, upsertSupplier } from "../api/client";

interface SupplierPickerProps {
  value: { supplier_id: number | null; supplier_name: string };
  onChange: (v: { supplier_id: number | null; supplier_name: string }) => void;
}

export default function SupplierPicker({ value, onChange }: SupplierPickerProps) {
  const [all, setAll] = useState<Supplier[]>([]);
  const [query, setQuery] = useState(value.supplier_name);
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(0);
  const [creating, setCreating] = useState(false);
  const wrap = useRef<HTMLDivElement | null>(null);

  useEffect(() => { fetchSuppliers().then(setAll).catch(() => setAll([])); }, []);
  useEffect(() => { setQuery(value.supplier_name); }, [value.supplier_name]);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (wrap.current && !wrap.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const filtered = query.trim()
    ? all.filter((s) => s.name.toLowerCase().includes(query.trim().toLowerCase()))
    : all;

  const pick = (s: Supplier) => {
    onChange({ supplier_id: s.id, supplier_name: s.name });
    setQuery(s.name);
    setOpen(false);
  };

  const createNew = async () => {
    if (!query.trim() || creating) return;
    setCreating(true);
    try {
      const s = await upsertSupplier(query.trim());
      setAll((prev) => prev.some((x) => x.id === s.id) ? prev : [...prev, s]);
      pick(s);
    } finally {
      setCreating(false);
    }
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
          if (value.supplier_id && e.target.value !== value.supplier_name) {
            onChange({ supplier_id: null, supplier_name: e.target.value });
          }
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKeyDown}
        placeholder="Search or add supplier…"
      />
      {open && (
        <div className="picker-menu">
          {filtered.length === 0 && !query.trim() && <div className="picker-empty">No suppliers yet</div>}
          {filtered.map((s, i) => (
            <div
              key={s.id}
              className={"picker-item" + (i === highlight ? " highlight" : "")}
              onClick={() => pick(s)}
              onMouseEnter={() => setHighlight(i)}
            >
              <div className="bold">{s.name}</div>
              {s.phone && <div className="text-muted" style={{ fontSize: 11 }}>{s.phone}</div>}
            </div>
          ))}
          {query.trim() && !filtered.some((s) => s.name.toLowerCase() === query.trim().toLowerCase()) && (
            <div
              className={"picker-item picker-item-create" + (highlight === filtered.length ? " highlight" : "")}
              onClick={createNew}
              onMouseEnter={() => setHighlight(filtered.length)}
            >
              + Create supplier "{query.trim()}"
            </div>
          )}
        </div>
      )}
    </div>
  );
}
