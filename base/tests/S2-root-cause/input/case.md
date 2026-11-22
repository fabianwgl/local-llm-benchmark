## On-call note

Handover from the previous on-call (Thursday 11 Sep, 10:35 UTC):

Since Tuesday's deploy (v2025.09.09-2) the order page throws intermittent 500s. Stack trace and a
log excerpt from this morning are attached. It comes and goes: reloading the page a minute later
usually works.

Tuesday's deploy contained two changes:

1. `render: show the loyalty tier badge next to the customer name` (touches `renderOrder.ts`)
2. `orders: fail fast on slow lookups, timeout 3000ms -> 800ms` (touches `orderService.ts`)

My guess is that some customers have no loyalty tier yet and change 1 blows up on them. I have a
revert of change 1 ready. Can you confirm that is the cause before I ship the revert?

## Stack trace

```
TypeError: Cannot read properties of undefined (reading 'customer')
    at renderOrder (file:///srv/app/src/render/renderOrder.ts:13:33)
    at async handleOrderPage (file:///srv/app/src/http/routes.ts:41:16)
    at async Server.<anonymous> (file:///srv/app/src/http/server.ts:22:5)
```

## Log excerpt (order service, one instance)

```
2025-09-11T10:13:58.412Z INFO  req=8f21 GET /orders/4417 200 41ms
2025-09-11T10:14:01.120Z INFO  req=8f25 GET /orders/5120 200 38ms
2025-09-11T10:14:02.951Z WARN  req=8f2a order 4417 lookup: timeout after 800ms
2025-09-11T10:14:02.953Z ERROR req=8f2a GET /orders/4417 500 803ms TypeError: Cannot read properties of undefined (reading 'customer')
2025-09-11T10:14:03.394Z INFO  db slow query 1243ms: SELECT o.*, c.name, c.loyalty_tier, i.* FROM orders o ... [4417]
2025-09-11T10:14:09.774Z ERROR req=8f31 GET /orders/4417 500 1ms TypeError: Cannot read properties of undefined (reading 'customer')
2025-09-11T10:14:15.002Z INFO  req=8f33 GET /orders/5120 200 1ms
2025-09-11T10:14:27.619Z ERROR req=8f3c GET /orders/4417 500 1ms TypeError: Cannot read properties of undefined (reading 'customer')
2025-09-11T10:14:44.200Z INFO  req=8f40 GET /orders/3302 200 44ms
2025-09-11T10:14:58.090Z ERROR req=8f47 GET /orders/4417 500 1ms TypeError: Cannot read properties of undefined (reading 'customer')
2025-09-11T10:15:01.700Z ERROR req=8f49 GET /orders/4417 500 0ms TypeError: Cannot read properties of undefined (reading 'customer')
2025-09-11T10:15:03.480Z INFO  req=8f4b GET /orders/4417 200 47ms
2025-09-11T10:15:20.115Z INFO  req=8f52 GET /orders/4417 200 1ms
2025-09-11T10:16:11.830Z INFO  req=8f60 GET /orders/3302 200 39ms
2025-09-11T10:18:47.266Z INFO  req=8f7e GET /orders/5120 200 43ms
2025-09-11T10:21:39.512Z INFO  nightly-export: batch 14/40 started (heavy read load on orders)
2025-09-11T10:21:40.301Z WARN  req=8fa3 order 5120 lookup: timeout after 800ms
2025-09-11T10:21:40.302Z ERROR req=8fa3 GET /orders/5120 500 802ms TypeError: Cannot read properties of undefined (reading 'customer')
2025-09-11T10:21:40.655Z INFO  db slow query 1151ms: SELECT o.*, c.name, c.loyalty_tier, i.* FROM orders o ... [5120]
2025-09-11T10:21:52.040Z ERROR req=8fa9 GET /orders/5120 500 1ms TypeError: Cannot read properties of undefined (reading 'customer')
2025-09-11T10:22:05.377Z INFO  req=8fb0 GET /orders/4417 200 40ms
2025-09-11T10:22:18.903Z ERROR req=8fb6 GET /orders/5120 500 0ms TypeError: Cannot read properties of undefined (reading 'customer')
2025-09-11T10:22:31.125Z INFO  req=8fba GET /orders/9001 404 37ms NotFoundError: order 9001
2025-09-11T10:22:38.480Z ERROR req=8fc1 GET /orders/5120 500 1ms TypeError: Cannot read properties of undefined (reading 'customer')
2025-09-11T10:22:41.012Z INFO  req=8fc4 GET /orders/5120 200 45ms
2025-09-11T10:23:02.558Z INFO  req=8fcf GET /orders/5120 200 1ms
2025-09-11T10:24:10.301Z INFO  req=8fe2 GET /orders/4417 200 42ms
2025-09-11T10:26:55.774Z INFO  nightly-export: batch 14/40 finished
2025-09-11T10:27:30.090Z INFO  req=9004 GET /orders/3302 200 41ms
2025-09-11T10:29:12.640Z INFO  req=9013 GET /orders/5120 200 44ms
```

