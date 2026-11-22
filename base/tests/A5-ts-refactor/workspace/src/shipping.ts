import { FREE_SHIPPING_THRESHOLD_CENTS } from "./config.ts";
import type { CountryCode } from "./types.ts";

interface ShippingRate {
  feeCents: number;
  freeShippingEligible: boolean;
  carrier: string;
}

const RATES: Record<CountryCode, ShippingRate> = {
  DE: { feeCents: 495, freeShippingEligible: true, carrier: "DHL" },
  AT: { feeCents: 790, freeShippingEligible: true, carrier: "DHL" },
  NL: { feeCents: 690, freeShippingEligible: true, carrier: "PostNL" },
  BE: { feeCents: 690, freeShippingEligible: true, carrier: "PostNL" },
  FR: { feeCents: 890, freeShippingEligible: true, carrier: "Colissimo" },
  CH: { feeCents: 1490, freeShippingEligible: false, carrier: "DHL Express" },
};

/** Shipping charged for an order of the given value. */
export function shippingFor(country: CountryCode, orderValueCents: number): number {
  const rate = RATES[country];
  if (rate.freeShippingEligible && orderValueCents >= FREE_SHIPPING_THRESHOLD_CENTS) {
    return 0;
  }
  return rate.feeCents;
}

export function carrierFor(country: CountryCode): string {
  return RATES[country].carrier;
}
