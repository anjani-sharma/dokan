import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  commitImport,
  discardImport,
  fetchSuppliers,
  fmt,
  listImports,
  uploadImports,
  uploadPaymentsCsv,
  type ImportJob,
  type ImportJobStatus,
  type Supplier,
} from "../api/client";
import Modal from "../components/Modal";
import { useToast } from "../hooks/useToast";

type Kind = "invoice" | "payment";

const STATUS_FILTERS: { key: ImportJobStatus | "all"; label: string }[] = [
  { key: "all",          label: "All" },
  { key: "pending",      label: "Pending" },
  { key: "extracting",   label: "Reading" },
  { key: "needs_review", label: "Needs review" },
  { key: "duplicate",    label: "Duplicates" },
  { key: "posted",       label: "Posted" },
  { key: "failed",       label: "Failed" },
];

const ACCEPT = "image/*,application/pdf";
const STATUS_COLORS: Record<ImportJobStatus, string> = {
  pending:      "#888",
  extracting:   "#1976d2",
  needs_review: "#f57c00",
  duplicate:    "#c62828",
  posted:       "#2e7d32",
  failed:       "#c62828",
};

export default function BulkImport() {
  const toast = useToast();
  const [kind, setKind]       = useState<Kind>("invoice");
  const [filter, setFilter]   = useState<ImportJobStatus | "all">("all");
  const [jobs, setJobs]       = useState<ImportJob[]>([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy]       = useState(false);
  const [dragging, setDragging] = useState(false);
  const [reviewJob, setReviewJob] = useState<ImportJob | null>(null);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const fileInput = useRef<HTMLInputElement | null>(null);
  const csvInput  = useRef<HTMLInputElement | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const params = filter === "all" ? { kind } : { kind, status: filter };
      const data = await listImports(params);
      setJobs(data);
    } finally {
      setLoading(false);
    }
  }, [kind, filter]);

  useEffect(() => { refresh(); }, [refresh]);

  // Suppliers loaded once for the review form dropdown.
  useEffect(() => {
    fetchSuppliers().then(setSuppliers).catch(() => undefined);
  }, []);

  // Poll while anything is still in flight. Stops as soon as the queue drains.
  const hasWaiting = jobs.some(
    (j) => j.status === "pending" || j.status === "extracting"
  );
  useEffect(() => {
    if (!hasWaiting) return;
    const t = setInterval(refresh, 5000);
    return () => clearInterval(t);
  }, [hasWaiting, refresh]);

  const uploadFiles = async (files: File[]) => {
    if (files.length === 0) return;
    setBusy(true);
    try {
      const res = await uploadImports(files, kind);
      toast.push({
        kind: "success",
        title: `${res.queued} file${res.queued === 1 ? "" : "s"} queued`,
        body: "Will appear under 'Reading' as the OCR worker picks them up.",
      });
      await refresh();
    } catch (e: unknown) {
      toast.push({ kind: "error", title: "Upload failed", body: errMsg(e) });
    } finally {
      setBusy(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  };

  const onDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(false);
    const files = Array.from(e.dataTransfer.files ?? []);
    uploadFiles(files);
  };

  const uploadCsv = async (file: File | undefined) => {
    if (!file) return;
    setBusy(true);
    try {
      const res = await uploadPaymentsCsv(file);
      toast.push({
        kind: "success",
        title: `${res.queued} payment row${res.queued === 1 ? "" : "s"} queued`,
      });
      await refresh();
    } catch (e: unknown) {
      toast.push({ kind: "error", title: "CSV upload failed", body: errMsg(e) });
    } finally {
      setBusy(false);
      if (csvInput.current) csvInput.current.value = "";
    }
  };

  const counts = useMemo(() => {
    const c: Partial<Record<ImportJobStatus, number>> = {};
    for (const j of jobs) c[j.status] = (c[j.status] ?? 0) + 1;
    return c;
  }, [jobs]);

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Bulk import</h1>
          <div className="page-subtitle">
            Drop invoice photos or PDFs — the OCR worker reads each one, flags duplicates,
            and queues them for your review before posting.
          </div>
        </div>
        <div className="header-actions">
          <div className="filter-group">
            <button
              className={`filter-btn ${kind === "invoice" ? "active" : ""}`}
              onClick={() => setKind("invoice")}
            >
              Invoices
            </button>
            <button
              className={`filter-btn ${kind === "payment" ? "active" : ""}`}
              onClick={() => setKind("payment")}
            >
              Payments
            </button>
          </div>
        </div>
      </div>

      {kind === "payment" && (
        <div style={{ marginBottom: 12, fontSize: 13 }}>
          Bulk CSV import:{" "}
          <a href="/payments-template.csv" download style={{ color: "#1976d2" }}>
            download template
          </a>
          {", "}
          fill in your rows, then upload:{" "}
          <button
            className="btn btn-small"
            onClick={() => csvInput.current?.click()}
            disabled={busy}
            style={{ marginLeft: 4 }}
          >
            Upload CSV
          </button>
          <input
            ref={csvInput}
            type="file" accept=".csv,text/csv"
            style={{ display: "none" }}
            onChange={(e) => uploadCsv(e.target.files?.[0])}
          />
        </div>
      )}

      {/* ── Drop zone ──────────────────────────────────────────────────── */}
      <div
        className="dropzone"
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => fileInput.current?.click()}
        style={{
          border: `2px dashed ${dragging ? "#1976d2" : "#bbb"}`,
          background: dragging ? "rgba(25,118,210,0.05)" : "#fafafa",
          borderRadius: 8,
          padding: "28px 16px",
          textAlign: "center",
          cursor: "pointer",
          marginBottom: 16,
          opacity: busy ? 0.6 : 1,
        }}
      >
        <input
          type="file"
          ref={fileInput}
          multiple
          accept={ACCEPT}
          style={{ display: "none" }}
          disabled={busy}
          onChange={(e) => uploadFiles(Array.from(e.target.files ?? []))}
        />
        <div style={{ fontSize: 16, fontWeight: 500 }}>
          {busy ? "Uploading…" : `Drop ${kind === "invoice" ? "invoice photos / PDFs" : "payment screenshots"} here`}
        </div>
        <div className="muted" style={{ marginTop: 6, fontSize: 13 }}>
          or click to choose files — JPG, PNG, WEBP, PDF
        </div>
      </div>

      {/* ── Status filters ─────────────────────────────────────────────── */}
      <div className="filter-group" style={{ marginBottom: 12 }}>
        {STATUS_FILTERS.map((f) => (
          <button
            key={f.key}
            className={`filter-btn ${filter === f.key ? "active" : ""}`}
            onClick={() => setFilter(f.key)}
          >
            {f.label}
            {f.key !== "all" && counts[f.key as ImportJobStatus] != null && (
              <span style={{ marginLeft: 6, opacity: 0.7 }}>
                ({counts[f.key as ImportJobStatus]})
              </span>
            )}
          </button>
        ))}
      </div>

      {/* ── Jobs table ─────────────────────────────────────────────────── */}
      {loading && jobs.length === 0 ? (
        <div className="page-loading">Loading…</div>
      ) : jobs.length === 0 ? (
        <div className="empty-state">
          No imports yet. Drop some files above to get started.
        </div>
      ) : (
        <div className="table-card">
          <table className="data-table">
            <thead>
              <tr>
                <th>File</th>
                <th>Status</th>
                <th>Supplier / Mode</th>
                <th>Date</th>
                <th style={{ textAlign: "right" }}>Amount</th>
                <th>Notes</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((j) => {
                const e = j.extracted ?? {};
                const supplier = String(e["supplier_name"] ?? e["payee_name"] ?? "—");
                const date = String(e["invoice_date"] ?? e["payment_date"] ?? "—");
                const amount = Number(e["total_amount"] ?? e["amount"] ?? 0);
                return (
                  <tr key={j.id}>
                    <td title={j.source_path} style={{ maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {j.original_filename ?? `#${j.id}`}
                    </td>
                    <td>
                      <span
                        className="badge"
                        style={{
                          background: STATUS_COLORS[j.status] + "22",
                          color: STATUS_COLORS[j.status],
                          padding: "2px 8px",
                          borderRadius: 12,
                          fontSize: 12,
                          fontWeight: 500,
                        }}
                      >
                        {j.status.replace("_", " ")}
                      </span>
                    </td>
                    <td>{supplier}</td>
                    <td>{date}</td>
                    <td style={{ textAlign: "right" }}>{amount ? fmt(amount) : "—"}</td>
                    <td style={{ color: "#c62828", fontSize: 12 }}>{j.error ?? ""}</td>
                    <td>
                      <button
                        className="btn btn-small"
                        onClick={() => setReviewJob(j)}
                        disabled={j.status === "posted"}
                      >
                        {j.status === "posted" ? "Posted" : "Review"}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {reviewJob && (
        <ReviewModal
          job={reviewJob}
          suppliers={suppliers}
          onClose={() => setReviewJob(null)}
          onPosted={() => { setReviewJob(null); refresh(); }}
          onDiscarded={() => { setReviewJob(null); refresh(); }}
        />
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────

interface ReviewProps {
  job: ImportJob;
  suppliers: Supplier[];
  onClose: () => void;
  onPosted: () => void;
  onDiscarded: () => void;
}

interface InvoiceItemDraft {
  product_name_raw: string;
  qty: string;
  unit_cost: string;
}

function ReviewModal({ job, suppliers, onClose, onPosted, onDiscarded }: ReviewProps) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);

  const e = job.extracted ?? {};
  const isInvoice = job.kind === "invoice";

  // ── Invoice form state ───────────────────────────────────────────────
  const [invoiceNumber, setInvoiceNumber] = useState(
    String(e["invoice_number"] ?? `INV-${job.id}-${Date.now()}`)
  );
  const [supplierId, setSupplierId] = useState<number | "">(
    typeof e["supplier_id"] === "number" ? (e["supplier_id"] as number) : ""
  );
  const [invoiceDate, setInvoiceDate] = useState(
    String(e["invoice_date"] ?? new Date().toISOString().slice(0, 10))
  );
  const [totalAmount, setTotalAmount] = useState(
    String(e["total_amount"] ?? 0)
  );
  const initialItems: InvoiceItemDraft[] = (Array.isArray(e["items"]) ? e["items"] : []).map(
    (it: any) => ({
      product_name_raw: String(it?.product_name ?? it?.product_name_raw ?? ""),
      qty: String(it?.qty ?? ""),
      unit_cost: String(it?.unit_cost ?? ""),
    })
  );
  const [items, setItems] = useState<InvoiceItemDraft[]>(
    initialItems.length > 0 ? initialItems : [{ product_name_raw: "", qty: "", unit_cost: "" }]
  );

  // ── Payment form state ──────────────────────────────────────────────
  const [paymentDate, setPaymentDate] = useState(
    String(e["payment_date"] ?? new Date().toISOString().slice(0, 10))
  );
  const [amount, setAmount] = useState(String(e["amount"] ?? 0));
  const [paymentMode, setPaymentMode] = useState(String(e["payment_mode"] ?? "cash"));
  const [direction, setDirection] = useState<"inflow" | "outflow">(
    (e["direction"] as "inflow" | "outflow") ?? "outflow"
  );
  const [paymentSupplierId, setPaymentSupplierId] = useState<number | "">(
    typeof e["supplier_id"] === "number" ? (e["supplier_id"] as number) : ""
  );
  const [txnRef, setTxnRef] = useState(String(e["transaction_ref"] ?? ""));
  const [note, setNote] = useState(String(e["note"] ?? ""));

  const updateItem = (idx: number, patch: Partial<InvoiceItemDraft>) =>
    setItems((prev) => prev.map((it, i) => (i === idx ? { ...it, ...patch } : it)));
  const addItem = () =>
    setItems((prev) => [...prev, { product_name_raw: "", qty: "", unit_cost: "" }]);
  const removeItem = (idx: number) =>
    setItems((prev) => prev.filter((_, i) => i !== idx));

  const commit = async () => {
    setBusy(true);
    try {
      if (isInvoice) {
        if (!supplierId) {
          toast.push({ kind: "error", title: "Pick a supplier first" });
          return;
        }
        const body = {
          invoice_number: invoiceNumber.trim(),
          supplier_id: Number(supplierId),
          invoice_date: invoiceDate,
          total_amount: Number(totalAmount) || 0,
          image_path: job.source_path,
          items: items
            .filter((it) => it.product_name_raw.trim())
            .map((it) => ({
              product_name_raw: it.product_name_raw.trim(),
              qty: Number(it.qty) || 0,
              unit_cost: Number(it.unit_cost) || 0,
            })),
        };
        try {
          await commitImport(job.id, body);
        } catch (err: unknown) {
          const r = (err as { response?: { status?: number; data?: { detail?: unknown } } }).response;
          const detail = r?.data?.detail;
          const isDup =
            r?.status === 409 &&
            typeof detail === "object" &&
            detail !== null &&
            (detail as { reason?: string }).reason === "duplicate";
          if (!isDup) throw err;
          const existing = (detail as { existing_invoice_id: number }).existing_invoice_id;
          if (!confirm(
            `This looks like a duplicate of invoice #${existing} ` +
            `(same supplier, date, and total). Post anyway?`,
          )) return;
          await commitImport(job.id, body, { force: true });
        }
        toast.push({ kind: "success", title: "Invoice posted", body: `Job #${job.id}` });
      } else {
        if (direction === "outflow" && !paymentSupplierId) {
          toast.push({
            kind: "error",
            title: "Pick a vendor",
            body: "Outflows must be booked against a supplier.",
          });
          return;
        }
        const body = {
          payment_date: paymentDate,
          amount: Number(amount) || 0,
          payment_mode: paymentMode,
          direction,
          transaction_ref: txnRef.trim() || null,
          image_path: job.source_path,
          note: note.trim() || null,
          purchase_invoice_id: null,
          supplier_id: direction === "outflow" ? Number(paymentSupplierId) : null,
          customer_id: null,
        };
        await commitImport(job.id, body);
        toast.push({ kind: "success", title: "Payment posted", body: `Job #${job.id}` });
      }
      onPosted();
    } catch (err: unknown) {
      toast.push({ kind: "error", title: "Post failed", body: errMsg(err) });
    } finally {
      setBusy(false);
    }
  };

  const discard = async () => {
    setBusy(true);
    try {
      await discardImport(job.id);
      toast.push({ kind: "info", title: "Discarded", body: `Job #${job.id}` });
      onDiscarded();
    } catch (err: unknown) {
      toast.push({ kind: "error", title: "Discard failed", body: errMsg(err) });
    } finally {
      setBusy(false);
    }
  };

  const dupLink = job.dup_of_invoice_id
    ? { label: `Duplicate of invoice #${job.dup_of_invoice_id}`, href: "/invoices" }
    : job.dup_of_payment_id
    ? { label: `Duplicate of payment #${job.dup_of_payment_id}`, href: "/payments" }
    : null;

  return (
    <Modal open={true} onClose={onClose} title={`Review ${job.kind} — job #${job.id}`} wide>
      {dupLink && (
        <div
          style={{
            background: "#ffebee",
            border: "1px solid #ef9a9a",
            color: "#b71c1c",
            padding: 10,
            borderRadius: 6,
            marginBottom: 12,
          }}
        >
          <strong>{dupLink.label}.</strong>{" "}
          <a href={dupLink.href} style={{ color: "#b71c1c", textDecoration: "underline" }}>
            View original
          </a>
          . You can still post anyway if this is a different document.
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1.2fr", gap: 16 }}>
        {/* Image preview */}
        <div style={{ background: "#000", borderRadius: 6, overflow: "hidden", maxHeight: 480 }}>
          {job.source_path.toLowerCase().endsWith(".pdf") ? (
            <div style={{ color: "#fff", padding: 24, textAlign: "center" }}>
              PDF — first page is what OCR read.
              <div style={{ marginTop: 8 }}>
                <a href={job.source_path} target="_blank" rel="noopener" style={{ color: "#90caf9" }}>
                  Open PDF
                </a>
              </div>
            </div>
          ) : (
            <img
              src={job.source_path}
              alt="Uploaded"
              style={{ width: "100%", height: "auto", maxHeight: 480, objectFit: "contain" }}
            />
          )}
        </div>

        {/* Editable form */}
        <div>
          {isInvoice ? (
            <InvoiceForm
              suppliers={suppliers}
              invoiceNumber={invoiceNumber} setInvoiceNumber={setInvoiceNumber}
              supplierId={supplierId} setSupplierId={setSupplierId}
              invoiceDate={invoiceDate} setInvoiceDate={setInvoiceDate}
              totalAmount={totalAmount} setTotalAmount={setTotalAmount}
              items={items} updateItem={updateItem} addItem={addItem} removeItem={removeItem}
            />
          ) : (
            <PaymentForm
              suppliers={suppliers}
              paymentDate={paymentDate} setPaymentDate={setPaymentDate}
              amount={amount} setAmount={setAmount}
              paymentMode={paymentMode} setPaymentMode={setPaymentMode}
              direction={direction} setDirection={setDirection}
              supplierId={paymentSupplierId} setSupplierId={setPaymentSupplierId}
              txnRef={txnRef} setTxnRef={setTxnRef}
              note={note} setNote={setNote}
            />
          )}

          <div style={{ display: "flex", gap: 8, marginTop: 16, justifyContent: "flex-end" }}>
            <button className="btn btn-secondary" onClick={discard} disabled={busy}>
              Discard
            </button>
            <button className="btn btn-primary" onClick={commit} disabled={busy}>
              {busy ? "Posting…" : dupLink ? "Post anyway" : "Post"}
            </button>
          </div>
        </div>
      </div>
    </Modal>
  );
}

// ─────────────────────────────────────────────────────────────────────────────

interface InvoiceFormProps {
  suppliers: Supplier[];
  invoiceNumber: string; setInvoiceNumber: (s: string) => void;
  supplierId: number | ""; setSupplierId: (s: number | "") => void;
  invoiceDate: string; setInvoiceDate: (s: string) => void;
  totalAmount: string; setTotalAmount: (s: string) => void;
  items: InvoiceItemDraft[];
  updateItem: (i: number, p: Partial<InvoiceItemDraft>) => void;
  addItem: () => void;
  removeItem: (i: number) => void;
}

function InvoiceForm(p: InvoiceFormProps) {
  return (
    <>
      <Field label="Invoice number">
        <input
          className="input"
          value={p.invoiceNumber}
          onChange={(e) => p.setInvoiceNumber(e.target.value)}
        />
      </Field>
      <Field label="Supplier">
        <select
          className="input"
          value={p.supplierId}
          onChange={(e) => p.setSupplierId(e.target.value ? Number(e.target.value) : "")}
        >
          <option value="">— pick supplier —</option>
          {p.suppliers.map((s) => (
            <option key={s.id} value={s.id}>{s.name}</option>
          ))}
        </select>
      </Field>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
        <Field label="Invoice date">
          <input
            className="input"
            type="date"
            value={p.invoiceDate}
            onChange={(e) => p.setInvoiceDate(e.target.value)}
          />
        </Field>
        <Field label="Total amount">
          <input
            className="input"
            type="number" step="0.01"
            value={p.totalAmount}
            onChange={(e) => p.setTotalAmount(e.target.value)}
          />
        </Field>
      </div>

      <div style={{ marginTop: 12, fontWeight: 500 }}>Items</div>
      <div style={{ maxHeight: 200, overflowY: "auto", border: "1px solid #eee", borderRadius: 4, padding: 6 }}>
        {p.items.map((it, idx) => (
          <div key={idx} style={{ display: "grid", gridTemplateColumns: "2fr 0.6fr 0.8fr auto", gap: 4, marginBottom: 4 }}>
            <input
              className="input" placeholder="Name"
              value={it.product_name_raw}
              onChange={(e) => p.updateItem(idx, { product_name_raw: e.target.value })}
            />
            <input
              className="input" placeholder="Qty" type="number" step="0.001"
              value={it.qty}
              onChange={(e) => p.updateItem(idx, { qty: e.target.value })}
            />
            <input
              className="input" placeholder="Cost" type="number" step="0.01"
              value={it.unit_cost}
              onChange={(e) => p.updateItem(idx, { unit_cost: e.target.value })}
            />
            <button className="btn btn-small" onClick={() => p.removeItem(idx)}>×</button>
          </div>
        ))}
      </div>
      <button className="btn btn-small" style={{ marginTop: 6 }} onClick={p.addItem}>+ Item</button>
    </>
  );
}

interface PaymentFormProps {
  suppliers: Supplier[];
  paymentDate: string; setPaymentDate: (s: string) => void;
  amount: string; setAmount: (s: string) => void;
  paymentMode: string; setPaymentMode: (s: string) => void;
  direction: "inflow" | "outflow"; setDirection: (s: "inflow" | "outflow") => void;
  supplierId: number | ""; setSupplierId: (s: number | "") => void;
  txnRef: string; setTxnRef: (s: string) => void;
  note: string; setNote: (s: string) => void;
}

function PaymentForm(p: PaymentFormProps) {
  return (
    <>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
        <Field label="Date">
          <input className="input" type="date" value={p.paymentDate}
            onChange={(e) => p.setPaymentDate(e.target.value)} />
        </Field>
        <Field label="Amount">
          <input className="input" type="number" step="0.01" value={p.amount}
            onChange={(e) => p.setAmount(e.target.value)} />
        </Field>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
        <Field label="Mode">
          <select className="input" value={p.paymentMode}
            onChange={(e) => p.setPaymentMode(e.target.value)}>
            <option value="cash">Cash</option>
            <option value="bank_deposit">Bank deposit</option>
            <option value="gpay">GPay</option>
            <option value="upi">UPI</option>
            <option value="other">Other</option>
          </select>
        </Field>
        <Field label="Direction">
          <select className="input" value={p.direction}
            onChange={(e) => p.setDirection(e.target.value as "inflow" | "outflow")}>
            <option value="outflow">Outflow (we pay)</option>
            <option value="inflow">Inflow (we receive)</option>
          </select>
        </Field>
      </div>
      {p.direction === "outflow" && (
        <Field label="Vendor">
          <select
            className="input"
            value={p.supplierId === "" ? "" : String(p.supplierId)}
            onChange={(e) => p.setSupplierId(e.target.value === "" ? "" : Number(e.target.value))}
          >
            <option value="">— pick vendor —</option>
            {p.suppliers.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </Field>
      )}
      <Field label="Transaction ref">
        <input className="input" value={p.txnRef}
          onChange={(e) => p.setTxnRef(e.target.value)} />
      </Field>
      <Field label="Note">
        <input className="input" value={p.note}
          onChange={(e) => p.setNote(e.target.value)} />
      </Field>
    </>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label style={{ display: "block", marginBottom: 8 }}>
      <div style={{ fontSize: 12, color: "#555", marginBottom: 2 }}>{label}</div>
      {children}
    </label>
  );
}

function errMsg(e: unknown): string {
  if (e instanceof Error) return e.message;
  if (typeof e === "object" && e !== null && "message" in e) {
    return String((e as { message: unknown }).message);
  }
  return "Something went wrong";
}
