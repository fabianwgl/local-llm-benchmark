"""Handlers for /v1/jobs."""
from tessera.api.http import Response
from tessera.errors import ValidationError
from tessera.models import JobSpec
from tessera.payload import prepare_payload

MAX_PAGE = 500


def create_job(req, ctx):
    spec = JobSpec.from_dict(req.json(), ctx.config.jobs.default_queue)
    stored = prepare_payload(spec.payload, ctx.config.jobs, ctx.store)
    job = ctx.store.insert_job(spec, stored)
    return Response.json(201, job.to_dict())


def list_jobs(req, ctx):
    limit = _limit(req)
    jobs = ctx.store.list_jobs(state=req.query.get("state"), queue=req.query.get("queue"),
                               limit=limit, after=req.query.get("after"))
    cursor = jobs[-1].id if len(jobs) == limit else None
    return Response.json(200, {"items": [job.to_dict() for job in jobs], "next": cursor})


def get_job(req, ctx):
    return Response.json(200, ctx.store.get_job(req.params["job_id"]).to_dict())


def cancel_job(req, ctx):
    job = ctx.dispatcher.cancel(req.params["job_id"], actor(req))
    return Response.json(200, job.to_dict())


def pause_job(req, ctx):
    job = ctx.dispatcher.pause(req.params["job_id"], actor(req))
    return Response.json(200, job.to_dict())


def resume_job(req, ctx):
    job = ctx.dispatcher.resume(req.params["job_id"], actor(req))
    return Response.json(200, job.to_dict())


def requeue_job(req, ctx):
    job = ctx.dispatcher.revive(req.params["job_id"], actor(req))
    return Response.json(200, job.to_dict())


def actor(req):
    return "api:" + (req.header("X-Tessera-Client") or "anonymous")


def _limit(req):
    raw = req.query.get("limit", "100")
    try:
        limit = int(raw)
    except ValueError:
        raise ValidationError("'limit' must be an integer") from None
    if not 1 <= limit <= MAX_PAGE:
        raise ValidationError("'limit' must be between 1 and %d" % MAX_PAGE)
    return limit
