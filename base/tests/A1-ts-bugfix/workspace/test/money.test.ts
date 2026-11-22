import { test } from "node:test";
import assert from "node:assert/strict";
import { allocate, applyBps, formatCents, roundCents } from "../src/index.ts";

test("roundCents rounds to the nearest cent", () => {
  assert.equal(roundCents(2.4), 2);
  assert.equal(roundCents(2.6), 3);
  assert.equal(roundCents(2.5), 3);
  assert.equal(roundCents(7), 7);
});

test("applyBps applies a percentage", () => {
  assert.equal(applyBps(1000, 1900), 190);
  assert.equal(applyBps(2000, 250), 50);
  assert.equal(applyBps(0, 1900), 0);
});

test("allocate splits evenly when it divides cleanly", () => {
  assert.deepEqual(allocate(100, [1, 1]), [50, 50]);
  assert.deepEqual(allocate(90, [1, 2]), [30, 60]);
  assert.deepEqual(allocate(1200, [1, 1, 1, 1]), [300, 300, 300, 300]);
});

test("allocate handles the edge cases", () => {
  assert.deepEqual(allocate(500, []), []);
  assert.throws(() => allocate(500, [0, 0]), RangeError);
});

test("formatCents formats amounts for display", () => {
  assert.equal(formatCents(123456), "1,234.56 EUR");
  assert.equal(formatCents(5), "0.05 EUR");
  assert.equal(formatCents(-1999, "USD"), "-19.99 USD");
});
