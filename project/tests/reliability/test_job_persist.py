from __future__ import annotations

from skillmerge.jobs.job_store import JobStore
from skillmerge.storage.db import Database
from skillmerge.storage.repos.jobs_repo import JobsRepo


def _store(tmp_path):
    db = Database(str(tmp_path / "index.db"))
    db.initialize()
    return JobStore(JobsRepo(db)), db


def test_running_becomes_failed_on_restart(tmp_path):
    store, db = _store(tmp_path)
    job = store.create("scan", {"roots": []})
    store.mark_running(job.id)
    assert store.get(job.id).status == "running"
    assert store.recover_startup() >= 1
    restored = store.get(job.id)
    assert restored.status == "failed"
    assert restored.finished_at
    assert "JOB_INTERRUPTED" in restored.error_json
    db.close_all()


def test_terminal_job_survives_restart(tmp_path):
    store, db = _store(tmp_path)
    job = store.create("scan", {"roots": ["D:/demo"]})
    store.mark_running(job.id)
    store.finish(job.id, "succeeded", result={"counts": {"found": 3}})
    db.close_all()

    db2 = Database(str(tmp_path / "index.db"))
    db2.initialize()
    store2 = JobStore(JobsRepo(db2))
    restored = store2.get(job.id)
    assert restored.status == "succeeded"
    assert restored.result()["counts"]["found"] == 3
    assert restored.params()["roots"] == ["D:/demo"]
    db2.close_all()


def test_queued_is_not_auto_executed_on_restart(tmp_path):
    store, db = _store(tmp_path)
    job = store.create("classify", {})
    assert store.recover_startup() == 0
    assert store.get(job.id).status == "queued"
    db.close_all()


def test_event_cleanup_removes_old_rows(tmp_path):
    store, db = _store(tmp_path)
    job = store.create("scan", {})
    repo = store.repo
    from skillmerge.storage.models import JobEvent

    repo.add_event(JobEvent(job_id=job.id, seq=1, phase="scan", current=1, total=2, message="x", created_at="2000-01-01T00:00:00Z"))
    repo.add_event(JobEvent(job_id=job.id, seq=2, phase="scan", current=2, total=2, message="y", created_at="2999-01-01T00:00:00Z"))
    assert repo.cleanup_events("2100-01-01T00:00:00Z") >= 1
    remaining = repo.events_since(job.id, 0)
    assert len(remaining) == 1
    db.close_all()