from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List, Optional

from ...util.textnorm import heading_key, normalize_heading
from ..merger.conflict import format_conflict, format_suggest, sim_text
from ..merger.dependencies import environment_section
from ..merger.paragraphs import dedupe_group

STANDARD_KEYS = {
    "name", "description", "version", "author", "merged-from", "merge-plan",
    "source-hashes", "generator",
}
_SPECIAL = set(":#{[,&*!|>@`\"'")
_NUMBER = re.compile(r"^[-+]?\d+(?:\.\d+)?$")
_BOOL_NULL = {"true", "false", "yes", "no", "on", "off", "null", "~", "none"}


def _manual_action(decisions: Optional[Dict[str, Any]], group: Dict[str, Any]) -> str:
    raw = (decisions or {}).get(group["key"]) or (decisions or {}).get(group["norm"])
    if isinstance(raw, dict):
        raw = raw.get("action")
    action = str(raw or "")
    return action if action in ("keepA", "keepB", "keepBoth", "manual") else ""


def _select_members(group: Dict[str, Any], strategy: str, action: str):
    members = sorted(group["members"], key=lambda item: (int(item["source_index"]), int(item["line"])))
    if action in ("keepA", "keepB"):
        selected = [members[0] if action == "keepA" else members[-1]]
    elif action in ("keepBoth", "manual") or group["decision"] != "auto":
        selected = list(members)
    elif strategy == "prefer-first":
        selected = [members[0]]
    elif strategy == "prefer-largest":
        selected = [max(members, key=lambda item: (len(item["body"]), -int(item["source_index"])))]
    else:
        selected = list(members)
    omitted = [member for member in members if member not in selected]
    return selected, omitted


def _comment_for(group: Dict[str, Any], member: Dict[str, Any], action: str) -> str:
    if action in ("keepA", "keepB") and group["decision"] in ("conflict", "suggest"):
        return ""
    value = group.get("sim")
    if group["decision"] == "conflict":
        return format_conflict(member.get("source_label", "unknown"), member.get("norm", ""), value)
    if group["decision"] == "suggest":
        return format_suggest(member.get("source_label", "unknown"), member.get("norm", ""), value)
    return ""


def _omitted_entries(group: Dict[str, Any], omitted: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "skill_id": member["skill_id"],
            "chapter_key": group["key"],
            "char_count": len(member["body"]),
            "body_hash": member["body_hash"],
        }
        for member in omitted
    ]


def _prepare_group(group: Dict[str, Any], strategy: str, action: str) -> Optional[Dict[str, Any]]:
    selected, omitted = _select_members(group, strategy, action)
    dedupe = dedupe_group(selected)
    kept_by_id = {item["skill_id"]: item["paragraphs"] for item in dedupe["kept"]}
    members_out = []
    for member in selected:
        paragraphs = kept_by_id.get(member["skill_id"], [])
        if not paragraphs and group["decision"] == "auto":
            continue
        members_out.append(
            {
                "skill_id": member["skill_id"],
                "source_index": int(member["source_index"]),
                "source_label": member.get("source_label", ""),
                "line": int(member["line"]),
                "paragraphs": [item["text"] for item in paragraphs],
                "comment": _comment_for(group, member, action),
            }
        )
    if not members_out:
        return None
    return {
        "key": group["key"],
        "norm": group["norm"],
        "title": group["title"],
        "level": int(group["level"]),
        "decision": group["decision"],
        "sim": group.get("sim"),
        "members": members_out,
        "omitted": _omitted_entries(group, omitted),
        "dropped": dedupe["dropped"],
        "near_dupes": dedupe["near_dupes"],
    }


