/** One line on an invoice. */
export interface LineItem {
  sku: string;
  description: string;
  quantity: number;
  unitPriceCents: number;
}

/** An invoice-level discount: a percentage in basis points, or a fixed amount in cents. */
export type Discount = { kind: "percent"; bps: number } | { kind: "fixed"; cents: number };

export interface Invoice {
  id: string;
  customer: string;
  lines: LineItem[];
  /** Tax rate in basis points, e.g. 1900 for 19 %. */
  taxRateBps: number;
  discount?: Discount;
}

export interface Totals {
  subtotalCents: number;
  discountCents: number;
  /** Subtotal minus discount: the base the tax is charged on. */
  taxableCents: number;
  taxCents: number;
  totalCents: number;
}

export interface LineBreakdown {
  sku: string;
  amountCents: number;
  discountCents: number;
  taxCents: number;
  totalCents: number;
}

export interface PaymentPart {
  account: string;
  weight: number;
}

export interface PaymentShare {
  account: string;
  cents: number;
}
