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


def test_platform_list_format_contract(tmp_path):
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
        assert len(data["items"]) == 28
        for item in data["items"]:
            assert isinstance(item["format"], dict)
            assert item["format"]["package_type"] in {"dir", "zip", "prompt"}
            assert item["format"]["skill_md_path"]
            assert item["format"]["rule_status"] in {"verified", "candidate"}
        workbuddy = next(item for item in data["items"] if item["id"] == "workbuddy")
        assert workbuddy["limits"] is None
        assert workbuddy["format"]["package_type"] == "zip"
        assert workbuddy["format"]["wrap"] is True
        assert workbuddy["format"]["skill_md_path"] == "skills/<name>/SKILL.md"
        assert workbuddy["format"]["rule_status"] == "candidate"
        assert workbuddy["format"]["install_scopes"] == []
        prompt = next(item for item in data["items"] if item["id"] == "prompt-only")
        assert prompt["format"]["package_type"] == "prompt"
        assert prompt["format"]["skill_md_path"] == "prompt.md"

        response, payload = _call(server, "/api/platforms/workbuddy", token)
        assert response.status == 200
        platform = payload["data"]["platform"]
        assert platform["limits"] is None
        assert platform["format"]["skill_md_path"] == "skills/<name>/SKILL.md"
        assert platform["format"]["requires_confirm"] is True
        assert platform["rule"]["id"] == "workbuddy"

        response, payload = _call(server, "/api/platforms/claude", token)
        platform = payload["data"]["platform"]
        assert platform["format"]["install_scopes"] == ["global", "project"]
        assert platform["format"]["rule_status"] == "verified"
    finally:
        server.shutdown()
        server.server_close()
        server.ctx.jobs.shutdown()
        server.ctx.db.close_all()
        thread.join(timeout=3)