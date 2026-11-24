from __future__ import annotations

import re
import unicodedata

_HASH_PREFIX = re.compile(r"^#{1,6}\s*")
_NUMBER_PREFIX = re.compile(r"^\s*(\d+(?:\.\d+)*)(?:[.、)）]\s*)?")
_PAREN_NUMBER = re.compile(r"^\s*[（(]\s*\d+\s*[)）]\s*")
_CHINESE_NUMBER = re.compile(r"^\s*[一二三四五六七八九十百]+\s*[、.．]\s*")
_BULLET = re.compile(r"^[-*+•·▪]\s*")
_SPACE = re.compile(r"\s+")
_TAIL_PUNCT = re.compile(r"[：:。.、,，;；!！?？]+$")


def normalize_heading(text: str) -> str:
    value = (text or "").strip()
    value = _HASH_PREFIX.sub("", value)
    value = _NUMBER_PREFIX.sub("", value)
    value = _PAREN_NUMBER.sub("", value)
    value = _CHINESE_NUMBER.sub("", value)
    value = _BULLET.sub("", value)
    value = unicodedata.normalize("NFKC", value)
    value = _SPACE.sub(" ", value).strip()
    value = _TAIL_PUNCT.sub("", value)
    if value and all((char.isascii() and (char.isalpha() or char in " -")) for char in value):
        value = value.lower()
    return value


def heading_key(text: str) -> str:
    return normalize_heading(text)[:200]


def normalize_paragraph(text: str) -> str:
    value = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    return _SPACE.sub(" ", value).strip()


def normalize_search(text: str, limit: int = 8192) -> str:
    value = _SPACE.sub(" ", (text or "").replace("\r\n", "\n")).strip()
    return value[:limit]


def collapse(text: str) -> str:
    return _SPACE.sub(" ", (text or "")).strip()