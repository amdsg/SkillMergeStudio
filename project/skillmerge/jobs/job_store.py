from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from ..storage.models import Job, dumps, loads
from ..storage.repos.jobs_repo import ALLOWED, JobsRepo
from ..util.errors import DomainError
from ..util.timeutil import utc_now_iso

JOB_TYPES = ("scan", "full_scan", "classify", "merge", "export")


class JobStore:
    def __init__(self, repo: JobsRepo) -> None:
        self.repo = repo

    def create(self, job_type: str, params: Dict[str, Any]) -> Job:
        if job_type not in JOB_TYPES:
            raise DomainError("INVALID_ARGUMENT", f"未知任务类型：{job_type}", "使用 scan/full_scan/classify/merge/export")
        job = Job(
            id=uuid.uuid4().hex,
            type=job_type,
            status="queued",
            params_json=dumps(params or {}),
            progress_json="{}",
            created_at=utc_now_iso(),
        )
        self.repo.create(job)
        return job

    def get(self, job_id: str) -> Optional[Job]:
        return self.repo.get(job_id)

    def require(self, job_id: str) -> Job:
        job = self.repo.get(job_id)
        if job is None:
            raise DomainError("NOT_FOUND", f"任务不存在：{job_id}", "刷新任务列表后重试", 404)
        return job

    def _transition(self, job_id: str, status: str, **kwargs) -> None:
        job = self.require(job_id)
        if status not in ALLOWED.get(job.status, set()):
            raise DomainError("JOB_STATE_CONFLICT", f"任务状态 {job.status} 不能变更为 {status}", "任务已结束，请刷新状态", 409)
        self.repo.update_status(job_id, status, kwargs.get("started_at"), kwargs.get("finished_at"))

    def mark_running(self, job_id: str) -> None:
        self._transition(job_id, "running", started_at=utc_now_iso())

    def finish(self, job_id: str, status: str, result: Any = None, error: Any = None) -> None:
        job = self.repo.get(job_id)
        if job is None:
            return
        if status not in ALLOWED.get(job.status, set()):
            if job.status in ("cancelled", "failed", "succeeded"):
                return
            raise DomainError("JOB_STATE_CONFLICT", f"任务状态 {job.status} 不能变更为 {status}", "刷新任务状态", 409)
        self.repo.finish(job_id, status, utc_now_iso(), result, error)

    def update_progress(self, job_id: str, progress: Dict[str, Any]) -> None:
        normalized = {
            "phase": str(progress.get("phase", "")),
            "current": int(progress.get("current", 0) or 0),
            "total": progress.get("total"),
            "message": str(progress.get("message", "")),
        }
        try:
            self.repo.update_progress(job_id, normalized)
        except Exception:
            pass

    def request_cancel(self, job_id: str, reason: str = "user") -> Job:
        job = self.require(job_id)
        if job.status not in ("queued", "running"):
            raise DomainError("JOB_STATE_CONFLICT", "任务已结束，无法取消", "查看任务结果或创建新任务", 409)
        self.repo.request_cancel(job_id, reason)
        if job.status == "queued":
            self.repo.update_status(job_id, "cancelled", finished_at=utc_now_iso())
            job.status = "cancelled"
        return job

    def as_dict(self, job: Job) -> Dict[str, Any]:
        return {
            "id": job.id,
            "type": job.type,
            "status": job.status,
            "params": loads(job.params_json, {}),
            "progress": job.progress(),
            "result": job.result(),
            "error": job.error(),
            "cancel_requested": bool(job.cancel_requested),
            "created_at": job.created_at,
            "started_at": job.started_at,
            "finished_at": job.finished_at,
        }

    def recover_startup(self) -> int:
        return self.repo.recover_startup()