.PHONY: nightly clean

# What cron runs on batch-01 every night (see RUNBOOK.md).
nightly:
	bash bin/nightly.sh

# Local development only: forget all job state.
clean:
	rm -rf var out
