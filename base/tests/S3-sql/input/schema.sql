CREATE TABLE customers (
  id           INTEGER PRIMARY KEY,
  name         TEXT NOT NULL,
  email        TEXT NOT NULL UNIQUE,
  country      TEXT NOT NULL,
  created_at   TEXT NOT NULL,             -- 'YYYY-MM-DD'
  referred_by  INTEGER REFERENCES customers(id)   -- the customer who referred this one, or NULL
);

CREATE TABLE categories (
  id    INTEGER PRIMARY KEY,
  name  TEXT NOT NULL UNIQUE
);

CREATE TABLE products (
  id           INTEGER PRIMARY KEY,
  name         TEXT NOT NULL,
  category_id  INTEGER NOT NULL REFERENCES categories(id),
  price_cents  INTEGER NOT NULL           -- today's list price
);

CREATE TABLE price_history (
  product_id   INTEGER NOT NULL REFERENCES products(id),
  valid_from   TEXT NOT NULL,             -- 'YYYY-MM-DD', first day this list price applies
  price_cents  INTEGER NOT NULL,
  PRIMARY KEY (product_id, valid_from)
);

CREATE TABLE orders (
  id           INTEGER PRIMARY KEY,
  customer_id  INTEGER NOT NULL REFERENCES customers(id),
  status       TEXT NOT NULL CHECK (status IN ('pending', 'paid', 'cancelled')),
  ordered_at   TEXT NOT NULL              -- 'YYYY-MM-DD HH:MM:SS', UTC
);

CREATE TABLE order_items (
  id                INTEGER PRIMARY KEY,
  order_id          INTEGER NOT NULL REFERENCES orders(id),
  product_id        INTEGER NOT NULL REFERENCES products(id),
  quantity          INTEGER NOT NULL,
  unit_price_cents  INTEGER NOT NULL      -- price actually charged per unit
);

CREATE TABLE refunds (
  id            INTEGER PRIMARY KEY,
  order_id      INTEGER NOT NULL REFERENCES orders(id),
  amount_cents  INTEGER NOT NULL,
  refunded_at   TEXT NOT NULL             -- 'YYYY-MM-DD HH:MM:SS', UTC
);
