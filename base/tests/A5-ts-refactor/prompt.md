# Ticket SHOP-5127: one pricing implementation for cart, quotes and invoices

From the tech lead:

> Every pricing change has to be made three times. `src/handlers/cart.ts`, `src/handlers/quote.ts`
> and `src/handlers/invoice.ts` each carry their own copy of the pricing code (line totals, volume
> discount, coupon, tax, shipping, total). Please move the pricing into one shared module that all
> three handlers use.
>
> This is a pure refactor. The web shop, the B2B portal and accounting depend on today's numbers
> to the cent, so every endpoint must keep returning exactly the response it returns today, for
> every request.

The repository in `/work` is `shopfront-api`. `README.md` and `docs/ARCHITECTURE.md` describe it.

## Requirements

1. Create `src/pricing/compute.ts`. It exports a synchronous function named `computePricing` that
   holds the pricing logic. You choose its parameters (inputs and any options). It returns a
   `PricingResult`, exported from the same module, with at least these fields:

   ```ts
   export interface PricedLine {
     sku: string;
     name: string;
     quantity: number;
     unitPriceCents: number;
     lineTotalCents: number;      // quantity x unit price
   }

   export interface PricingResult {
     lines: PricedLine[];         // the lines the endpoint reports, in request order
     subtotalCents: number;
     volumeDiscountCents: number;
     couponDiscountCents: number;
     netCents: number;            // subtotal minus both discounts
     taxCents: number;
     shippingCents: number;
     totalCents: number;          // net + tax + shipping
   }
   ```

2. The cart, quote and invoice handlers import `computePricing` from `src/pricing/compute.ts` and
   take every amount they report (line amounts, subtotal, discounts, net, tax, shipping, total)
   from its result. No pricing arithmetic stays in the handlers. Validation, numbering, dates and
   the shape of each response stay where they are.
3. No observable change: for any request, `handle()` returns the same status and the same body as
   before the refactor.
4. Do not modify the existing tests, `package.json` or `tsconfig.json`. New tests are welcome.

Run the tests with `npm test` and the type check with `npm run typecheck`; both must pass.

In your finish summary, say how the three copies compared and how `computePricing` covers each
handler.
