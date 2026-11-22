import { getProduct } from "../catalog.ts";
import { QUOTE_VALIDITY_DAYS } from "../config.ts";
import { couponDiscount, findCoupon } from "../coupons.ts";
import { addDays } from "../dates.ts";
import { formatCents } from "../format.ts";
import { ok } from "../http.ts";
import { quoteNumber } from "../ids.ts";
import { applyBps } from "../money.ts";
import { shippingFor } from "../shipping.ts";
import { taxRateFor } from "../tax.ts";
import type { ApiRequest, ApiResponse, QuoteLine, QuoteResponse } from "../types.ts";
import { validateQuoteRequest } from "../validation.ts";
import { volumeDiscountBps } from "../volume.ts";

/**
 * POST /quotes
 *
 * Builds a written quote for business customers (sales team and the B2B portal). The quote is
 * returned, not stored; the number is derived from the date and customer so retries are stable.
 */
export function createQuote(req: ApiRequest): ApiResponse<QuoteResponse> {
  const request = validateQuoteRequest(req.body);
  const country = request.country;

  const lines: QuoteLine[] = [];
  for (const input of request.lines) {
    if (input.quantity === 0) {
      continue;
    }
    const product = getProduct(input.sku)!;
    lines.push({
      sku: product.sku,
      description: product.name,
      quantity: input.quantity,
      unitPriceCents: product.priceCents,
      amountCents: input.quantity * product.priceCents,
    });
  }

  const subtotalCents = lines.reduce((sum, line) => sum + line.amountCents, 0);
  const volumeDiscountCents = lines.reduce(
    (sum, line) => sum + applyBps(line.amountCents, volumeDiscountBps(line.quantity)),
    0,
  );

  const coupon = request.coupon ? findCoupon(request.coupon) : undefined;
  const couponDiscountCents =
    coupon && subtotalCents >= coupon.minSubtotalCents
      ? couponDiscount(coupon, subtotalCents - volumeDiscountCents)
      : 0;

  const netCents = Math.max(0, subtotalCents - volumeDiscountCents - couponDiscountCents);
  const taxCents = applyBps(netCents, taxRateFor(country));
  const shippingCents = shippingFor(country, netCents + taxCents);
  const totalCents = netCents + taxCents + shippingCents;

  const issuedOn = request.date;
  return ok({
    quote: {
      number: quoteNumber(issuedOn, request.customer.company ?? request.customer.name),
      customer: { name: request.customer.name, company: request.customer.company ?? null },
      issuedOn,
      validUntil: addDays(issuedOn, request.validityDays ?? QUOTE_VALIDITY_DAYS),
      country,
      lines,
      totals: {
        subtotalCents,
        volumeDiscountCents,
        couponDiscountCents,
        netCents,
        taxCents,
        shippingCents,
        totalCents,
      },
      display: {
        subtotal: formatCents(subtotalCents),
        tax: formatCents(taxCents),
        shipping: shippingCents === 0 ? "free" : formatCents(shippingCents),
        total: formatCents(totalCents),
      },
    },
  });
}
