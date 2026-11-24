from __future__ import annotations

import hashlib
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from skillmerge.services.merger.merge_service import MergeOptions
from tests.golden.cases import CASES, build_inputs, expected_root, input_root, normalize_plan, source_names
from tests.helpers import build_env, named_skills, scan


def _copy_tree(source: str, target: str) -> None:
    for dirpath, dirnames, filenames in os.walk(source):
        dirnames.sort()
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, source)
            destination = os.path.join(target, rel)
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            shutil.copyfile(full, destination)


def _sums(target: str) -> None:
    lines = []
    for dirpath, dirnames, filenames in os.walk(target):
        dirnames.sort()
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, target).replace(os.sep, "/")
            if rel == "SHA256SUMS":
                continue
            with open(full, "rb") as handle:
                lines.append((hashlib.sha256(handle.read()).hexdigest(), rel))
    lines.sort(key=lambda item: item[1])
    with open(os.path.join(target, "SHA256SUMS"), "w", encoding="utf-8", newline="\n") as handle:
        for digest, rel in lines:
            handle.write(f"{digest}  {rel}\n")


def main() -> int:
    for case in CASES:
        root = input_root(case)
        os.makedirs(root, exist_ok=True)
        build_inputs(case, root)
        temp = tempfile.mkdtemp(prefix="sms_golden_")
        env = build_env(Path(temp))
        scan(env, root)
        skills = named_skills(env, source_names(case))
        if not all(skills):
            raise SystemExit(f"缺少 golden 输入：{case['key']}")
        result = env.merge.merge(
            skills,
            MergeOptions(name=case["name"], platform="generic", aliases=case["aliases"]),
        )
        target = expected_root(case)
        os.makedirs(target, exist_ok=True)
        _copy_tree(result["dir_path"], target)
        manifest = os.path.join(target, "manifest.json")
        if os.path.isfile(manifest):
            os.remove(manifest)
        with open(os.path.join(result["dir_path"], "merge_plan.json"), encoding="utf-8") as handle:
            normalized = normalize_plan(handle.read())
        with open(os.path.join(target, "merge_plan.json"), "w", encoding="utf-8", newline="\n") as handle:
            handle.write(normalized)
        _sums(target)
        print(f"generated {case['key']} -> {target}")
        env.db.close_all()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())