import { describe, it, expect, vi, beforeEach, beforeAll } from "vitest";

// Stub the browser globals client.ts touches at module load. Vitest runs in
// node by default; flipping to jsdom would also work but is heavier.
beforeAll(() => {
  const store = new Map<string, string>();
  (globalThis as unknown as { localStorage: Storage }).localStorage = {
    getItem: (k: string) => (store.has(k) ? store.get(k)! : null),
    setItem: (k: string, v: string) => { store.set(k, v); },
    removeItem: (k: string) => { store.delete(k); },
    clear: () => store.clear(),
    key: () => null,
    length: 0,
  };
  (globalThis as unknown as { window: { location: { reload: () => void } } }).window =
    { location: { reload: () => {} } };
});

// Mock axios so we can capture every outbound request without touching the
// network. We replicate the surface client.ts uses: create() returning a
// chainable instance with .post/.get/.put/.delete and request/response
// interceptors.
const captured: { url?: string; method?: string; body?: unknown }[] = [];
const mockResponse: { data: unknown; status: number } = { data: null, status: 200 };

vi.mock("axios", () => {
  const make = (method: string) => (url: string, body?: unknown) => {
    captured.push({ method, url, body });
    return Promise.resolve({ ...mockResponse, headers: {}, config: {} });
  };
  const instance = {
    get:    (url: string, opts?: { params?: unknown }) => { captured.push({ method: "get", url, body: opts?.params }); return Promise.resolve({ ...mockResponse, headers: {}, config: {} }); },
    post:   make("post"),
    put:    make("put"),
    delete: (url: string) => { captured.push({ method: "delete", url }); return Promise.resolve({ ...mockResponse, headers: {}, config: {} }); },
    interceptors: {
      request:  { use: () => 0 },
      response: { use: () => 0 },
    },
  };
  return { default: { create: () => instance }, AxiosError: class {} };
});

// eslint-disable-next-line import/first
import { fmt, createSale, getToken, setToken, clearToken } from "./client";

describe("fmt", () => {
  it("formats with Indian rupee symbol and two decimals", () => {
    expect(fmt(1234.5)).toBe("₹1,234.50");
    expect(fmt(0)).toBe("₹0.00");
  });

  it("uses Indian (en-IN) digit grouping for large numbers", () => {
    expect(fmt(123456)).toBe("₹1,23,456.00");
    expect(fmt(1234567.89)).toBe("₹12,34,567.89");
  });
});

describe("auth token helpers", () => {
  beforeEach(() => clearToken());
  it("set/get/clear round-trip via localStorage", () => {
    expect(getToken()).toBeNull();
    setToken("abc123");
    expect(getToken()).toBe("abc123");
    clearToken();
    expect(getToken()).toBeNull();
  });
});

describe("createSale", () => {
  beforeEach(() => { captured.length = 0; });

  it("posts to /sales/daily with the expected body, coerces Decimal-string fields in the response", async () => {
    mockResponse.data = {
      id: 42,
      sale_date: "2026-05-11",
      product_id: 7,
      product_name_raw: "MCB",
      qty_sold: "3",
      selling_price: "85.50",
      line_total: "256.50",
      source: "manual",
      created_at: "2026-05-11T09:30:00",
    };

    const result = await createSale({
      sale_date: "2026-05-11",
      product_id: 7,
      product_name_raw: "MCB",
      qty_sold: 3,
      selling_price: 85.5,
      source: "manual",
      raw_input: null,
    });

    // Verify request shape
    expect(captured).toHaveLength(1);
    expect(captured[0].method).toBe("post");
    expect(captured[0].url).toBe("/sales/daily");
    expect(captured[0].body).toMatchObject({
      sale_date: "2026-05-11",
      product_id: 7,
      product_name_raw: "MCB",
      qty_sold: 3,
      selling_price: 85.5,
      source: "manual",
    });

    // Verify response coercion (backend returns Decimal as strings)
    expect(typeof result.qty_sold).toBe("number");
    expect(typeof result.selling_price).toBe("number");
    expect(typeof result.line_total).toBe("number");
    expect(result.line_total).toBe(256.5);
  });
});
