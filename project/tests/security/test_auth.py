from __future__ import annotations

import http.client
import json
import threading

from skillmerge.app import build_app
from skillmerge.security import host_allowed, origin_allowed, redact


def test_host_and_origin_unit():
    assert host_allowed("127.0.0.1:8765", 8765)
    assert host_allowed("localhost:8765", 8765)
    assert not host_allowed("evil.example:8765", 8765)
    assert origin_allowed("http://127.0.0.1:8765", 8765)
    assert origin_allowed("http://localhost:8765", 8765)
    assert not origin_allowed("http://evil.example:8765", 8765)
    assert "sk-" not in redact("api_key=sk-1234567890")


def _server(tmp_path):
    server = build_app(host="127.0.0.1", preferred_port=0, data_dir=str(tmp_path / "data"), check_pid=False)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _call(server, method, path, body=None, headers=None):
    connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
    connection.request(method, path, body=body, headers=headers or {})
    response = connection.getresponse()
    raw = response.read()
    content_type = response.getheader("Content-Type", "")
    connection.close()
    payload = None
    if raw and "application/json" in content_type:
        payload = json.loads(raw.decode("utf-8"))
    return response, payload


def test_http_security_matrix(tmp_path):
    server, thread = _server(tmp_path)
    token = server.token.value
    try:
        response, _ = _call(server, "GET", "/")
        assert response.status == 200
        assert "sms_session" in (response.getheader("Set-Cookie") or "")

        response, payload = _call(server, "GET", "/api/health")
        assert response.status == 401
        assert payload["error"]["code"] == "UNAUTHENTICATED"

        response, payload = _call(server, "GET", "/api/health", headers={"X-Skillmerge-Token": token})
        assert response.status == 200
        assert payload["data"]["ok"] is True

        base = {"Content-Type": "application/json", "X-Skillmerge-Token": token, "Origin": "http://127.0.0.1:%d" % server.server_address[1]}
        response, payload = _call(server, "POST", "/api/scan", body="{}", headers=base)
        assert response.status == 400
        assert payload["error"]["code"] == "MISSING_CSRF_HEADER"

        headers = dict(base)
        headers["X-Skillmerge"] = "1"
        headers["Origin"] = "http://evil.example"
        response, payload = _call(server, "POST", "/api/scan", body="{}", headers=headers)
        assert response.status == 403
        assert payload["error"]["code"] == "ORIGIN_FORBIDDEN"
        assert response.getheader("Access-Control-Allow-Origin") is None

        headers = dict(base)
        headers["X-Skillmerge"] = "1"
        headers["Content-Length"] = "6000000"
        response, payload = _call(server, "POST", "/api/scan", headers=headers)
        assert response.status == 413

        response, payload = _call(server, "GET", "/", headers={"Host": "evil.example"})
        assert response.status == 403
    finally:
        server.shutdown()
        server.server_close()
        server.ctx.jobs.shutdown()
        server.ctx.db.close_all()
        thread.join(timeout=3)