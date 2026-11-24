from __future__ import annotations

from ..util.errors import DomainError


def get_job(ctx, request):
    job = ctx.job_store.require(request.params.get("id", ""))
    return 200, ctx.job_store.as_dict(job)


def cancel_job(ctx, request):
    job = ctx.jobs.cancel(request.params.get("id", ""))
    return 200, job


def sse_stub(ctx, request):
    return 204, {}


def list_jobs(ctx, request):
    jobs = ctx.jobs.repo.recent(20)
    return 200, {"items": [ctx.job_store.as_dict(job) for job in jobs]}


def require_job_id(request) -> str:
    job_id = request.params.get("id", "")
    if not job_id:
        raise DomainError("INVALID_ARGUMENT", "缺少任务 id", "请求 /api/jobs/{id}")
    return job_id