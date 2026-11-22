"""Operator endpoints under /v1/admin."""
from tessera.api import jobs
from tessera.api.http import Response
from tessera.scheduler.backoff import schedule
from tessera.scheduler.retry import RetryPolicy
from tessera.util.timeutil import isoformat


def register(router):
    router.add("GET", "/v1/admin/leader", leader_status)
    router.add("GET", "/v1/admin/dead-letters", list_dead_letters)
    router.add("POST", "/v1/admin/jobs/{job_id}/requeue", jobs.requeue_job)
    router.add("POST", "/v1/admin/drain", drain)
    router.add("GET", "/v1/admin/retry-policies", retry_policies)


def leader_status(req, ctx):
    return Response.json(200, {"node": ctx.node_id, "leader": ctx.elector.is_leader})


def list_dead_letters(req, ctx):
    items = ctx.store.list_dead_letters(limit=200)
    return Response.json(200, {"items": [
        {"job_id": i["job_id"], "reason": i["reason"], "created_at": isoformat(i["created_at"])} for i in items
    ]})


def drain(req, ctx):
    ctx.pool.drain()
    return Response.json(202, {"node": ctx.node_id, "draining": True})


def retry_policies(req, ctx):
    retry = ctx.config.retry
    out = {}
    for name in ["*"] + sorted(retry.policies.as_dict()):
        policy = RetryPolicy.resolve(retry, name)
        out[name] = {
            "max_attempts": policy.max_attempts,
            "delays": schedule(policy.base_delay, policy.multiplier, policy.max_delay, policy.max_attempts),
        }
    return Response.json(200, out)
