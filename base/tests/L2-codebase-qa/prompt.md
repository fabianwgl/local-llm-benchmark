Below is the complete source of `tessera`, a job scheduler service: a Python package, SQL migrations, YAML configuration and a TypeScript client. Read it and answer eight questions about how it behaves. Answer from the code itself.

{{include:input/codebase.md}}

## Deployment

Unless a question says otherwise, assume this production deployment. Each node is started from the repository root with

```sh
TESSERA_NODE_ID=node-a TESSERA_RETRY_BASE_DELAY=10 TESSERA_RETRY_MAX_DELAY=120 \
  tessera serve --config config/tessera.yaml --max-backoff 4m
```

No other `TESSERA_*` environment variables are set. PyYAML and psycopg2 are installed and the database schema is fully migrated.

## Questions

1. A job's handler raises an ordinary exception and the job will be retried. Which method or function of the tessera code issues the SQL statement that writes this failed attempt into the `job_attempts` table? Answer as `Class.method` (or `module.function` for a module-level function).
2. A job of type `report.render` fails on its third attempt (its handler raises an ordinary exception). How many seconds after that failure is its next attempt scheduled? Answer with a number.
3. Which environment variable, when set to `1`, makes a node skip leader election? Give its exact name.
4. `tessera/worker.py` imports `lease_expiry`. More than one module in the code base defines a function with that name. In which module is the function that `worker.py` actually calls defined? Give the dotted module path.
5. A request handler is a function with the signature `(req, ctx)`. Exactly one of the handlers defined in `tessera/api/jobs.py`, `tessera/api/runs.py` and `tessera/api/admin.py` is never registered with the router. Which one? Answer as `module.function`, for example `jobs.create_job`.
6. One function acquires a job lock (see `tessera/scheduler/locks.py`) and does not release it on one of its error paths. Which one? Answer as `Class.method`.
7. A client sends `POST /v1/jobs` for a job whose payload serialises to 102,400 bytes (the whole request body is about 101 KiB). What happens to the payload? Answer in at most 12 words, naming the exact HTTP status, exception or database table involved.
8. Which method of the TypeScript client sends `POST /v1/jobs/{job_id}/runs`, and what is the exact name of the idempotency header it sends with that request? Answer as `method, Header-Name`.

For questions 2 and 7, also give a short trace of at most 60 words each: the files and functions involved, in order, and the configuration values that decide the answer, with the layer each value comes from.

## Answer format

Answer with one JSON object in a fenced `json` block, in exactly this shape. Give one answer per question and do not list alternatives.

```json
{
  "q1": "Class.method",
  "q2": "a number of seconds",
  "q3": "ENV_VAR_NAME",
  "q4": "dotted.module.path",
  "q5": "module.function",
  "q6": "Class.method",
  "q7": "what happens, at most 12 words",
  "q8": "method, Header-Name",
  "trace_q2": "at most 60 words",
  "trace_q7": "at most 60 words"
}
```
