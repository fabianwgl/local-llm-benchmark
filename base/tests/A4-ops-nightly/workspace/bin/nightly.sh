#!/usr/bin/env bash
# finance-nightly: apply migrations, import the shop's order exports, write the daily revenue report.
# Runs from cron on batch-01 via `make nightly`. RUNBOOK.md describes what it must do.

cd "$(dirname "$0")/.." || exit 1

DB=var/nightly.db
STAGE=var/stage
REPORT=out/report.csv

log() { echo "nightly: $*"; }
die() { echo "nightly: error: $*" >&2; exit 1; }

migrate() {
    for m in migrations/*.sql; do
        log "migration $(basename $m)"
        sqlite3 $DB < $m
    done
}

# Every staged row gets the name of its export appended, so each stored row can be traced back
# to the file it came from (source_file).
stage_rows() {
    awk -v src="$2" 'NR > 1 { print $0 "," src }' $1 > $STAGE/rows.csv
}

load_orders() {
    sqlite3 $DB <<SQL
DROP TABLE IF EXISTS stage_orders;
CREATE TABLE stage_orders (order_id, ordered_on, customer, channel, shipping_cents, status, source_file);
.import --csv $STAGE/rows.csv stage_orders
INSERT INTO orders (order_id, ordered_on, customer, channel, shipping_cents, status, source_file)
SELECT order_id, ordered_on, customer, channel, CAST(shipping_cents AS INTEGER), status, source_file
FROM stage_orders;
DROP TABLE stage_orders;
SQL
}

load_items() {
    sqlite3 $DB <<SQL
DROP TABLE IF EXISTS stage_items;
CREATE TABLE stage_items (order_id, line_no, sku, description, qty, unit_price_cents, source_file);
.import --csv $STAGE/rows.csv stage_items
INSERT INTO order_items (order_id, line_no, sku, description, qty, unit_price_cents, source_file)
SELECT order_id, CAST(line_no AS INTEGER), sku, description, CAST(qty AS INTEGER),
       CAST(unit_price_cents AS INTEGER), source_file
FROM stage_items;
DROP TABLE stage_items;
SQL
}

import_file() {
    local f=$1 name
    name=$(basename $f)
    case $name in
        orders_*.csv) stage_rows $f "$name"; load_orders ;;
        items_*.csv)  stage_rows $f "$name"; load_items ;;
        *) die "unknown input file: $name" ;;
    esac
    log "imported $name"
}

mkdir -p var $STAGE out

migrate

for f in $(ls incoming/*.csv); do
    import_file $f
done

sqlite3 -header -csv $DB < sql/report.sql > $REPORT
log "report written to $REPORT"
