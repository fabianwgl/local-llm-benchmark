import { test } from "node:test";
import assert from "node:assert/strict";
import { computeTotals, discountFor, lineBreakdown } from "../src/index.ts";
import type { Invoice } from "../src/index.ts";

const base: Invoice = {
  id: "INV-1001",
  customer: "Acme GmbH",
  taxRateBps: 1900,
  lines: [
    { sku: "A-1", description: "Widget", quantity: 2, unitPriceCents: 1000 },
    { sku: "B-7", description: "Setup fee", quantity: 1, unitPriceCents: 5000 },
  ],
};

test("computeTotals without a discount", () => {
  assert.deepEqual(computeTotals(base), {
    subtotalCents: 7000, discountCents: 0, taxableCents: 7000, taxCents: 1330, totalCents: 8330,
  });
});

test("computeTotals with a percentage discount", () => {
  const totals = computeTotals({ ...base, discount: { kind: "percent", bps: 1000 } });
  assert.equal(totals.discountCents, 700);
  assert.equal(totals.taxableCents, 6300);
  assert.equal(totals.taxCents, 1197);
  assert.equal(totals.totalCents, 7497);
});

test("a fixed discount never exceeds the subtotal", () => {
  assert.equal(discountFor(7000, { kind: "fixed", cents: 500 }), 500);
  assert.equal(discountFor(300, { kind: "fixed", cents: 500 }), 300);
  assert.throws(() => discountFor(300, { kind: "percent", bps: 20000 }), RangeError);
});

test("lineBreakdown lists every line", () => {
  const rows = lineBreakdown(base);
  assert.deepEqual(rows.map((r) => r.sku), ["A-1", "B-7"]);
  assert.deepEqual(rows.map((r) => r.amountCents), [2000, 5000]);
  assert.deepEqual(rows.map((r) => r.taxCents), [380, 950]);
});
