import { describe, it, expect } from "vitest";
import { fmt } from "./client";

describe("fmt", () => {
  it("formats with Indian rupee symbol and two decimals", () => {
    expect(fmt(1234.5)).toBe("₹1,234.50");
    expect(fmt(0)).toBe("₹0.00");
  });

  it("uses Indian (en-IN) digit grouping for large numbers", () => {
    // en-IN groups as 1,23,456 — not the en-US 123,456
    expect(fmt(123456)).toBe("₹1,23,456.00");
    expect(fmt(1234567.89)).toBe("₹12,34,567.89");
  });
});
