# Architecture

## Layers

```
router.ts            path + method -> handler; turns thrown HttpErrors into error responses
handlers/*.ts        one file per resource; validate, compute, shape the response
validation.ts        request parsing; throws ValidationError (400) / UnprocessableError (422)
catalog.ts           products (in code; the catalogue is small)
coupons.ts           coupon table and coupon maths
tax.ts               VAT rates per country
shipping.ts          shipping fees per country, free-shipping rule
volume.ts            volume discount tiers
money.ts             integer-cent helpers (rounding, basis points)
format.ts, dates.ts, ids.ts, http.ts, config.ts, errors.ts, types.ts
```

Dependencies point downwards only: handlers may import anything below them, domain modules never
import handlers, and nothing imports the router except `index.ts`.

## Conventions

- **Handlers are pure.** No I/O, no clock, no randomness: everything a handler needs is in the
  request (quote and invoice dates are passed in). The same request always gives the same
  response, which is what lets the order service retry invoice rendering safely.
- **Validate first.** A handler calls its `validate*Request` function before doing anything else.
  After validation, SKUs are known to exist and to be active, quantities are whole numbers from 0
  to `MAX_QUANTITY`, and coupon codes are known (eligibility is checked later).
- **Throw, do not return, errors.** Handlers throw `HttpError` subclasses; the router converts
  them. Unexpected exceptions become a 500 without details.
- **Money is integer cents.** Never divide an amount and keep the fraction around; round with
  the helpers in `money.ts`.
- **Response shapes are contracts.** The web shop, the B2B portal and the order service parse these
  responses. Field names, nesting and values must not change without coordinating with those
  teams; accounting reconciles invoices to the cent.

## History

The cart endpoint came first. Quotes were added for the B2B portal in 2024 and invoices when
billing moved in-house in 2025; both started from a copy of the cart pricing code, which is why
`handlers/cart.ts`, `handlers/quote.ts` and `handlers/invoice.ts` each contain their own pricing
section.
