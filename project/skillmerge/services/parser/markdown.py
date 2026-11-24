from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from ...util.hashing import sha256_text
from ...util.textnorm import normalize_heading, normalize_paragraph

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})(.*)$")


@dataclass
class MarkdownInfo:
    headings: List[Dict[str, object]]
    paragraphs: List[Dict[str, object]]
    lines: int
    chars: int
    fence_unclosed: bool


def _fence_marker(line: str) -> Optional[Tuple[str, int]]:
    match = FENCE_RE.match(line)
    if not match:
        return None
    marker = match.group(1)
    return marker[0], len(marker)


def _append_paragraph(paragraphs, buffer, start_line, in_fence) -> None:
    raw = "\n".join(buffer).strip("\n")
    if not raw.strip():
        return
    norm = normalize_paragraph(raw)
    paragraphs.append(
        {
            "text": raw,
            "norm": norm,
            "hash": sha256_text(norm),
            "line": start_line,
            "fence": bool(in_fence),
        }
    )


def parse_markdown(body: str) -> MarkdownInfo:
    text = (body or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    headings: List[Dict[str, object]] = []
    paragraphs: List[Dict[str, object]] = []
    fence = None
    buffer: List[str] = []
    start_line = 0
    for index, line in enumerate(lines, start=1):
        marker = _fence_marker(line)
        if fence is None and marker:
            if buffer:
                _append_paragraph(paragraphs, buffer, start_line, False)
                buffer = []
            fence = marker
            buffer = [line]
            start_line = index
            continue
        if fence is not None:
            buffer.append(line)
            if marker and marker[0] == fence[0] and marker[1] >= fence[1] and not line.strip()[len(marker[0]):]:
                fence = None
                _append_paragraph(paragraphs, buffer, start_line, True)
                buffer = []
                start_line = 0
            continue
        if not line.strip():
            if buffer:
                _append_paragraph(paragraphs, buffer, start_line, False)
                buffer = []
                start_line = 0
            continue
        match = HEADING_RE.match(line)
        if match:
            if buffer:
                _append_paragraph(paragraphs, buffer, start_line, False)
                buffer = []
                start_line = 0
            level = len(match.group(1))
            raw_text = match.group(2).strip()
            headings.append(
                {
                    "level": level,
                    "text": raw_text,
                    "norm": normalize_heading(raw_text),
                    "line": index,
                }
            )
            continue
        if not buffer:
            start_line = index
        buffer.append(line)
    if buffer:
        _append_paragraph(paragraphs, buffer, start_line, fence is not None)
    return MarkdownInfo(headings, paragraphs, len(lines), len(text), fence is not None)


def duplicate_heading_count(headings: List[Dict[str, object]]) -> int:
    seen = set()
    duplicates = 0
    for heading in headings:
        norm = str(heading.get("norm") or "")
        if not norm:
            continue
        if norm in seen:
            duplicates += 1
        else:
            seen.add(norm)
    return duplicates