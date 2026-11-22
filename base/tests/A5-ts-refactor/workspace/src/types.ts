// Shared types for shopfront-api. Amounts are always integer cents; rates are basis points
// (1 bp = 0.01 %, so 1900 bps = 19 %).

export type CountryCode = "DE" | "AT" | "FR" | "NL" | "BE" | "CH";

export interface Product {
  sku: string;
  name: string;
  priceCents: number;
  category: "peripherals" | "displays" | "audio" | "storage" | "cables" | "accessories";
  active: boolean;
}

export type Coupon =
  | { code: string; kind: "percent"; bps: number; minSubtotalCents: number; description: string }
  | { code: string; kind: "fixed"; cents: number; minSubtotalCents: number; description: string };

/** One requested line, as it arrives from a client. */
export interface LineInput {
  sku: string;
  quantity: number;
}

// ---- transport ------------------------------------------------------------

export interface ApiRequest {
  method: string;
  path: string;
  body?: unknown;
  query?: Record<string, string>;
}

export interface ApiResponse<T = unknown> {
  status: number;
  body: T;
}

export interface ErrorBody {
  error: { code: string; message: string };
}

export type Handler = (req: ApiRequest, params: Record<string, string>) => ApiResponse;

// ---- cart -----------------------------------------------------------------

export interface CartRequest {
  items: LineInput[];
  country: CountryCode;
  couponCode?: string;
}

export interface CartItem {
  sku: string;
  name: string;
  quantity: number;
  unitPriceCents: number;
  lineTotalCents: number;
}

export interface CartResponse {
  currency: string;
  items: CartItem[];
  itemCount: number;
  subtotalCents: number;
  volumeDiscountCents: number;
  couponDiscountCents: number;
  taxCents: number;
  shippingCents: number;
  totalCents: number;
  freeShipping: boolean;
}

// ---- quote ----------------------------------------------------------------

export interface QuoteRequest {
  customer: { name: string; company?: string; email?: string };
  lines: LineInput[];
  country: CountryCode;
  coupon?: string;
  date: string;
  validityDays?: number;
}

export interface QuoteLine {
  sku: string;
  description: string;
  quantity: number;
  unitPriceCents: number;
  amountCents: number;
}

export interface QuoteTotals {
  subtotalCents: number;
  volumeDiscountCents: number;
  couponDiscountCents: number;
  netCents: number;
  taxCents: number;
  shippingCents: number;
  totalCents: number;
}

export interface QuoteResponse {
  quote: {
    number: string;
    customer: { name: string; company: string | null };
    issuedOn: string;
    validUntil: string;
    country: CountryCode;
    lines: QuoteLine[];
    totals: QuoteTotals;
    display: { subtotal: string; tax: string; shipping: string; total: string };
  };
}

// ---- invoice --------------------------------------------------------------

export interface InvoiceRequest {
  orderId: string;
  customerId: string;
  billingCountry: CountryCode;
  items: LineInput[];
  couponCode?: string;
  issueDate: string;
}

export interface InvoicePosition {
  position: number;
  sku: string;
  description: string;
  quantity: number;
  unitPriceCents: number;
  netCents: number;
}

export interface InvoiceResponse {
  invoice: {
    number: string;
    orderId: string;
    customerId: string;
    issueDate: string;
    dueDate: string;
    billingCountry: CountryCode;
    positions: InvoicePosition[];
    subtotalCents: number;
    discounts: { volumeCents: number; couponCents: number; couponCode: string | null };
    netCents: number;
    taxRateBps: number;
    taxCents: number;
    shippingCents: number;
    grossCents: number;
  };
}
