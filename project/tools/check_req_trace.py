#!/usr/bin/env python3
"""需求 ↔ 证据映射校验器（M6 / T6-01）。--check 只读，不写盘。"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / ".codeartsdoer/specs/skillmerge_studio/spec.md"
MAP_PATH = ROOT / "docs/req-map.json"
SUMMARY_JSON = ROOT / "reports/verification-summary.json"
SUMMARY_MD = ROOT / "docs/verification-summary.md"

REQ_RE = re.compile(r"^- \*\*(REQ-[A-Z]+-\d{3})\*\* \[(P[012])\]", re.M)
KINDS = frozenset({"pytest", "manual", "gate", "script", "browser"})
LEVELS = frozenset({"auto-http", "auto-logic", "auto-dom", "static", "manual", "blocked"})
STATUSES = frozenset({"verified", "partial", "blocked", "exempt", "not_started"})
EXEMPT_BASIS = frozenset({"REQ-CON-012", "REQ-CON-013"})
ACCEPTANCE_FIELDS = (
    "basis_req",
    "type",
    "substitute_evidence",
    "accepter",
    "accepted_at",
    "review_trigger",
    "valid_until",
)
CONDITION_BY_REQ = {
    "REQ-VER-003": "browser_dependency_not_approved_or_manual_record_missing",
    "REQ-VER-006": "missing_endpoint",
    "REQ-VER-008": "missing_env_macos",
    "REQ-VER-009": "missing_env_linux",
    "REQ-VER-011": "missing_isolated_root",
    "REQ-VER-015": "sampling_ratio_unconfirmed",
    "REQ-VER-017": "user_acceptance_required(trash_p2_entry)",
}
CLOSURE_JSON = ROOT / "reports" / "closure-summary.json"
WORD_PATTERNS = (
    (r"(?:338|321)\s*条[^\n。]{0,12}(?:全部|均|逐条)?[^\n。]{0,6}(?:通过|已验证)", "count-claim"),
    (r"P0[^\n。]{0,10}(?:全部|100%)[^\n。]{0,6}(?:通过|覆盖)", "p0-claim"),
    (r"浏览器[^\n。]{0,12}(?:自动化)?[^\n。]{0,6}已验证", "browser-claim"),
    (r"AI\s*质量[^\n。]{0,10}(?:已|均)?(?:验收|验证)", "ai-claim"),
    (r"三平台[^\n。]{0,10}(?:兼容|已验证)", "platform-claim"),
    (r"真实[^\n。]{0,12}安装[^\n。]{0,6}(?:已验证|通过)", "install-claim"),
    (r"(?:全部|所有)[^\n。]{0,10}已验证", "all-claim"),
)
NEGATION = re.compile(r"不得|禁止|未|不|无法|不可|没有|cannot|not", re.I)
KNOWN_GAPS = (
    "逐条节点级证据尚未建立：当前 {total} 条需求为文件级落点，测试节点与需求为多对多。",
    "浏览器行为未执行：仅有 `docs/browser-manual-checklist.md`（manual，待人工）。",
    "真实 AI 端点未验收：REQ-VER-006/007 为 blocked（missing_endpoint）。",
    "macOS/Linux 未实跑：REQ-VER-008/009 为 blocked。",
    "真实平台目录安装未执行：REQ-VER-010/011 为 partial（temp_only）。",
    "`.trash` 自动删除永久豁免；只读统计可执行，人工确认清理待 Q-37。",
    "域表由脚本生成，锚点为文件级（README.txt），不是逐条通过证据。",
)


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def extract_entries(text: str):
    entries = []
    section = ""
    for number, line in enumerate(text.splitlines(), 1):
        if line.startswith("## "):
            section = line[3:].strip()
        match = REQ_RE.match(line)
        if match:
            entries.append(
                {"req": match.group(1), "prio": match.group(2), "line": number, "section": section}
            )
    return entries


def parse_claims(text: str):
    total = re.search(r"需求条目总数：\*\*(\d+)\*\*", text)
    dist = re.search(
        r"\*\*P0：(\d+) 条[^*]*\*\*、\*\*P1：(\d+) 条[^*]*\*\*、\*\*P2：(\d+) 条", text
    )
    claims = {"total": int(total.group(1)) if total else None}
    for index, prio in enumerate(("P0", "P1", "P2")):
        claims[prio] = int(dist.group(index + 1)) if dist else None
    return claims


def load_map():
    if not MAP_PATH.is_file():
        return None
    try:
        return json.loads(MAP_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def save_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def collect_nodes():
    command = [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"]
    try:
        proc = subprocess.run(command, cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        return {"ok": False, "nodes": set(), "collected": 0, "total": 0, "deselected": 0}
    nodes = {
        line.strip()
        for line in proc.stdout.splitlines()
        if "::" in line and not line.startswith(("=", "no tests"))
    }
    summary = re.search(r"(\d+)/(\d+) tests? collected", proc.stdout)
    deselected = re.search(r"(\d+) deselected", proc.stdout)
    return {
        "ok": proc.returncode == 0,
        "nodes": nodes,
        "collected": int(summary.group(1)) if summary else 0,
        "total": int(summary.group(2)) if summary else 0,
        "deselected": int(deselected.group(1)) if deselected else 0,
    }


def resolve_anchor(anchor, nodes) -> bool:
    kind = str(anchor.get("kind", ""))
    target = str(anchor.get("id", ""))
    if kind == "pytest":
        return target in nodes
    if kind == "manual":
        path, _, line = target.partition("#L")
        full = ROOT / path
        if not full.is_file() or not line.isdigit():
            return False
        try:
            lines = full.read_text(encoding="utf-8").splitlines()
        except OSError:
            return False
        index = int(line) - 1
        return 0 <= index < len(lines) and lines[index].strip().startswith(("- [ ]", "- [x]"))
    if kind in ("gate", "script", "browser"):
        return (ROOT / target).is_file()
    return False


def derive_status(item, nodes) -> str:
    status = str(item.get("status", "not_started"))
    if status in ("blocked", "exempt"):
        return status
    evidence = item.get("evidence") or []
    required = [a for a in (item.get("anchors") or []) if a.get("required")]
    if status == "verified":
        if not evidence:
            return "partial"
        if required and not all(resolve_anchor(a, nodes) for a in required):
            return "partial"
    return status


def freshness(args):
    if args.since:
        return args.since, "explicit"
    path = ROOT / (args.since_path or "skillmerge")
    if not path.exists():
        return None, "unknown"
    latest = 0.0
    for dirpath, dirnames, filenames in os.walk(path):
        dirnames[:] = [name for name in dirnames if name != "__pycache__"]
        for name in filenames:
            try:
                latest = max(latest, os.path.getmtime(os.path.join(dirpath, name)))
            except OSError:
                continue
    return latest, "path" if latest else "unknown"


def render_trace(data) -> str:
    items = data.get("items") or []
    total = len(items)
    verified = [str(item.get("req")) for item in items if str(item.get("status")) == "verified"]
    exempt_ids = [str(item.get("req")) for item in items if str(item.get("status")) == "exempt"]
    passed = len(verified)
    exempt = len(exempt_ids)
    pending = total - passed - exempt
    grouped = {}
    for item in items:
        parts = str(item.get("req", "")).split("-")
        domain = parts[1] if len(parts) >= 3 else "UNKNOWN"
        grouped.setdefault(domain, []).append(item)
    lines = [
        f"# 需求追溯（{total} 条，按域汇总；通过 {passed} / 未执行 {pending} / 豁免 {exempt}）",
        "",
        f"日期：{datetime.now(timezone.utc).date().isoformat()}",
        "",
        "机读真源：`docs/req-map.json` + `tools/check_req_trace.py --check`。",
        "本文件由 `tools/check_req_trace.py --trace-out` 生成；锚点为文件级，不是逐条通过证据。",
        "",
        "| 需求域 | 条数 | 主要落点 | 状态分布 |",
        "| --- | --- | --- | --- |",
    ]
    for domain in sorted(grouped):
        entries = grouped[domain]
        anchors = sorted(
            {
                str(anchor.get("id"))
                for entry in entries
                for anchor in (entry.get("anchors") or [])
                if anchor.get("id")
            }
        )
        primary = " / ".join(anchors[:2]) if anchors else "—"
        distribution = {}
        for entry in entries:
            status = str(entry.get("status", "not_started"))
            distribution[status] = distribution.get(status, 0) + 1
        status_text = " / ".join(f"{key}:{value}" for key, value in sorted(distribution.items()))
        lines.append(f"| REQ-{domain} | {len(entries)} | {primary} | {status_text} |")
    blocked = [str(item.get("req")) for item in items if str(item.get("status")) == "blocked"]
    partial = [str(item.get("req")) for item in items if str(item.get("status")) == "partial"]
    lines.extend(["", "## 已知缺口（不虚报）", ""])
    for index, gap in enumerate(KNOWN_GAPS, 1):
        lines.append(f"{index}. {gap.format(total=total)}")
    lines.extend(
        [
            "",
            "### 状态速览（由脚本派生）",
            "",
            f"- verified（{passed}）：{', '.join(verified) if verified else '无'}",
            f"- blocked（{len(blocked)}）：{', '.join(blocked) if blocked else '无'}",
            f"- partial（{len(partial)}）：{', '.join(partial) if partial else '无'}",
            f"- exempt（{len(exempt_ids)}）：{', '.join(exempt_ids) if exempt_ids else '无'}",
            "",
            "> 本文件不提供完成率字段；blocked/exempt 不计入通过。",
            "",
        ]
    )
    return "\n".join(lines)


def write_trace(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(render_trace(data), encoding="utf-8")
    os.replace(tmp, path)


def check_wording():
    issues = []
    targets = [ROOT / "README.txt", ROOT / "web" / "index.html"]
    targets += sorted((ROOT / "web").rglob("*.js"))
    targets += sorted((ROOT / "docs").rglob("*.md"))
    for path in targets:
        if not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for number, line in enumerate(lines, 1):
            for pattern, label in WORD_PATTERNS:
                for match in re.finditer(pattern, line):
                    window = line[max(0, match.start() - 14): match.end() + 14]
                    if NEGATION.search(window):
                        continue
                    rel = path.relative_to(ROOT).as_posix()
                    issues.append(f"M6-WORDING[{label}] {rel}:{number}: {match.group(0)[:80]}")
    return issues


def derive_closure(data):
    items = data.get("items") or []
    verified, accepted, open_items = [], [], []
    for item in items:
        req = str(item.get("req"))
        status = str(item.get("status", "not_started"))
        acceptance = item.get("acceptance") or {}
        if status == "verified":
            verified.append(req)
            continue
        if status == "exempt" and acceptance.get("state") == "accepted" and all(
            acceptance.get(field) for field in ACCEPTANCE_FIELDS
        ):
            accepted.append(req)
            continue
        if status == "exempt":
            reason = "exemption_not_accepted" if acceptance.get("state") != "accepted" else "acceptance_incomplete"
        elif status in ("blocked", "partial", "not_started"):
            reason = "not_executed"
        else:
            reason = status
        reason = str(item.get("open_reason") or reason)
        condition = str(item.get("required_condition") or CONDITION_BY_REQ.get(req, "run_or_provide_evidence"))
        open_items.append({"req": req, "open_reason": reason, "required_condition": condition})
    total = int(data.get("spec_entries") or len(items))
    closed = len(verified) + len(accepted)
    reasons = {}
    for entry in open_items:
        reasons[entry["open_reason"]] = reasons.get(entry["open_reason"], 0) + 1
    return {
        "schema_version": 1,
        "total": total,
        "verified": len(verified),
        "accepted_exempt": len(accepted),
        "closed": closed,
        "open": len(open_items),
        "open_ids": [entry["req"] for entry in open_items],
        "open_by_reason": dict(sorted(reasons.items())),
        "open_details": open_items,
        "acceptance_ids": accepted,
        "identity_ok": len(items) == total and closed + len(open_items) == total,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "spec_digest": str(data.get("spec_digest", "")),
    }


def check_closure(items, by_req):
    errors = []
    if not derive_closure({"items": items})["identity_ok"]:
        errors.append("M6-CLOSURE-IDENTITY")
    for item in items:
        req = str(item.get("req"))
        status = str(item.get("status", "not_started"))
        acceptance = item.get("acceptance")
        if status == "exempt":
            if not isinstance(acceptance, dict):
                errors.append(f"M6-ACCEPT-MISSING-FIELD: {req}")
                continue
            for field in ACCEPTANCE_FIELDS:
                if not acceptance.get(field):
                    errors.append(f"M6-ACCEPT-MISSING-FIELD: {req} {field}")
            evidence = acceptance.get("substitute_evidence")
            if evidence and not (ROOT / str(evidence)).exists():
                errors.append(f"M6-ACCEPT-EVIDENCE-MISSING: {req}")
        elif acceptance:
            errors.append(f"M6-ACCEPT-NOT-EXEMPT: {req}")
        if status not in ("verified", "exempt") and "required_condition" in item:
            if not str(item.get("required_condition") or "").strip():
                errors.append(f"M6-OPEN-NO-CONDITION: {req}")
    cmp_item = by_req.get("REQ-CMP-001")
    if cmp_item and cmp_item.get("status") == "verified":
        passes = [e for e in cmp_item.get("evidence") or [] if e.get("kind") == "platform" and e.get("result") == "pass"]
        if len(passes) < 3:
            errors.extend(["M6-CMP-OVERCLAIM", "M6-REDLINE-VIOLATION#platform"])
    v11 = by_req.get("REQ-VER-011")
    if v11 and v11.get("status") == "verified":
        evidence = v11.get("evidence") or []
        if not any(e.get("kind") == "install_isolated" and e.get("executed") for e in evidence):
            errors.append("M6-REDLINE-VIOLATION#real-dir")
    v19 = by_req.get("REQ-VER-019")
    if v19 and v19.get("status") == "exempt":
        errors.append("M6-EXEMPT-ILLEGAL: REQ-VER-019")
    return errors


def check_map(data, entries, nodes, strict, since="", since_path=""):
    errors, warnings = [], []
    items = data.get("items") or []
    by_req = {str(item.get("req")): item for item in items}
    spec_reqs = {entry["req"] for entry in entries}
    for req in sorted(spec_reqs - set(by_req)):
        errors.append(f"M6-SET-MISSING: {req}")
    for req in sorted(set(by_req) - spec_reqs):
        warnings.append(f"M6-SET-EXTRA: {req}")
    if data.get("spec_entries") != len(entries):
        errors.append(f"M6-CLAIM-MISMATCH: entries={len(entries)} map={data.get('spec_entries')}")
    if data.get("spec_digest") != digest(SPEC.read_text(encoding="utf-8")):
        errors.append("M6-CLAIM-MISMATCH: spec_digest")
    for item in items:
        req = str(item.get("req"))
        status = str(item.get("status", ""))
        if status not in STATUSES:
            errors.append(f"M6-SCHEMA-ENUM: {req} status={status}")
        if status == "blocked" and not item.get("missing"):
            errors.append(f"M6-BLOCKED-NO-REASON: {req}")
        if status == "exempt" and str(item.get("basis_req", "")) not in EXEMPT_BASIS:
            errors.append(f"M6-EXEMPT-ILLEGAL: {req}")
        anchors = item.get("anchors") or []
        for anchor in anchors:
            if anchor.get("kind") not in KINDS:
                errors.append(f"M6-SCHEMA-ENUM: {req} kind={anchor.get('kind')}")
            if anchor.get("level") not in LEVELS:
                errors.append(f"M6-SCHEMA-ENUM: {req} level={anchor.get('level')}")
            if not resolve_anchor(anchor, nodes):
                errors.append(f"M6-ANCHOR-MISSING: {req} {anchor.get('id')}")
        if item.get("prio") == "P0" and status != "exempt" and not any(a.get("required") for a in anchors):
            errors.append(f"M6-P0-NO-ANCHOR: {req}")
        if status == "verified" and derive_status(item, nodes) != "verified":
            errors.append(f"M6-VERIFIED-NO-EVIDENCE: {req}")
    errors.extend(check_wording())
    errors.extend(check_closure(items, by_req))
    _, mode = freshness(type("Args", (), {"since": since, "since_path": since_path})())
    if strict and mode == "unknown":
        errors.append("M6-EVIDENCE-STALE: freshness=unknown")
    unique_ids = len({a.get("id") for item in items for a in item.get("anchors", [])})
    if unique_ids < len(items):
        warnings.append("M6-SHARED-NODES: 多对多映射，禁止声称一对一")
    return errors, warnings


def _summary_lines(total, payload, closure):
    sub = payload["not_executed_sub"]
    return [
        "# 验收汇总（机器生成，勿手改）",
        "",
        f"- 合计：{total}",
        f"- 通过：{payload['passed']}",
        f"- 未执行：{payload['not_executed']}（blocked {sub['blocked']} / 手工未勾选 {sub['manual_unchecked']} / 未开始 {sub['not_started']} / partial {sub['partial']}）",
        f"- 豁免：{payload['exempt']}",
        "",
        "## 闭合（ClosureSummary）",
        "",
        f"- 已闭合：{closure['closed']}（verified {closure['verified']} / 用户接受豁免 {closure['accepted_exempt']}）",
        f"- 未闭合：{closure['open']}",
        f"- 恒等式：closed + open = {total} → {closure['identity_ok']}",
        f"- 未闭合原因：{json.dumps(closure['open_by_reason'], ensure_ascii=False)}",
        "",
        "> 本文件不提供完成率字段；blocked/exempt 不计入通过。",
        "> 机读来源：reports/verification-summary.json 与 reports/closure-summary.json",
        "",
    ]


def render_summary(data, entries):
    items = data.get("items") or []
    passed, not_executed, exempt = [], [], []
    sub = {"blocked": 0, "manual_unchecked": 0, "not_started": 0, "partial": 0}
    for item in items:
        status = str(item.get("status", "not_started"))
        req = str(item.get("req"))
        if status == "verified":
            passed.append(req)
            continue
        if status == "exempt":
            exempt.append(req)
            continue
        not_executed.append(req)
        if status == "blocked":
            sub["blocked"] += 1
        elif status == "partial":
            sub["partial"] += 1
        elif any(a.get("level") == "manual" for a in item.get("anchors", [])):
            sub["manual_unchecked"] += 1
        else:
            sub["not_started"] += 1
    total = len(items)
    if len(passed) + len(not_executed) + len(exempt) != total:
        raise SystemExit("M6-SUM-MERGE")
    payload = {
        "schema_version": 1,
        "total": total,
        "passed": len(passed),
        "not_executed": len(not_executed),
        "exempt": len(exempt),
        "not_executed_sub": sub,
        "passed_ids": passed,
        "exempt_ids": exempt,
        "blocked_ids": [str(i["req"]) for i in items if i.get("status") == "blocked"],
        "sampling": data.get("sampling") or {"ratio": 0.2, "ratio_confirmed": False, "records": []},
    }
    save_json(SUMMARY_JSON, payload)
    closure = derive_closure(data)
    lines = _summary_lines(total, payload, closure)
    SUMMARY_MD.parent.mkdir(parents=True, exist_ok=True)
    tmp = SUMMARY_MD.with_suffix(".md.tmp")
    tmp.write_text("\n".join(lines), encoding="utf-8")
    os.replace(tmp, SUMMARY_MD)
    return payload


def write_skeleton(entries, claims, prune=False):
    existing = load_map() or {}
    by_req = {str(item.get("req")): item for item in existing.get("items", [])}
    items, added, changed = [], 0, 0
    for entry in entries:
        item = by_req.get(entry["req"])
        if item is None:
            item = {
                "req": entry["req"],
                "prio": entry["prio"],
                "task": "",
                "anchors": [],
                "status": "not_started",
                "evidence": [],
                "checked_at": "",
                "missing": [],
                "basis_req": "",
                "note": "",
            }
            added += 1
        elif item.get("prio") != entry["prio"]:
            item["prio"] = entry["prio"]
            changed += 1
        items.append(item)
    spec_reqs = {entry["req"] for entry in entries}
    for req in sorted(set(by_req) - spec_reqs):
        if not prune:
            items.append(by_req[req])
    p0_total = sum(1 for entry in entries if entry["prio"] == "P0")
    sampling = dict(existing.get("sampling") or {})
    sampling["ratio"] = 0.20
    sampling["required_total"] = math.ceil(p0_total * 0.20)
    sampling.setdefault("ratio_confirmed", False)
    sampling.setdefault("records", [])
    data = {
        "schema_version": 1,
        "spec_entries": len(entries),
        "spec_unique": len(spec_reqs),
        "spec_digest": digest(SPEC.read_text(encoding="utf-8")),
        "claims": claims,
        "sampling": sampling,
        "items": items,
    }
    save_json(MAP_PATH, data)
    print(f"M6-WRITE: 新增 {added} / 变更 {changed} / 合计 {len(items)}")
    return 0


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="需求映射校验（M6）")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--collect-refresh", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--since", default="")
    parser.add_argument("--since-path", default="")
    parser.add_argument("--sampling-ratio", type=float, default=0.20)
    parser.add_argument("--audit-out", default="")
    parser.add_argument("--trace-out", default="")
    parser.add_argument("--prune", action="store_true")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.check and args.write:
        print("M6-ARG-CONFLICT: --check 与 --write 只能二选一", file=sys.stderr)
        return 2
    if args.trace_out and args.write:
        print("M6-ARG-CONFLICT: --trace-out 与 --write 只能二选一", file=sys.stderr)
        return 2
    if not SPEC.is_file():
        print("M6-INPUT-MISSING: spec.md", file=sys.stderr)
        return 2
    text = SPEC.read_text(encoding="utf-8")
    entries = extract_entries(text)
    claims = parse_claims(text)
    if not entries:
        print("M6-EXTRACT-EMPTY", file=sys.stderr)
        return 1
    if args.write:
        return write_skeleton(entries, claims, args.prune)
    data = load_map()
    if data is None:
        print("M6-INPUT-MISSING: docs/req-map.json", file=sys.stderr)
        return 2
    if args.trace_out:
        write_trace(Path(args.trace_out), data)
        print(f"M6-TRACE: {args.trace_out} items={len(data.get('items') or [])}")
        return 0
    if args.collect_refresh:
        nodes = collect_nodes()
        print(f"M6-COLLECT: {nodes['collected']}/{nodes['total']} deselected={nodes['deselected']} ok={nodes['ok']}")
        return 0
    if args.summary:
        payload = render_summary(data, entries)
        closure = derive_closure(data)
        save_json(CLOSURE_JSON, closure)
        if args.audit_out:
            audit = {
                "generated_at": closure["generated_at"],
                "open_ids": closure["open_ids"],
                "refusals": [],
                "baseline": {"map_items": len(data.get("items") or []), "summary_total": payload["total"]},
            }
            save_json(Path(args.audit_out), audit)
        print(
            f"M6-SUMMARY: total={payload['total']} passed={payload['passed']} "
            f"not_executed={payload['not_executed']} exempt={payload['exempt']}; "
            f"closure verified={closure['verified']} accepted={closure['accepted_exempt']} "
            f"closed={closure['closed']} open={closure['open']} identity_ok={closure['identity_ok']}"
        )
        return 0 if closure["identity_ok"] else 1
    nodes = collect_nodes()
    errors, warnings = check_map(data, entries, nodes["nodes"], args.strict, args.since, args.since_path)
    for item in errors:
        print(item, file=sys.stderr)
    for item in warnings:
        print(item, file=sys.stderr)
    print(f"M6-CHECK: errors={len(errors)} warnings={len(warnings)} nodes={nodes['collected']}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())