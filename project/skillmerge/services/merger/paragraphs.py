from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from ...util.hashing import sha256_text
from ...util.textnorm import normalize_paragraph
from .similarity import similarity

FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
NEAR_DUPLICATE = 0.90
MAX_NEAR_COMPARISONS = 400


def split_paragraphs(text: str) -> List[Dict[str, Any]]:
    lines = (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    paragraphs: List[Dict[str, Any]] = []
    buffer: List[str] = []
    fence = None
    start = 0

    def flush() -> None:
        nonlocal buffer, start
        raw = "\n".join(buffer).strip("\n")
        if raw.strip():
            norm = normalize_paragraph(raw)
            paragraphs.append(
                {
                    "index": len(paragraphs),
                    "text": raw,
                    "norm": norm,
                    "hash": sha256_text(norm),
                }
            )
        buffer = []
        start = 0

    for index, line in enumerate(lines, start=1):
        match = FENCE_RE.match(line)
        if fence is None:
            if match:
                if buffer:
                    flush()
                marker = match.group(1)
                fence = (marker[0], len(marker))
                buffer = [line]
                start = index
                continue
            if not line.strip():
                flush()
                continue
            if not buffer:
                start = index
            buffer.append(line)
            continue
        buffer.append(line)
        if match:
            marker = match.group(1)
            if marker[0] == fence[0] and len(marker) >= fence[1] and not line.strip()[len(marker):]:
                fence = None
                flush()
    if buffer:
        flush()
    return paragraphs


def _near_dupes(kept_hashes: Dict[str, Dict[str, Any]], paragraph: Dict[str, Any], budget: List[int]) -> List[Dict[str, Any]]:
    result = []
    if len(paragraph["norm"]) < 20:
        return result
    for other_hash, other in sorted(kept_hashes.items()):
        if other_hash == paragraph["hash"]:
            continue
        if other["skill_id"] == paragraph["skill_id"]:
            continue
        if budget[0] >= MAX_NEAR_COMPARISONS:
            break
        budget[0] += 1
        value = similarity(paragraph["text"], other["text"]).value
        if value is not None and value >= NEAR_DUPLICATE:
            result.append(
                {
                    "a_hash": other_hash,
                    "b_hash": paragraph["hash"],
                    "sim": value,
                    "a_source": other["skill_id"],
                    "b_source": paragraph["skill_id"],
                }
            )
    return result


def dedupe_group(members: List[Dict[str, Any]]) -> Dict[str, Any]:
    ordered = sorted(members, key=lambda item: int(item.get("source_index", 0)))
    seen: Dict[str, Dict[str, Any]] = {}
    kept: List[Dict[str, Any]] = []
    dropped: List[Dict[str, Any]] = []
    near_dupes: List[Dict[str, Any]] = []
    budget = [0]
    for member in ordered:
        skill_id = str(member.get("skill_id", ""))
        kept_paragraphs = []
        for paragraph in split_paragraphs(str(member.get("body", ""))):
            existing = seen.get(paragraph["hash"])
            if existing is not None and existing["skill_id"] != skill_id:
                dropped.append(
                    {
                        "source": skill_id,
                        "para_index": paragraph["index"],
                        "hash": paragraph["hash"],
                        "reason": "exact-duplicate",
                        "kept_from": existing["skill_id"],
                    }
                )
                continue
            record = {
                "skill_id": skill_id,
                "text": paragraph["text"],
                "hash": paragraph["hash"],
                "norm": paragraph["norm"],
            }
            if existing is None:
                seen[paragraph["hash"]] = record
                near_dupes.extend(_near_dupes(seen, record, budget))
            kept_paragraphs.append({"text": paragraph["text"], "hash": paragraph["hash"]})
        kept.append(
            {
                "skill_id": skill_id,
                "source_index": int(member.get("source_index", 0)),
                "source_label": member.get("source_label", ""),
                "paragraphs": kept_paragraphs,
            }
        )
    return {"kept": kept, "dropped": dropped, "near_dupes": near_dupes}