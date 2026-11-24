from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .yaml_subset import WARN_DUP_KEY, parse_yaml

WARN_FM_MISSING = "FM_MISSING"
WARN_FM_UNCLOSED = "FM_UNCLOSED"
WARN_ENCODING = "ENCODING_SUSPECT"
WARN_ZERO_BYTE = "ZERO_BYTE"


@dataclass
class ParsedDocument:
    frontmatter: Dict[str, Any] = field(default_factory=dict)
    body: str = ""
    has_frontmatter: bool = False
    warnings: List[Dict[str, str]] = field(default_factory=list)
    parse_error: Optional[str] = None
    encoding_suspect: bool = False
    raw_text: str = ""
    file_size: int = 0

    def meta(self, key: str) -> str:
        value = self.frontmatter.get(key)
        if value is None:
            metadata = self.frontmatter.get("metadata")
            if isinstance(metadata, dict):
                value = metadata.get(key)
        if value is None:
            return ""
        if isinstance(value, (dict, list)):
            return ""
        return str(value).strip()

    def name(self) -> str:
        return self.meta("name")

    def description(self) -> str:
        return self.meta("description") or self.meta("summary")


def _warn(code: str, message: str, fix: str = "", level: str = "warn") -> Dict[str, str]:
    return {"code": code, "level": level, "message": message, "fix": fix}


def decode_bytes(data: bytes) -> Tuple[str, bool, List[Dict[str, str]]]:
    warnings: List[Dict[str, str]] = []
    suspect = False
    if b"\x00" in data:
        warnings.append(_warn(WARN_ZERO_BYTE, "文件包含零字节，可能不是纯文本", "用编辑器另存为 UTF-8 文本"))
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("utf-8", errors="replace")
        suspect = True
        warnings.append(_warn(WARN_ENCODING, "文件不是合法 UTF-8，已用替换字符保留内容", "将 SKILL.md 转换为 UTF-8 编码"))
    return text, suspect, warnings


def normalize_text(text: str) -> str:
    value = (text or "").lstrip("\ufeff")
    return value.replace("\r\n", "\n").replace("\r", "\n")


def split_frontmatter(text: str) -> Tuple[str, str, bool, List[Dict[str, str]]]:
    warnings: List[Dict[str, str]] = []
    normalized = normalize_text(text)
    lines = normalized.split("\n")
    if not lines or lines[0].strip() != "---":
        warnings.append(_warn(WARN_FM_MISSING, "未找到 frontmatter（首行应为 ---）", "在文件开头加入 --- 包裹元数据"))
        return "", normalized, False, warnings
    end = -1
    for index in range(1, len(lines)):
        if lines[index].strip() in ("---", "..."):
            end = index
            break
    if end < 0:
        warnings.append(_warn(WARN_FM_UNCLOSED, "frontmatter 起始 --- 未闭合，整篇按正文处理", "在元数据末尾补一行 ---"))
        return "", normalized, False, warnings
    frontmatter_text = "\n".join(lines[1:end])
    body = "\n".join(lines[end + 1:])
    return frontmatter_text, body, True, warnings


def parse_document(text: str, file_size: int = 0) -> ParsedDocument:
    normalized = normalize_text(text)
    fm_text, body, has_fm, warnings = split_frontmatter(normalized)
    result = ParsedDocument(body=body, has_frontmatter=has_fm, warnings=list(warnings), raw_text=normalized, file_size=file_size)
    if has_fm:
        parsed = parse_yaml(fm_text)
        result.frontmatter = parsed.data
        result.warnings.extend(parsed.warnings)
        if not parsed.ok:
            result.parse_error = "YAML_PARSE_FAILED"
    return result


def read_document(path: str) -> ParsedDocument:
    with open(path, "rb") as handle:
        data = handle.read()
    text, suspect, warnings = decode_bytes(data)
    result = parse_document(text, len(data))
    result.encoding_suspect = suspect
    result.warnings = warnings + result.warnings
    return result


def has_duplicate_keys(warnings: List[Dict[str, str]]) -> bool:
    return any(item.get("code") == WARN_DUP_KEY for item in warnings)