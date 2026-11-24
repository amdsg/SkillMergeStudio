from __future__ import annotations

import http.client
import threading
import time

import pytest

from skillmerge.app import build_app
from skillmerge.config import paths
from skillmerge.storage.db import Database
from skillmerge.storage.models import Skill
from skillmerge.storage.repos.skills_repo import SkillsRepo

pytestmark = pytest.mark.perf


def _seed(tmp_path, count=1000):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    db = Database(paths.db_path(str(data_dir)))
    db.initialize()
    repo = SkillsRepo(db)
    skills = [
        Skill(
            id=f"skill{i:05d}",
            path=str(tmp_path / "skills" / f"s{i}" / "SKILL.md"),
            real_path=str(tmp_path / "skills" / f"s{i}"),
            name=f"skill-{i:05d}",
            description="demo skill for p95 measurement",
            category="未分类",
            size_bytes=1024 + i,
            chars=120,
            mtime=1700000000.0 + i,
            content_hash=f"hash{i:05d}",
            quality_score=70,
        )
        for i in range(count)
    ]
    repo.upsert_many(skills)
    db.close_all()
    return data_dir


def _get(server, path):
    port = server.server_address[1]
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    connection.request("GET", path, headers={"X-Skillmerge-Token": server.token.value})
    response = connection.getresponse()
    body = response.read()
    connection.close()
    return response.status, body


def test_list_p95_under_200ms(tmp_path):
    data_dir = _seed(tmp_path, 1000)
    server = build_app(host="127.0.0.1", preferred_port=0, data_dir=str(data_dir), check_pid=False)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        samples = []
        for _ in range(100):
            started = time.perf_counter()
            status, body = _get(server, "/api/skills?limit=100")
            samples.append(time.perf_counter() - started)
            assert status == 200
            assert body
        samples.sort()
        p95 = samples[min(len(samples) - 1, int(len(samples) * 0.95))]
        assert p95 < 0.2, f"p95={p95:.3f}s"

        status, body = _get(server, "/api/skills?limit=100&sort=mtime&category=%E6%9C%AA%E5%88%86%E7%B1%BB")
        assert status == 200
    finally:
        server.shutdown()
        server.server_close()
        server.ctx.jobs.shutdown()
        server.ctx.db.close_all()
        thread.join(timeout=3)