from __future__ import annotations

import http.client
import json
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
    token = server.token.value
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    connection.request(
        "POST",
        "/api/scan",
        body=json.dumps({"roots": [str(root)], "depth": 5}),
        headers={
            "Content-Type": "application/json",
            "X-Skillmerge": "1",
            "X-Skillmerge-Token": token,
            "Origin": f"http://127.0.0.1:{port}",
        },
    )
    payload = json.loads(connection.getresponse().read().decode("utf-8"))
    connection.close()
    assert payload["ok"] is True
    return payload["data"]["job_id"]


def _stream(server, job_id, last_event_id=""):
    port = server.server_address[1]
    headers = {"X-Skillmerge-Token": server.token.value}
    if last_event_id:
        headers["Last-Event-ID"] = str(last_event_id)
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=25)
    connection.request("GET", f"/api/jobs/{job_id}/events", headers=headers)
    response = connection.getresponse()
    content_type = response.getheader("Content-Type", "")
    raw = response.read().decode("utf-8", "replace")
    connection.close()
    return response.status, content_type, raw


def test_sse_stream_delivers_progress_and_done(tmp_path):
    root = tmp_path / "skills"
    write_skill(root, "alpha", "alpha", "demo", "# Alpha\n\n## 流程\n\n步骤")
    server, thread = _server(tmp_path)
    try:
        job_id = _submit_scan(server, root)
        status, content_type, text = _stream(server, job_id)
        assert status == 200
        assert content_type.startswith("text/event-stream")
        assert "data:" in text
        assert "event: done" in text

        ids = [int(value) for value in re.findall(r"^id: (\d+)$", text, re.M)]
        assert ids
        assert ids == sorted(ids)
        assert len(ids) == len(set(ids))

        status, _content_type, resumed = _stream(server, job_id, ids[0])
        assert status == 200
        assert "event: done" in resumed
        resumed_ids = [int(value) for value in re.findall(r"^id: (\d+)$", resumed, re.M)]
        if resumed_ids:
            assert min(resumed_ids) > ids[0]
    finally:
        server.shutdown()
        server.server_close()
        server.ctx.jobs.shutdown()
        server.ctx.db.close_all()
        thread.join(timeout=3)


def test_sse_unknown_job_returns_404(tmp_path):
    server, thread = _server(tmp_path)
    try:
        port = server.server_address[1]
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        connection.request(
            "GET",
            "/api/jobs/missing/events",
            headers={"X-Skillmerge-Token": server.token.value},
        )
        response = connection.getresponse()
        body = response.read().decode("utf-8")
        connection.close()
        assert response.status == 404
        assert "NOT_FOUND" in body
    finally:
        server.shutdown()
        server.server_close()
        server.ctx.jobs.shutdown()
        server.ctx.db.close_all()
        thread.join(timeout=3)