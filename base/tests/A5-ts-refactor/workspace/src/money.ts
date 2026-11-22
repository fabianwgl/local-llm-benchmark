// Integer-cent arithmetic. Nothing in shopfront-api stores money as a float number of euros.

/** Rounds to the nearest integer; halves go away from zero (2.5 -> 3, -2.5 -> -3). */
export function roundHalfUp(value: number): number {
  const sign = value < 0 ? -1 : 1;
  return sign * Math.floor(Math.abs(value) + 0.5);
}

/**
 * Converts an amount expressed in cent-basis-points (cents multiplied by a rate in bps) back
 * to whole cents. Integer division keeps the result exact for the inputs we deal with.
 */
export function bpsToCents(basis: number): number {
  if (!Number.isFinite(basis)) {
    throw new RangeError(`invalid amount: ${basis}`);
  }
  const sign = basis < 0 ? -1 : 1;
  return sign * Math.floor((Math.abs(basis) + 5000) / 10000);
}

/** `cents` multiplied by a rate in basis points, rounded to whole cents. */
export function applyBps(cents: number, bps: number): number {
  return bpsToCents(cents * bps);
}

export function sumCents(amounts: readonly number[]): number {
  let total = 0;
  for (const amount of amounts) {
    total += amount;
  }
  return total;
}

export function assertCents(value: number, label: string): void {
  if (!Number.isSafeInteger(value)) {
    throw new RangeError(`${label} must be a whole number of cents, got ${value}`);
  }
}
