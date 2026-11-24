from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

from ...util.hashing import sha256_text
from ...util.textnorm import heading_key, normalize_paragraph
from ..parser.markdown import parse_markdown
from .conflict import decision_for
from .similarity import similarity

MIN_SIM = 0.35
MAX_CROSS_COMPARISONS = 200


def extract_chapters(
    body: str,
    skill_id: str,
    source_index: int,
    source_label: str,
) -> List[Dict[str, Any]]:
    text = (body or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    headings = parse_markdown(text).headings
    if not headings:
        return [_chapter("正文", 2, 1, text, skill_id, source_index, source_label)]
    min_level = min(int(item["level"]) for item in headings)
    chapters: List[Dict[str, Any]] = []
    first_line = int(headings[0]["line"])
    preamble = "\n".join(lines[: max(0, first_line - 1)]).strip("\n")
    if preamble.strip():
        chapters.append(_chapter("概述", 2, 1, preamble, skill_id, source_index, source_label))
    for index, heading in enumerate(headings):
        if int(heading["level"]) != min_level:
            continue
        start = int(heading["line"])
        end = len(lines)
        for later in headings[index + 1:]:
            if int(later["level"]) <= min_level:
                end = int(later["line"]) - 1
                break
        chapter_body = "\n".join(lines[start:end]).strip("\n")
        chapters.append(
            _chapter(str(heading["text"]), min_level, start, chapter_body, skill_id, source_index, source_label)
        )
    return chapters


def _chapter(title: str, level: int, line: int, body: str, skill_id: str, source_index: int, label: str) -> Dict[str, Any]:
    norm = heading_key(title)
    if not norm:
        norm = f"§untitled:{source_index}:{line}"
    return {
        "title": title,
        "norm": norm,
        "level": int(level),
        "line": int(line),
        "body": body,
        "body_hash": sha256_text(normalize_paragraph(body)),
        "skill_id": skill_id,
        "source_index": int(source_index),
        "source_label": label,
    }


class AliasResolver:
    def __init__(self, aliases: Optional[Iterable[Dict[str, str]]] = None) -> None:
        self._parent: Dict[str, str] = {}
        for item in aliases or []:
            left = heading_key(str(item.get("from", "")))
            right = heading_key(str(item.get("to", "")))
            if left and right:
                self.union(left, right)

    def find(self, value: str) -> str:
        parent = self._parent.setdefault(value, value)
        if parent != value:
            self._parent[value] = self.find(parent)
        return self._parent[value]

    def union(self, left: str, right: str) -> None:
        root_left = self.find(left)
        root_right = self.find(right)
        if root_left == root_right:
            return
        if root_left <= root_right:
            self._parent[root_right] = root_left
        else:
            self._parent[root_left] = root_right

    def canonical(self, value: str) -> str:
        if value.startswith("§untitled:") or not value:
            return value
        root = self.find(value)
        component = [key for key in self._parent if self.find(key) == root]
        return min(component + [root])


def _rank_chapters(chapters_by_source: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    flat: List[Dict[str, Any]] = []
    rank = 0
    for source in chapters_by_source:
        for chapter in sorted(source, key=lambda item: int(item.get("line", 0))):
            rank += 1
            record = dict(chapter)
            record["first_seen_rank"] = rank
            flat.append(record)
    return flat


def _build_groups(flat: List[Dict[str, Any]], aliases: AliasResolver) -> List[Dict[str, Any]]:
    buckets: Dict[Tuple[int, str], List[Dict[str, Any]]] = {}
    for chapter in flat:
        canonical = aliases.canonical(str(chapter["norm"]))
        key = (int(chapter["level"]), canonical)
        buckets.setdefault(key, []).append(chapter)
    groups: List[Dict[str, Any]] = []
    for (level, canonical), members in buckets.items():
        members.sort(key=lambda item: (int(item["source_index"]), int(item["line"])))
        aliases_hit = any(str(item["norm"]) != canonical for item in members)
        groups.append(
            {
                "norm": canonical,
                "title": members[0]["title"],
                "level": level,
                "members": members,
                "aliases_hit": aliases_hit,
                "cross_title": False,
                "sim_pairs": [],
                "first_seen_rank": min(int(item["first_seen_rank"]) for item in members),
            }
        )
    return groups


def _pair_sims(members: List[Dict[str, Any]], budget_ms: int = 60) -> List[Dict[str, Any]]:
    pairs = []
    for index, left in enumerate(members):
        for right in members[index + 1:]:
            if left["body_hash"] == right["body_hash"]:
                value = 1.0
            else:
                value = similarity(left["body"], right["body"], budget_ms).value
            pairs.append(
                {"a": left["skill_id"], "b": right["skill_id"], "sim": value}
            )
    return pairs


def _similar_pass(groups: List[Dict[str, Any]], cancel_token=None) -> None:
    singles = [group for group in groups if len(group["members"]) == 1 and not group["norm"].startswith("§untitled:")]
    candidates = []
    comparisons = 0
    for index, left in enumerate(singles):
        for right in singles[index + 1:]:
            if left["level"] != right["level"]:
                continue
            if comparisons >= MAX_CROSS_COMPARISONS:
                break
            comparisons += 1
            if cancel_token is not None and cancel_token.is_set():
                return
            value = similarity(left["members"][0]["body"], right["members"][0]["body"]).value
            if value is not None and value >= MIN_SIM:
                candidates.append((value, left, right))
    candidates.sort(
        key=lambda item: (
            -item[0],
            item[1]["norm"],
            item[2]["norm"],
            item[1]["members"][0]["skill_id"],
            item[2]["members"][0]["skill_id"],
        )
    )
    consumed = set()
    for value, left, right in candidates:
        left_id = id(left)
        right_id = id(right)
        if left_id in consumed or right_id in consumed:
            continue
        consumed.add(left_id)
        consumed.add(right_id)
        merged = dict(left)
        merged["members"] = sorted(
            left["members"] + right["members"],
            key=lambda item: (int(item["source_index"]), int(item["line"])),
        )
        merged["cross_title"] = True
        merged["aliases_hit"] = left["aliases_hit"] or right["aliases_hit"]
        merged["sim_pairs"] = [{"a": left["members"][0]["skill_id"], "b": right["members"][0]["skill_id"], "sim": value}]
        merged["first_seen_rank"] = min(left["first_seen_rank"], right["first_seen_rank"])
        merged["norm"] = left["norm"]
        merged["title"] = left["title"]
        merged["level"] = left["level"]
        group_index = next(index for index, group in enumerate(groups) if group is left)
        groups[group_index] = merged
        groups[:] = [group for group in groups if group is not right]


def _decide(group: Dict[str, Any]) -> Tuple[Optional[float], str, List[Dict[str, Any]]]:
    members = group["members"]
    if len(members) == 1:
        return 1.0, "auto", []
    pairs = _pair_sims(members)
    values = [pair["sim"] for pair in pairs]
    if any(value is None for value in values):
        return None, "review", pairs
    if group["cross_title"]:
        value = max(values)
        return value, decision_for(value, same_title=False), pairs
    value = min(values)
    return value, decision_for(value, same_title=True), pairs


def align_sources(
    chapters_by_source: List[List[Dict[str, Any]]],
    aliases: Optional[Iterable[Dict[str, str]]] = None,
    cancel_token=None,
) -> List[Dict[str, Any]]:
    resolver = AliasResolver(aliases)
    flat = _rank_chapters(chapters_by_source)
    groups = _build_groups(flat, resolver)
    _similar_pass(groups, cancel_token)
    used_keys = set()
    for group in groups:
        value, decision, pairs = _decide(group)
        group["sim"] = value
        group["decision"] = decision
        group["sim_pairs"] = group.get("sim_pairs") or pairs
        key = str(group["norm"])
        if key in used_keys:
            key = f"{key}#l{group['level']}"
        counter = 2
        base = key
        while key in used_keys:
            key = f"{base}#{counter}"
            counter += 1
        used_keys.add(key)
        group["key"] = key
    groups.sort(key=lambda item: (int(item["first_seen_rank"]), str(item["norm"]).encode("utf-8")))
    return groups