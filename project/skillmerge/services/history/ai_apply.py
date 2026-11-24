from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Tuple

from ...storage.models import dumps

from ...util.errors import DomainError
from ...util.hashing import aggregate_hash, sha256_file
from ...util.timeutil import utc_now_iso
from ..parser.markdown import parse_markdown


def _split_frontmatter(text: str) -> Tuple[List[str], List[str]]:
    lines = text.split("\n")
    if lines and lines[0].strip() == "---":
        for index in range(1, len(lines)):
            if lines[index].strip() == "---":
                return lines[: index + 1], lines[index + 1:]
    return [], lines


def _replace_chapters(text: str, replacements: Dict[str, str]) -> Tuple[str, List[str]]:
    head, body_lines = _split_frontmatter(text)
    body = "\n".join(body_lines)
    headings = [item for item in parse_markdown(body).headings if int(item["level"]) > 1]
    if not headings:
        return text, []
    minimum = min(int(item["level"]) for item in headings)
    tops = [item for item in headings if int(item["level"]) == minimum]
    edits: List[Tuple[int, int, List[str]]] = []
    applied: List[str] = []
    for index, heading in enumerate(tops):
        end = len(body_lines)
        if index + 1 < len(tops):
            end = int(tops[index + 1]["line"])
        norm = str(heading["norm"]) or str(heading["text"])
        if norm not in replacements:
            continue
        start = int(heading["line"])
        edits.append((start, end, [body_lines[start], ""] + replacements[norm].split("\n")))
        applied.append(norm)
    if not applied:
        return text, []
    for start, end, new_lines in sorted(edits, key=lambda item: item[0], reverse=True):
        body_lines[start:end] = new_lines
    return "\n".join(head + body_lines), applied


def _refresh_manifest(root: str, manifest: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
    files: List[Dict[str, Any]] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(name for name in dirnames if name not in (".trash", "__pycache__"))
        for name in sorted(filenames):
            if name == "manifest.json":
                continue
            full = os.path.join(dirpath, name)
            if os.path.islink(full):
                continue
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            files.append({"path": rel, "size_bytes": os.path.getsize(full), "sha256": sha256_file(full)})
    files.sort(key=lambda item: item["path"])
    updated = dict(manifest)
    updated["files"] = files
    updated["dir_sha256"] = aggregate_hash([(item["path"], item["sha256"]) for item in files])
    updated["total_size_bytes"] = sum(int(item["size_bytes"]) for item in files)
    ai = dict(updated.get("ai") or {})
    ai.update({"applied": True, "applied_keys": keys, "applied_at": utc_now_iso()})
    updated["ai"] = ai
    return updated


def _write_atomic(path: str, content: str) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def apply_ai_suggestions(repo, artifact, keys: List[str]) -> Dict[str, Any]:
    if artifact.status != "active":
        raise DomainError("NOT_FOUND", "产物不是 active 状态", "刷新历史列表后重试", 404)
    if not os.path.isdir(artifact.dir_path):
        raise DomainError("NOT_FOUND", "产物目录不存在", "刷新历史列表或重建", 404)
    wanted = [str(item) for item in keys if str(item).strip()][:200]
    if not wanted:
        raise DomainError("INVALID_ARGUMENT", "keys 不能为空", "传入已确认的章节 key", 400)
    suggestion_path = os.path.join(artifact.dir_path, "ai_suggestions.json")
    if not os.path.isfile(suggestion_path):
        raise DomainError("AI_NOT_CONFIRMED", "该产物没有 AI 建议稿", "先以 use_ai=true 合并并查看 diff", 409)
    try:
        with open(suggestion_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError) as exc:
        raise DomainError("STORAGE_ERROR", "AI 建议稿损坏", f"重新生成建议稿：{exc}", 500)
    by_key = {
        str(item.get("key")): str(item.get("text", ""))
        for item in payload.get("suggestions", [])
        if isinstance(item, dict) and item.get("key") and item.get("text")
    }
    replacements = {key: by_key[key] for key in wanted if key in by_key}
    skipped = [key for key in wanted if key not in by_key]
    if not replacements:
        raise DomainError("INVALID_ARGUMENT", "没有可应用的章节 key", "重新生成建议稿后选择存在的章节", 400)
    skill_path = os.path.join(artifact.dir_path, "SKILL.md")
    try:
        with open(skill_path, "r", encoding="utf-8") as handle:
            original = handle.read()
    except OSError as exc:
        raise DomainError("STORAGE_ERROR", "SKILL.md 读取失败", str(exc), 500)
    updated, applied = _replace_chapters(original, replacements)
    if not applied:
        raise DomainError("INVALID_ARGUMENT", "章节标题已变化，建议稿无法定位", "重建产物后重新生成 AI 建议", 409)
    manifest = artifact.manifest()
    _write_atomic(skill_path, updated)
    try:
        new_manifest = _refresh_manifest(artifact.dir_path, manifest, applied)
        _write_atomic(os.path.join(artifact.dir_path, "manifest.json"), dumps(new_manifest))
        repo.update_integrity(
            artifact.id,
            str(new_manifest["dir_sha256"]),
            int(new_manifest["total_size_bytes"]),
            dumps(new_manifest),
        )
    except Exception as exc:  # noqa: BLE001
        try:
            _write_atomic(skill_path, original)
        except OSError:
            pass
        raise DomainError("STORAGE_ERROR", "AI 建议写入失败，已回滚正文", f"检查目录权限：{exc}", 500)

    return {
        "artifact_id": artifact.id,
        "applied_keys": applied,
        "skipped_keys": skipped,
        "sha256": new_manifest["dir_sha256"],
        "total_size_bytes": new_manifest["total_size_bytes"],
    }