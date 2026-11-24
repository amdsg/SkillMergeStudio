from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Optional

from ...util.hashing import sha256_text
from .dependencies import install_command


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def _chapter_record(group: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "key": group["key"],
        "norm": group["norm"],
        "title": group["title"],
        "level": int(group["level"]),
        "first_seen_rank": int(group["first_seen_rank"]),
        "aliases_hit": bool(group.get("aliases_hit")),
        "cross_title": bool(group.get("cross_title")),
        "decision": group["decision"],
        "sim": group.get("sim"),
        "members": [
            {
                "skill_id": member["skill_id"],
                "line": int(member["line"]),
                "body_hash": member["body_hash"],
                "source_index": int(member["source_index"]),
                "title": member["title"],
                "norm": member["norm"],
            }
            for member in group["members"]
        ],
        "sim_pairs": group.get("sim_pairs", []),
    }


def build_plan(
    name: str,
    strategy: str,
    sources: List[Dict[str, Any]],
    chapter_map: List[Dict[str, Any]],
    resource_decisions: Iterable[Dict[str, Any]],
    packages: List[Dict[str, str]],
    dedup: Dict[str, Any],
    decisions: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    plan = {
        "plan_version": 1,
        "name": name,
        "strategy": strategy,
        "sources": [
            {
                "skill_id": source["skill_id"],
                "source_hash": source["source_hash"],
                "path": source["path"],
                "name": source.get("name", ""),
                "category": source.get("category", ""),
                "platform": source.get("platform", ""),
            }
            for source in sources
        ],
        "chapter_map": [_chapter_record(group) for group in chapter_map],
        "decisions": [
            {"key": key, "action": action}
            for key, action in sorted((decisions or {}).items())
        ],
        "resource_decisions": list(resource_decisions),
        "dependency_summary": {
            "packages": packages,
            "command": install_command(packages),
        },
        "omitted": list(dedup.get("omitted", [])),
        "dedup": {
            "duplicate_paragraphs": int(dedup.get("duplicate_paragraphs", 0)),
            "suggested_near_dupes": int(dedup.get("suggested_near_dupes", 0)),
            "dropped": list(dedup.get("dropped", [])),
            "near_dupes": list(dedup.get("near_dupes", [])),
        },
    }
    return plan


def plan_hash(plan: Dict[str, Any]) -> str:
    return sha256_text(canonical_json(plan))