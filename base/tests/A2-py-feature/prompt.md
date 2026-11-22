# Ticket TT-58: recurring tasks

The repository in `/work` is `tasktrack`, our command-line task tracker (see `README.md`).

Implement recurring tasks exactly as specified in `docs/SPEC-recurring.md`. That document is the
contract, including the version 2 store file and the error behaviour. Everything the spec does
not change must keep working as it does today.

Also update `README.md` for the new behaviour and add tests for it. Do not edit the existing
tests or the spec.

Run the tests with `python3 -m pytest -q`.
