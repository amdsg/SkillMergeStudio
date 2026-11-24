#!/usr/bin/env python3
"""Default-off capabilities and minimal extension permissions."""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULTS = ROOT / "agent" / "config" / "defaults.py"
MANIFEST = ROOT / "extension" / "manifest.json"
REQUIRED_OFF = ("real_write", "upgrade_replace", "official_claim", "binary_convert", "auto_check")
FORBIDDEN_PERMISSIONS = {"<all_urls>", "unlimitedStorage", "externally_connectable", "content_scripts"}


def load_defaults():
    spec = importlib.util.spec_from_file_location("wb_defaults", DEFAULTS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.CAPABILITIES


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="default-off capability gate")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    errors = []
    if not DEFAULTS.is_file():
        print("WB-DEFAULT: defaults.py missing", file=sys.stderr)
        return 2
    try:
        capabilities = load_defaults()
    except Exception as error:  # noqa: BLE001 - gate reports the failure
        print(f"WB-DEFAULT: cannot import defaults: {error}", file=sys.stderr)
        return 2
    for capability in REQUIRED_OFF:
        if capabilities.get(capability) is not False:
            errors.append(f"WB-DEFAULT-1 {capability} must be false")
    if not MANIFEST.is_file():
        errors.append("WB-DEFAULT-2 manifest.json missing")
    else:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        host_permissions = manifest.get("host_permissions") or []
        for permission in host_permissions:
            if permission in FORBIDDEN_PERMISSIONS or permission.startswith("https://"):
                errors.append(f"WB-DEFAULT-2 forbidden host permission {permission}")
        if "content_scripts" in manifest:
            errors.append("WB-DEFAULT-2 content_scripts must not be declared")
        if "externally_connectable" in manifest:
            errors.append("WB-DEFAULT-2 externally_connectable must not be declared")
        permissions = set(manifest.get("permissions") or [])
        if "storage" not in permissions:
            errors.append("WB-DEFAULT-2 storage permission missing")
        if "unlimitedStorage" in permissions:
            errors.append("WB-DEFAULT-2 unlimitedStorage forbidden")
    for path in (ROOT / "agent").rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="replace")
        if "skip_confirm" in text or "bypass_confirm" in text:
            errors.append(f"WB-DEFAULT-3 {path.relative_to(ROOT).as_posix()}: bypass switch detected")
    for item in errors:
        print(item, file=sys.stderr)
    print(f"WB-DEFAULT: capabilities={len(capabilities)} errors={len(errors)}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())