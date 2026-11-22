import { test } from "node:test";
import assert from "node:assert/strict";
import { handle } from "../src/index.ts";

test("health check answers", () => {
  assert.deepEqual(handle({ method: "GET", path: "/health" }), {
    status: 200,
    body: { status: "ok", service: "shopfront-api" },
  });
});

test("unknown routes return 404", () => {
  assert.equal(handle({ method: "GET", path: "/orders" }).status, 404);
});

test("a known path with the wrong method returns 405", () => {
  assert.equal(handle({ method: "GET", path: "/cart/price" }).status, 405);
});

test("products can be filtered by category", () => {
  const body = handle({ method: "GET", path: "/products", query: { category: "audio" } }).body as any;
  assert.deepEqual(body.products.map((p: any) => p.sku), ["HS-PRO", "SPK-MINI"]);
  assert.equal(body.products[0].price, "129.99 EUR");
});

test("discontinued products are not found", () => {
  assert.equal(handle({ method: "GET", path: "/products/KB-90" }).status, 404);
  assert.equal(handle({ method: "GET", path: "/products/KB-101" }).status, 200);
});

test("coupon check reports the minimum order value", () => {
  const body = handle({ method: "POST", path: "/coupons/check", body: { code: "spring15", subtotalCents: 9999 } })
    .body as any;
  assert.deepEqual(body, { code: "SPRING15", valid: false, reason: "minimum order value is 100.00 EUR" });
});
