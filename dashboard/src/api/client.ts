import axios from "axios";

const api = axios.create({ baseURL: "/api" });

// ── Types ──────────────────────────────────────────────────────────────────

export interface Product {
  id: number;
  sku: string;
  name: string;
  unit: string | null;
  cost_price: number;
  selling_price: number;
  stock_qty: number;
  reorder_level: number;
  is_active: boolean;
}

export interface InvoiceItem {
  id: number;
  product_name_raw: string | null;
  qty: number;
  unit_cost: number;
  line_total: number;
}

export interface Invoice {
  id: number;
  invoice_number: string;
  supplier_id: number;
  invoice_date: string;
  total_amount: number;
  paid_amount: number;
  status: "unpaid" | "partial" | "paid";
  notes: string | null;
  items: InvoiceItem[];
}

export interface Payment {
  id: number;
  payment_date: string;
  amount: number;
  payment_mode: string;
  direction: "inflow" | "outflow";
  purchase_invoice_id: number | null;
  transaction_ref: string | null;
  note: string | null;
}

export interface SaleRow {
  id: number;
  product_name: string;
  qty_sold: number;
  selling_price: number;
  line_total: number;
  source: string;
}

export interface DailyReport {
  date: string;
  total_sales: number;
  received: number;
  paid_out: number;
  sales_count: number;
  low_stock_count: number;
  sales: SaleRow[];
  payments: { id: number; amount: number; payment_mode: string; direction: string }[];
  low_stock: { id: number; name: string; stock_qty: number; reorder_level: number; unit: string | null }[];
}

export interface WeeklyReport {
  week_start: string;
  week_end: string;
  total_sales: number;
  received: number;
  paid_out: number;
  sales_count: number;
  total_outstanding: number;
  top_by_qty: { name: string; qty: number }[];
  top_by_revenue: { name: string; revenue: number }[];
}

export interface StockMovement {
  id: number;
  product_id: number;
  movement_type: string;
  qty_change: number;
  reference_type: string | null;
  moved_at: string;
}

export interface OutstandingData {
  total_outstanding: number;
  invoices: {
    id: number;
    invoice_number: string;
    invoice_date: string;
    total_amount: number;
    paid_amount: number;
    outstanding: number;
    status: string;
  }[];
}

// ── API calls ──────────────────────────────────────────────────────────────

export const fetchDailyReport = (date?: string): Promise<DailyReport> =>
  api.get("/reports/daily", { params: date ? { report_date: date } : {} }).then(r => r.data);

export const fetchWeeklyReport = (): Promise<WeeklyReport> =>
  api.get("/reports/weekly").then(r => r.data);

export const fetchOutstanding = (): Promise<OutstandingData> =>
  api.get("/reports/outstanding").then(r => r.data);

export const fetchProducts = (activeOnly = true): Promise<Product[]> =>
  api.get("/products", { params: { active_only: activeOnly } }).then(r => r.data);

export const fetchLowStock = (): Promise<Product[]> =>
  api.get("/products/low-stock").then(r => r.data);

export const fetchInvoices = (status?: string): Promise<Invoice[]> =>
  api.get("/invoices", { params: status ? { status } : {} }).then(r => r.data);

export const fetchPayments = (params?: {
  direction?: string;
  payment_mode?: string;
  payment_date?: string;
}): Promise<Payment[]> =>
  api.get("/payments", { params }).then(r =>
    r.data.map((p: Payment) => ({ ...p, amount: Number(p.amount) }))
  );

export const fetchStockMovements = (productId?: number): Promise<StockMovement[]> =>
  api.get("/stock/movements", { params: productId ? { product_id: productId } : {} }).then(r => r.data);

export const triggerDailyReport = (): Promise<void> =>
  api.post("/reports/trigger/daily").then(() => undefined);

export const triggerWeeklyReport = (): Promise<void> =>
  api.post("/reports/trigger/weekly").then(() => undefined);

export const fmt = (n: number) =>
  `₹${n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
