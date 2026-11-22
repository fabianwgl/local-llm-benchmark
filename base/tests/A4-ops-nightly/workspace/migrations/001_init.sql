-- Initial schema for the finance nightly: the shop's orders and their item rows.

CREATE TABLE IF NOT EXISTS orders (
    order_id       TEXT    NOT NULL,
    ordered_on     TEXT    NOT NULL,   -- YYYY-MM-DD
    customer       TEXT    NOT NULL,
    shipping_cents INTEGER NOT NULL,
    status         TEXT    NOT NULL,   -- paid | pending | cancelled | refunded
    source_file    TEXT    NOT NULL    -- export the row was imported from
);

CREATE TABLE IF NOT EXISTS order_items (
    order_id         TEXT    NOT NULL,
    line_no          INTEGER NOT NULL,
    sku              TEXT    NOT NULL,
    description      TEXT    NOT NULL,
    qty              INTEGER NOT NULL,
    unit_price_cents INTEGER NOT NULL,
    source_file      TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS order_items_by_order ON order_items (order_id);
