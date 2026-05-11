import axios, { AxiosError } from "axios";

const TOKEN_KEY = "dokane_token";

const api = axios.create({ baseURL: "/api" });

// ── Auth interceptors ──────────────────────────────────────────────────────

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err: AxiosError) => {
    if (err.response?.status === 401) {
      localStorage.removeItem(TOKEN_KEY);
      // Re-render the auth gate; SPA reload is the simplest safe reset.
      if (typeof window !== "undefined") window.location.reload();
    }
    return Promise.reject(err);
  },
);

export const getToken = (): string | null => localStorage.getItem(TOKEN_KEY);
export const setToken = (t: string): void => localStorage.setItem(TOKEN_KEY, t);
export const clearToken = (): void => localStorage.removeItem(TOKEN_KEY);

export const login = (pin: string): Promise<{ token: string }> =>
  api.post("/auth/login", { pin }).then((r) => r.data);

// ── Types ──────────────────────────────────────────────────────────────────

export interface Supplier {
  id: number;
  name: string;
  phone: string | null;
  address: string | null;
}

export interface SupplierSummary {
  id: number;
  name: string;
  phone: string | null;
  total_invoiced: number;
  total_paid: number;
  balance: number;             // positive = we owe the supplier
  last_activity: string | null;
}

export interface SupplierLedgerEntry {
  entry_date: string;
  entry_type: "invoice" | "payment";
  description: string;
  debit: number;
  credit: number;
  running_balance: number;
  source_id: number;
}

export interface SupplierLedger {
  supplier_id: number;
  supplier_name: string;
  phone: string | null;
  address: string | null;
  entries: SupplierLedgerEntry[];
  total_invoiced: number;
  total_paid: number;
  balance: number;
}

export interface OcrInvoiceItem {
  product_name: string;
  qty: number | null;
  unit: string | null;
  unit_cost: number | null;
}

export interface OcrInvoiceResult {
  type: "invoice" | "payment_slip" | "unknown";
  confidence: "high" | "medium" | "low";
  supplier_name: string | null;
  invoice_number: string | null;
  invoice_date: string | null;
  items: OcrInvoiceItem[];
  total_amount: number | null;
  notes: string | null;
  image_path: string;
  // Present when type === "payment_slip"
  payment_mode?: "cash" | "bank_deposit" | "gpay" | "upi" | "other" | null;
  amount?: number | null;
  transaction_ref?: string | null;
  payment_date?: string | null;
  payee_name?: string | null;
  note?: string | null;
}

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
  sale_date: string;
  product_id: number | null;
  customer_id: number | null;
  product_name_raw: string | null;
  qty_sold: number;
  selling_price: number;
  line_total: number;
  source: string;
  created_at: string;
}

export interface Customer {
  id: number;
  name: string;
  phone: string | null;
  address: string | null;
  notes: string | null;
  created_at: string;
}

export interface CustomerSummary {
  id: number;
  name: string;
  phone: string | null;
  total_sales: number;
  total_received: number;
  balance: number;
  last_activity: string | null;
}

export interface CustomerLedgerEntry {
  entry_date: string;
  entry_type: "sale" | "payment";
  description: string;
  qty: number | null;
  debit: number;
  credit: number;
  running_balance: number;
  source_id: number;
}

export interface CustomerLedger {
  customer: Customer;
  entries: CustomerLedgerEntry[];
  total_sales: number;
  total_received: number;
  balance: number;
}

export interface CustomerCreate {
  name: string;
  phone?: string | null;
  address?: string | null;
  notes?: string | null;
}

