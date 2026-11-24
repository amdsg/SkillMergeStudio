"""Redaction for diagnostics: tokens, keys and home prefixes."""
from __future__ import annotations

import re

PATTERNS = (
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"), "<TOKEN>"),
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "<TOKEN>"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "<TOKEN>"),
    (re.compile(r"Bearer\s+[A-Za-z0-9._-]{8,}"), "Bearer <TOKEN>"),
    (re.compile(r"[A-Za-z]:\\Users\\[^\\\r\n\"']+"), "<home>"),
    (re.compile(r"/home/[^/\s\"']+"), "<home>"),
    (re.compile(r"/Users/[^/\s\"']+"), "<home>"),
)


def redact_text(value: str) -> str:
    text = str(value)
    for pattern, replacement in PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def redact_obj(value):
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {key: redact_obj(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_obj(item) for item in value]
    return value