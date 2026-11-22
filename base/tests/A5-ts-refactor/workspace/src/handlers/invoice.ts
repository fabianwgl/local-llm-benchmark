import { getProduct } from "../catalog.ts";
import { PAYMENT_TERMS_DAYS } from "../config.ts";
import { findCoupon, normalizeCode } from "../coupons.ts";
import { addDays } from "../dates.ts";
import { created } from "../http.ts";
import { invoiceNumber } from "../ids.ts";
import { applyBps, bpsToCents } from "../money.ts";
import { shippingFor } from "../shipping.ts";
import { taxRateFor } from "../tax.ts";
import type { ApiRequest, ApiResponse, InvoicePosition, InvoiceResponse } from "../types.ts";
import { validateInvoiceRequest } from "../validation.ts";
import { volumeDiscountBps } from "../volume.ts";

/**
 * POST /invoices
 *
 * Renders the invoice document for a paid order. The order service calls this once per order
 * and archives the result; accounting reconciles against these numbers.
 */
export function createInvoice(req: ApiRequest): ApiResponse<InvoiceResponse> {
  const order = validateInvoiceRequest(req.body);
  const taxRateBps = taxRateFor(order.billingCountry);

  const positions: InvoicePosition[] = order.items.map((item, index) => {
    const product = getProduct(item.sku)!;
    return {
      position: index + 1,
      sku: product.sku,
      description: product.name,
      quantity: item.quantity,
      unitPriceCents: product.priceCents,
      netCents: product.priceCents * item.quantity,
    };
  });

  let subtotalCents = 0;
  for (const p of positions) {
    subtotalCents += p.netCents;
  }

  // Coupon
  const coupon = order.couponCode ? findCoupon(order.couponCode) : undefined;
  let couponCents = 0;
  if (coupon !== undefined && subtotalCents >= coupon.minSubtotalCents) {
    couponCents =
      coupon.kind === "percent" ? applyBps(subtotalCents, coupon.bps) : Math.min(coupon.cents, subtotalCents);
  }

  // Volume discount
  let volumeBasis = 0;
  for (const p of positions) {
    volumeBasis += p.netCents * volumeDiscountBps(p.quantity);
  }
  const volumeCents = bpsToCents(volumeBasis);

  const netCents = Math.max(0, subtotalCents - couponCents - volumeCents);
  const taxCents = applyBps(netCents, taxRateBps);
  const shippingCents = shippingFor(order.billingCountry, netCents);
  const grossCents = netCents + taxCents + shippingCents;

  return created({
    invoice: {
      number: invoiceNumber(order.orderId),
      orderId: order.orderId,
      customerId: order.customerId,
      issueDate: order.issueDate,
      dueDate: addDays(order.issueDate, PAYMENT_TERMS_DAYS),
      billingCountry: order.billingCountry,
      positions,
      subtotalCents,
      discounts: {
        volumeCents,
        couponCents,
        couponCode: coupon ? normalizeCode(coupon.code) : null,
      },
      netCents,
      taxRateBps,
      taxCents,
      shippingCents,
      grossCents,
    },
  });
}
