import type { CountryCode } from "./types.ts";

// Standard VAT rates in basis points. We only sell standard-rated goods.
const VAT_BPS: Record<CountryCode, number> = {
  DE: 1900,
  AT: 2000,
  FR: 2000,
  NL: 2100,
  BE: 2100,
  CH: 810,
};

export function isSupportedCountry(value: string): value is CountryCode {
  return Object.prototype.hasOwnProperty.call(VAT_BPS, value);
}

export function supportedCountries(): CountryCode[] {
  return Object.keys(VAT_BPS) as CountryCode[];
}

export function taxRateFor(country: CountryCode): number {
  return VAT_BPS[country];
}
