import { describeCoupon, findCoupon, isEligible } from "../coupons.ts";
import { ValidationError } from "../errors.ts";
import { formatCents } from "../format.ts";
import { ok } from "../http.ts";
import type { ApiRequest, ApiResponse } from "../types.ts";

/**
 * POST /coupons/check  { code, subtotalCents? }
 *
 * Lets the checkout page tell the customer early whether a code will apply.
 */
export function checkCoupon(req: ApiRequest): ApiResponse {
  const body = (req.body ?? {}) as { code?: unknown; subtotalCents?: unknown };
  if (typeof body.code !== "string" || body.code.trim() === "") {
    throw new ValidationError("code is required");
  }
  const coupon = findCoupon(body.code);
  if (!coupon) {
    return ok({ code: body.code, valid: false, reason: "unknown code" });
  }
  if (body.subtotalCents !== undefined) {
    if (typeof body.subtotalCents !== "number" || !Number.isInteger(body.subtotalCents)) {
      throw new ValidationError("subtotalCents must be a whole number");
    }
    if (!isEligible(coupon, body.subtotalCents)) {
      return ok({
        code: coupon.code,
        valid: false,
        reason: `minimum order value is ${formatCents(coupon.minSubtotalCents)}`,
      });
    }
  }
  return ok({ code: coupon.code, valid: true, description: describeCoupon(coupon) });
}
