from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional

from ...util.hashing import sha256_file
from ...util.textnorm import normalize_heading

BINARY_KINDS = frozenset({"binary"})
SUSPICIOUS_EXT = frozenset(
    {".exe", ".dll", ".so", ".dylib", ".bin", ".msi", ".com", ".scr", ".bat", ".cmd", ".ps1", ".vbs", ".jar"}
)
PRUNE = frozenset({".git", ".hg", ".svn", "__pycache__", "node_modules", "venv", ".venv", ".cache", ".pytest_cache"})
SKIP_FILES = frozenset({".DS_Store"})
SKIP_SUFFIX = (".pyc", ".pyo")


def classify(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".ico", ".tiff"}:
        return "image"
    if ext in {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac"}:
        return "audio"
    if ext in {".mp4", ".mov", ".avi", ".mkv", ".webm", ".wmv"}:
        return "video"
    if ext in {".md", ".txt", ".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".csv", ".rtf"}:
        return "document"
    if ext in {".json", ".yaml", ".yml", ".toml", ".xml", ".db", ".sqlite"}:
        return "data"
    if ext in {".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".c", ".cpp", ".h", ".sh"}:
        return "code"
    if ext in {".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar"}:
        return "archive"
    if ext in SUSPICIOUS_EXT:
        return "binary"
    return "other"


def enumerate_resources(root: str, main_file: str = "SKILL.md") -> List[Dict[str, Any]]:
    resources: List[Dict[str, Any]] = []

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            name for name in dirnames if name not in PRUNE and not os.path.islink(os.path.join(dirpath, name))
        )
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            if os.path.islink(full):
                continue
            if name in SKIP_FILES or name.lower().endswith(SKIP_SUFFIX) or name == main_file:
                continue
            try:
                size = os.path.getsize(full)
            except OSError:
                continue
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            resources.append(
                {
                    "path": rel,
                    "size_bytes": int(size),
                    "sha256": sha256_file(full),
                    "kind": classify(rel),
                }
            )
    resources.sort(key=lambda item: item["path"])
    return resources


def has_suspicious_binary(resources: List[Dict[str, Any]]) -> bool:
    return any(item.get("kind") == "binary" for item in resources)


def _split_names(value: str) -> List[str]:
    parts = re.split(r"[\n,，;；]+", value)
    return [part.strip() for part in parts if part.strip()]


def _from_frontmatter(frontmatter: Dict[str, Any]) -> List[Dict[str, str]]:
    raw: Optional[Any] = None
    for key, value in frontmatter.items():
        if str(key).strip().lower() in ("dependencies", "dependency", "requirements"):
            raw = value
            break
    items: List[Dict[str, str]] = []
    if isinstance(raw, list):
        for value in raw:
            text = str(value).strip()
            if text:
                items.append({"name": text, "source": "frontmatter", "raw": text})
    elif isinstance(raw, dict):
        for key, value in raw.items():
            text = str(value).strip()
            items.append({"name": text or str(key), "source": "frontmatter", "raw": f"{key}: {value}"})
    elif raw:
        for text in _split_names(str(raw)):
            items.append({"name": text, "source": "frontmatter", "raw": text})
    return items


def _from_requirements(root: str) -> List[Dict[str, str]]:
    path = os.path.join(root, "requirements.txt")
    if not os.path.isfile(path):
        return []
    items: List[Dict[str, str]] = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                text = line.split("#", 1)[0].strip()
                if not text or text.startswith("-"):
                    continue
                name = re.split(r"[<>=!~\[ ]", text, maxsplit=1)[0].strip()
                if name:
                    items.append({"name": name, "source": "requirements.txt", "raw": text})
    except OSError:
        return []
    return items


def _environment_section(body: str) -> str:
    lines = (body or "").split("\n")
    collected: List[str] = []
    active = False
    level = 0
    for line in lines:
        match = re.match(r"^(#{1,6})\s+(.*)$", line)
        if match:
            current = len(match.group(1))
            norm = normalize_heading(match.group(2))
            if any(word in norm for word in ("环境要求", "依赖", "requirements", "environment", "dependencies")):
                active = True
                level = current
                continue
            if active and current <= level:
                break
        if active:
            collected.append(line)
    return "\n".join(collected)


def _from_body(body: str) -> List[Dict[str, str]]:
    section = _environment_section(body)
    if not section:
        return []
    items: List[Dict[str, str]] = []
    for line in section.split("\n"):
        text = line.strip()
        if not text:
            continue
        pip = re.match(r"^(?:python\s+-m\s+)?pip3?\s+install\s+(.+)$", text)
        if pip:
            for name in re.split(r"\s+", pip.group(1)):
                if name and not name.startswith("-"):
                    items.append({"name": name, "source": "environment-section", "raw": text})
            continue
        bullet = re.match(r"^[-*+]\s+(.+)$", text)
        if bullet:
            value = bullet.group(1).strip()
            name = re.split(r"[<>=!~ ]", value, maxsplit=1)[0].strip()
            if name and not name.startswith(("http://", "https://")):
                items.append({"name": name, "source": "environment-section", "raw": value})
    return items


def parse_dependencies(frontmatter: Dict[str, Any], body: str, root: str) -> List[Dict[str, str]]:
    combined = _from_frontmatter(frontmatter) + _from_requirements(root) + _from_body(body)
    seen = set()
    result: List[Dict[str, str]] = []
    for item in combined:
        key = item["name"].strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result