#!/usr/bin/env python3
"""Submission layout gate: 14 stable checks, 9 assert switches, release gate."""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from submission_rules import (  # noqa: E402
    CONTENT_DIRS,
    REQUIRED_HITS,
    ROOT_FILES,
    has_blacklisted_segment,
    is_doc_only,
    iter_files,
    parse_zip_name,
    scan_text_file,
    validate_layout,
)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROOT = ROOT.parent
META_KEYS = ("work", "entry_no", "team", "version", "contact", "date")
EVIDENCE_TYPES = (
    "spec-dialog", "design-dialog", "task-plan", "codegen", "refactor",
    "debug", "test-run", "prompt-log", "machine-artifact",
)
EVIDENCE_FIELDS = ("id", "type", "path", "captured_at", "related_file", "stage", "is_current_version", "adopted", "note")
VIDEO_LINK_KEYS = ("url", "verified_at", "valid_until", "duration_sec")


def load(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def check_root(root: Path) -> dict:
    errors = validate_layout(root)
    return {"status": "PASS" if not errors else "FAIL", "detail": "; ".join(f"{e['code']}:{e['detail']}" for e in errors[:10])}


def check_nested(root: Path) -> dict:
    nested = []
    for name in CONTENT_DIRS:
        if (root / name / name).is_dir():
            nested.append(f"{name}/{name}")
    return {"status": "PASS" if not nested else "FAIL", "detail": ", ".join(nested)}


def check_nonempty(root: Path) -> dict:
    problems = []
    for name in CONTENT_DIRS:
        base = root / name
        if not base.is_dir():
            problems.append(f"{name}: missing")
            continue
        if name == "video":
            media = [path for path in base.rglob("*") if path.suffix.lower() in (".mp4", ".mov")]
            link = base / "VIDEO_LINK.txt"
            if not media and not link.is_file():
                problems.append("video: no media and no VIDEO_LINK.txt")
            continue
        material = [path for path in base.rglob("*") if path.is_file() and path.stat().st_size > 0 and not is_doc_only(path.name)]
        if not material:
            problems.append(f"{name}: only docs or empty")
    return {"status": "PASS" if not problems else "FAIL", "detail": "; ".join(problems)}


def check_required(root: Path) -> dict:
    problems = []
    for directory, names in REQUIRED_HITS.items():
        for name in names:
            if not any((root / directory).rglob(name)):
                problems.append(f"{directory}/{name}")
    demo = root / "project" / "demo-skills"
    if not any(path.is_file() for path in demo.rglob("*")) if demo.is_dir() else True:
        problems.append("project/demo-skills")
    return {"status": "PASS" if not problems else "FAIL", "detail": ", ".join(problems)}


def check_zip_name(zip_path: str) -> dict:
    if not zip_path:
        return {"status": "SKIP", "detail": "no --zip"}
    try:
        parse_zip_name(Path(zip_path).name)
        return {"status": "PASS", "detail": Path(zip_path).name}
    except ValueError as error:
        return {"status": "FAIL", "detail": str(error)}


def check_blacklist(root: Path) -> dict:
    hits = []
    for path in iter_files(root):
        reason = has_blacklisted_segment(path, root)
        if reason:
            hits.append(f"{path.relative_to(root).as_posix()} ({reason})")
    return {"status": "PASS" if not hits else "FAIL", "detail": "; ".join(hits[:10]) + (f" ... +{len(hits) - 10}" if len(hits) > 10 else "")}


def check_scan(root: Path) -> dict:
    risks = []
    for path in iter_files(root):
        relative = path.relative_to(root).as_posix()
        if has_blacklisted_segment(path, root):
            continue
        risks.extend(scan_text_file(path, relative))
    detail = "; ".join(f"{risk['code']} {risk['path']}:{risk['line']}" for risk in risks[:10])
    return {"status": "PASS" if not risks else "FAIL", "detail": detail}


def parse_meta(text: str) -> dict:
    match = re.search(r"```(?:submission-meta)?\s*\n(.*?)```", text, re.S)
    if not match:
        return {}
    meta = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip().lower()
            if key in META_KEYS:
                meta[key] = value.strip().strip(",")
    return meta


def check_meta(root: Path) -> dict:
    text = load(root / "SUBMISSION-CHECKLIST.md")
    meta = parse_meta(text)
    missing = [key for key in META_KEYS if not meta.get(key)]
    if missing:
        return {"status": "FAIL", "detail": f"missing {missing}"}
    return {"status": "PASS", "detail": json.dumps(meta, ensure_ascii=False)}


def check_scripts(root: Path) -> dict:
    problems = []
    for name in ("install.bat", "install.sh"):
        text = load(root / "readme" / name)
        if not text:
            problems.append(f"{name}: missing")
            continue
        if not re.search(r"sys\.version_info\s*>=\s*\(\s*3\s*,\s*(?:1[1-9]|[2-9]\d)\s*\)", text):
            problems.append(f"{name}: version < 3.11")
        if "3, 9" in text or "3.9" in text:
            problems.append(f"{name}: legacy version")
        if "[FIX]" not in text:
            problems.append(f"{name}: no readable fix")
        if "--dev" not in text:
            problems.append(f"{name}: no --dev guard")
        if "codearts_proof" not in text:
            problems.append(f"{name}: no five-directory check")
    return {"status": "PASS" if not problems else "FAIL", "detail": "; ".join(problems)}


def check_ppt(root: Path) -> dict:
    base = root / "ppt"
    files = [path for path in base.glob("*") if path.suffix.lower() in (".pptx", ".pdf")] if base.is_dir() else []
    if not files:
        return {"status": "FAIL", "detail": "no pptx/pdf"}
    pptx = next((path for path in files if path.suffix.lower() == ".pptx"), None)
    if pptx is None:
        return {"status": "PASS", "detail": "pdf only; page count is manual"}
    try:
        with zipfile.ZipFile(pptx) as bundle:
            xml = bundle.read("ppt/presentation.xml").decode("utf-8", errors="replace")
        slides = len(re.findall(r"<p:sldId\b", xml))
    except (KeyError, zipfile.BadZipFile):
        return {"status": "FAIL", "detail": "invalid pptx"}
    status = "PASS" if 5 <= slides <= 20 else "FAIL"
    return {"status": status, "detail": f"slides={slides}"}


def check_video(root: Path) -> dict:
    base = root / "video"
    media = [path for path in base.rglob("*") if path.suffix.lower() in (".mp4", ".mov")] if base.is_dir() else []
    if media:
        return {"status": "PASS", "detail": media[0].name}
    link = load(base / "VIDEO_LINK.txt")
    if not link.strip():
        return {"status": "FAIL", "detail": "no video and no link"}
    fields = {}
    for line in link.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()
    missing = [key for key in VIDEO_LINK_KEYS if not fields.get(key) or "待填写" in fields.get(key, "")]
    if missing:
        return {"status": "FAIL", "detail": f"missing {missing}"}
    try:
        duration = int(re.sub(r"\D", "", fields["duration_sec"]) or "999")
    except ValueError:
        duration = 999
    if duration > 180:
        return {"status": "FAIL", "detail": f"duration={duration}"}
    return {"status": "PASS", "detail": fields.get("url", "")[:80]}


def check_evidence(root: Path) -> dict:
    base = root / "codearts_proof"
    index = base / "EVIDENCE-INDEX.md"
    if not index.is_file():
        return {"status": "FAIL", "detail": "EVIDENCE-INDEX.md missing"}
    text = load(index)
    missing = [field for field in EVIDENCE_FIELDS if field not in text]
    types = [value for value in EVIDENCE_TYPES if value in text]
    if missing:
        return {"status": "FAIL", "detail": f"missing fields {missing}"}
    if not types:
        return {"status": "FAIL", "detail": "no evidence rows"}
    return {"status": "PASS", "detail": f"types={len(types)}"}


def check_health(url: str) -> dict:
    if not url:
        return {"status": "SKIP", "detail": "no --health"}
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return {"status": "PASS" if response.status == 200 else "FAIL", "detail": str(payload)[:120]}
    except Exception as error:  # noqa: BLE001 - gate reports failure
        return {"status": "FAIL", "detail": str(error)}


def check_manifest(root: Path, manifest: str) -> dict:
    if not manifest:
        return {"status": "SKIP", "detail": "no --manifest"}
    text = load(Path(manifest))
    if not text:
        return {"status": "FAIL", "detail": "manifest missing"}
    header = {}
    body = []
    for line in text.splitlines():
        if ":" in line and not line.startswith(("0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "a", "b", "c", "d", "e", "f")):
            key, value = line.split(":", 1)
            header[key.strip()] = value.strip()
        elif line.strip():
            body.append(line)
    problems = []
    if int(header.get("files", "-1")) != len(body):
        problems.append(f"files={header.get('files')} lines={len(body)}")
    for key in ("work", "version", "generated_at", "files", "total_bytes", "builder"):
        if not header.get(key):
            problems.append(f"missing {key}")
    return {"status": "PASS" if not problems else "FAIL", "detail": "; ".join(problems)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="submission layout gate")
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    parser.add_argument("--zip", default="")
    parser.add_argument("--manifest", default="")
    parser.add_argument("--health", default="")
    for name in ("root", "nonempty", "clean", "meta", "scripts", "health", "ppt", "video", "evidence-index"):
        parser.add_argument(f"--assert-{name}", action="store_true")
    parser.add_argument("--release-gate", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    if not root.is_dir():
        print("E_ROOT_MISSING: root not found", file=sys.stderr)
        return 2
    selected = {
        "C-DEL-01": ("root structure", check_root(root)),
        "C-DEL-02": ("no nested directories", check_nested(root)),
        "C-DEL-03": ("five non-empty directories", check_nonempty(root)),
        "C-DEL-04": ("required minimum files", check_required(root)),
        "C-DEL-05": ("zip name", check_zip_name(args.zip)),
        "C-DEL-06": ("forbidden paths", check_blacklist(root)),
        "C-DEL-07": ("content scan", check_scan(root)),
        "C-DEL-08": ("submission metadata", check_meta(root)),
        "C-DEL-09": ("install scripts", check_scripts(root)),
        "C-DEL-10": ("ppt structure", check_ppt(root)),
        "C-DEL-11": ("video or link", check_video(root)),
        "C-DEL-12": ("evidence index", check_evidence(root)),
        "C-DEL-13": ("health endpoint", check_health(args.health)),
        "C-DEL-14": ("manifest consistency", check_manifest(root, args.manifest)),
    }
    if not args.release_gate:
        active = {
            "C-DEL-01": args.assert_root, "C-DEL-02": args.assert_root,
            "C-DEL-03": args.assert_nonempty, "C-DEL-04": args.assert_nonempty,
            "C-DEL-05": bool(args.zip), "C-DEL-06": args.assert_clean,
            "C-DEL-07": args.assert_clean or args.assert_root, "C-DEL-08": args.assert_meta,
            "C-DEL-09": args.assert_scripts, "C-DEL-10": args.assert_ppt,
            "C-DEL-11": args.assert_video, "C-DEL-12": args.assert_evidence_index,
            "C-DEL-13": args.assert_health or bool(args.health),
            "C-DEL-14": bool(args.manifest),
        }
        if not any(active.values()):
            active["C-DEL-01"] = active["C-DEL-06"] = True
    else:
        active = {key: True for key in selected}
    checks = []
    for check_id, (title, result) in selected.items():
        if not active.get(check_id):
            continue
        checks.append({"id": check_id, "title": title, **result})
    manual = []
    if args.release_gate:
        for item in ("ppt content quality", "video continuity", "codearts screenshots authenticity", "evidence semantic consistency", "reviewer demo readiness", "core highlight verifiability"):
            manual.append({"id": "MANUAL", "title": item, "status": "MANUAL", "detail": "requires human review"})
    failed = [check for check in checks if check["status"] == "FAIL"]
    skipped = [check for check in checks if check["status"] == "SKIP"]
    verdict = "not_submittable"
    if args.release_gate and not failed and not skipped and not manual:
        verdict = "submittable"
    payload = {
        "ok": not failed,
        "root": str(root),
        "checks": checks,
        "manual": manual,
        "gaps": failed + manual,
        "verdict": verdict,
        "auto": {
            "pass": len([check for check in checks if check["status"] == "PASS"]),
            "fail": len(failed),
            "skip": len(skipped),
        },
        "manual_counts": {"total": len(manual), "passed": 0},
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=1))
    else:
        for check in checks + manual:
            print(f"[{check['status']}] {check['id']} {check['title']} — {check['detail']}")
        print(f"WB-SUBMISSION: auto_pass={payload['auto']['pass']} auto_fail={payload['auto']['fail']} auto_skip={payload['auto']['skip']} manual={len(manual)} verdict={verdict}")
    if args.release_gate:
        return 0 if verdict == "submittable" else 1
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())