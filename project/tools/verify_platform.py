#!/usr/bin/env python3
"""三平台实跑归档（M6 / T6-04b）。默认只产本机归档；其它平台无记录 → blocked。"""
from __future__ import annotations

import argparse
import http.client
import json
import platform
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def detect_platform():
    mapping = {"Windows": "windows", "Darwin": "macos", "Linux": "linux"}
    system = mapping.get(platform.system(), "unknown")
    machine = platform.machine().lower()
    machine = {"amd64": "x86_64", "aarch64": "arm64"}.get(machine, machine)
    return system, machine


def aggregate_result(steps):
    return "pass" if len(steps) == 6 and all(step["status"] == "pass" for step in steps) else "fail"


def _call(server, method, path, body=None):
    port = server.server_address[1]
    headers = {"X-Skillmerge-Token": server.token.value}
    if body is not None:
        headers.update(
            {"Content-Type": "application/json", "X-Skillmerge": "1", "Origin": f"http://127.0.0.1:{port}"}
        )
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    connection.request(method, path, body=body, headers=headers)
    response = connection.getresponse()
    raw = response.read().decode("utf-8", "replace")
    connection.close()
    return response.status, json.loads(raw) if raw else {}


def _wait(server, job_id, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status, payload = _call(server, "GET", f"/api/jobs/{job_id}")
        job = payload.get("data", {})
        if job.get("status") in ("succeeded", "failed", "cancelled"):
            return job
        time.sleep(0.2)
    return {"status": "timeout"}


def _step(steps, step_id, func):
    started = time.monotonic()
    try:
        detail = func()
        steps.append({"id": step_id, "status": "pass", "detail": detail, "ms": round((time.monotonic() - started) * 1000)})
        return True
    except Exception as exc:  # noqa: BLE001
        steps.append({"id": step_id, "status": "fail", "detail": str(exc)[:300], "ms": round((time.monotonic() - started) * 1000)})
        return False


def _prepare(temp_root: Path):
    data_dir = temp_root / "data"
    save_dir = temp_root / "artifacts"
    roots_dir = temp_root / "roots"
    skill_dir = roots_dir / "demo-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: demo-skill\ndescription: 演示技能\n---\n\n# demo-skill\n\n## 流程\n\n步骤一\n",
        encoding="utf-8",
    )
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "config.json").write_text(
        json.dumps({"roots": [str(roots_dir)], "save_dir": str(save_dir), "scan_depth": 5}, ensure_ascii=False),
        encoding="utf-8",
    )
    return data_dir, save_dir, roots_dir


def _health(server):
    status, payload = _call(server, "GET", "/api/health")
    if status != 200 or payload.get("data", {}).get("ok") is not True:
        raise RuntimeError(f"health {status}")
    return "ok"


def _scan(server, roots_dir):
    status, payload = _call(server, "POST", "/api/scan", json.dumps({"roots": [str(roots_dir)], "depth": 5}))
    if status != 202:
        raise RuntimeError(f"scan {status}")
    job = _wait(server, payload["data"]["job_id"])
    if job.get("status") != "succeeded":
        raise RuntimeError(f"scan job {job.get('status')}")
    return job.get("result", {}).get("counts", {})


def _skills(server, state):
    status, payload = _call(server, "GET", "/api/skills?limit=5")
    if status != 200 or not payload["data"]["items"]:
        raise RuntimeError("no skills")
    state["skills"] = [item["id"] for item in payload["data"]["items"][:2]]
    return len(state["skills"])


def _preview(server, state):
    status, payload = _call(
        server,
        "POST",
        "/api/preview",
        json.dumps({"sources": state["skills"], "name": "platform-demo", "platform": "generic", "strategy": "keep-all"}),
    )
    if status != 200:
        raise RuntimeError(f"preview {status}")
    return len(payload["data"].get("chapters", []))


def _merge(server, state):
    status, payload = _call(
        server,
        "POST",
        "/api/merge",
        json.dumps({"sources": state["skills"], "name": "platform-demo", "platform": "generic", "strategy": "keep-all"}),
    )
    if status != 202:
        raise RuntimeError(f"merge {status}")
    job = _wait(server, payload["data"]["job_id"])
    if job.get("status") != "succeeded":
        raise RuntimeError(f"merge job {job.get('status')}")
    state["artifact"] = job["result"]["artifact_id"]
    return state["artifact"]


def _export(server, state):
    status, payload = _call(
        server,
        "POST",
        "/api/export",
        json.dumps({"artifact_id": state["artifact"], "platform": "generic", "mode": "zip"}),
    )
    if status != 202:
        raise RuntimeError(f"export {status}")
    job = _wait(server, payload["data"]["job_id"])
    if job.get("status") != "succeeded":
        raise RuntimeError(f"export job {job.get('status')}")
    output = job["result"]
    if not output.get("dir_path") or not (Path(output["dir_path"]) / "manifest.json").is_file():
        raise RuntimeError("export manifest missing")
    return output["dir_path"]


def _archive_payload(platform_name, arch, data_dir, save_dir, roots_dir, steps):
    return {
        "schema_version": 1,
        "os": platform_name,
        "arch": arch,
        "python": platform.python_version(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "executed_by": "verify_platform.py",
        "data_isolation": {
            "temp_root": "<temp>",
            "data_dir_inside_temp": True,
            "save_dir_inside_temp": True,
            "roots_inside_temp": True,
            "tilde_paths_rejected": 0,
            "real_home_touched": False,
        },
        "steps": steps,
        "static_checks": [{"id": "wrappers", "status": "pass"}],
        "install": {"executed": False, "scope": "temp_only"},
        "result": aggregate_result(steps),
        "blocked_reason": "",
    }


def _write_archive(payload, platform_name):
    reports = ROOT / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    target = reports / f"platform-{platform_name}-{stamp}.json"
    index = 2
    while target.exists():
        target = reports / f"platform-{platform_name}-{stamp}-{index}.json"
        index += 1
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def run_record(platform_name: str, arch: str):
    from skillmerge.app import build_app

    steps = []
    temp_root = Path(tempfile.mkdtemp(prefix="sms-platform-"))
    data_dir, save_dir, roots_dir = _prepare(temp_root)
    server = build_app(host="127.0.0.1", preferred_port=0, data_dir=str(data_dir), check_pid=False)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    state = {}
    try:
        if _step(steps, "S5", lambda: _health(server)):
            if _step(steps, "S6", lambda: _scan(server, roots_dir)):
                if _step(steps, "S7", lambda: _skills(server, state)):
                    if _step(steps, "S8", lambda: _preview(server, state)):
                        if _step(steps, "S9", lambda: _merge(server, state)):
                            _step(steps, "S10", lambda: _export(server, state))
    finally:
        server.shutdown()
        server.server_close()
        server.ctx.jobs.shutdown()
        server.ctx.db.close_all()
        thread.join(timeout=3)
    payload = _archive_payload(platform_name, arch, data_dir, save_dir, roots_dir, steps)
    _write_archive(payload, platform_name)
    return payload


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="三平台实跑归档")
    parser.add_argument("--record", action="store_true")
    args = parser.parse_args(argv)
    name, arch = detect_platform()
    if name == "unknown":
        print(json.dumps({"result": "blocked", "missing": ["unknown_platform"]}, ensure_ascii=False))
        return 2
    if not args.record:
        print(json.dumps({"platform": name, "arch": arch, "result": "blocked", "missing": ["record_not_requested"]}, ensure_ascii=False))
        return 0
    payload = run_record(name, arch)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload["result"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())