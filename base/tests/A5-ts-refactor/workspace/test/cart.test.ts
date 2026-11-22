import { test } from "node:test";
import assert from "node:assert/strict";
import { handle } from "../src/index.ts";

function priceCart(body: unknown) {
  return handle({ method: "POST", path: "/cart/price", body });
}

test("cart prices a single line", () => {
  const res = priceCart({ items: [{ sku: "KB-101", quantity: 1 }], country: "DE" });
  assert.equal(res.status, 200);
  assert.deepEqual(res.body, {
    currency: "EUR",
    items: [{ sku: "KB-101", name: "Mechanical keyboard", quantity: 1, unitPriceCents: 8990, lineTotalCents: 8990 }],
    itemCount: 1,
    subtotalCents: 8990,
    volumeDiscountCents: 0,
    couponDiscountCents: 0,
    taxCents: 1708,
    shippingCents: 0,
    totalCents: 10698,
    freeShipping: true,
  });
});

test("cart charges shipping below the free-shipping threshold", () => {
  const body = priceCart({ items: [{ sku: "MS-220", quantity: 2 }], country: "DE" }).body as any;
  assert.equal(body.subtotalCents, 4990);
  assert.equal(body.taxCents, 948);
  assert.equal(body.shippingCents, 495);
  assert.equal(body.totalCents, 6433);
  assert.equal(body.freeShipping, false);
});

test("cart applies the volume tier of a line", () => {
  const body = priceCart({ items: [{ sku: "CB-USBC", quantity: 10 }], country: "FR" }).body as any;
  assert.equal(body.subtotalCents, 7990);
  assert.equal(body.volumeDiscountCents, 240);
  assert.equal(body.taxCents, 1550);
  assert.equal(body.totalCents, 9300);
});

test("cart applies a percentage coupon", () => {
  const body = priceCart({
    items: [{ sku: "HS-PRO", quantity: 2 }, { sku: "MS-220", quantity: 1 }],
    country: "CH",
    couponCode: "WELCOME10",
  }).body as any;
  assert.equal(body.subtotalCents, 28493);
  assert.equal(body.couponDiscountCents, 2849);
  assert.equal(body.taxCents, 2077);
  assert.equal(body.totalCents, 29211);
});

test("cart ignores a coupon below its minimum order value", () => {
  const body = priceCart({ items: [{ sku: "KB-101", quantity: 1 }], country: "DE", couponCode: "SPRING15" }).body as any;
  assert.equal(body.couponDiscountCents, 0);
  assert.equal(body.totalCents, 10698);
});

test("cart rejects an unknown coupon", () => {
  const res = priceCart({ items: [{ sku: "KB-101", quantity: 1 }], country: "DE", couponCode: "FREESHIP" });
  assert.equal(res.status, 422);
  assert.equal((res.body as any).error.code, "unknown_coupon");
});

test("cart never ships to Switzerland for free", () => {
  const body = priceCart({ items: [{ sku: "MON-27", quantity: 1 }], country: "CH" }).body as any;
  assert.equal(body.shippingCents, 1490);
  assert.equal(body.taxCents, 2260);
  assert.equal(body.totalCents, 31650);
});
