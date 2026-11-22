You are taking over an on-call shift. A colleague left you the note, stack trace, log excerpt, and source files below.

{{include:input/case.md}}

## Your task

Find the root cause of the 500s and answer your colleague. Your answer must cover:

1. **Mechanism**: what exactly goes wrong, step by step, from the trigger to the exception.
2. **Timing**: why the errors come and go the way the log shows.
3. **Fix**: the code change that removes the cause.
4. **The proposed revert**: whether reverting change 1 would fix the problem, and why or why not.
5. **Regression test**: a test (code or precise steps) that fails on the current code and passes with your fix.

End your answer with exactly these two lines, naming the single place you consider the root cause, using a path and line number from the listings above:

```
ROOT_CAUSE_FILE: <path>
ROOT_CAUSE_LINE: <line number>
```
