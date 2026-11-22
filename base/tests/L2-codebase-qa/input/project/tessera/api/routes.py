"""Routes of the public API."""
from tessera.api import jobs, runs

ROUTES = [
    ("POST", "/v1/jobs", jobs.create_job),
    ("GET", "/v1/jobs", jobs.list_jobs),
    ("GET", "/v1/jobs/{job_id}", jobs.get_job),
    ("POST", "/v1/jobs/{job_id}/cancel", jobs.cancel_job),
    ("POST", "/v1/jobs/{job_id}/pause", jobs.pause_job),
    ("POST", "/v1/jobs/{job_id}/resume", jobs.resume_job),
    ("GET", "/v1/jobs/{job_id}/runs", runs.list_runs),
    ("POST", "/v1/jobs/{job_id}/runs", runs.start_run),
    ("GET", "/v1/runs/{run_id}", runs.get_run),
]
