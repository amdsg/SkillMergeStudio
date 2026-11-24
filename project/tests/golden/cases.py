from __future__ import annotations

import json
import os

from tests.helpers import write_skill

CASES = [
    {
        "key": "g1_single",
        "name": "golden-g1",
        "aliases": [],
        "skills": [
            {
                "folder": "a",
                "name": "g1-a",
                "description": "单源合并",
                "body": "## 工作流\n\n步骤一：读取输入数据。\n\n步骤二：输出结果。",
            }
        ],
    },
    {
        "key": "g2_three_sources",
        "name": "golden-g2",
        "aliases": [],
        "skills": [
            {
                "folder": "a",
                "name": "g2-a",
                "description": "三源 A",
                "body": "## 工作流\n\n公共步骤：校验输入。\n\n步骤一：读取数据。",
            },
            {
                "folder": "b",
                "name": "g2-b",
                "description": "三源 B",
                "body": "## 工作流\n\n公共步骤：校验输入。\n\n步骤二：生成报告。",
            },
            {
                "folder": "c",
                "name": "g2-c",
                "description": "三源 C",
                "body": "## 工作流\n\n步骤三：保存产物。",
            },
        ],
    },
    {
        "key": "g3_conflicts",
        "name": "golden-g3",
        "aliases": [],
        "skills": [
            {"folder": "a", "name": "g3-a", "description": "冲突 A", "body": "## 方案\n\n甲方案内容"},
            {"folder": "b", "name": "g3-b", "description": "冲突 B", "body": "## 方案\n\n乙方案内容"},
        ],
    },
    {
        "key": "g4_resources",
        "name": "golden-g4",
        "aliases": [],
        "skills": [
            {
                "folder": "a",
                "name": "g4-a",
                "description": "资源 A",
                "body": "## 工作流\n\n步骤一：读取资源。",
                "assets": {"assets/logo.txt": "same", "assets/conflict.txt": "A"},
            },
            {
                "folder": "b",
                "name": "g4-b",
                "description": "资源 B",
                "body": "## 工作流\n\n步骤二：输出资源。",
                "assets": {"assets/logo.txt": "same", "assets/conflict.txt": "B"},
            },
        ],
    },
    {
        "key": "g5_aliases",
        "name": "golden-g5",
        "aliases": [{"from": "工作流程", "to": "工作流"}],
        "skills": [
            {"folder": "a", "name": "g5-a", "description": "别名 A", "body": "## 工作流程\n\n统一流程：先校验再输出。"},
            {"folder": "b", "name": "g5-b", "description": "别名 B", "body": "## 工作流\n\n统一流程：先校验再输出。"},
        ],
    },
]


def input_root(case) -> str:
    root = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(root, "..", "..", "fixtures", "golden", case["key"], "input")


def expected_root(case) -> str:
    root = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(root, "..", "..", "fixtures", "golden", case["key"], "expected")


def build_inputs(case, root: str) -> None:
    for skill in case["skills"]:
        write_skill(
            root,
            skill["folder"],
            skill["name"],
            skill["description"],
            skill["body"],
            skill.get("assets"),
        )


def source_names(case):
    return [skill["name"] for skill in case["skills"]]


def normalize_plan(text: str) -> str:
    data = json.loads(text)
    mapping = {}
    for index, source in enumerate(data.get("sources", [])):
        source["path"] = "<source>"
        source_id = source.get("skill_id")
        if source_id:
            mapping[source_id] = "<skill-%d>" % index
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    for source_id, placeholder in sorted(mapping.items(), key=lambda item: -len(item[0])):
        raw = raw.replace('"%s"' % source_id, '"%s"' % placeholder)
    return raw + "\n"