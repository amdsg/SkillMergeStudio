from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Tuple

from ...util.errors import DomainError
from .namer import slugify

MAX_TRIGGER = 40


def _sentence(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text:
        return ""
    for mark in ("。", "！", "？", ".", "!", "?"):
        index = text.find(mark)
        if index > 0:
            return text[: index + 1].strip()
    return text


def _unique(values: Iterable[str]) -> List[str]:
    result = []
    seen = set()
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen and text != "未分类":
            seen.add(text)
            result.append(text)
    return result


def _ensure_period(value: str) -> str:
    text = value.strip()
    return text if text.endswith(("。", ".", "！", "？")) else text + "。"


def rewrite_description(
    rule: Dict[str, Any],
    original: str,
    sources: List[Dict[str, Any]],
    chapters: List[str],
    trigger: str = "",
) -> Tuple[str, str]:
    maximum = int(rule["description"]["max_chars"])
    if original.strip() and len(original.strip()) <= maximum:
        return _ensure_period(original.strip()), "original"
    categories = "、".join(_unique(str(item.get("category", "")) for item in sources)[:3]) or "跨领域"
    names = [str(item.get("name", "")).strip() for item in sources if item.get("name")][:3]
    name_text = "、".join(names) or "多个技能"
    chapter_text = "、".join(_unique(chapters)[:3]) or "相关工作流"
    source_trigger = trigger.strip() or _sentence(str((sources[0] if sources else {}).get("description", "")))
    source_trigger = source_trigger[:MAX_TRIGGER].rstrip("。.！!？?") or "相关工作流"
    candidates = [
        f"合并 {len(sources)} 个技能（{categories}），涵盖 {name_text}。当任务涉及 {source_trigger} 时使用。",
        f"合并 {len(sources)} 个技能（{categories}），涵盖 {name_text}。",
        f"合并 {len(sources)} 个技能（{categories}），涵盖 {chapter_text}。",
        f"合并 {len(sources)} 个技能（{categories}）。",
        f"合并 {len(sources)} 个技能。",
    ]
    for index, candidate in enumerate(candidates, start=1):
        text = _ensure_period(candidate)
        if len(text) <= maximum:
            return text, f"L{index}"
    raise DomainError(
        "EXPORT_BLOCKED",
        "描述无法在不截断的情况下压到平台上限",
        f"手动填写不超过 {maximum} 字符的描述，或选择其他平台",
        466,
    )


def default_frontmatter(
    rule: Dict[str, Any],
    name: str,
    description: str,
    existing: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[Dict[str, str]]]:
    patch = dict(existing)
    patch["name"] = name
    patch["description"] = description
    warnings = []
    required = list(rule["frontmatter"].get("required", []))
    defaults = dict(rule["frontmatter"].get("defaults", {}))
    for key in required:
        if key in ("name", "description") and patch.get(key):
            continue
        if patch.get(key):
            continue
        if key == "description_zh":
            patch[key] = description
        elif key == "description_en":
            patch[key] = slugify(description) or "merged-skill"
        elif key in defaults:
            patch[key] = defaults[key]
        elif key == "version":
            patch[key] = "1.0.0"
        elif key == "author":
            patch[key] = "unknown"
        else:
            patch[key] = ""
        warnings.append(
            {
                "code": "DEFAULT_APPLIED",
                "level": "warn",
                "message": f"已为必填字段 {key} 补默认值",
                "fix": f"如需自定义，请在导出前填写 {key}",
            }
        )
    return patch, warnings