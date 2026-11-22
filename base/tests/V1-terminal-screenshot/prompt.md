The attached image is a screenshot of a developer's terminal. They tried to start a project's containers and then ran a database migration. Read the screenshot and diagnose what went wrong.

Reply with one JSON object in a fenced `json` block, in exactly this shape:

```json
{
  "failing_container": "the container that failed to start",
  "conflicting_port": 0,
  "holder_process": "the name of the process that is the reason for the failure",
  "holder_pid": 0,
  "exception_file": "the file name in the Python traceback where the developer's own code failed",
  "exception_line": 0,
  "root_cause": "one of: port_conflict, wrong_credentials, image_missing, migration_bug, network_misconfigured",
  "explanation": "in at most 80 words: what happened, in causal order",
  "next_command": "the single shell command you would run next to fix the problem"
}
```

Use only what is visible in the screenshot. Do not guess values that are not shown.
