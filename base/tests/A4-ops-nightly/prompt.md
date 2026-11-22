# OPS-2187: finance nightly is red and its numbers are wrong

Handover from the outgoing on-call, Wednesday 5 March:

> The finance nightly (the repository in `/work`, deployed to batch-01) has failed every night since
> Tuesday's 02:30 run. The cron output is in `logs/last_failure.log`; I didn't get further than that.
>
> It was wrong before it went red, too. Finance reconciled Sunday's report against the payment
> provider: for 2025-03-01, channel web, they have 3 paid orders and 140.95 EUR. Our report said
> 3 orders and 160.80 EUR (`revenue_cents` 16080). Since then they don't trust any of our numbers.
>
> `RUNBOOK.md` is what the job is supposed to do; finance relies on it.

Fix the job so that it behaves as `RUNBOOK.md` describes, for the exports now in `incoming/` and for
whatever the shop exports next. Don't edit `RUNBOOK.md`, `logs/last_failure.log` or the export files.

`make nightly` runs the job; `make clean` resets local state (`var/` and `out/`).
