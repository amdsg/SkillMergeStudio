from __future__ import annotations

import difflib
import json
from typing import Any, Dict, List

MIN_RETENTION = 0.5


def _compact(text: str) -> str:
    return "".join(str(text).split())


def build_prompt(name: str, chapters: List[Dict[str, Any]]) -> str:
    payload = [
        {"key": str(item.get("key", "")), "title": str(item.get("title", "")), "text": str(item.get("text", ""))}
        for item in chapters
    ]
    return (
        "你是技能文档整合助手。只做章节级整合，必须保留全部事实、命令、代码块、链接与参数；"
        "禁止摘要、禁止压缩、禁止删除步骤。只返回严格 JSON，不要 Markdown。格式："
        '{"suggestions":[{"key":"章节key","text":"整合后的完整章节正文"}]}。'
        "只能使用输入中存在的 key；无法改进时不返回该 key。"
        f"产物名称：{name}。章节：{json.dumps(payload, ensure_ascii=False)}"
    )


def _strip_fence(text: str) -> str:
    value = text.strip()
    if value.startswith("```"):
        first = value.find("\n")
        last = value.rfind("```")
        if first != -1 and last > first:
            return value[first + 1:last].strip()
    return value


def parse_suggestions(raw: str, chapters: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    parsed = json.loads(_strip_fence(str(raw or "")))
    rows = parsed.get("suggestions") if isinstance(parsed, dict) else None
    if not isinstance(rows, list):
        raise ValueError("AI JSON 缺少 suggestions 数组")
    result: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("suggestions 项不是对象")
        key = str(row.get("key", ""))
        body = str(row.get("text", "")).strip()
        chapter = chapters.get(key)
        if chapter is None or not body:
            continue
        before = _compact(chapter["text"])
        after = _compact(body)
        if before and len(after) < len(before) * MIN_RETENTION:
            continue
        if before and after == before:
            continue
        result.append(
            {
                "key": key,
                "title": str(chapter["title"]),
                "before_chars": len(before),
                "after_chars": len(after),
                "before": chapter["text"],
                "text": body,
                "diff": diff_text(chapter["text"], body),
            }
        )
    return result


def diff_text(old: str, new: str) -> List[str]:
    return list(
        difflib.unified_diff(
            str(old).splitlines(),
            str(new).splitlines(),
            fromfile="before",
            tofile="after",
            lineterm="",
            n=1,
        )
    )


def apply_suggestions(chapters: List[Dict[str, Any]], suggestions: List[Dict[str, Any]], confirmed: List[str]) -> int:
    by_key = {str(item.get("key")): str(item.get("text", "")) for item in suggestions}
    allowed = set(str(item) for item in confirmed)
    applied = 0
    for chapter in chapters:
        key = str(chapter.get("key", ""))
        if key in by_key and key in allowed:
            chapter["text"] = by_key[key]
            applied += 1
    return applied