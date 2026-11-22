import { applyBps } from "./money.ts";
import type { Discount } from "./types.ts";

/** The discount in cents for a given subtotal. A fixed discount never exceeds the subtotal. */
export function discountFor(subtotalCents: number, discount?: Discount): number {
  if (!discount) return 0;
  if (discount.kind === "fixed") {
    if (discount.cents < 0) throw new RangeError("a fixed discount cannot be negative");
    return Math.min(discount.cents, subtotalCents);
  }
  if (discount.bps < 0 || discount.bps > 10000) {
    throw new RangeError("a percentage discount must be between 0 and 10000 bps");
  }
  return applyBps(subtotalCents, discount.bps);
}
