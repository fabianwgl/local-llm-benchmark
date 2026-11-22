import { test } from "node:test";
import assert from "node:assert/strict";
import { creditNote, splitPayment } from "../src/index.ts";
import type { Invoice } from "../src/index.ts";

const invoice: Invoice = {
  id: "INV-1002",
  customer: "Borealis Oy",
  taxRateBps: 2000,
  discount: { kind: "fixed", cents: 20000 },
  lines: [{ sku: "C-3", description: "Consulting day", quantity: 4, unitPriceCents: 80000 }],
};

test("a full credit note reverses the invoice", () => {
  assert.deepEqual(creditNote(invoice, 10000), {
    subtotalCents: -320000, discountCents: -20000, taxableCents: -300000, taxCents: -60000, totalCents: -360000,
  });
});

test("a credit note rejects an invalid share", () => {
  assert.throws(() => creditNote(invoice, 0), RangeError);
  assert.throws(() => creditNote(invoice, 10001), RangeError);
});

test("splitPayment keeps the account names", () => {
  const shares = splitPayment(9000, [{ account: "ops", weight: 1 }, { account: "rnd", weight: 2 }]);
  assert.deepEqual(shares, [{ account: "ops", cents: 3000 }, { account: "rnd", cents: 6000 }]);
  assert.throws(() => splitPayment(100, [{ account: "x", weight: 1 }, { account: "x", weight: 1 }]));
});
