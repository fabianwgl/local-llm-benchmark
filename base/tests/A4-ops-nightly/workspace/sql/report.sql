-- Daily paid revenue per sales channel. bin/nightly.sh writes the result to out/report.csv.
-- Columns, filter and order: RUNBOOK.md, section "3. Report".

SELECT o.ordered_on                                       AS day,
       o.channel                                          AS channel,
       COUNT(DISTINCT o.order_id)                         AS orders,
       SUM(i.qty)                                         AS items,
       SUM(i.qty * i.unit_price_cents + o.shipping_cents) AS revenue_cents
FROM orders o
JOIN order_items i ON i.order_id = o.order_id
WHERE o.status = 'paid'
GROUP BY o.ordered_on, o.channel
ORDER BY day, channel;
