import { test } from "node:test";
import assert from "node:assert/strict";
import { handle } from "../src/index.ts";

function createInvoice(body: unknown) {
  return handle({ method: "POST", path: "/invoices", body });
}

test("invoice numbers its positions and computes the gross amount", () => {
  const res = createInvoice({
    orderId: "ord-1001",
    customerId: "C-0042",
    billingCountry: "DE",
    items: [{ sku: "KB-101", quantity: 1 }, { sku: "MS-220", quantity: 2 }],
    issueDate: "2026-04-01",
  });
  assert.equal(res.status, 201);
  const inv = (res.body as any).invoice;
  assert.equal(inv.number, "INV-ORD-1001");
  assert.deepEqual(inv.positions.map((p: any) => [p.position, p.sku, p.netCents]), [
    [1, "KB-101", 8990],
    [2, "MS-220", 4990],
  ]);
  assert.equal(inv.subtotalCents, 13980);
  assert.equal(inv.taxRateBps, 1900);
  assert.equal(inv.taxCents, 2656);
  assert.equal(inv.shippingCents, 0);
  assert.equal(inv.grossCents, 16636);
});

test("invoice is due fourteen days after it is issued", () => {
  const inv = (createInvoice({
    orderId: "ord-1002",
    customerId: "C-0042",
    billingCountry: "FR",
    items: [{ sku: "MS-220", quantity: 1 }],
    issueDate: "2026-12-24",
  }).body as any).invoice;
  assert.equal(inv.dueDate, "2027-01-07");
  assert.equal(inv.shippingCents, 890);
  assert.equal(inv.grossCents, 3884);
});

test("invoice with a fixed coupon and a volume discount", () => {
  const inv = (createInvoice({
    orderId: "ord-1003",
    customerId: "C-0077",
    billingCountry: "BE",
    items: [{ sku: "KB-101", quantity: 30 }],
    couponCode: "big20",
    issueDate: "2026-05-05",
  }).body as any).invoice;
  assert.deepEqual(inv.discounts, { volumeCents: 13485, couponCents: 2000, couponCode: "BIG20" });
  assert.equal(inv.netCents, 254215);
  assert.equal(inv.taxCents, 53385);
  assert.equal(inv.grossCents, 307600);
});

test("invoice rejects a malformed order id", () => {
  const res = createInvoice({
    orderId: "ord 1004!",
    customerId: "C-0077",
    billingCountry: "BE",
    items: [{ sku: "KB-101", quantity: 1 }],
    issueDate: "2026-05-05",
  });
  assert.equal(res.status, 400);
});
