#!/usr/bin/env python3
"""Engine directory hash snapshot: before/after agent runs must match."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

WB_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = WB_ROOT.parent
TARGETS = ("skillmerge", "platforms")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot() -> dict:
    files = {}
    for name in TARGETS:
        base = PROJECT_ROOT / name
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            files[path.relative_to(PROJECT_ROOT).as_posix()] = sha256_file(path)
    return {"count": len(files), "files": files}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="engine hash snapshot")
    parser.add_argument("--write", default="")
    parser.add_argument("--compare", default="")
    args = parser.parse_args(argv)
    current = snapshot()
    if args.write:
        out = Path(args.write)
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(out.suffix + ".tmp")
        tmp.write_text(json.dumps(current, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
        os.replace(tmp, out)
        print(f"WB-HASH: wrote {out} files={current['count']}")
        return 0
    if args.compare:
        path = Path(args.compare)
        if not path.is_file():
            print(f"WB-HASH: baseline missing {path}", file=sys.stderr)
            return 2
        baseline = json.loads(path.read_text(encoding="utf-8"))
        before = baseline.get("files") or {}
        after = current["files"]
        added = sorted(set(after) - set(before))
        removed = sorted(set(before) - set(after))
        changed = sorted(key for key in set(before) & set(after) if before[key] != after[key])
        for item in added:
            print(f"WB-HASH-1 added {item}", file=sys.stderr)
        for item in removed:
            print(f"WB-HASH-1 removed {item}", file=sys.stderr)
        for item in changed:
            print(f"WB-HASH-1 changed {item}", file=sys.stderr)
        print(f"WB-HASH: baseline={baseline.get('count')} current={current['count']} changed={len(added) + len(removed) + len(changed)}")
        return 0 if not (added or removed or changed) else 1
    print(f"WB-HASH: files={current['count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())