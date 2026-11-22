# invoice-kit

Invoice maths for the billing service. Everything is computed in **integer cents**; no amount is
ever stored as a floating-point number of euros.

## Usage

```ts
import { computeTotals, lineBreakdown, creditNote, splitPayment } from "./src/index.ts";

const invoice = {
  id: "INV-1001",
  customer: "Acme GmbH",
  taxRateBps: 1900, // 19.00 %
  discount: { kind: "percent", bps: 1000 }, // 10.00 %
  lines: [
    { sku: "A-1", description: "Widget", quantity: 3, unitPriceCents: 1250 },
    { sku: "B-7", description: "Setup fee", quantity: 1, unitPriceCents: 5000 },
  ],
};

computeTotals(invoice); // { subtotalCents, discountCents, taxableCents, taxCents, totalCents }
lineBreakdown(invoice); // the same amounts, spread over the lines
creditNote(invoice, 5000); // credit note for 50.00 % of the invoice (all amounts negative)
splitPayment(10000, [{ account: "ops", weight: 1 }, { account: "rnd", weight: 2 }]);
```

Rates and shares are given in basis points (bps): 1 bp = 0.01 %, so 1900 bps = 19 %.

## Rounding rules

These rules are the contract with our customers' accounting systems.

1. **Half away from zero.** When an amount falls exactly between two cents it is rounded away
   from zero: 2.5 becomes 3 and -2.5 becomes -3. Everything else rounds to the nearest cent.
2. **Allocations never lose or invent a cent.** `allocate(total, weights)` splits `total`
   proportionally to `weights`, and the parts always add up to exactly `total`. Each part first
   gets its exact share rounded down; the cents that are left over are then handed out one at a
   time to the parts with the largest fractional remainder, earlier parts first when remainders
   are equal. Example: `allocate(100, [1, 1, 1])` is `[34, 33, 33]`.
   A negative total is allocated as its absolute value and then negated:
   `allocate(-100, [1, 1, 1])` is `[-34, -33, -33]`.
3. **The discount is rounded once.** A percentage discount is applied to the invoice subtotal
   and rounded once. It is then spread over the lines with `allocate`.
4. **Tax is rounded once.** Tax is the tax rate applied to the discounted subtotal
   (`taxableCents`), rounded once for the whole invoice. It is never computed line by line and
   summed. The per-line tax shown in `lineBreakdown` is that single amount spread over the lines
   with `allocate`.
5. **A credit note mirrors the invoice.** A credit note for a share of an invoice has exactly
   the amounts an invoice for that share would have, with a negative sign.

## Development

```
npm test            # node --test
npm run typecheck   # tsc --noEmit
```

There are no dependencies. Tests use the Node.js built-in test runner and run the TypeScript
sources directly.
