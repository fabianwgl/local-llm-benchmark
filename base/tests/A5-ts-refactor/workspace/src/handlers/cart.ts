import { getProduct } from "../catalog.ts";
import { CURRENCY } from "../config.ts";
import { couponDiscount, findCoupon, isEligible } from "../coupons.ts";
import { ok } from "../http.ts";
import { applyBps, bpsToCents, sumCents } from "../money.ts";
import { shippingFor } from "../shipping.ts";
import { taxRateFor } from "../tax.ts";
import type { ApiRequest, ApiResponse, CartItem, CartResponse } from "../types.ts";
import { validateCartRequest } from "../validation.ts";
import { volumeDiscountBps } from "../volume.ts";

/**
 * POST /cart/price
 *
 * Prices the basket shown in the web shop's mini cart and checkout page. Called on every
 * basket change, so it must stay cheap: no I/O, no persistence.
 */
export function priceCart(req: ApiRequest): ApiResponse<CartResponse> {
  const cart = validateCartRequest(req.body);

  // Lines
  const items: CartItem[] = cart.items
    .filter((item) => item.quantity > 0)
    .map((item) => {
      const product = getProduct(item.sku)!;
      return {
        sku: product.sku,
        name: product.name,
        quantity: item.quantity,
        unitPriceCents: product.priceCents,
        lineTotalCents: product.priceCents * item.quantity,
      };
    });
  const subtotalCents = sumCents(items.map((item) => item.lineTotalCents));

  // Volume discount, per line by quantity tier
  let volumeBasis = 0;
  for (const item of items) {
    volumeBasis += item.lineTotalCents * volumeDiscountBps(item.quantity);
  }
  const volumeDiscountCents = bpsToCents(volumeBasis);

  // Coupon
  let couponDiscountCents = 0;
  if (cart.couponCode) {
    const coupon = findCoupon(cart.couponCode)!;
    if (isEligible(coupon, subtotalCents)) {
      couponDiscountCents = couponDiscount(coupon, subtotalCents - volumeDiscountCents);
    }
  }

  const netCents = Math.max(0, subtotalCents - volumeDiscountCents - couponDiscountCents);

  // Shipping and tax
  const shippingCents = shippingFor(cart.country, netCents);
  const taxCents = applyBps(netCents, taxRateFor(cart.country));
  const totalCents = netCents + taxCents + shippingCents;

  return ok({
    currency: CURRENCY,
    items,
    itemCount: items.reduce((n, item) => n + item.quantity, 0),
    subtotalCents,
    volumeDiscountCents,
    couponDiscountCents,
    taxCents,
    shippingCents,
    totalCents,
    freeShipping: shippingCents === 0,
  });
}
