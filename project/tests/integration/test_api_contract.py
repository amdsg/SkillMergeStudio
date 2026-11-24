from __future__ import annotations

import http.client
import json
import threading

from skillmerge.app import build_app


def _call(server, path, token):
    connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=10)
    connection.request("GET", path, headers={"X-Skillmerge-Token": token})
    response = connection.getresponse()
    body = response.read()
    connection.close()
    return response, json.loads(body.decode("utf-8")) if body else None


def test_platform_api_contract(tmp_path):
    server = build_app(host="127.0.0.1", preferred_port=0, data_dir=str(tmp_path / "data"), check_pid=False)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    token = server.token.value
    try:
        response, payload = _call(server, "/api/platforms", token)
        assert response.status == 200
        data = payload["data"]
        assert data["counts"]["total"] == 28
        assert data["counts"]["verified"] == 3
        assert data["counts"]["candidate"] == 25
        assert data["counts"]["evidence_total"] == 36
        assert data["page"] == {"limit": 0, "offset": 0, "total": 28}
        assert data["total"] == 28
        assert len(data["items"]) == 28
        assert data["sources"]["discovery_round"] == "2026-11-22"

        response, payload = _call(server, "/api/platforms?verified=false", token)
        assert response.status == 200
        assert payload["data"]["page"]["total"] == 25
        assert all(item["requires_confirm"] for item in payload["data"]["items"])

        response, payload = _call(server, "/api/platforms?kind=prompt", token)
        assert payload["data"]["page"]["total"] == 1
        assert payload["data"]["items"][0]["id"] == "prompt-only"

        response, payload = _call(server, "/api/platforms?group=Claude%20%E7%94%9F%E6%80%81", token)
        assert payload["data"]["page"]["total"] == 1
        assert payload["data"]["items"][0]["id"] == "claude"

        response, payload = _call(server, "/api/platforms?q=claude", token)
        assert payload["data"]["page"]["total"] >= 1
        assert payload["data"]["items"][0]["matched_by"] in ("id", "label")

        response, payload = _call(server, "/api/platforms?limit=5&offset=2", token)
        assert payload["data"]["page"] == {"limit": 5, "offset": 2, "total": 28}
        assert len(payload["data"]["items"]) == 5

        response, payload = _call(server, "/api/platforms/claude", token)
        assert response.status == 200
        assert payload["data"]["platform"]["id"] == "claude"
        assert payload["data"]["platform"]["limits"]["bundle_max_mb"] == 30
        assert payload["data"]["verification"]["latest"] is None

        response, payload = _call(server, "/api/platforms/workbuddy", token)
        assert payload["data"]["platform"]["limits"] is None
        assert payload["data"]["platform"]["legacy_limits_present"] is True
        assert payload["data"]["platform"]["requires_confirm"] is True

        response, payload = _call(server, "/api/platforms?kind=plugin", token)
        assert response.status == 400
        assert payload["error"]["code"] == "INVALID_ARGUMENT"
    finally:
        server.shutdown()
        server.server_close()
        server.ctx.jobs.shutdown()
        server.ctx.db.close_all()
        thread.join(timeout=3)