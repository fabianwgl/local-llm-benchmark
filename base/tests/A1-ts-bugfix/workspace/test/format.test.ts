import { test } from "node:test";
import assert from "node:assert/strict";
import { renderInvoice } from "../src/index.ts";

test("renderInvoice produces the receipt text", () => {
  const text = renderInvoice({
    id: "INV-1003",
    customer: "Cobalt Ltd",
    taxRateBps: 1900,
    discount: { kind: "fixed", cents: 1000 },
    lines: [{ sku: "A-1", description: "Widget", quantity: 3, unitPriceCents: 2000 }],
  });
  const lines = text.split("\n");
  assert.equal(lines[0], "Invoice INV-1003");
  assert.ok(lines.some((l) => l.startsWith("Subtotal") && l.endsWith("60.00 EUR")));
  assert.ok(lines.some((l) => l.startsWith("Discount") && l.endsWith("-10.00 EUR")));
  assert.ok(lines.some((l) => l.startsWith("Tax (19%)") && l.endsWith("9.50 EUR")));
  assert.ok(lines.some((l) => l.startsWith("Total") && l.endsWith("59.50 EUR")));
});
