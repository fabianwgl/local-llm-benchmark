import { getOrSet, invalidate } from "../lib/cache.ts";
import { db } from "../lib/db.ts";
import { NotFoundError } from "../lib/errors.ts";
import { withTimeout } from "../lib/withTimeout.ts";
import { toOrder } from "./mapping.ts";
import type { Order } from "./types.ts";

const ORDER_TTL_MS = 60_000;
const LOOKUP_TIMEOUT_MS = 800;

async function fetchOrder(id: number): Promise<Order> {
  const rows = await db.query(
    "SELECT o.*, c.name, c.loyalty_tier, i.* FROM orders o" +
      " JOIN customers c ON c.id = o.customer_id" +
      " JOIN order_items i ON i.order_id = o.id WHERE o.id = $1",
    [id],
  );
  if (rows.length === 0) throw new NotFoundError(`order ${id}`);
  return toOrder(rows);
}

/** Load an order, cached for a minute because the order page is refreshed a lot. */
export function getOrder(id: number): Promise<Order> {
  return getOrSet(`order:${id}`, ORDER_TTL_MS, () =>
    withTimeout(fetchOrder(id), LOOKUP_TIMEOUT_MS, `order ${id} lookup`),
  ) as Promise<Order>;
}

/** Called by the checkout flow after an order is changed. */
export function orderChanged(id: number): void {
  invalidate(`order:${id}`);
}
