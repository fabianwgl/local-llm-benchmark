/** Money helpers. All amounts are integer cents. See README.md, "Rounding rules". */

/** Round to the nearest whole cent. */
export function roundCents(value: number): number {
  return Math.round(value);
}

/** Apply a rate in basis points (1 bp = 0.01 %) to an amount in cents. */
export function applyBps(cents: number, bps: number): number {
  return roundCents((cents * bps) / 10000);
}

/** Split `total` cents across `weights`, proportionally to each weight. */
export function allocate(total: number, weights: number[]): number[] {
  if (weights.length === 0) return [];
  const sum = weights.reduce((a, b) => a + b, 0);
  if (sum <= 0) throw new RangeError("weights must add up to a positive number");
  return weights.map((w) => roundCents((total * w) / sum));
}

/** Format cents for display, e.g. 123456 -> "1,234.56 EUR". */
export function formatCents(cents: number, currency = "EUR"): string {
  const sign = cents < 0 ? "-" : "";
  const abs = Math.abs(cents);
  const whole = Math.floor(abs / 100).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const frac = (abs % 100).toString().padStart(2, "0");
  return `${sign}${whole}.${frac} ${currency}`;
}
