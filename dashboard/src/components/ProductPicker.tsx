import { useEffect, useRef, useState } from "react";
import { fetchProductByBarcode, Product, searchProducts } from "../api/client";

interface ProductPickerProps {
  value: { product_id: number | null; product_name: string };
  onChange: (v: { product_id: number | null; product_name: string; selling_price?: number; cost_price?: number }) => void;
  placeholder?: string;
}

// Camera scanning is available wherever getUserMedia exists. We try the
// browser's native BarcodeDetector first (fast, Chromium-based) and fall
// back to @zxing/browser everywhere else — including iOS Safari, which
// doesn't ship BarcodeDetector. ZXing is dynamic-imported when the user
// actually opens the scanner so it doesn't bloat the main bundle.
const HAS_CAMERA =
  typeof navigator !== "undefined" &&
  !!navigator.mediaDevices &&
  typeof navigator.mediaDevices.getUserMedia === "function";

export default function ProductPicker({ value, onChange, placeholder }: ProductPickerProps) {
  const [query, setQuery] = useState(value.product_name);
  const [results, setResults] = useState<Product[]>([]);
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(0);
  const [scanning, setScanning] = useState(false);
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

  // Try barcode lookup first; if no match, fall back to free-text. Triggered
  // either by Enter on a numeric-only input or by the Scan flow's onResult.
  const handleScannedCode = async (code: string) => {
    setQuery(code);
    try {
      const p = await fetchProductByBarcode(code);
      pick(p);
    } catch {
      // Unknown barcode — leave the value as-is so the user can decide
      // whether to register it against an existing product via the Stock
      // page or proceed as free text.
      onChange({ product_id: null, product_name: code });
      setOpen(true);
    }
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") { setHighlight((h) => Math.min(h + 1, results.length)); e.preventDefault(); }
    else if (e.key === "ArrowUp") { setHighlight((h) => Math.max(h - 1, 0)); e.preventDefault(); }
    else if (e.key === "Enter") {
      e.preventDefault();
      // Numeric-only entry that hasn't matched a product is almost certainly
      // a barcode (handheld scanners type the code then hit Enter).
      const q = query.trim();
      if (q && /^\d{6,}$/.test(q) && results.every((r) => r.id.toString() !== q)) {
        void handleScannedCode(q);
        return;
      }
      if (highlight < results.length) pick(results[highlight]);
      else useFreeText();
    } else if (e.key === "Escape") setOpen(false);
  };

  return (
    <div className="picker" ref={wrap}>
      <div style={{ display: "flex", gap: 6 }}>
        <input
          className="form-input"
          style={{ flex: 1 }}
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
          placeholder={placeholder ?? "Search by name, SKU, or scan barcode…"}
        />
        {HAS_CAMERA && (
          <button
            type="button" className="btn btn-secondary btn-sm"
            onClick={() => setScanning(true)} title="Scan barcode"
          >📷</button>
        )}
      </div>
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
                {p.sku}{p.barcode ? ` · ⌗${p.barcode}` : ""} · stock {p.stock_qty}{p.unit ? " " + p.unit : ""} · ₹{p.selling_price}
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

      {scanning && (
        <BarcodeScannerModal
          onClose={() => setScanning(false)}
          onResult={(code) => {
            setScanning(false);
            void handleScannedCode(code);
          }}
        />
      )}
    </div>
  );
}

// ── Camera-based barcode scanner ─────────────────────────────────────────
//
// Two backends: browser-native BarcodeDetector when present (Chromium),
// and @zxing/browser elsewhere — Safari, Firefox, older Android Chrome.
// Loads ZXing on demand via dynamic import so the main bundle stays small.

type ZxingControls = { stop: () => void };

function BarcodeScannerModal({
  onResult, onClose,
}: { onResult: (code: string) => void; onClose: () => void }) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let stopped = false;
    let stream: MediaStream | null = null;
    let frame = 0;
    let zxingControls: ZxingControls | null = null;

    const hasNative =
      typeof (window as unknown as { BarcodeDetector?: unknown }).BarcodeDetector === "function";

    const fail = (e: unknown) => {
      if (stopped) return;
      setError(e instanceof Error ? e.message : "Could not access camera");
    };

    const startNative = async () => {
      type Detector = { detect: (s: CanvasImageSource) => Promise<{ rawValue: string }[]> };
      const W = window as unknown as {
        BarcodeDetector: new (opts?: { formats?: string[] }) => Detector;
      };
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment" }, audio: false,
      });
      if (stopped || !videoRef.current) return;
      videoRef.current.srcObject = stream;
      await videoRef.current.play();
      const detector = new W.BarcodeDetector({
        formats: ["ean_13", "ean_8", "upc_a", "upc_e", "code_128", "code_39", "qr_code"],
      });
      const tick = async () => {
        if (stopped || !videoRef.current) return;
        try {
          const codes = await detector.detect(videoRef.current);
          if (codes.length > 0) { onResult(codes[0].rawValue); return; }
        } catch { /* keep scanning */ }
        frame = requestAnimationFrame(tick);
      };
      frame = requestAnimationFrame(tick);
    };

    const startZxing = async () => {
      const { BrowserMultiFormatReader } = await import("@zxing/browser");
      if (stopped || !videoRef.current) return;
      const reader = new BrowserMultiFormatReader();
      const controls = await reader.decodeFromVideoDevice(
        undefined, // let the lib pick the rear camera
        videoRef.current,
        (result) => {
          if (stopped) return;
          if (result) onResult(result.getText());
        },
      );
      zxingControls = controls;
    };

    (async () => {
      try {
        if (hasNative) await startNative();
        else await startZxing();
      } catch (e) {
        fail(e);
      }
    })();

    return () => {
      stopped = true;
      cancelAnimationFrame(frame);
      if (zxingControls) zxingControls.stop();
      if (stream) stream.getTracks().forEach((t) => t.stop());
    };
  }, [onResult]);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal-card"
        style={{ maxWidth: 480 }}
        onClick={(e) => e.stopPropagation()}
        role="dialog" aria-modal="true"
      >
        <div className="modal-head">
          <h2>Scan barcode</h2>
          <button className="modal-close" onClick={onClose} aria-label="Close">×</button>
        </div>
        <div className="modal-body">
          {error ? (
            <div className="form-error">{error}</div>
          ) : (
            <video
              ref={videoRef}
              playsInline muted
              style={{ width: "100%", borderRadius: 12, background: "#000" }}
            />
          )}
          <div className="text-muted" style={{ fontSize: 12, marginTop: 8 }}>
            Point at the barcode. Scanning happens automatically.
          </div>
        </div>
      </div>
    </div>
  );
}
