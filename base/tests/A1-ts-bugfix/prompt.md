# Ticket SUP-3312: invoice amounts are off by a cent

Forwarded by support from the finance team of a customer:

> We reconcile your invoices against our ledger and keep finding one-cent differences.
>
> 1. Invoice INV-2291 has three lines of 1 x 0.99 EUR at 19% VAT. The subtotal is 2.97 EUR, so the VAT
>    should be 0.56 EUR (2.97 x 0.19 = 0.5643). Your system shows 0.57 EUR.
> 2. When we split a payment across cost centres, the parts do not always add up to the amount we paid.
>    Splitting 100.00 EUR three ways gave us 99.99 EUR in total.
> 3. Credit notes are sometimes one cent smaller than the invoice they reverse.

The repository in `/work` is `invoice-kit`, the library that does this maths. Its intended behaviour is
documented in `README.md` under "Rounding rules".

Find and fix the causes of all three reports, keep the public API unchanged, and add regression tests.

Run the tests with `npm test` and the type check with `npm run typecheck`.
