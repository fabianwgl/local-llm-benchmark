import { escapeHtml } from "../lib/html.ts";
import { formatMoney } from "../lib/money.ts";
import { getOrder } from "../orders/orderService.ts";
import type { LoyaltyTier } from "../orders/types.ts";

function tierBadge(tier: LoyaltyTier | undefined): string {
  return tier ? ` <span class="tier tier-${tier}">${tier}</span>` : "";
}

/** Render the HTML fragment for the order page. */
export async function renderOrder(id: number): Promise<string> {
  const order = await getOrder(id);
  const badge = tierBadge(order.customer.loyaltyTier);
  const header = `<h1>Order ${order.id} for ${escapeHtml(order.customer.name)}${badge}</h1>`;

  const rows = order.items.map((item) => {
    const total = formatMoney(item.quantity * item.unitPriceCents, order.currency);
    return `<tr><td>${escapeHtml(item.title)}</td><td>${item.quantity}</td><td>${total}</td></tr>`;
  });

  const footer = `<p class="total">Total: ${formatMoney(order.totalCents, order.currency)}</p>`;
  return [header, "<table>", ...rows, "</table>", footer].join("\n");
}