def prepare_chapters(
    chapter_map: List[Dict[str, Any]],
    strategy: str = "keep-all",
    decisions: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    prepared = []
    dropped: List[Dict[str, Any]] = []
    near_dupes: List[Dict[str, Any]] = []
    warnings: List[Dict[str, str]] = []
    for group in chapter_map:
        action = _manual_action(decisions, group)
        if strategy == "manual" and group["decision"] == "auto" and not action:
            warnings.append(
                {
                    "code": "MANUAL_DECISION_MISSING",
                    "level": "warn",
                    "message": f"章节 {group['title']} 缺少 manual 决策，已保留双方",
                    "fix": "在预览中为每个章节选择 keepA / keepB / keepBoth",
                }
            )
        item = _prepare_group(group, strategy, action)
        if item is None:
            continue
        dropped.extend(item["dropped"])
        near_dupes.extend(item["near_dupes"])
        prepared.append(item)
    return {
        "chapters": prepared,
        "dropped": dropped,
        "near_dupes": near_dupes,
        "warnings": warnings,
        "duplicate_paragraphs": len(dropped),
        "suggested_near_dupes": len(near_dupes),
    }


def default_description(name: str, sources: List[Dict[str, Any]]) -> str:
    categories = sorted({str(item.get("category") or "") for item in sources} - {"", "未分类"})
    names = [str(item.get("name") or "") for item in sources if item.get("name")]
    category_text = "、".join(categories) if categories else "跨领域"
    name_text = "、".join(names[:3]) + ("等" if len(names) > 3 else "")
    return f"合并 {len(sources)} 个技能（{category_text}），涵盖 {name_text}，当任务涉及相关工作流时使用。"


def _needs_quote(text: str) -> bool:
    value = text.strip()
    if value != text or not value:
        return True
    if any(char in _SPECIAL for char in value):
        return True
    if value.lower() in _BOOL_NULL or _NUMBER.match(value):
        return True
    if value.startswith(("-", "?", " ")):
        return True
    return False


def _scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if _needs_quote(text):
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return text


def _dump_value(key: str, value: Any, indent: int = 0) -> List[str]:
    prefix = " " * indent
    if isinstance(value, str) and "\n" in value:
        lines = [f"{prefix}{key}: |"]
        lines.extend(" " * (indent + 2) + line for line in value.split("\n"))
        return lines
    if isinstance(value, list):
        lines = [f"{prefix}{key}:"]
        for item in value:
            lines.append(" " * (indent + 2) + "- " + _scalar(item))
        return lines
    if isinstance(value, dict):
        lines = [f"{prefix}{key}:"]
        for sub_key in sorted(value.keys()):
            lines.extend(_dump_value(str(sub_key), value[sub_key], indent + 2))
        return lines
    return [f"{prefix}{key}: {_scalar(value)}"]


def render_frontmatter(name: str, description: str, sources: List[Dict[str, Any]]) -> str:
    lines = ["---"]
    entries = [
        ("name", name),
        ("description", description),
        ("version", "1.0.0"),
        ("author", "Skill Merge Studio"),
        ("merged-from", [f'{source.get("name", "")} ({source.get("platform", "unknown")})' for source in sources]),
        ("merge-plan", "./merge_plan.json"),
        ("source-hashes", [f"sha256:{source['source_hash']}" for source in sources]),
        ("generator", "skillmerge-studio/1.0.0"),
    ]
    for key, value in entries:
        lines.extend(_dump_value(key, value))
    extras: Dict[str, Any] = {}
    for source in sources:
        for key, value in dict(source.get("frontmatter") or {}).items():
            if key not in STANDARD_KEYS and key not in extras and not isinstance(value, dict):
                extras[key] = value
    for key in sorted(extras.keys()):
        lines.extend(_dump_value(key, extras[key]))
    lines.append("---")
    return "\n".join(lines)


def _generated_title(base: str, prepared: List[Dict[str, Any]]) -> str:
    norms = {str(item["norm"]) for item in prepared}
    return base if normalize_heading(base) not in norms else base + "（合并生成）"


def _render_sources(sources: List[Dict[str, Any]]) -> str:
    lines = ["## 来源说明", "", f"本次合并来自 {len(sources)} 个技能：", ""]
    for source in sources:
        lines.append(f'- {source.get("name", "")}（{source.get("platform", "unknown")}）')
    return "\n".join(lines)


def _render_body(prepared: List[Dict[str, Any]]) -> str:
    blocks = []
    for chapter in prepared:
        level = max(2, min(6, int(chapter["level"])))
        lines = ["#" * level + " " + (chapter["title"] or "未命名章节")]
        for member in chapter["members"]:
            if member.get("comment"):
                lines.extend(["", member["comment"], ""])
            text = "\n\n".join(member["paragraphs"])
            if text:
                lines.extend(["", text])
        blocks.append("\n".join(lines).rstrip())
    return "\n\n".join(blocks)


def _render_report(
    strategy: str,
    sources: List[Dict[str, Any]],
    prepared: List[Dict[str, Any]],
    dedup: Dict[str, Any],
    title: str,
) -> str:
    conflicts = [item for item in prepared if item["decision"] == "conflict"]
    suggests = [item for item in prepared if item["decision"] == "suggest"]
    reviews = [item for item in prepared if item["decision"] == "review"]
    omitted = [entry for item in prepared for entry in item["omitted"]]
    lines = [
        f"## {title}",
        "",
        f"- 策略：{strategy}",
        f"- 源技能：{len(sources)} 个",
        f"- 完全相同段落去重：{int(dedup.get('duplicate_paragraphs', 0))}",
        f"- 近重复建议（未删除）：{int(dedup.get('suggested_near_dupes', 0))}",
        f"- 冲突章节：{len(conflicts)}",
        f"- 建议合并章节：{len(suggests)}",
        f"- 差异较大需复核：{len(reviews)}",
        "- 生成器：skillmerge-studio/1.0.0",
    ]
    if conflicts:
        lines.extend(["", "### 冲突章节", ""])
        for item in conflicts:
            labels = " / ".join(sorted({member["source_label"] for member in item["members"]}))
            lines.append(f'- {item["title"]}（sim={sim_text(item.get("sim"))}）：{labels}')
    if suggests:
        lines.extend(["", "### 建议合并章节（需人工确认）", ""])
        for item in suggests:
            labels = " / ".join(sorted({member["source_label"] for member in item["members"]}))
            lines.append(f'- {item["title"]}（sim={sim_text(item.get("sim"))}）：{labels}')
    if reviews:
        lines.extend(["", "### 差异较大，提示复核", ""])
        for item in reviews:
            lines.append(f'- {item["title"]}（sim={sim_text(item.get("sim"))}）')
    if omitted:
        lines.extend(["", "### 已省略内容（可由 merge_plan 回滚）", ""])
        for entry in omitted:
            lines.append(f'- {entry["chapter_key"]}：{entry["skill_id"]}（{entry["char_count"]} 字符）')
    return "\n".join(lines)


def assemble_document(
    name: str,
    description: str,
    sources: List[Dict[str, Any]],
    prepared: List[Dict[str, Any]],
    packages: List[Dict[str, str]],
    dedup: Dict[str, Any],
    strategy: str,
) -> str:
    frontmatter = render_frontmatter(name, description, sources)
    h1 = "# " + name
    sources_section = _render_sources(sources)
    env_title = _generated_title("环境要求", prepared)
    env_section = environment_section(packages)
    if env_section:
        env_section = env_section.replace("## 环境要求", f"## {env_title}", 1).rstrip()
    body = _render_body(prepared)
    report_title = _generated_title("合并报告", prepared)
    report = _render_report(strategy, sources, prepared, dedup, report_title)
    parts = [frontmatter, h1, sources_section]
    if env_section:
        parts.append(env_section)
    if body:
        parts.append(body)
    parts.append(report)
    text = "\n\n".join(parts).rstrip() + "\n"
    return text


def estimate_volume(text: str, resources: Iterable[Dict[str, Any]] = ()) -> int:
    return len(text.encode("utf-8")) + sum(int(item.get("size_bytes", 0)) for item in resources)


def trim_suggestions(prepared: List[Dict[str, Any]], current_bytes: int, limit_bytes: int) -> List[Dict[str, Any]]:
    chapters = []
    for chapter in prepared:
        content = "\n\n".join(
            "\n\n".join(member["paragraphs"]) for member in chapter["members"]
        )
        size = len(("\n\n".join([chapter["title"], content])).encode("utf-8"))
        priority = 3
        norm = str(chapter["norm"])
        if any(word in norm for word in ("示例", "例子", "example", "附录", "appendix")):
            priority = 1
        elif any(word in norm for word in ("参考", "reference", "扩展", "背景")):
            priority = 2
        elif any(word in norm for word in ("工作流", "流程", "约束", "要求", "workflow")):
            priority = 4
        chapters.append(
            {"chapter": chapter["title"], "bytes": size, "priority": priority}
        )
    chapters.sort(key=lambda item: (item["priority"], -item["bytes"], item["chapter"]))
    result = []
    projected = current_bytes
    for item in chapters:
        if projected <= limit_bytes:
            break
        projected -= item["bytes"]
        result.append(dict(item, projected_bytes=max(0, projected)))
    return result