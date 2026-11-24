"""Merge preview: chapter alignment, conflicts, deterministic bytes, zero writes."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from agent.core.paths import data_dir
from agent.http.errors import DomainError

DOWNLOADS = data_dir() / "downloads"
HEADING = re.compile(r"^(#{1,6})\s+(.+)$", re.M)


def _body(raw: bytes) -> dict:
    if not raw:
        return {}
    data = json.loads(raw.decode("utf-8"))
    return data if isinstance(data, dict) else {}


def _sections(text: str) -> list[tuple[str, str]]:
    matches = list(HEADING.finditer(text))
    if not matches:
        return [("", text.strip())]
    result = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        result.append((match.group(2).strip(), text[start:end].strip()))
    return result


def _load_source(name: str) -> str:
    source = DOWNLOADS / name
    if not source.exists():
        raise DomainError("E_SOURCE_NOT_DOWNLOADED", "wb.error.source_not_downloaded",
                          params={"source": name}, fix_key="wb.fix.redownload_source")
    entry = source / "SKILL.md" if source.is_dir() else source
    if entry.is_file():
        return entry.read_text(encoding="utf-8", errors="replace")
    candidate = next((item for item in sorted(source.rglob("*.md"))), None) if source.is_dir() else None
    if candidate is None:
        raise DomainError("E_SOURCE_NOT_DOWNLOADED", "wb.error.source_not_downloaded",
                          params={"source": name}, fix_key="wb.fix.redownload_source")
    return candidate.read_text(encoding="utf-8", errors="replace")


def preview_endpoint(params, body, request_id):
    payload = _body(body)
    sources = [str(name) for name in payload.get("sources") or []]
    if len(sources) < 2:
        raise DomainError("E_MERGE_SOURCES_INSUFFICIENT", "wb.error.merge_sources",
                          params={"count": len(sources)}, fix_key="wb.fix.check_input")
    texts = [_load_source(name) for name in sources]
    chapter_map: dict[str, list[tuple[str, str]]] = {}
    for name, text in zip(sources, texts):
        for title, content in _sections(text):
            chapter_map.setdefault(title, []).append((name, content))
    conflicts = []
    blocks = []
    for title in sorted(chapter_map):
        entries = chapter_map[title]
        unique = {content for _, content in entries}
        if len(unique) > 1:
            conflicts.append({"chapter": title, "sources": [name for name, _ in entries]})
            blocks.append(f"## {title}\n")
            for name, content in entries:
                blocks.append(f"<!-- source: {name} -->\n{content}\n")
        else:
            blocks.append(f"## {title}\n{entries[0][1]}\n")
    merged = "\n".join(blocks).strip() + "\n"
    merge_plan = {
        "version": 1,
        "strategy": str(payload.get("strategy", "keep-all")),
        "conflict_count": len(conflicts),
    }
    digest = hashlib.sha256((merged + json.dumps(merge_plan, sort_keys=True)).encode("utf-8")).hexdigest()[:16]
    return {
        "dry_run": True,
        "sources": sources,
        "merge_plan": merge_plan,
        "conflicts": conflicts,
        "bytes": len(merged.encode("utf-8")),
        "plan_hash": digest,
        "diff": [{"chapter": item["chapter"], "state": "conflict"} for item in conflicts],
        "merged_text": merged,
        "writes": 0,
    }