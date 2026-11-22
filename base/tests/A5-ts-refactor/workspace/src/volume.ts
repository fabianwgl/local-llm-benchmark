// Volume discount tiers. A line qualifies on its own quantity; quantities are not pooled across lines.

interface Tier {
  minQuantity: number;
  bps: number;
}

const TIERS: readonly Tier[] = [
  { minQuantity: 50, bps: 800 },
  { minQuantity: 25, bps: 500 },
  { minQuantity: 10, bps: 300 },
];

/** Discount rate in basis points for a line of `quantity` units (0 below the first tier). */
export function volumeDiscountBps(quantity: number): number {
  for (const tier of TIERS) {
    if (quantity >= tier.minQuantity) {
      return tier.bps;
    }
  }
  return 0;
}

export function volumeTiers(): Tier[] {
  return TIERS.map((t) => ({ ...t }));
}
