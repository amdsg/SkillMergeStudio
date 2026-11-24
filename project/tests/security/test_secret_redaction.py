from __future__ import annotations

import http.client
import json
import threading

from skillmerge.app import build_app
from skillmerge.util.logging import redact

SECRET = "sk-test-secret-1234567890"


def test_redact_covers_common_shapes():
    assert SECRET not in redact(f"api_key={SECRET}")
    assert SECRET not in redact(f"Authorization: Bearer {SECRET}")
    assert SECRET not in redact(f'{{"api_key": "{SECRET}"}}')
    assert SECRET not in redact(f"X-Skillmerge-Token: {SECRET}")


def _server(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "config.json").write_text(
        json.dumps(
            {
                "ai": {
                    "enabled": True,
                    "base_url": "http://127.0.0.1:9/v1",
                    "model": "demo",
                    "api_key": SECRET,
                }
            }
        ),
        encoding="utf-8",
    )
    server = build_app(host="127.0.0.1", preferred_port=0, data_dir=str(data_dir), check_pid=False)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _get(server, path, headers=None):
    port = server.server_address[1]
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    connection.request("GET", path, headers=headers or {})
    response = connection.getresponse()
    raw = response.read().decode("utf-8", "replace")
    connection.close()
    return response.status, raw


def test_responses_never_expose_plaintext_key(tmp_path):
    server, thread = _server(tmp_path)
    token = server.token.value
    headers = {"X-Skillmerge-Token": token}
    try:
        status, body = _get(server, "/api/config", headers)
        assert status == 200
        assert SECRET not in body
        payload = json.loads(body)["data"]
        assert payload["ai"]["api_key_set"] is True

        for path in ("/api/health", "/api/platforms", "/api/skills", "/api/history", "/api/categories"):
            status, body = _get(server, path, headers)
            assert status == 200
            assert SECRET not in body

        port = server.server_address[1]
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        connection.request(
            "POST",
            "/api/ai/test",
            body="{}",
            headers={
                "Content-Type": "application/json",
                "X-Skillmerge": "1",
                "X-Skillmerge-Token": token,
                "Origin": f"http://127.0.0.1:{port}",
            },
        )
        response = connection.getresponse()
        body = response.read().decode("utf-8", "replace")
        connection.close()
        assert response.status == 200
        assert SECRET not in body
        assert json.loads(body)["data"]["reachable"] is False
    finally:
        server.shutdown()
        server.server_close()
        server.ctx.jobs.shutdown()
        server.ctx.db.close_all()
        thread.join(timeout=3)