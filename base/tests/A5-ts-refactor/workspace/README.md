# shopfront-api

Pricing and document API behind the web shop and the B2B portal: it prices carts, writes quotes
for business customers, and renders invoices for paid orders.

The service is a set of pure handler functions. A handler takes a plain request object
(`{ method, path, body, query }`) and returns a plain response object (`{ status, body }`). The
HTTP adapter that sits in front of it lives in the platform repository and is not part of this
code base.

```ts
import { handle } from "./src/index.ts";

handle({
  method: "POST",
  path: "/cart/price",
  body: { items: [{ sku: "KB-101", quantity: 2 }], country: "DE", couponCode: "WELCOME10" },
});
// { status: 200, body: { currency: "EUR", items: [...], subtotalCents: 17980, ..., totalCents: 19257 } }
```

## Endpoints

| Method | Path | Handler | Used by |
|---|---|---|---|
| GET | `/health` | `handlers/meta.ts` | load balancer |
| GET | `/countries` | `handlers/meta.ts` | checkout page |
| GET | `/products`, `/products/:sku` | `handlers/products.ts` | shop front end |
| POST | `/coupons/check` | `handlers/coupons.ts` | checkout page |
| POST | `/cart/price` | `handlers/cart.ts` | mini cart, checkout page |
| POST | `/quotes` | `handlers/quote.ts` | sales team, B2B portal |
| POST | `/invoices` | `handlers/invoice.ts` | order service (once per paid order) |

Request and response shapes are the interfaces in `src/types.ts`. Error responses have the
shape `{ error: { code, message } }` with status 400 (malformed request), 404, 405 or 422
(well-formed but not acceptable, for example an unknown product or coupon).

## Money

- All amounts are **integer cents**; rates are **basis points** (1900 bps = 19 %).
- Rounding goes to the nearest cent, halves away from zero (`src/money.ts`).
- Catalogue prices are net. VAT is charged at the standard rate of the destination country
  (`src/tax.ts`).
- Volume discounts depend on the quantity of a single line: 3 % from 10 units, 5 % from 25,
  8 % from 50 (`src/volume.ts`).
- Coupons take a percentage or a fixed amount off and may require a minimum order value
  (`src/coupons.ts`). Unknown codes are rejected with 422; a known code below its minimum
  simply does not apply.
- Shipping is a flat fee per country, waived from 75.00 EUR except for Switzerland
  (`src/shipping.ts`, `src/config.ts`).

## Development

```
npm test            # node --test (Node.js 24 runs the TypeScript sources directly)
npm run typecheck   # tsc --noEmit
```

There are no dependencies. Keep it that way: the service is vendored into the platform build,
which does not run `npm install` for it.
