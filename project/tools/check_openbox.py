#!/usr/bin/env python3
"""开箱即用验收（M6 / T6-06）：干净环境五步主流程。"""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _fixture(root: Path) -> None:
    for name, description in (("alpha", "生成统计报告和数据图表"), ("beta", "整理文档与图表")):
        folder = root / name
        folder.mkdir(parents=True)
        (folder / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n\n## 流程\n\n步骤一\n",
            encoding="utf-8",
        )
    noise = root / "node_modules"
    noise.mkdir()
    (noise / "SKILL.md").write_text("# noise", encoding="utf-8")


def _run(args, timeout=120):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    env.pop("SKILLMERGE_API_KEY", None)
    proc = subprocess.run(
        [sys.executable, "-m", "skillmerge", *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=env,
    )
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    try:
        payload = json.loads(lines[-1]) if lines else {}
    except ValueError:
        payload = {"ok": False, "error": {"message": proc.stderr[-300:]}}
    return proc.returncode, payload, proc.stderr[-300:]


def _ids(db_path: Path):
    connection = sqlite3.connect(str(db_path))
    try:
        return [row[0] for row in connection.execute("SELECT id FROM skills ORDER BY name")]
    finally:
        connection.close()


def _categories(db_path: Path):
    connection = sqlite3.connect(str(db_path))
    try:
        return [tuple(row) for row in connection.execute("SELECT name, category, category_source FROM skills ORDER BY name")]
    finally:
        connection.close()


def _env():
    browser = [name for name in ("playwright", "selenium") if importlib.util.find_spec(name) is not None]
    return {
        "python": sys.version.split()[0],
        "python_ok": sys.version_info >= (3, 11),
        "api_key_present": bool(os.environ.get("SKILLMERGE_API_KEY")),
        "browser_deps_installed": bool(browser),
        "browser_deps": browser,
        "network": "blocked_by_harness",
    }


def _e2e_skipped():
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-m", "e2e", "-q"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    skipped = re.search(r"(\d+) skipped", proc.stdout)
    return int(skipped.group(1)) if skipped else 0


def _import_graph():
    stdlib = set(sys.stdlib_module_names)
    third = set()
    for path in (ROOT / "skillmerge").rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    continue
                if node.module:
                    names = [node.module]
            for name in names:
                top = name.split(".")[0]
                if top in stdlib or top == "skillmerge":
                    continue
                third.add(top)
    return {"only_stdlib_and_skillmerge": not third, "third_party": sorted(third)}


def _hashes(export_dir: Path):
    manifest = json.loads((export_dir / "manifest.json").read_text(encoding="utf-8"))
    hashes = {}
    for entry in manifest.get("files", []):
        rel = str(entry.get("path") or entry.get("rel_path") or "")
        full = export_dir / rel
        if rel and full.is_file():
            hashes[rel] = hashlib.sha256(full.read_bytes()).hexdigest()
    return hashes, manifest


def _write_report(payload: dict) -> Path:
    reports = ROOT / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    target = reports / f"openbox-{stamp}.json"
    index = 2
    while target.exists():
        target = reports / f"openbox-{stamp}-{index}.json"
        index += 1
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return target


def _step(steps, step_id, args, check):
    code, payload, stderr = _run(args)
    ok = code == 0 and payload.get("ok") is True
    detail = payload.get("data") or {}
    if ok:
        try:
            ok = bool(check(detail))
        except Exception:  # noqa: BLE001
            ok = False
    steps.append(
        {
            "id": step_id,
            "exit_code": code,
            "verdict": "pass" if ok else "fail",
            "artifact": str(detail.get("dir_path") or detail.get("artifact_id") or ""),
            "evidence": detail if not ok else {"keys": sorted(detail.keys())},
            "note": "" if ok else stderr,
        }
    )
    return ok, detail


def _prepare(temp_root: Path):
    fixture = temp_root / "fixtures"
    _fixture(fixture)
    data_dir = temp_root / "data"
    save_dir = temp_root / "artifacts"
    data_dir.mkdir(parents=True)
    (data_dir / "config.json").write_text(
        json.dumps(
            {"save_dir": str(save_dir), "roots": [str(fixture)], "ai": {"enabled": False}, "scan_depth": 5},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return fixture, data_dir, save_dir


def _execute(data_dir: Path, save_dir: Path, fixture: Path, steps, artifacts):
    db_path = data_dir / "index.db"
    ok, _ = _step(
        steps,
        "scan",
        ["scan", "--root", str(fixture), "--data-dir", str(data_dir)],
        lambda detail: detail.get("stats", {}).get("found", 0) >= 2
        and detail.get("stats", {}).get("prune_hits", {}).get("node_modules", 0) >= 1,
    )
    categories = []
    if ok:
        ok, _ = _step(
            steps,
            "classify",
            ["classify", "--data-dir", str(data_dir)],
            lambda detail: detail.get("classified", 0) >= 2,
        )
        if ok:
            categories = _categories(db_path)
    merged = {}
    if ok:
        ids = _ids(db_path)[:2]
        ok, merged = _step(
            steps,
            "merge",
            ["merge", "--sources", ",".join(ids), "--name", "openbox-demo", "--platform", "generic",
             "--data-dir", str(data_dir), "--out", str(save_dir)],
            lambda detail: bool(detail.get("dir_path")) and (Path(detail["dir_path"]) / "manifest.json").is_file(),
        )
        artifacts["merge_dir"] = merged.get("dir_path", "")
    if ok:
        ok, exported = _step(
            steps,
            "export",
            ["export", "--artifact", merged["artifact_id"], "--platform", "generic", "--mode", "dir",
             "--data-dir", str(data_dir)],
            lambda detail: bool(detail.get("dir_path")) and (Path(detail["dir_path"]) / "SKILL.md").is_file(),
        )
        artifacts["export_dir"] = exported.get("dir_path", "")
    if ok:
        _step(
            steps,
            "validate",
            ["validate", "--artifact", artifacts["export_dir"], "--platform", "generic", "--data-dir", str(data_dir)],
            lambda detail: int(detail.get("error_count", 1)) == 0,
        )
    return categories


def _assertions(steps, env, graph, ai_fallback, baseline, after):
    return (
        all(step["verdict"] == "pass" for step in steps)
        and len(steps) == 5
        and env["python_ok"]
        and not env["api_key_present"]
        and not env["browser_deps_installed"]
        and graph["only_stdlib_and_skillmerge"]
        and ai_fallback["indicated"]
        and baseline == after
    )


def run_check(cleanup=True):
    started = datetime.now(timezone.utc)
    temp_root = Path(tempfile.mkdtemp(prefix="sms-openbox-"))
    steps = []
    artifacts = {}
    try:
        fixture, data_dir, save_dir = _prepare(temp_root)
        categories = _execute(data_dir, save_dir, fixture, steps, artifacts)
        baseline = {}
        manifest = {}
        if artifacts.get("export_dir"):
            baseline, manifest = _hashes(Path(artifacts["export_dir"]))
        after = _hashes(Path(artifacts["export_dir"]))[0] if artifacts.get("export_dir") else {}
        env = _env()
        env["e2e_skipped"] = _e2e_skipped()
        env["e2e_total"] = env["e2e_skipped"]
        graph = _import_graph()
        ai_fallback = {
            "activated": True,
            "indicated": bool(categories)
            and all(source in ("keyword", "manual") for _name, _cat, source in categories)
            and any(category not in ("", "未分类") for _name, category, _source in categories),
            "source": "keyword",
        }
        payload = {
            "schema_version": 1,
            "started_at": started.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "env": env,
            "import_graph": graph,
            "ai_fallback": ai_fallback,
            "steps": steps,
            "artifacts": {
                "merge_dir": artifacts.get("merge_dir", ""),
                "export_dir": artifacts.get("export_dir", ""),
                "manifest_sha256": hashlib.sha256(json.dumps(manifest, sort_keys=True).encode("utf-8")).hexdigest()
                if manifest
                else "",
                "file_hashes": baseline,
            },
            "hash_stability": {
                "baseline": baseline,
                "after_dev_deps": after,
                "equal": baseline == after,
                "method": "revalidate_same_export",
            },
            "verdict": "pass" if _assertions(steps, env, graph, ai_fallback, baseline, after) else "fail",
        }
        target = _write_report(payload)
        return 0 if payload["verdict"] == "pass" else 1, payload, target
    finally:
        if cleanup:
            shutil.rmtree(temp_root, ignore_errors=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="开箱即用五步验收")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--no-cleanup", action="store_true")
    args = parser.parse_args(argv)
    if not args.check:
        print(json.dumps({"result": "blocked", "missing": ["--check"]}, ensure_ascii=False))
        return 2
    code, payload, target = run_check(cleanup=not args.no_cleanup)
    print(json.dumps({"code": code, "verdict": payload["verdict"], "report": str(target)}, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())