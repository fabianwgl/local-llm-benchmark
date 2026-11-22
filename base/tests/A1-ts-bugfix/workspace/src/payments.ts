import { allocate } from "./money.ts";
import type { PaymentPart, PaymentShare } from "./types.ts";

/** Split a payment across accounts (cost centres), proportionally to their weights. */
export function splitPayment(totalCents: number, parts: PaymentPart[]): PaymentShare[] {
  if (!Number.isInteger(totalCents)) throw new RangeError("a payment must be whole cents");
  const seen = new Set<string>();
  for (const part of parts) {
    if (seen.has(part.account)) throw new Error(`duplicate account ${part.account}`);
    seen.add(part.account);
  }
  const shares = allocate(totalCents, parts.map((p) => p.weight));
  return parts.map((part, i) => ({ account: part.account, cents: shares[i] }));
}
