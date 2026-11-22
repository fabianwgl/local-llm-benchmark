import { applyBps } from "./money.ts";
import type { Coupon } from "./types.ts";

const COUPONS: readonly Coupon[] = [
  { code: "WELCOME10", kind: "percent", bps: 1000, minSubtotalCents: 0, description: "10 % off your first order" },
  { code: "LOYAL7", kind: "percent", bps: 700, minSubtotalCents: 0, description: "7 % for returning customers" },
  { code: "SPRING15", kind: "percent", bps: 1500, minSubtotalCents: 10000, description: "15 % off from 100 EUR" },
  { code: "TAKE5", kind: "fixed", cents: 500, minSubtotalCents: 2500, description: "5 EUR off from 25 EUR" },
  { code: "BIG20", kind: "fixed", cents: 2000, minSubtotalCents: 20000, description: "20 EUR off from 200 EUR" },
];

export function normalizeCode(code: string): string {
  return code.trim().toUpperCase();
}

export function findCoupon(code: string): Coupon | undefined {
  const wanted = normalizeCode(code);
  return COUPONS.find((c) => c.code === wanted);
}

/** Whether an order with this subtotal qualifies for the coupon. */
export function isEligible(coupon: Coupon, subtotalCents: number): boolean {
  return subtotalCents >= coupon.minSubtotalCents;
}

/** The amount a coupon takes off `baseCents`. A fixed coupon never takes off more than the base. */
export function couponDiscount(coupon: Coupon, baseCents: number): number {
  if (coupon.kind === "percent") {
    return applyBps(baseCents, coupon.bps);
  }
  return Math.min(coupon.cents, baseCents);
}

export function describeCoupon(coupon: Coupon): string {
  return `${coupon.code}: ${coupon.description}`;
}
