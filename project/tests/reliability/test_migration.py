from __future__ import annotations

import os

from skillmerge.storage.db import Database


def test_fresh_database_has_seven_tables(tmp_path):
    db = Database(str(tmp_path / "index.db"))
    db.initialize()
    assert db.user_version() == 3
    rows = db.query_all("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    names = {str(row["name"]) for row in rows}
    expected = {"skills", "skill_locations", "scans", "jobs", "job_events", "artifacts", "merge_sources"}
    assert expected.issubset(names)
    db.close_all()


def test_reopen_is_idempotent(tmp_path):
    path = str(tmp_path / "index.db")
    first = Database(path)
    first.initialize()
    first.close_all()
    second = Database(path)
    second.initialize()
    assert second.user_version() == 3
    second.close_all()
    assert os.path.isfile(path)


def test_foreign_key_cascade(tmp_path):
    db = Database(str(tmp_path / "index.db"))
    db.initialize()
    with db.write_tx() as conn:
        conn.execute(
            "INSERT INTO jobs (id,type,status,params_json,created_at) VALUES ('j1','scan','queued','{}','2026-01-01T00:00:00.000Z')"
        )
        conn.execute(
            "INSERT INTO job_events (job_id,seq,phase,current,message,created_at) VALUES ('j1',1,'start',0,'','2026-01-01T00:00:00.000Z')"
        )
    with db.write_tx() as conn:
        conn.execute("DELETE FROM jobs WHERE id='j1'")
    assert db.scalar("SELECT COUNT(*) FROM job_events") == 0
    db.close_all()