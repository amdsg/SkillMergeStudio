from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Tuple

from .taxonomy import category_index, merge_categories


def _text(value: str) -> str:
    return unicodedata.normalize("NFKC", str(value or "")).lower()


def _matches(word: str, text: str) -> bool:
    probe = _text(word).strip()
    if not probe:
        return False
    if re.search(r"[a-z0-9]", probe):
        pattern = r"(?<![a-z0-9])" + re.escape(probe) + r"(?![a-z0-9])"
        return bool(re.search(pattern, text, re.I))
    return probe in text


def classify_text(name: str, description: str, config) -> Dict[str, Any]:
    fields = (("name", _text(name), 1), ("description", _text(description), 2))
    categories = merge_categories(config)
    scores: Dict[str, int] = {}
    hits: List[Dict[str, Any]] = []
    for category in categories:
        seen = set()
        for word in category["keywords"]:
            for field, text, field_weight in fields:
                key = (category["name"], word, field)
                if key in seen or not _matches(word, text):
                    continue
                seen.add(key)
                weight = field_weight
                scores[category["name"]] = scores.get(category["name"], 0) + weight
                hits.append({"word": word, "field": field, "weight": weight, "category": category["name"]})
    if not scores:
        return {"category": "未分类", "confidence": 0.10, "hits": [], "source": "keyword"}
    index = category_index(config)
    ordered = sorted(scores.items(), key=lambda item: (-item[1], index.get(item[0], 9999), item[0]))
    category, raw = ordered[0]
    confidence = min(0.95, 0.35 + 0.15 * raw)
    if all(item["field"] == "name" for item in hits):
        confidence = min(confidence, 0.60)
    return {
        "category": category,
        "confidence": round(confidence, 3),
        "hits": sorted(hits, key=lambda item: (-item["weight"], item["word"], item["field"])),
        "source": "keyword",
        "raw": raw,
    }