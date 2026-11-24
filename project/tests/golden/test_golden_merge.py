from __future__ import annotations

import hashlib
import json
import os

import pytest

from skillmerge.services.merger.merge_service import MergeOptions
from tests.golden.cases import CASES, expected_root, input_root, normalize_plan, source_names
from tests.helpers import build_env, named_skills, scan


def _file_map(root):
    result = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            with open(full, "rb") as handle:
                result[rel] = handle.read()
    result.pop("manifest.json", None)
    result.pop("SHA256SUMS", None)
    return result


def _verify_sums(expected):
    sums_path = os.path.join(expected, "SHA256SUMS")
    assert os.path.isfile(sums_path), "运行 python tools/make_golden.py 生成 golden"
    listed = set()
    with open(sums_path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            digest, rel = line.split("  ", 1)
            listed.add(rel)
            with open(os.path.join(expected, rel), "rb") as target:
                actual = hashlib.sha256(target.read()).hexdigest()
            assert actual == digest, f"golden 文件被修改：{rel}"
    assert listed == set(_file_map(expected).keys())


@pytest.mark.parametrize("case", CASES, ids=[case["key"] for case in CASES])
def test_golden_merge_bytes(case, tmp_path):
    expected = expected_root(case)
    _verify_sums(expected)
    root = input_root(case)
    assert os.path.isdir(root), f"缺少 golden 输入：{root}"
    env = build_env(tmp_path)
    scan(env, root)
    skills = named_skills(env, source_names(case))
    assert all(skills)
    options = MergeOptions(
        name=case["name"],
        platform="generic",
        strategy="keep-all",
        aliases=case["aliases"],
    )
    first = env.merge.merge(skills, options)
    actual = _file_map(first["dir_path"])
    expected_files = _file_map(expected)
    actual_plan = actual.pop("merge_plan.json").decode("utf-8")
    expected_plan = expected_files.pop("merge_plan.json").decode("utf-8")
    assert set(actual.keys()) == set(expected_files.keys())
    assert actual == expected_files
    assert normalize_plan(actual_plan) == normalize_plan(expected_plan)
    manifest = json.load(open(os.path.join(first["dir_path"], "manifest.json"), encoding="utf-8"))
    assert manifest["created_at"]
    assert manifest["platform"] == "generic"

    second = env.merge.merge(skills, options)
    with open(os.path.join(second["dir_path"], "SKILL.md"), "rb") as handle:
        assert handle.read() == actual["SKILL.md"]
    with open(os.path.join(second["dir_path"], "merge_plan.json"), encoding="utf-8") as handle:
        assert normalize_plan(handle.read()) == normalize_plan(expected_plan)
    env.db.close_all()