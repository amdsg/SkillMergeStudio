"""Format detection from structural signatures only. Never uses repo metadata."""
from __future__ import annotations

import json
import re
from pathlib import Path

PROFILES = Path(__file__).resolve().parents[1] / "adapters" / "import_profiles"


def load_profiles() -> list[dict]:
    index = json.loads((PROFILES / "_index.json").read_text(encoding="utf-8"))
    profiles = []
    for item in index.get("profiles", []):
        data = json.loads((PROFILES / item["file"]).read_text(encoding="utf-8"))
        profiles.append(data)
    return profiles


def detect(text: str, explicit_profile: str = "") -> dict:
    if explicit_profile:
        return {
            "profile_id": str(explicit_profile),
            "confidence": 1.0,
            "evidence": ["user_selected"],
            "format_recognized": True,
        }
    best = None
    for profile in load_profiles():
        hits = []
        for signature in profile.get("signatures") or []:
            if re.search(signature, text, re.M):
                hits.append(signature)
        if hits and (best is None or len(hits) > len(best[1])):
            best = (profile, hits)
    if best is None:
        return {
            "profile_id": "generic_markdown",
            "confidence": 0.3,
            "evidence": ["no_signature"],
            "format_recognized": False,
        }
    profile, hits = best
    return {
        "profile_id": profile["profile_id"],
        "confidence": min(0.9, 0.5 + 0.1 * len(hits)),
        "evidence": hits,
        "format_recognized": True,
    }