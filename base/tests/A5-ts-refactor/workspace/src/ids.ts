import { compactDate } from "./dates.ts";

/** Quote numbers are derived from the issue date and the customer, so a retried request gets the same number. */
export function quoteNumber(isoDate: string, customerName: string): string {
  const slug = customerName
    .normalize("NFKD")
    .replace(/[^A-Za-z0-9]+/g, "")
    .toUpperCase()
    .slice(0, 8);
  return `Q-${compactDate(isoDate)}-${slug || "ANON"}`;
}

export function invoiceNumber(orderId: string): string {
  return `INV-${orderId.toUpperCase()}`;
}
