from __future__ import annotations

from typing import Iterable, List

from ..exporter.namer import slugify as ascii_slugify


def slugify(text: str) -> str:
    return ascii_slugify(text, max_length=64)


def unique_slug(text: str, existing: Iterable[str]) -> str:
    base = slugify(text)
    if not base:
        base = "category"
    used = {str(item) for item in existing}
    if base not in used:
        return base
    index = 2
    while f"{base}-{index}" in used:
        index += 1
    return f"{base}-{index}"


def category_slug(name: str, slug_map: dict, existing: Iterable[str]) -> str:
    mapped = str((slug_map or {}).get(name, "")).strip()
    return unique_slug(mapped or name, existing)


def all_slugs(names: List[str], slug_map: dict) -> List[str]:
    result = []
    for name in names:
        result.append(unique_slug((slug_map or {}).get(name, name), result))
    return result