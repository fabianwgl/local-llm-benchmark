You are a senior engineer on a billing team. Your team lead has asked for a short decision memo.

## The problem

The nightly job `invoice-run` creates the invoices for all customers and e-mails them. It takes about 40 minutes and must take effect exactly once per night. Until now it ran from cron on a single VM, which is being decommissioned. The service now runs as three identical instances on a container platform. All three have the same scheduler configuration, so all three would start the job at 02:00.

Three options are on the table:

1. A PostgreSQL advisory lock: whichever instance gets the lock runs the job.
2. A Redis lock (`SET key value NX PX <ttl>`): whichever instance sets the key runs the job.
3. The platform's managed queue: a scheduled event puts one message on the queue each night, and whichever instance receives it runs the job.

## Facts about our environment

- PostgreSQL 15, one primary and one asynchronous read replica. The application reaches it through PgBouncer in transaction pooling mode. A direct connection to the primary is possible but is not what the application uses today.
- Redis 7 is used purely as a cache: a single node, no persistence, `maxmemory-policy allkeys-lru`, and it is restarted on every deploy.
- The managed queue delivers at least once. Its visibility timeout defaults to 30 seconds and can be set or extended up to 12 hours.
- The platform may stop and replace any instance at any time (deploys, scaling, node maintenance), with 30 seconds' notice.
- The job writes invoices to PostgreSQL and sends e-mails through a provider whose API accepts an idempotency key.

## What to write

A memo of at most 350 words in total, in Markdown, with exactly this structure:

1. The first line starts with `Recommendation:` and states your choice in one sentence.
2. A comparison table with exactly three rows, one per option, and exactly these four columns: `Option`, `What can make it run twice`, `If the runner is killed mid-run`, `Extra work needed`.
3. A short explanation of your reasoning.
4. A section headed `What would change my mind`.

Be specific to this environment. Do not state anything about these technologies that is not true.
