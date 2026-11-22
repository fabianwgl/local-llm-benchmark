"""Handlers for runs."""
from tessera.api.http import Response
from tessera.api.jobs import actor
from tessera.util.timeutil import utcnow


def list_runs(req, ctx):
    job_id = req.params["job_id"]
    ctx.store.get_job(job_id)
    return Response.json(200, {"items": [run.to_dict() for run in ctx.store.list_runs(job_id)]})


def start_run(req, ctx):
    job = ctx.dispatcher.run_now(req.params["job_id"], actor(req), utcnow())
    return Response.json(202, job.to_dict())


def get_run(req, ctx):
    return Response.json(200, ctx.store.get_run(req.params["run_id"]).to_dict())


def get_run_output(req, ctx):
    run = ctx.store.get_run(req.params["run_id"])
    if run.output is None:
        return Response.empty(204)
    return Response(200, run.output.encode("utf-8"), {"Content-Type": "application/json"})
