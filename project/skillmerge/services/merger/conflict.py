from __future__ import annotations

from typing import Optional


def decision_for(value: Optional[float], same_title: bool = True) -> str:
    if value is None:
        return "review"
    if not same_title:
        if value >= 0.72:
            return "suggest"
        if value >= 0.35:
            return "review"
        return "auto"
    if value >= 1.0:
        return "auto"
    if value >= 0.72:
        return "suggest"
    if value >= 0.35:
        return "review"
    return "conflict"


def sim_text(value: Optional[float]) -> str:
    return "NA" if value is None else f"{value:.3f}"


def format_conflict(source: str, norm: str, value: Optional[float]) -> str:
    return f"<!-- conflict: source={source}:{norm}, sim={sim_text(value)} -->"


def format_suggest(source: str, norm: str, value: Optional[float]) -> str:
    return f"<!-- suggest-merge: source={source}:{norm}, sim={sim_text(value)} -->"


def label_for(member: dict) -> str:
    return str(member.get("source_label") or member.get("platform_origin") or "unknown")


def member_norm(member: dict) -> str:
    return str(member.get("norm") or "untitled")