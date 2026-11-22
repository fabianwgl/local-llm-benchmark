import { computeTotals } from "./invoice.ts";
import { applyBps } from "./money.ts";
import type { Invoice, Totals } from "./types.ts";

/**
 * Totals of a credit note that reverses `shareBps` of an invoice (10000 = the whole invoice).
 * Every amount is negative or zero.
 */
export function creditNote(invoice: Invoice, shareBps: number): Totals {
  if (shareBps <= 0 || shareBps > 10000) {
    throw new RangeError("a credit note must cover between 0 and 10000 bps of the invoice");
  }
  const totals = computeTotals(invoice);
  const subtotalCents = applyBps(-totals.subtotalCents, shareBps);
  const discountCents = applyBps(-totals.discountCents, shareBps);
  const taxableCents = subtotalCents - discountCents;
  const taxCents = applyBps(taxableCents, invoice.taxRateBps);
  return { subtotalCents, discountCents, taxableCents, taxCents, totalCents: taxableCents + taxCents };
}
