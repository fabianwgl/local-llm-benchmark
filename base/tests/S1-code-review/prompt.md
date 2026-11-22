You are reviewing pull request #482, "Password reset flow with rate limiting", for a Python web service backed by PostgreSQL.

Below are the files the PR adds or changes, followed by two existing files for context. Every line starts with its line number in the new version of the file. Lines added by the PR are marked `+`; lines without a mark are unchanged.

{{include:input/pr.md}}

## Your task

Review the PR for defects that matter: security vulnerabilities, bugs, data-loss risks, and race conditions. Do not report style preferences.

Reply with one JSON object in a fenced `json` block and nothing after it, in this shape:

```json
{"findings": [{"file": "path/to/file", "line": 0, "severity": "critical | high | medium | low", "issue": "what is wrong and why it matters", "fix": "the concrete change you would ask for"}]}
```

Rules:
- At most 12 findings, ordered from most to least severe.
- `line` is the number printed at the start of the offending line.
- Report only problems you are confident are real. Incorrect findings count against the review.
