from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from typing import Any, Dict, List, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from skillmerge.services.exporter.platform_registry.migrate_v1 import normalize_v1, normalize_v2
from skillmerge.services.exporter.platform_registry.loader import load_registry

BACKUP = ".backup-v1"
CHANGELOG = "CHANGELOG-platforms.md"


def _files(directory: str) -> List[str]:
    return [
        name
        for name in sorted(os.listdir(directory))
        if name.endswith(".json") and name != "schema.json" and not name.endswith(".meta.json")
    ]


def _read(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _migrate(raw: Dict[str, Any]) -> Dict[str, Any]:
    version = int(raw.get("rule_schema_version", 1))
    if version == 1:
        return normalize_v1(raw)
    if version == 2:
        return normalize_v2(raw)
    raise SystemExit(f"不支持的 rule_schema_version={version}")


def _write(path: str, data: Dict[str, Any]) -> None:
    payload = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def _hash(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _counts(directory: str) -> Tuple[Dict[str, int], List[str]]:
    result = load_registry(directory)
    return result.counts.as_dict(), [entry.id for entry in result.entries]


def check(directory: str) -> int:
    before_counts, before_ids = _counts(directory)
    with tempfile.TemporaryDirectory(prefix="sms_migrate_") as temp:
        shutil.copyfile(os.path.join(directory, "schema.json"), os.path.join(temp, "schema.json"))
        for name in _files(directory):
            payload = _migrate(_read(os.path.join(directory, name)))
            with open(os.path.join(temp, name), "w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
        after_counts, after_ids = _counts(temp)
    same_counts = before_counts == after_counts
    same_ids = sorted(before_ids) == sorted(after_ids)
    legacy = 0
    for name in _files(directory):
        payload = _migrate(_read(os.path.join(directory, name)))
        if payload.get("legacy_limits"):
            legacy += 1
    print(f"预计 counts 变化 0：{'是' if same_counts else '否'}")
    print(f"基线 id 集合不变：{'是' if same_ids else '否'}")
    print(f"将写入 legacy_limits 的条目：{legacy}")
    print(f"before={before_counts}")
    print(f"after ={after_counts}")
    return 0 if same_counts and same_ids else 1


def _backup(directory: str) -> str:
    target = os.path.join(directory, BACKUP)
    if os.path.isdir(target) and os.listdir(target):
        return target
    os.makedirs(target, exist_ok=True)
    for name in _files(directory):
        shutil.copyfile(os.path.join(directory, name), os.path.join(target, name))
    return target


def _changelog(directory: str, rows: List[Dict[str, Any]]) -> None:
    path = os.path.join(directory, CHANGELOG)
    lines = []
    if not os.path.isfile(path):
        lines.append("# Platform rules migration changelog\n\n")
    lines.append("## 2026-11-22 M3b v1 → v2\n\n")
    lines.append("| file | id | legacy_limits | old_sha256 | new_sha256 |\n")
    lines.append("| --- | --- | --- | --- | --- |\n")
    for row in rows:
        lines.append(
            f"| {row['file']} | {row['id']} | {row['legacy']} | {row['old']} | {row['new']} |\n"
        )
    with open(path, "a", encoding="utf-8", newline="\n") as handle:
        handle.writelines(lines)


def apply(directory: str) -> int:
    before_counts, before_ids = _counts(directory)
    backup = _backup(directory)
    rows = []
    for name in _files(directory):
        path = os.path.join(directory, name)
        raw = _read(path)
        migrated = _migrate(raw)
        old_hash = _hash(path)
        if int(raw.get("rule_schema_version", 1)) == 1:
            _write(path, migrated)
        rows.append(
            {
                "file": name,
                "id": str(migrated["id"]),
                "legacy": bool(migrated.get("legacy_limits")),
                "old": old_hash,
                "new": _hash(path),
            }
        )
    after_counts, after_ids = _counts(directory)
    changed = [row for row in rows if row["old"] != row["new"]]
    if changed:
        _changelog(directory, changed)
    print(f"备份目录：{backup}")
    print(f"迁移文件：{len(rows)}")
    print(f"counts 变化：{'0' if before_counts == after_counts else before_counts}")
    print(f"id 集合不变：{'是' if sorted(before_ids) == sorted(after_ids) else '否'}")
    print(f"after={after_counts}")
    return 0 if before_counts == after_counts and sorted(before_ids) == sorted(after_ids) else 1


def rollback(directory: str) -> int:
    backup = os.path.join(directory, BACKUP)
    if not os.path.isdir(backup):
        print("没有 .backup-v1，无法回滚")
        return 1
    for name in sorted(os.listdir(backup)):
        if name.endswith(".json"):
            shutil.copyfile(os.path.join(backup, name), os.path.join(directory, name))
    counts, _ids = _counts(directory)
    print(f"已回滚到 {backup}")
    print(f"counts={counts}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="migrate_registry.py")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--apply", action="store_true")
    group.add_argument("--rollback", action="store_true")
    parser.add_argument("--directory", default=os.path.join(ROOT, "platforms"))
    args = parser.parse_args(argv)
    directory = os.path.abspath(args.directory)
    if args.check:
        return check(directory)
    if args.apply:
        return apply(directory)
    return rollback(directory)


if __name__ == "__main__":
    raise SystemExit(main())