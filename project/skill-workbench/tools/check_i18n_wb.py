#!/usr/bin/env python3
"""English-mode gate: dictionary parity, three-source scan, screens and reasons."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXT = ROOT / "extension"
ZH = EXT / "lib" / "i18n" / "zh.js"
EN = EXT / "lib" / "i18n" / "en.js"
SCREENS = EXT / "i18n-screens.json"
REASONS = EXT / "i18n-reasons.json"
ALLOWLIST = EXT / "i18n-allowlist.json"
CJK = re.compile(r"[\u4e00-\u9fff]")
ENTRY = re.compile(r'^\s*"([^"]+)"\s*:\s*"((?:[^"\\]|\\.)*)"', re.M)
JS_STRING = re.compile(r'"((?:[^"\\]|\\.)*)"|\'((?:[^\'\\]|\\.)*)\'|`([^`]*)`')
REASON_USAGE = re.compile(r'reason_code["\']?\s*[:=]\s*["\']([a-z_]+)["\']')
TOOL_REASONS = {"matched_detected", "no_tool_hint", "no_detected_tool", "tool_evidence_unknown"}
APP_REASONS = {"not_fetched", "not_declared", "declared_universal", "declared_targets", "field_unregistered"}
REQUIRED_REASONS = TOOL_REASONS | APP_REASONS | {"target_not_registered", "legacy_missing", "invalid_value", "parse_failed", "cannot_compare"}


def entries(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    return {key: value for key, value in ENTRY.findall(text)}


def load(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return fallback


def scan_js(paths, allow_values: set[str]) -> list[str]:
    issues = []
    for path in paths:
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        rel = path.relative_to(ROOT).as_posix()
        for number, line in enumerate(lines, 1):
            for match in JS_STRING.finditer(line):
                value = next((group for group in match.groups() if group is not None), "")
                if not value or not CJK.search(value):
                    continue
                if any(allowed in value for allowed in allow_values):
                    continue
                issues.append(f"{rel}:{number}: hardcoded-cjk: {value[:60]}")
    return issues


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="workbench i18n gate")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--assert-keys", action="store_true")
    parser.add_argument("--assert-screens", action="store_true")
    parser.add_argument("--assert-reasons", action="store_true")
    parser.add_argument("--assert-allowlist", action="store_true")
    parser.add_argument("--assert-q17-default", action="store_true")
    parser.add_argument("--evidence-dir", default="")
    parser.add_argument("--report", default="")
    args = parser.parse_args(argv)
    errors: list[str] = []
    zh = entries(ZH)
    en = entries(EN)
    if not zh or not en:
        errors.append("WB-I18N-1 dictionaries missing or empty")
    missing_en = sorted(set(zh) - set(en))
    extra_en = sorted(set(en) - set(zh))
    for key in missing_en:
        errors.append(f"WB-I18N-1 missing en key: {key}")
    for key in extra_en:
        errors.append(f"WB-I18N-1 extra en key: {key}")
    allow_data = load(ALLOWLIST, {})
    allow_values = {str(item.get("value", "")) for item in allow_data.get("entries", []) if item.get("value")}
    for key, value in en.items():
        if CJK.search(value) and not any(allowed in value for allowed in allow_values):
            errors.append(f"WB-I18N-2 en value contains CJK: {key}")
    ui_sources = list((EXT / "ui").rglob("*.js")) + list((EXT / "lib").rglob("*.js"))
    ui_sources = [path for path in ui_sources if path.name not in ("zh.js",)]
    background = EXT / "background.js"
    if background.is_file():
        ui_sources.append(background)
    errors.extend(scan_js(ui_sources, allow_values))
    for folder in (ROOT / "agent" / "api", ROOT / "agent" / "core"):
        for path in folder.rglob("*.py"):
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for number, line in enumerate(lines, 1):
                if line.strip().startswith("#"):
                    continue
                for match in re.finditer(r'"([^"]*)"|\'([^\']*)\'', line):
                    value = match.group(1) if match.group(1) is not None else match.group(2)
                    if value and CJK.search(value):
                        errors.append(f"{path.relative_to(ROOT).as_posix()}:{number}: agent-cjk: {value[:60]}")
    screens = load(SCREENS, {})
    screen_items = screens.get("screens") or []
    if args.assert_screens:
        expected = int(screens.get("expected_count", 0))
        if expected != len(screen_items):
            errors.append(f"WB-I18N-3 screen count mismatch expected={expected} actual={len(screen_items)}")
        for screen in screen_items:
            if not screen.get("screen_id") or not screen.get("states") or not screen.get("assertions"):
                errors.append(f"WB-I18N-3 incomplete screen {screen.get('screen_id')}")
    if args.assert_q17_default and screens.get("doc_surfaces"):
        errors.append("WB-I18N-4 doc_surfaces must stay empty under Q-17 default")
    reasons = load(REASONS, {}).get("reasons", {})
    if args.assert_reasons:
        for reason in sorted(REQUIRED_REASONS):
            if reason not in reasons:
                errors.append(f"WB-I18N-5 unregistered reason_code: {reason}")
        for path in list((ROOT / "agent").rglob("*.py")):
            text = path.read_text(encoding="utf-8", errors="replace")
            for reason in REASON_USAGE.findall(text):
                if reason not in reasons and reason not in {"not_fetched"}:
                    errors.append(f"WB-I18N-5 reason_code without i18n key: {reason}")
    if args.assert_allowlist:
        for entry in allow_data.get("entries", []):
            for field in ("value", "category", "reason", "added_at"):
                if not entry.get(field):
                    errors.append(f"WB-I18N-6 allowlist missing {field}")
            if entry.get("category") not in ("user_data", "proper_noun"):
                errors.append(f"WB-I18N-6 allowlist category illegal: {entry.get('category')}")
    evidence = Path(args.evidence_dir) if args.evidence_dir else None
    if evidence is not None:
        count = len(list(evidence.glob("**/*"))) if evidence.is_dir() else 0
        if count == 0:
            errors.append("WB-I18N-7 evidence directory missing or empty")
    if args.report:
        out = Path(args.report)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"errors": errors, "screens": len(screen_items), "keys": len(zh)}, ensure_ascii=False, indent=1), encoding="utf-8")
    for item in errors:
        print(item, file=sys.stderr)
    print(f"WB-I18N: keys={len(zh)} en_keys={len(en)} screens={len(screen_items)} errors={len(errors)}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())