## Source files

Each line starts with its line number.

### `src/render/renderOrder.ts`

```
  1  import { escapeHtml } from "../lib/html.ts";
  2  import { formatMoney } from "../lib/money.ts";
  3  import { getOrder } from "../orders/orderService.ts";
  4  import type { LoyaltyTier } from "../orders/types.ts";
  5  
  6  function tierBadge(tier: LoyaltyTier | undefined): string {
  7    return tier ? ` <span class="tier tier-${tier}">${tier}</span>` : "";
  8  }
  9  
 10  /** Render the HTML fragment for the order page. */
 11  export async function renderOrder(id: number): Promise<string> {
 12    const order = await getOrder(id);
 13    const badge = tierBadge(order.customer.loyaltyTier);
 14    const header = `<h1>Order ${order.id} for ${escapeHtml(order.customer.name)}${badge}</h1>`;
 15  
 16    const rows = order.items.map((item) => {
 17      const total = formatMoney(item.quantity * item.unitPriceCents, order.currency);
 18      return `<tr><td>${escapeHtml(item.title)}</td><td>${item.quantity}</td><td>${total}</td></tr>`;
 19    });
 20  
 21    const footer = `<p class="total">Total: ${formatMoney(order.totalCents, order.currency)}</p>`;
 22    return [header, "<table>", ...rows, "</table>", footer].join("\n");
 23  }
```

### `src/orders/orderService.ts`

```
  1  import { getOrSet, invalidate } from "../lib/cache.ts";
  2  import { db } from "../lib/db.ts";
  3  import { NotFoundError } from "../lib/errors.ts";
  4  import { withTimeout } from "../lib/withTimeout.ts";
  5  import { toOrder } from "./mapping.ts";
  6  import type { Order } from "./types.ts";
  7  
  8  const ORDER_TTL_MS = 60_000;
  9  const LOOKUP_TIMEOUT_MS = 800;
 10  
 11  async function fetchOrder(id: number): Promise<Order> {
 12    const rows = await db.query(
 13      "SELECT o.*, c.name, c.loyalty_tier, i.* FROM orders o" +
 14        " JOIN customers c ON c.id = o.customer_id" +
 15        " JOIN order_items i ON i.order_id = o.id WHERE o.id = $1",
 16      [id],
 17    );
 18    if (rows.length === 0) throw new NotFoundError(`order ${id}`);
 19    return toOrder(rows);
 20  }
 21  
 22  /** Load an order, cached for a minute because the order page is refreshed a lot. */
 23  export function getOrder(id: number): Promise<Order> {
 24    return getOrSet(`order:${id}`, ORDER_TTL_MS, () =>
 25      withTimeout(fetchOrder(id), LOOKUP_TIMEOUT_MS, `order ${id} lookup`),
 26    ) as Promise<Order>;
 27  }
 28  
 29  /** Called by the checkout flow after an order is changed. */
 30  export function orderChanged(id: number): void {
 31    invalidate(`order:${id}`);
 32  }
```

### `src/lib/cache.ts`

```
  1  type Entry = { value: unknown; expiresAt: number };
  2  
  3  const store = new Map<string, Entry>();
  4  
  5  /** Return the cached value for `key`, or run `loader`, cache its result for `ttlMs`, and return it. */
  6  export async function getOrSet<T>(key: string, ttlMs: number, loader: () => Promise<T>): Promise<T> {
  7    const now = Date.now();
  8    const hit = store.get(key);
  9    if (hit && hit.expiresAt > now) {
 10      return hit.value as T;
 11    }
 12    const value = await loader();
 13    store.set(key, { value, expiresAt: now + ttlMs });
 14    return value;
 15  }
 16  
 17  export function invalidate(key: string): void {
 18    store.delete(key);
 19  }
 20  
 21  export function size(): number {
 22    return store.size;
 23  }
```

### `src/lib/withTimeout.ts`

```
  1  import { logger } from "./logger.ts";
  2  
  3  /** Wait for `promise`, but give up after `ms` milliseconds. */
  4  export function withTimeout<T>(promise: Promise<T>, ms: number, label = "operation"): Promise<T | undefined> {
  5    return new Promise((resolve, reject) => {
  6      const timer = setTimeout(() => {
  7        logger.warn(`${label}: timeout after ${ms}ms`);
  8        resolve(undefined);
  9      }, ms);
 10      promise.then(
 11        (value) => {
 12          clearTimeout(timer);
 13          resolve(value);
 14        },
 15        (error) => {
 16          clearTimeout(timer);
 17          reject(error);
 18        },
 19      );
 20    });
 21  }
```
