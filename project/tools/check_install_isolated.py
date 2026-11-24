#!/usr/bin/env python3
"""隔离安装根校验（M6 / T6-04c）。缺 --root 即拒绝，默认不写真实目录。"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from skillmerge.config import paths
from skillmerge.services.exporter.builder import prepare_spec
from skillmerge.services.exporter.installer import install_copy
from skillmerge.services.exporter.registry import PlatformRegistry
from skillmerge.services.parser.frontmatter import read_document

MAX_SNAPSHOT_ENTRIES = 20000


def _snapshot(root: Path):
    result = {}
    entries = 0
    if not root.exists():
        return result, False
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(name for name in dirnames if name not in (".trash", ".staging"))
        for name in sorted(filenames):
            entries += 1
            if entries > MAX_SNAPSHOT_ENTRIES:
                return result, True
            full = Path(dirpath) / name
            rel = full.relative_to(root).as_posix()
            if full.is_symlink():
                try:
                    result[rel] = "link:" + os.readlink(full)
                except OSError:
                    result[rel] = "link:?"
                continue
            try:
                result[rel] = "sha256:" + hashlib.sha256(full.read_bytes()).hexdigest()
            except OSError:
                result[rel] = "unreadable"
    return result, False


def _guard(root: Path, force: bool) -> str:
    if "~" in str(root):
        return "VERIFY_TILDE_PATH"
    try:
        real = root.resolve()
        home = Path.home().resolve()
    except OSError:
        return "VERIFY_PATH_INVALID"
    if (real == home or home in real.parents) and not force:
        return "VERIFY_ESCAPE_REAL_HOME"
    return ""


def _blocked(missing, extra=None):
    payload = {"result": "blocked", "missing": missing}
    if extra:
        payload.update(extra)
    print(json.dumps(payload, ensure_ascii=False))
    return 2


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    target = path.with_name(path.stem + "-" + stamp + path.suffix)
    if not target.exists():
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def _run_install(root: Path, source: Path, args):
    document = read_document(str(source / "SKILL.md"))
    registry = PlatformRegistry(paths.platforms_dir())
    entry = registry.entry(args.platform)
    if entry is None:
        return _blocked(["missing_platform"])
    rule = entry.as_rule()
    target_root = root / "skills"
    rule["install"] = {"project": str(target_root)}
    name = args.name or str(document.frontmatter.get("name") or source.name)
    spec = prepare_spec(str(source), rule, name, document.description(), "install")
    before, before_truncated = _snapshot(target_root)
    target, checks = install_copy(
        str(source), rule, args.scope, name, spec, str(root), str(root / ".trash")
    )
    after, after_truncated = _snapshot(target_root)
    changed = sorted(key for key in before if key in after and before[key] != after[key])
    removed = sorted(key for key in before if key not in after)
    truncated = before_truncated or after_truncated
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "platform": args.platform,
        "scope": args.scope,
        "install": {
            "executed": True,
            "target": str(target),
            "existing_unchanged": not changed and not removed,
            "changed": changed[:20],
            "removed": removed[:20],
            "truncated": truncated,
            "checks": checks,
        },
        "result": "partial" if truncated else ("pass" if not changed and not removed else "fail"),
    }
    _write(ROOT / "reports" / "install-isolated.json", payload)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload["result"] == "pass" else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="隔离安装根校验")
    parser.add_argument("--root", default="")
    parser.add_argument("--source", default="")
    parser.add_argument("--platform", default="generic")
    parser.add_argument("--scope", default="project")
    parser.add_argument("--name", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--i-understand-this-is-isolated", action="store_true")
    args = parser.parse_args(argv)

    if not args.root:
        return _blocked(
            ["missing_isolated_root"],
            {"install": {"executed": False, "scope": "temp_only"}, "notes": ["--root 无默认值；默认不写真实目录"]},
        )
    root = Path(args.root)
    reason = _guard(root, args.i_understand_this_is_isolated)
    if reason:
        return _blocked([reason])
    root.mkdir(parents=True, exist_ok=True)
    if not os.access(root, os.W_OK):
        return _blocked(["root_not_writable"])
    if not args.source:
        return _blocked(["missing_source"], {"root": str(root)})
    source = Path(args.source)
    if not (source / "SKILL.md").is_file():
        return _blocked(["missing_artifact"])
    if args.dry_run:
        print(json.dumps({"result": "planned", "root": str(root), "source": str(source)}, ensure_ascii=False))
        return 0
    return _run_install(root, source, args)


if __name__ == "__main__":
    raise SystemExit(main())