export interface DailyReport {
  date: string;
  total_sales: number;
  received: number;
  paid_out: number;
  sales_count: number;
  low_stock_count: number;
  sales: { id: number; product_name: string; qty_sold: number; selling_price: number; line_total: number; source: string }[];
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

// ── Mutation request shapes (mirror backend Pydantic schemas) ───────────────

export interface SaleCreate {
  sale_date: string;
  product_id: number | null;
  customer_id?: number | null;
  product_name_raw: string | null;
  qty_sold: number;
  selling_price: number;
  source: string;
  raw_input: string | null;
}

export interface SaleUpdate {
  qty_sold?: number;
  selling_price?: number;
  product_id?: number | null;
  customer_id?: number | null;
  product_name_raw?: string | null;
}

export interface InvoiceItemCreate {
  product_id: number | null;
  product_name_raw: string | null;
  qty: number;
  unit_cost: number;
}

export interface InvoiceCreate {
  invoice_number: string;
  supplier_id: number;
  invoice_date: string;
  total_amount: number;
  notes: string | null;
  image_path: string | null;
  items: InvoiceItemCreate[];
}

export interface InvoiceUpdate {
  paid_amount?: number;
  status?: string;
  notes?: string | null;
}

export interface PaymentCreate {
  payment_date: string;
  amount: number;
  payment_mode: string;
  direction: "inflow" | "outflow";
  purchase_invoice_id: number | null;
  customer_id?: number | null;
  transaction_ref: string | null;
  image_path: string | null;
  note: string | null;
}

// ── Helpers ────────────────────────────────────────────────────────────────

const toNum = (v: unknown): number => Number(v ?? 0);

export const fmt = (n: number): string =>
  `₹${n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const coerceProduct = (p: Product): Product => ({
  ...p,
  cost_price:    toNum(p.cost_price),
  selling_price: toNum(p.selling_price),
  stock_qty:     toNum(p.stock_qty),
  reorder_level: toNum(p.reorder_level),
});

const coerceSale = (s: SaleRow): SaleRow => ({
  ...s,
  qty_sold:      toNum(s.qty_sold),
  selling_price: toNum(s.selling_price),
  line_total:    toNum(s.line_total),
});

const coerceCustomerSummary = (s: CustomerSummary): CustomerSummary => ({
  ...s,
  total_sales:    toNum(s.total_sales),
  total_received: toNum(s.total_received),
  balance:        toNum(s.balance),
});

const coerceSupplierSummary = (s: SupplierSummary): SupplierSummary => ({
  ...s,
  total_invoiced: toNum(s.total_invoiced),
  total_paid:     toNum(s.total_paid),
  balance:        toNum(s.balance),
});

const coerceSupplierLedger = (l: SupplierLedger): SupplierLedger => ({
  ...l,
  total_invoiced: toNum(l.total_invoiced),
  total_paid:     toNum(l.total_paid),
  balance:        toNum(l.balance),
  entries: l.entries.map((e) => ({
    ...e,
    debit:           toNum(e.debit),
    credit:          toNum(e.credit),
    running_balance: toNum(e.running_balance),
  })),
});

const coerceLedger = (l: CustomerLedger): CustomerLedger => ({
  ...l,
  total_sales:    toNum(l.total_sales),
  total_received: toNum(l.total_received),
  balance:        toNum(l.balance),
  entries: l.entries.map((e) => ({
    ...e,
    qty:             e.qty == null ? null : toNum(e.qty),
    debit:           toNum(e.debit),
    credit:          toNum(e.credit),
    running_balance: toNum(e.running_balance),
  })),
});

const coerceInvoice = (inv: Invoice): Invoice => ({
  ...inv,
  total_amount: toNum(inv.total_amount),
  paid_amount:  toNum(inv.paid_amount),
  items: (inv.items ?? []).map((item) => ({
    ...item,
    qty:        toNum(item.qty),
    unit_cost:  toNum(item.unit_cost),
    line_total: toNum(item.qty) * toNum(item.unit_cost),
  })),
});

const coercePayment = (p: Payment): Payment => ({ ...p, amount: toNum(p.amount) });

// ── Analytics (one-shot dashboard payload) ─────────────────────────────────

export interface AnalyticsKpi {
  sales: number;
  received: number;
  paid_out: number;
  net: number;
}

export interface AnalyticsTrendPoint {
  date: string;
  total: number;
}

export interface AnalyticsTopProduct {
  name: string;
  qty: number;
  revenue: number;
}

export interface AnalyticsParty {
  id: number;
  name: string;
  phone: string | null;
  balance: number;
  last_activity: string | null;
}

export interface AnalyticsLowStock {
  id: number;
  name: string;
  stock_qty: number;
  reorder_level: number;
  unit: string | null;
}

export interface CashDrawer {
  cash: number;
  upi: number;
  card: number;
  other: number;
  count: number;
}

export interface ActivityEvent {
  kind: "sale" | "payment";
  date: string;
  title: string;
  amount: number;
}

export interface AnalyticsPayload {
  sales_trend_30d: AnalyticsTrendPoint[];
  sales_by_product_30d: AnalyticsTopProduct[];
  low_stock: AnalyticsLowStock[];
  stock_value_on_hand: number;
  customers_outstanding: AnalyticsParty[];
  suppliers_outstanding: AnalyticsParty[];
  kpis: {
    today: AnalyticsKpi;
    week: AnalyticsKpi;
    month: AnalyticsKpi;
  };
  cash_drawer: CashDrawer;
  recent_activity: ActivityEvent[];
}

const coerceKpi = (k: AnalyticsKpi): AnalyticsKpi => ({
  sales: toNum(k.sales),
  received: toNum(k.received),
  paid_out: toNum(k.paid_out),
  net: toNum(k.net),
});

const coerceParty = (p: AnalyticsParty): AnalyticsParty => ({ ...p, balance: toNum(p.balance) });

export const fetchAnalytics = (): Promise<AnalyticsPayload> =>
  api.get("/reports/analytics").then((r) => {
    const d = r.data as AnalyticsPayload;
    return {
      sales_trend_30d:       d.sales_trend_30d.map((t) => ({ ...t, total: toNum(t.total) })),
      sales_by_product_30d:  d.sales_by_product_30d.map((p) => ({
        ...p, qty: toNum(p.qty), revenue: toNum(p.revenue),
      })),
      low_stock:             d.low_stock.map((l) => ({
        ...l, stock_qty: toNum(l.stock_qty), reorder_level: toNum(l.reorder_level),
      })),
      stock_value_on_hand:   toNum(d.stock_value_on_hand),
      customers_outstanding: d.customers_outstanding.map(coerceParty),
      suppliers_outstanding: d.suppliers_outstanding.map(coerceParty),
      kpis: {
        today: coerceKpi(d.kpis.today),
        week:  coerceKpi(d.kpis.week),
        month: coerceKpi(d.kpis.month),
      },
      cash_drawer: {
        cash:  toNum(d.cash_drawer.cash),
        upi:   toNum(d.cash_drawer.upi),
        card:  toNum(d.cash_drawer.card),
        other: toNum(d.cash_drawer.other),
        count: d.cash_drawer.count,
      },
      recent_activity: d.recent_activity.map((e) => ({ ...e, amount: toNum(e.amount) })),
    };
  });

// ── Reads ──────────────────────────────────────────────────────────────────

export const fetchDailyReport = (date?: string): Promise<DailyReport> =>
  api.get("/reports/daily", { params: date ? { report_date: date } : {} }).then(r => r.data);

export const fetchWeeklyReport = (): Promise<WeeklyReport> =>
  api.get("/reports/weekly").then(r => r.data);

export const fetchOutstanding = (): Promise<OutstandingData> =>
  api.get("/reports/outstanding").then(r => r.data);

export const fetchProducts = (activeOnly = true): Promise<Product[]> =>
  api.get("/products", { params: { active_only: activeOnly } }).then(r => r.data.map(coerceProduct));

export const fetchLowStock = (): Promise<Product[]> =>
  api.get("/products/low-stock").then(r => r.data.map(coerceProduct));

export const searchProducts = (name: string): Promise<Product[]> =>
  api.get("/products/search", { params: { name } }).then(r => r.data.map(coerceProduct));

export const fetchSuppliers = (): Promise<Supplier[]> =>
  api.get("/products/suppliers").then(r => r.data);

export const fetchInvoices = (status?: string): Promise<Invoice[]> =>
  api.get("/invoices", { params: status ? { status } : {} }).then(r => r.data.map(coerceInvoice));

export const fetchPayments = (params?: {
  direction?: string;
  payment_mode?: string;
  payment_date?: string;
}): Promise<Payment[]> =>
  api.get("/payments", { params }).then(r => r.data.map(coercePayment));

export const fetchSales = (sale_date?: string): Promise<SaleRow[]> =>
  api.get("/sales/daily", { params: sale_date ? { sale_date } : {} }).then(r => r.data.map(coerceSale));

export const fetchStockMovements = (productId?: number): Promise<StockMovement[]> =>
  api.get("/stock/movements", { params: productId ? { product_id: productId } : {} }).then(r =>
    r.data.map((m: StockMovement) => ({ ...m, qty_change: toNum(m.qty_change) }))
  );

// ── Mutations ──────────────────────────────────────────────────────────────

export const createSale = (body: SaleCreate): Promise<SaleRow> =>
  api.post("/sales/daily", body).then(r => coerceSale(r.data));

export const updateSale = (id: number, body: SaleUpdate): Promise<SaleRow> =>
  api.put(`/sales/daily/${id}`, body).then(r => coerceSale(r.data));

export const deleteSale = (id: number): Promise<void> =>
  api.delete(`/sales/daily/${id}`).then(() => undefined);

export const createInvoice = (body: InvoiceCreate): Promise<Invoice> =>
  api.post("/invoices", body).then(r => coerceInvoice(r.data));

export const updateInvoice = (id: number, body: InvoiceUpdate): Promise<Invoice> =>
  api.put(`/invoices/${id}`, body).then(r => coerceInvoice(r.data));

export const createPayment = (body: PaymentCreate): Promise<Payment> =>
  api.post("/payments", body).then(r => coercePayment(r.data));

export const upsertSupplier = (name: string): Promise<Supplier> =>
  api.post("/products/suppliers/upsert", { name }).then(r => r.data);

export const fetchSupplierSummaries = (): Promise<SupplierSummary[]> =>
  api.get("/products/suppliers/summaries").then(r => r.data.map(coerceSupplierSummary));

export const fetchSupplierOutstanding = (): Promise<SupplierSummary[]> =>
  api.get("/products/suppliers/outstanding").then(r => r.data.map(coerceSupplierSummary));

export const fetchSupplierLedger = (id: number): Promise<SupplierLedger> =>
  api.get(`/products/suppliers/${id}/ledger`).then(r => coerceSupplierLedger(r.data));

export const updateSupplier = (id: number, body: Partial<Pick<Supplier, "name" | "phone" | "address">>): Promise<Supplier> =>
  api.put(`/products/suppliers/${id}`, body).then(r => r.data);

export const ocrInvoiceUpload = (file: File): Promise<OcrInvoiceResult> => {
  const fd = new FormData();
  fd.append("file", file);
  return api.post("/invoices/ocr", fd, {
    headers: { "Content-Type": "multipart/form-data" },
  }).then(r => r.data);
};

// ── Customers ──────────────────────────────────────────────────────────────

export const fetchCustomers = (q?: string): Promise<CustomerSummary[]> =>
  api.get("/customers", { params: q ? { q } : {} }).then(r => r.data.map(coerceCustomerSummary));

export const fetchOutstandingCustomers = (): Promise<CustomerSummary[]> =>
  api.get("/customers/outstanding").then(r => r.data.map(coerceCustomerSummary));

export const fetchCustomerLedger = (id: number): Promise<CustomerLedger> =>
  api.get(`/customers/${id}/ledger`).then(r => coerceLedger(r.data));

export const createCustomer = (body: CustomerCreate): Promise<Customer> =>
  api.post("/customers", body).then(r => r.data);

export const updateCustomer = (id: number, body: Partial<CustomerCreate>): Promise<Customer> =>
  api.put(`/customers/${id}`, body).then(r => r.data);

export const upsertCustomer = (body: CustomerCreate): Promise<Customer> =>
  api.post("/customers/upsert", body).then(r => r.data);

export const triggerDailyReport = (): Promise<void> =>
  api.post("/reports/trigger/daily").then(() => undefined);

export const triggerWeeklyReport = (): Promise<void> =>
  api.post("/reports/trigger/weekly").then(() => undefined);
