You are working with a SQLite database (version 3.40) for an online shop. Write four queries.

## Schema

```sql
{{include:input/schema.sql}}
```

## Sample data

This is a small sample so you can see the shape of the data. Your queries will also be run against a larger database with the same schema.

```sql
{{include:input/sample_data.sql}}
```

## Definitions

- The *revenue* of an order is the sum of `quantity * unit_price_cents` over its order items.
- Only orders with `status = 'paid'` count. Pending and cancelled orders, their items, and their refunds are ignored everywhere.
- The *day* of an order is the date part of `ordered_at` (`'YYYY-MM-DD'`).

## Queries

**Q1. Monthly net revenue for 2025 with a moving average.** Return one row for each of the twelve calendar months of 2025, including months that have no paid orders.
- `month`: `'YYYY-MM'`.
- `net_cents`: revenue of the paid orders placed in that month, minus the refunds on those orders. A refund belongs to the month in which its order was placed, whatever the refund's own date. 0 for a month with no paid orders.
- `moving_avg_cents`: the average of `net_cents` over that month and the two months before it, using only months of 2025 (so January averages one month and February two). Round to the nearest whole cent, halves up, and return an integer.

Order by `month` ascending.

**Q2. Referral networks.** `customers.referred_by` says who referred a customer. For every customer who was not referred by anyone and who has referred at least one other customer, report their *network*: all customers reachable from them by following referrals, at any depth, not counting themselves.
- `root_id`: the id of that customer.
- `network_size`: how many customers are in the network.
- `max_depth`: 1 if the network only has direct referrals, 2 if it includes a referral of a referral, and so on.
- `network_revenue_cents`: the total revenue of the paid orders placed by the customers in the network. The root's own orders do not count. 0 if there are none.

Order by `network_revenue_cents` descending, then `root_id` ascending.

**Q3. Discount against the list price.** A product's *list price on a day* is the `price_cents` of its `price_history` row with the latest `valid_from` on or before that day. For each product sold in at least one paid order, compare what was charged with the list price on the day of each order:
- `product_id`
- `units`: total quantity sold in paid orders.
- `list_value_cents`: the sum, over its paid order items, of `quantity` times the list price on the order's day.
- `charged_cents`: the sum of `quantity * unit_price_cents` over the same items.
- `discount_cents`: `list_value_cents - charged_cents` (negative when the product sold above list).

Return only products whose `discount_cents` is not 0. Order by `discount_cents` descending, then `product_id` ascending.

**Q4. Longest purchase streak.** For each customer with at least one paid order, find their longest run of consecutive days on which they placed at least one paid order.
Columns: `customer_id`, `streak_days` (the length of that run), `streak_start` (its first day, `'YYYY-MM-DD'`; if the customer has several runs of that same length, the earliest one). Order by `streak_days` descending, then `customer_id` ascending.

## Output format

Reply with four fenced `sql` code blocks, in order. Start each block with a comment line `-- Q1`, `-- Q2`, `-- Q3`, `-- Q4`. Each block must contain a single `SELECT` statement (a `WITH` clause, including `WITH RECURSIVE`, is fine). Columns must appear in the order listed above.
