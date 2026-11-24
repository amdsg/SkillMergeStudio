from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any, Dict, Optional

from ...util.errors import DomainError


def _fold(text: str) -> str:
    value = unicodedata.normalize("NFKD", str(text or ""))
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = value.lower()
    value = re.sub(r"[^a-z0-9-]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value


def slugify(text: str, max_length: int = 64, add_hash: bool = False) -> str:
    value = _fold(text)
    if not value or len(value) <= max_length:
        return value
    if not add_hash:
        return value
    digest = hashlib.sha1(str(text).encode("utf-8")).hexdigest()[:4]
    head = value[: max(1, max_length - 5)].rstrip("-")
    if "-" in head:
        head = head.rsplit("-", 1)[0] or head
    return f"{head}-{digest}"[:max_length]


def _frontmatter_name(frontmatter: Dict[str, Any]) -> str:
    for key in ("slug", "name_en"):
        value = frontmatter.get(key)
        if value:
            return str(value)
    return ""


def generate_name(
    rule: Dict[str, Any],
    original_name: str,
    name_en: str = "",
    frontmatter: Optional[Dict[str, Any]] = None,
    category: str = "",
    slug_map: Optional[Dict[str, str]] = None,
) -> str:
    max_length = int(rule["name"]["max_length"])
    if name_en.strip():
        value = slugify(name_en, max_length)
        if not value:
            raise DomainError(
                "EXPORT_BLOCKED",
                "显式英文名为空或无法转换为 a-z0-9-",
                "填写仅含字母、数字与连字符的英文名，或改用 generic 平台",
                466,
            )
        return value
    value = slugify(_frontmatter_name(frontmatter or {}), max_length)
    if value:
        return value
    value = slugify(original_name, max_length, add_hash=True)
    if value:
        return value
    category_slug = (slug_map or {}).get(category) or slugify(category)
    if not category_slug:
        category_slug = "skill"
    return slugify(f"{category_slug}-01", max_length, add_hash=True)


def forbidden_hits(name: str, rule: Dict[str, Any]) -> list:
    lowered = str(name).casefold()
    return [part for part in rule["name"].get("forbidden_parts", []) if str(part).casefold() in lowered]