Below is one hour of merged logs from five services (gateway, orders, payments, inventory, db-proxy). During this hour customers could not check out for a while. You are writing the incident analysis.

Every line has the form `<timestamp> <service> <level> <message>`. The gateway logs one line per HTTP response it sends; `req=` is the request id.

```
{{include:input/incident.log}}
```

## Your task

Work out what caused the checkout failures and answer with one JSON object in a fenced `json` block, in exactly this shape:

```json
{
  "root_cause_service": "the service where the causing change happened",
  "change_time": "HH:MM:SS of the log line that records the causing change",
  "config_key": "the setting that was changed",
  "first_symptom_time": "HH:MM:SS of the first WARN or ERROR line that the change caused",
  "fix_time": "HH:MM:SS of the log line that records the change that ended the incident",
  "fix_revision": "the revision that ended the incident",
  "rollback_helped": false,
  "failed_requests": 0,
  "evidence": ["3 to 5 log lines, copied exactly, that prove the causal chain"],
  "red_herrings": ["things in the log that look related to the incident but are not"],
  "explanation": "the causal chain from the change to the customer-facing failures, in at most 150 words"
}
```

- `rollback_helped`: true or false, whether the rollback during the incident stopped the failures.
- `failed_requests`: the number of distinct request ids that received at least one 502 response from the gateway.
- Times are taken from the log, without the date and without milliseconds.
