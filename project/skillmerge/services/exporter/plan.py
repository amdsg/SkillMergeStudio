from __future__ import annotations

import json
import re
from pathlib import PurePosixPath
from typing import Any, Dict, List

PREFERRED = (
    "name", "description", "description_zh", "description_en",
    "version", "author", "merged-from", "merge-plan", "source-hashes", "generator",
)
_SPECIAL = set(":#{[,&*!|>@`\"'\\")
_NUMBER = re.compile(r"^[-+]?\d+(?:\.\d+)?$")
_BOOL = {"true", "false", "yes", "no", "on", "off", "null", "~", "none"}


def layout_prefix(rule: Dict[str, Any], name: str) -> str:
    path = str(rule["package"]["skill_md_path"]).replace("<name>", name)
    parts = PurePosixPath(path).parts
    return "/".join(parts[:-1]) + "/" if len(parts) > 1 else ""


def skill_md_rel(rule: Dict[str, Any], name: str) -> str:
    return str(rule["package"]["skill_md_path"]).replace("<name>", name)


def _scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if (
        not text
        or text.strip() != text
        or any(char in _SPECIAL for char in text)
        or text.lower() in _BOOL
        or _NUMBER.match(text)
        or text.startswith(("-", "?", " "))
    ):
        return json.dumps(text, ensure_ascii=False)
    return text


def _dump(key: str, value: Any, indent: int = 0) -> List[str]:
    prefix = " " * indent
    if isinstance(value, str) and "\n" in value:
        return [f"{prefix}{key}: |"] + [" " * (indent + 2) + line for line in value.split("\n")]
    if isinstance(value, list):
        return [f"{prefix}{key}:"] + [" " * (indent + 2) + "- " + _scalar(item) for item in value]
    if isinstance(value, dict):
        lines = [f"{prefix}{key}:"]
        for sub in sorted(value.keys()):
            lines.extend(_dump(str(sub), value[sub], indent + 2))
        return lines
    return [f"{prefix}{key}: {_scalar(value)}"]


def render_frontmatter(data: Dict[str, Any]) -> str:
    keys = [key for key in PREFERRED if key in data]
    keys.extend(sorted(key for key in data if key not in PREFERRED))
    lines = ["---"]
    for key in keys:
        lines.extend(_dump(key, data[key]))
    lines.append("---")
    return "\n".join(lines) + "\n"


def build_adapt_plan(rule: Dict[str, Any], name: str, frontmatter: Dict[str, Any]) -> Dict[str, Any]:
    prefix = layout_prefix(rule, name)
    return {
        "naming": name,
        "layout": {"prefix": prefix, "skill_md_path": skill_md_rel(rule, name)},
        "frontmatter_patch": frontmatter,
        "steps": ["mkdir", "write_text", "copy_resource", "patch_frontmatter", "zip", "install_copy"],
    }