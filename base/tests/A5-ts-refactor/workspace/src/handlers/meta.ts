import { FREE_SHIPPING_THRESHOLD_CENTS } from "../config.ts";
import { formatBps } from "../format.ts";
import { ok } from "../http.ts";
import { carrierFor } from "../shipping.ts";
import { supportedCountries, taxRateFor } from "../tax.ts";
import type { ApiResponse } from "../types.ts";

/** GET /health */
export function health(): ApiResponse {
  return ok({ status: "ok", service: "shopfront-api" });
}

/** GET /countries: where we ship, with the VAT rate and carrier for each. */
export function listCountries(): ApiResponse {
  return ok({
    freeShippingThresholdCents: FREE_SHIPPING_THRESHOLD_CENTS,
    countries: supportedCountries().map((code) => ({
      code,
      vat: formatBps(taxRateFor(code)),
      carrier: carrierFor(code),
    })),
  });
}
