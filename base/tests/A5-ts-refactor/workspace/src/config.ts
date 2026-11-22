// Shop-wide settings. Values here are product decisions; change them only with a ticket.

export const CURRENCY = "EUR";

/** Orders at or above this value ship for free (where free shipping is offered at all). */
export const FREE_SHIPPING_THRESHOLD_CENTS = 7500;

/** A quote stays valid for this many days unless the request asks for something else. */
export const QUOTE_VALIDITY_DAYS = 30;
export const MAX_QUOTE_VALIDITY_DAYS = 90;

/** Invoices are due this many days after the issue date. */
export const PAYMENT_TERMS_DAYS = 14;

/** Upper bound on lines per request, to keep responses small. */
export const MAX_LINES = 100;

/** Upper bound on the quantity of one line. Larger orders go through sales. */
export const MAX_QUANTITY = 999;
