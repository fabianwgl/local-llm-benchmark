-- Since March the exports carry the sales channel (web, marketplace, phone); finance reports by channel.

ALTER TABLE orders ADD COLUMN channel TEXT NOT NULL DEFAULT 'web';

CREATE INDEX orders_by_day_channel ON orders (ordered_on, channel);
