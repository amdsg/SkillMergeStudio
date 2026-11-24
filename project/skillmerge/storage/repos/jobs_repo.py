from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..db import Database
from ..models import Job, JobEvent, dumps, loads

ALLOWED = {
    "queued": {"running", "cancelled"},
    "running": {"succeeded", "failed", "cancelled"},
    "succeeded": set(),
    "failed": set(),
    "cancelled": set(),
}


class JobsRepo:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create(self, job: Job) -> None:
        with self.db.write_tx() as conn:
            conn.execute(
                """
                INSERT INTO jobs (id, type, status, params_json, progress_json, result_json, error_json,
                    cancel_requested, cancel_reason, created_at, started_at, finished_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    job.id, job.type, job.status, job.params_json, job.progress_json, job.result_json,
                    job.error_json, job.cancel_requested, job.cancel_reason, job.created_at,
                    job.started_at, job.finished_at,
                ),
            )

    def get(self, job_id: str) -> Optional[Job]:
        row = self.db.query_one("SELECT * FROM jobs WHERE id=?", (job_id,))
        return Job.from_row(row) if row else None

    def update_status(self, job_id: str, status: str, started_at: Optional[str] = None, finished_at: Optional[str] = None) -> None:
        with self.db.write_tx() as conn:
            conn.execute(
                "UPDATE jobs SET status=?, started_at=COALESCE(?, started_at), finished_at=COALESCE(?, finished_at) WHERE id=?",
                (status, started_at, finished_at, job_id),
            )

    def update_progress(self, job_id: str, progress: Dict[str, Any]) -> None:
        with self.db.write_tx() as conn:
            conn.execute("UPDATE jobs SET progress_json=? WHERE id=?", (dumps(progress), job_id))

    def finish(self, job_id: str, status: str, finished_at: str, result: Any = None, error: Any = None) -> None:
        with self.db.write_tx() as conn:
            conn.execute(
                "UPDATE jobs SET status=?, finished_at=?, result_json=?, error_json=? WHERE id=?",
                (status, finished_at, dumps(result) if result is not None else None, dumps(error) if error is not None else None, job_id),
            )

    def request_cancel(self, job_id: str, reason: str = "user") -> None:
        with self.db.write_tx() as conn:
            conn.execute("UPDATE jobs SET cancel_requested=1, cancel_reason=? WHERE id=?", (reason, job_id))

    def active(self) -> List[Job]:
        rows = self.db.query_all("SELECT * FROM jobs WHERE status IN ('queued','running') ORDER BY created_at")
        return [Job.from_row(row) for row in rows]

    def recent(self, limit: int = 20) -> List[Job]:
        rows = self.db.query_all("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (int(limit),))
        return [Job.from_row(row) for row in rows]

    def counts(self) -> Dict[str, int]:
        rows = self.db.query_all("SELECT status, COUNT(*) AS n FROM jobs GROUP BY status")
        result = {"queued": 0, "running": 0}
        for row in rows:
            result[str(row["status"])] = int(row["n"])
        return result

    def add_event(self, event: JobEvent) -> None:
        with self.db.write_tx() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO job_events (job_id, seq, phase, current, total, message, created_at) VALUES (?,?,?,?,?,?,?)",
                (event.job_id, int(event.seq), event.phase, int(event.current), event.total, event.message, event.created_at),
            )

    def events_since(self, job_id: str, seq: int, limit: int = 256) -> List[Dict[str, Any]]:
        rows = self.db.query_all(
            "SELECT * FROM job_events WHERE job_id=? AND seq>? ORDER BY seq ASC LIMIT ?",
            (job_id, int(seq), int(limit)),
        )
        return [dict(row) for row in rows]

    def cleanup_events(self, before: str) -> int:
        with self.db.write_tx() as conn:
            cursor = conn.execute("DELETE FROM job_events WHERE created_at < ?", (before,))
            return cursor.rowcount

    def recover_startup(self) -> int:
        with self.db.write_tx() as conn:
            cursor = conn.execute(
                "UPDATE jobs SET status='failed', finished_at=COALESCE(finished_at, datetime('now')), "
                "error_json=? WHERE status='running'",
                (dumps({"code": "JOB_INTERRUPTED", "message": "进程重启，运行中的任务已终止", "fix": "重新创建任务"}),),
            )
            return cursor.rowcount