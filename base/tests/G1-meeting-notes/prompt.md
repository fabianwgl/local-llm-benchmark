Below is the transcript of a team meeting. Write the meeting notes as one JSON object in a fenced `json` block, in exactly this shape:

```json
{
  "decisions": ["one sentence per decision the team made"],
  "action_items": [{"owner": "first name", "task": "what they committed to do", "due": "YYYY-MM-DD"}],
  "open_questions": ["one sentence per question that was raised and left unresolved"],
  "summary": "at most 120 words"
}
```

Rules:
- Record how the meeting ended. If something was decided and later changed, or a task moved to another person, record only the final state.
- An action item is a task that a named person committed to do. Leave out jokes and things nobody committed to.
- Resolve every date to `YYYY-MM-DD` using the meeting date in the header. Use `null` for `due` only if no date was given.
- Add nothing that is not in the transcript.

## Transcript

{{include:input/transcript.md}}
