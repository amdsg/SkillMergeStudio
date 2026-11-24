from __future__ import annotations

import os
from typing import Any, Dict, List, Tuple

from ...config import defaults
from .markdown import MarkdownInfo, duplicate_heading_count
from .frontmatter import ParsedDocument, has_duplicate_keys
from .resources import has_suspicious_binary


def _detail(code: str, reason: str) -> Dict[str, Any]:
    delta = 0
    for item in defaults.QUALITY_DEDUCTIONS:
        if item["code"] == code:
            delta = int(item["delta"])
            break
    return {"code": code, "delta": -delta, "reason": reason}


def score_quality(
    document: ParsedDocument,
    markdown: MarkdownInfo,
    resources: List[Dict[str, Any]],
    directory_name: str,
) -> Tuple[int, List[Dict[str, Any]], List[Dict[str, str]]]:
    details: List[Dict[str, Any]] = []
    warnings: List[Dict[str, str]] = list(document.warnings)
    if document.parse_error:
        details.append(_detail("PARSE_FAILED", document.parse_error))
        warnings.append({"code": "PARSE_FAILED", "level": "error", "message": "frontmatter 解析失败", "fix": "检查 YAML 语法并重新扫描"})
    if not document.body.strip():
        details.append(_detail("BODY_EMPTY", "正文为空"))
    if not document.has_frontmatter:
        details.append(_detail("FM_MISSING", "缺少 frontmatter"))
    name = document.name()
    description = document.description()
    if not name:
        details.append(_detail("NAME_MISSING", "frontmatter 缺少 name"))
    if not description:
        details.append(_detail("DESC_MISSING", "frontmatter 缺少 description"))
    if document.encoding_suspect:
        details.append(_detail("ENCODING_SUSPECT", "编码异常"))
    if name and directory_name and name.casefold() != directory_name.casefold():
        details.append(_detail("NAME_MISMATCH", f"name={name} 与目录 {directory_name} 不一致"))
    if markdown.lines > 5000 or document.file_size > 200 * 1024:
        details.append(_detail("TOO_LONG", "正文或文件过大"))
    if has_suspicious_binary(resources):
        details.append(_detail("BINARY_RESOURCE", "存在可疑二进制资源"))
    duplicates = duplicate_heading_count(markdown.headings)
    if duplicates:
        penalty = min(15, duplicates * 5)
        details.append({"code": "DUP_HEADING", "delta": -penalty, "reason": f"{duplicates} 个重复标题"})
    if has_duplicate_keys(document.warnings):
        details.append(_detail("DUP_KEY", "frontmatter 存在重复键"))
    if markdown.fence_unclosed:
        details.append(_detail("FENCE_UNCLOSED", "代码围栏未闭合"))
        warnings.append({"code": "FENCE_UNCLOSED", "level": "warn", "message": "代码围栏未闭合", "fix": "补全 ``` 或 ~~~ 围栏"})
    total = sum(abs(int(item["delta"])) for item in details)
    score = max(0, 100 - total)
    return score, details, warnings


def directory_name_for(path: str) -> str:
    return os.path.basename(os.path.dirname(os.path.abspath(path)) if os.path.isfile(path) else path)