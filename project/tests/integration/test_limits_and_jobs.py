from __future__ import annotations

import json
import os
import threading
import time

import pytest

from skillmerge.app import build_app
from skillmerge.services.scanner.walker import WalkOptions, walk
from skillmerge.jobs.cancel import CancelToken


def test_walk_limit_and_time_budget(tmp_path):
    root = str(tmp_path / "skills")
    for index in range(12):
        folder = os.path.join(root, f"s{index}")
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "SKILL.md"), "w", encoding="utf-8") as handle:
            handle.write(f"---\nname: s{index}\ndescription: d\n---\n\n# S\n")
    result = walk([{"path": root, "platform": "custom"}], WalkOptions(depth=3, limit=5))
    assert len(result.candidates) == 5
    assert result.accumulator.stats.limit_hit is True
    assert result.accumulator.uncovered_dirs
    timed = walk([{"path": root, "platform": "custom"}], WalkOptions(depth=3, limit=50, time_limit=0))
    assert timed.accumulator.stats.time_limit_hit is True


def test_walk_cancel_token(tmp_path):
    root = str(tmp_path / "skills")
    os.makedirs(root, exist_ok=True)
    token = CancelToken()
    token.set()
    started = time.monotonic()
    result = walk([{"path": root, "platform": "custom"}], WalkOptions(depth=3), cancel_token=token)
    assert result.cancelled is True
    assert time.monotonic() - started < 5


def test_symlink_not_followed(tmp_path):
    root = str(tmp_path / "skills")
    target = os.path.join(root, "real")
    os.makedirs(target, exist_ok=True)
    with open(os.path.join(target, "SKILL.md"), "w", encoding="utf-8") as handle:
        handle.write("---\nname: real\ndescription: d\n---\n\n# R\n")
    link = os.path.join(root, "link")
    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError):
        pytest.skip("当前系统不允许创建符号链接")
    result = walk([{"path": root, "platform": "custom"}], WalkOptions(depth=3))
    paths = [item["path"].replace("\\", "/") for item in result.candidates]
    assert len(paths) == 1
    assert "/real/" in paths[0]
    assert not any("/link/" in path for path in paths)


def _headers(server, token):
    return {
        "Content-Type": "application/json",
        "X-Skillmerge": "1",
        "X-Skillmerge-Token": token,
        "Origin": "http://127.0.0.1:%d" % server.server_address[1],
    }


def test_cancel_and_health_during_long_job(tmp_path):
    import http.client

    server = build_app(host="127.0.0.1", preferred_port=0, data_dir=str(tmp_path / "data"), check_pid=False)

    def slow_scan(**kwargs):
        token = kwargs["cancel_token"]
        for _ in range(200):
            if token.is_set():
                return {"cancelled": True}
            time.sleep(0.02)
        return {"cancelled": False}

    server.ctx.scanner.scan = slow_scan
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    token = server.token.value

    def call(method, path, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
        conn.request(method, path, body=body, headers=_headers(server, token))
        response = conn.getresponse()
        raw = response.read()
        conn.close()
        return response, json.loads(raw.decode("utf-8")) if raw else None

    try:
        response, payload = call("POST", "/api/scan", json.dumps({"roots": [str(tmp_path)]}))
        assert response.status == 202
        job_id = payload["data"]["job_id"]

        for _ in range(20):
            started = time.monotonic()
            response, payload = call("GET", "/api/health")
            elapsed = time.monotonic() - started
            assert response.status == 200
            assert payload["data"]["ok"] is True
            assert elapsed < 2.0

        response, payload = call("POST", f"/api/jobs/{job_id}/cancel", "{}")
        assert response.status == 200

        deadline = time.time() + 5
        status = ""
        while time.time() < deadline:
            response, payload = call("GET", f"/api/jobs/{job_id}")
            status = payload["data"]["status"]
            if status == "cancelled":
                break
            time.sleep(0.1)
        assert status == "cancelled"
    finally:
        server.shutdown()
        server.server_close()
        server.ctx.jobs.shutdown()
        server.ctx.db.close_all()
        thread.join(timeout=3)