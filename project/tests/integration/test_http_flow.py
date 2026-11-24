from __future__ import annotations

import http.client
import json
import os
import threading
import time

from skillmerge.app import build_app

FIXTURES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fixtures")
SKILLS = os.path.join(FIXTURES, "skills")


def _call(server, method, path, body=None, headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=10)
    conn.request(method, path, body=body, headers=headers or {})
    response = conn.getresponse()
    raw = response.read()
    conn.close()
    return response, json.loads(raw.decode("utf-8")) if raw and "application/json" in (response.getheader("Content-Type") or "") else None


def _headers(server, token):
    return {
        "Content-Type": "application/json",
        "X-Skillmerge": "1",
        "X-Skillmerge-Token": token,
        "Origin": "http://127.0.0.1:%d" % server.server_address[1],
    }


def test_http_scan_flow(tmp_path):
    server = build_app(host="127.0.0.1", preferred_port=0, data_dir=str(tmp_path / "data"), check_pid=False)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    token = server.token.value
    try:
        response, payload = _call(server, "GET", "/api/health", headers={"X-Skillmerge-Token": token})
        assert response.status == 200
        assert payload["data"]["db"] == "ok"

        body = json.dumps({"roots": [SKILLS], "depth": 10})
        response, payload = _call(server, "POST", "/api/scan", body=body, headers=_headers(server, token))
        assert response.status == 202
        job_id = payload["data"]["job_id"]

        deadline = time.time() + 8
        status = ""
        while time.time() < deadline:
            response, job = _call(server, "GET", f"/api/jobs/{job_id}", headers={"X-Skillmerge-Token": token})
            status = job["data"]["status"]
            if status in ("succeeded", "failed", "cancelled"):
                break
            time.sleep(0.1)
        assert status == "succeeded"

        response, listing = _call(server, "GET", "/api/skills?limit=200", headers={"X-Skillmerge-Token": token})
        assert response.status == 200
        assert listing["data"]["page"]["total"] >= 4
        assert any(item["name"] == "basic" for item in listing["data"]["items"])

        response, categories = _call(server, "GET", "/api/categories", headers={"X-Skillmerge-Token": token})
        assert response.status == 200
        assert categories["data"]["total"] >= 1

        save_dir = server.ctx.config.save_dir
        assert os.path.isdir(save_dir) and os.listdir(save_dir) == []
        ids = [
            item["id"] for item in listing["data"]["items"]
            if item["name"] in ("basic", "deep-skill", "copy-skill")
        ]
        assert len(ids) == 3
        preview_body = json.dumps(
            {"sources": ids, "name": "api-merged", "platform": "generic", "strategy": "keep-all"}
        )
        response, preview = _call(server, "POST", "/api/preview", body=preview_body, headers=_headers(server, token))
        assert response.status == 200
        assert preview["data"]["chapters"]
        assert preview["data"]["plan_summary"]["sources_count"] == 3
        assert os.listdir(save_dir) == []

        merge_body = json.dumps({"sources": ids, "name": "api-merged", "platform": "generic"})
        response, payload = _call(server, "POST", "/api/merge", body=merge_body, headers=_headers(server, token))
        assert response.status == 202
        merge_job = payload["data"]["job_id"]
        deadline = time.time() + 10
        status = ""
        result = None
        while time.time() < deadline:
            response, job = _call(server, "GET", f"/api/jobs/{merge_job}", headers={"X-Skillmerge-Token": token})
            status = job["data"]["status"]
            if status in ("succeeded", "failed", "cancelled"):
                result = job["data"]["result"]
                break
            time.sleep(0.1)
        assert status == "succeeded"
        assert result and os.path.isfile(os.path.join(result["dir_path"], "SKILL.md"))

        response, platforms = _call(server, "GET", "/api/platforms", headers={"X-Skillmerge-Token": token})
        assert response.status == 200
        assert any(item["id"] == "generic" for item in platforms["data"]["items"])
        for asset in ("/css/m2.css", "/css/m3.css", "/js/app.js"):
            response, _ = _call(server, "GET", asset)
            assert response.status == 200

        export_body = json.dumps(
            {"artifact_id": result["artifact_id"], "platform": "claude", "mode": "zip"}
        )
        response, payload = _call(server, "POST", "/api/export", body=export_body, headers=_headers(server, token))
        assert response.status == 202
        export_job = payload["data"]["job_id"]
        deadline = time.time() + 15
        export_result = None
        status = ""
        while time.time() < deadline:
            response, job = _call(server, "GET", f"/api/jobs/{export_job}", headers={"X-Skillmerge-Token": token})
            status = job["data"]["status"]
            if status in ("succeeded", "failed", "cancelled"):
                export_result = job["data"]["result"]
                break
            time.sleep(0.1)
        assert status == "succeeded", export_result
        assert export_result["zip_path"] and os.path.isfile(export_result["zip_path"])
        connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=10)
        connection.request("GET", export_result["download_url"], headers={"X-Skillmerge-Token": token})
        download = connection.getresponse()
        body = download.read()
        disposition = download.getheader("Content-Disposition") or ""
        connection.close()
        assert download.status == 200
        assert body[:2] == b"PK"
        assert "attachment" in disposition
    finally:
        server.shutdown()
        server.server_close()
        server.ctx.jobs.shutdown()
        server.ctx.db.close_all()
        thread.join(timeout=3)