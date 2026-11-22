import { test } from "node:test";
import assert from "node:assert/strict";
import { applyBps, bpsToCents, roundHalfUp, sumCents } from "../src/money.ts";
import { formatBps, formatCents } from "../src/format.ts";

test("applyBps rounds half a cent up", () => {
  assert.equal(applyBps(1000, 1900), 190);
  assert.equal(applyBps(1010, 500), 51);
  assert.equal(applyBps(7990, 300), 240);
  assert.equal(applyBps(0, 2100), 0);
  assert.equal(bpsToCents(-25000), -3);
});

test("roundHalfUp and sumCents", () => {
  assert.equal(roundHalfUp(2.5), 3);
  assert.equal(roundHalfUp(-2.5), -3);
  assert.equal(roundHalfUp(2.49), 2);
  assert.equal(sumCents([100, 250, 5]), 355);
});

test("amounts and rates are formatted for display", () => {
  assert.equal(formatCents(123456), "1,234.56 EUR");
  assert.equal(formatCents(5), "0.05 EUR");
  assert.equal(formatBps(1900), "19 %");
  assert.equal(formatBps(810), "8.1 %");
});
