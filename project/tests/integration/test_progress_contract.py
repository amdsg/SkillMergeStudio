from __future__ import annotations

import http.client
import json
import os
import re
import threading

from skillmerge.app import build_app
from tests.helpers import write_skill


def _server(tmp_path):
    server = build_app(host="127.0.0.1", preferred_port=0, data_dir=str(tmp_path / "data"), check_pid=False)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _submit_scan(server, root):
    port = server.server_address[1]
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    connection.request(
        "POST",
        "/api/scan",
        body=json.dumps({"roots": [str(root)], "depth": 5}),
        headers={
            "Content-Type": "application/json",
            "X-Skillmerge": "1",
            "X-Skillmerge-Token": server.token.value,
            "Origin": f"http://127.0.0.1:{port}",
        },
    )
    payload = json.loads(connection.getresponse().read().decode("utf-8"))
    connection.close()
    assert payload["ok"] is True
    return payload["data"]["job_id"]


def _stream(server, job_id):
    connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=30)
    connection.request(
        "GET",
        f"/api/jobs/{job_id}/events",
        headers={"X-Skillmerge-Token": server.token.value},
    )
    response = connection.getresponse()
    content_type = response.getheader("Content-Type", "")
    raw = response.read().decode("utf-8", "replace")
    connection.close()
    return response.status, content_type, raw


def _events(raw):
    result = []
    for block in raw.split("\n\n"):
        seq = None
        data = None
        event = ""
        for line in block.splitlines():
            if line.startswith("id: "):
                try:
                    seq = int(line[4:].strip())
                except ValueError:
                    seq = None
            elif line.startswith("data: "):
                try:
                    data = json.loads(line[6:])
                except ValueError:
                    data = None
            elif line.startswith("event: "):
                event = line[7:].strip()
        if data is not None:
            result.append({"seq": seq, "data": data, "event": event})
    return result


def test_scan_progress_contract(tmp_path):
    root = tmp_path / "skills"
    write_skill(root, "alpha", "alpha", "demo", "## 流程\n\n步骤一：读取。")
    write_skill(root, "beta", "beta", "demo b", "## 流程\n\n步骤二：写出。")
    server, thread = _server(tmp_path)
    try:
        job_id = _submit_scan(server, root)
        status, content_type, raw = _stream(server, job_id)
        assert status == 200
        assert content_type.startswith("text/event-stream")
        events = _events(raw)
        assert events
        phases = [item["data"].get("phase") for item in events]
        assert "walk" in phases
        assert "parse" in phases
        assert "write" in phases

        walk = [item["data"] for item in events if item["data"].get("phase") == "walk"]
        assert walk
        assert any(int(item.get("total") or 0) == 0 for item in walk)

        for phase in ("parse", "write"):
            frames = [item["data"] for item in events if item["data"].get("phase") == phase]
            assert frames
            assert all(int(item.get("total") or 0) > 0 for item in frames)
            currents = [int(item.get("current") or 0) for item in frames]
            assert currents == sorted(currents)

        seqs = [item["seq"] for item in events if item["seq"] is not None]
        assert seqs
        assert seqs == sorted(seqs)
        assert len(seqs) == len(set(seqs))

        final = [item["data"] for item in events if item["data"].get("phase") == "succeeded"]
        assert final
        assert int(final[-1].get("current")) == 1
        assert int(final[-1].get("total")) == 1

        jobs = server.ctx.job_store.as_dict(server.ctx.job_store.require(job_id))
        assert jobs["status"] == "succeeded"
        assert jobs["progress"]
        assert {"phase", "current", "total"}.issubset(jobs["progress"].keys())
    finally:
        server.shutdown()
        server.server_close()
        server.ctx.jobs.shutdown()
        server.ctx.db.close_all()
        thread.join(timeout=3)


def test_empty_scan_has_no_determinate_frames(tmp_path):
    root = tmp_path / "empty"
    os.makedirs(root, exist_ok=True)
    server, thread = _server(tmp_path)
    try:
        job_id = _submit_scan(server, root)
        status, _content_type, raw = _stream(server, job_id)
        assert status == 200
        events = _events(raw)
        phases = {item["data"].get("phase") for item in events}
        assert "walk" in phases
        assert "parse" not in phases
        assert "write" not in phases
        assert any(item["data"].get("phase") == "succeeded" for item in events)
    finally:
        server.shutdown()
        server.server_close()
        server.ctx.jobs.shutdown()
        server.ctx.db.close_all()
        thread.join(timeout=3)