import { CURRENCY } from "./config.ts";

/** 123456 -> "1,234.56 EUR". */
export function formatCents(cents: number, currency: string = CURRENCY): string {
  const sign = cents < 0 ? "-" : "";
  const abs = Math.abs(cents);
  const whole = Math.floor(abs / 100).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const frac = (abs % 100).toString().padStart(2, "0");
  return `${sign}${whole}.${frac} ${currency}`;
}

/** 1900 -> "19 %", 810 -> "8.1 %". */
export function formatBps(bps: number): string {
  const pct = bps / 100;
  return `${Number.isInteger(pct) ? pct.toString() : pct.toFixed(2).replace(/0+$/, "")} %`;
}
