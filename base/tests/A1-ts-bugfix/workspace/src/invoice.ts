import { discountFor } from "./discount.ts";
import { allocate, applyBps } from "./money.ts";
import type { Invoice, LineBreakdown, LineItem, Totals } from "./types.ts";

export function lineAmount(line: LineItem): number {
  if (!Number.isInteger(line.quantity) || line.quantity < 0) {
    throw new RangeError(`invalid quantity for ${line.sku}`);
  }
  if (!Number.isInteger(line.unitPriceCents)) {
    throw new RangeError(`unit price for ${line.sku} must be whole cents`);
  }
  return line.quantity * line.unitPriceCents;
}

/** Invoice totals: subtotal, discount, tax base, tax, and grand total. */
export function computeTotals(invoice: Invoice): Totals {
  const amounts = invoice.lines.map(lineAmount);
  const subtotalCents = amounts.reduce((a, b) => a + b, 0);
  const discountCents = discountFor(subtotalCents, invoice.discount);
  const taxableCents = subtotalCents - discountCents;

  const discountShares = subtotalCents > 0 ? allocate(discountCents, amounts) : amounts.map(() => 0);
  let taxCents = 0;
  for (let i = 0; i < amounts.length; i++) {
    taxCents += applyBps(amounts[i] - discountShares[i], invoice.taxRateBps);
  }

  return { subtotalCents, discountCents, taxableCents, taxCents, totalCents: taxableCents + taxCents };
}

/** The invoice totals spread over the lines, for the ledger export. */
export function lineBreakdown(invoice: Invoice): LineBreakdown[] {
  const totals = computeTotals(invoice);
  const amounts = invoice.lines.map(lineAmount);
  if (totals.subtotalCents === 0) {
    return invoice.lines.map((line) => ({
      sku: line.sku, amountCents: 0, discountCents: 0, taxCents: 0, totalCents: 0,
    }));
  }
  const discounts = allocate(totals.discountCents, amounts);
  const net = amounts.map((amount, i) => amount - discounts[i]);
  const taxes = totals.taxableCents > 0 ? allocate(totals.taxCents, net) : net.map(() => 0);
  return invoice.lines.map((line, i) => ({
    sku: line.sku,
    amountCents: amounts[i],
    discountCents: discounts[i],
    taxCents: taxes[i],
    totalCents: net[i] + taxes[i],
  }));
}
