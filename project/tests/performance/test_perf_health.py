from __future__ import annotations

import http.client
import threading
import time

import pytest

from skillmerge.app import build_app
from skillmerge.services.scanner.scanner_service import ScanOptions
from tests.helpers import write_skill

pytestmark = pytest.mark.perf


def _health(server):
    port = server.server_address[1]
    started = time.perf_counter()
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    connection.request("GET", "/api/health", headers={"X-Skillmerge-Token": server.token.value})
    response = connection.getresponse()
    body = response.read()
    connection.close()
    return response.status, body, time.perf_counter() - started


def test_health_stays_fast_during_scan(tmp_path):
    root = tmp_path / "skills"
    for index in range(400):
        write_skill(root, f"s{index:04d}", f"skill-{index:04d}", "demo", f"# Skill {index}\n\n## 流程\n\n步骤 {index}")
    server = build_app(host="127.0.0.1", preferred_port=0, data_dir=str(tmp_path / "data"), check_pid=False)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = {}

        def run_scan():
            result["scan"] = server.ctx.scanner.scan(
                options=ScanOptions(roots=[str(root)], depth=5, limit=4000)
            )

        worker = threading.Thread(target=run_scan)
        worker.start()
        slowest = 0.0
        for _ in range(20):
            status, body, elapsed = _health(server)
            assert status == 200
            assert b'"ok":true' in body
            slowest = max(slowest, elapsed)
        worker.join(timeout=120)
        assert not worker.is_alive()
        assert result["scan"]["stats"]["found"] >= 1
        assert slowest < 2.0, f"slowest health={slowest:.3f}s"
    finally:
        server.shutdown()
        server.server_close()
        server.ctx.jobs.shutdown()
        server.ctx.db.close_all()
        thread.join(timeout=3)