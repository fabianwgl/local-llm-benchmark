import { computeTotals, lineAmount } from "./invoice.ts";
import { formatCents } from "./money.ts";
import type { Invoice } from "./types.ts";

function pad(label: string, value: string, width = 44): string {
  const gap = Math.max(1, width - label.length - value.length);
  return label + " ".repeat(gap) + value;
}

/** Plain-text rendering used in e-mail receipts. */
export function renderInvoice(invoice: Invoice, currency = "EUR"): string {
  const totals = computeTotals(invoice);
  const out: string[] = [`Invoice ${invoice.id}`, `Customer: ${invoice.customer}`, ""];
  for (const line of invoice.lines) {
    out.push(pad(`${line.quantity} x ${line.description}`, formatCents(lineAmount(line), currency)));
  }
  out.push("");
  out.push(pad("Subtotal", formatCents(totals.subtotalCents, currency)));
  if (totals.discountCents > 0) {
    out.push(pad("Discount", formatCents(-totals.discountCents, currency)));
  }
  const rate = (invoice.taxRateBps / 100).toFixed(2).replace(/\.?0+$/, "");
  out.push(pad(`Tax (${rate}%)`, formatCents(totals.taxCents, currency)));
  out.push(pad("Total", formatCents(totals.totalCents, currency)));
  return out.join("\n");
}
