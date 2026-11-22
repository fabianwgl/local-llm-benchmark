import { test } from "node:test";
import assert from "node:assert/strict";
import { handle } from "../src/index.ts";

function createQuote(body: unknown) {
  return handle({ method: "POST", path: "/quotes", body });
}

test("quote gets a stable number and a validity date", () => {
  const res = createQuote({
    customer: { name: "Jana Novak", company: "Northwind Traders" },
    lines: [{ sku: "KB-101", quantity: 1 }],
    country: "DE",
    date: "2026-03-30",
  });
  assert.equal(res.status, 200);
  const quote = (res.body as any).quote;
  assert.equal(quote.number, "Q-20260330-NORTHWIN");
  assert.deepEqual(quote.customer, { name: "Jana Novak", company: "Northwind Traders" });
  assert.equal(quote.issuedOn, "2026-03-30");
  assert.equal(quote.validUntil, "2026-04-29");
});

test("quote totals with a fixed coupon", () => {
  const quote = (createQuote({
    customer: { name: "Ola Berg" },
    lines: [{ sku: "MON-27", quantity: 2 }],
    country: "NL",
    coupon: "BIG20",
    date: "2026-06-01",
    validityDays: 7,
  }).body as any).quote;
  assert.equal(quote.validUntil, "2026-06-08");
  assert.deepEqual(quote.lines, [
    { sku: "MON-27", description: "27-inch monitor", quantity: 2, unitPriceCents: 27900, amountCents: 55800 },
  ]);
  assert.deepEqual(quote.totals, {
    subtotalCents: 55800,
    volumeDiscountCents: 0,
    couponDiscountCents: 2000,
    netCents: 53800,
    taxCents: 11298,
    shippingCents: 0,
    totalCents: 65098,
  });
});

test("quote shows formatted amounts", () => {
  const quote = (createQuote({
    customer: { name: "Ola Berg" },
    lines: [{ sku: "HS-PRO", quantity: 1 }],
    country: "AT",
    date: "2026-06-01",
  }).body as any).quote;
  assert.deepEqual(quote.display, {
    subtotal: "129.99 EUR",
    tax: "26.00 EUR",
    shipping: "free",
    total: "155.99 EUR",
  });
});

test("quote rejects an impossible date", () => {
  const res = createQuote({
    customer: { name: "Ola Berg" },
    lines: [{ sku: "HS-PRO", quantity: 1 }],
    country: "AT",
    date: "2026-02-30",
  });
  assert.equal(res.status, 400);
});
