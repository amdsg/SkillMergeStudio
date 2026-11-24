"""Download endpoint: local archives by default, live GitHub zipball when enabled."""
from __future__ import annotations

import hashlib
import json

from pathlib import Path

from agent.core.archive import copy_tree, extract_zip
from agent.core.hashing import sha256_file
from agent.core.index_store import unique_dir
from agent.core.paths import data_dir
from agent.core.records import append
from agent.core.source_ref import build
from agent.http.errors import DomainError
from agent.net.live import get_client, is_live

DOWNLOADS = data_dir() / "downloads"


def _body(raw: bytes) -> dict:
    if not raw:
        return {}
    data = json.loads(raw.decode("utf-8"))
    return data if isinstance(data, dict) else {}


def download(params, body, request_id):
    payload = _body(body)
    repo = str(payload.get("repo_full_name", "")).strip()
    local_path = str(payload.get("local_path", "")).strip()
    if not repo:
        raise DomainError("E_BAD_REQUEST", "wb.error.bad_request",
                          params={"fields": ["repo_full_name"]}, fix_key="wb.fix.check_input")
    if is_live() and not local_path:
        return _download_live(payload, repo)
    if not local_path:
        raise DomainError("E_BAD_REQUEST", "wb.error.bad_request",
                          params={"fields": ["local_path"]}, fix_key="wb.fix.check_input")
    source = Path(local_path)
    if not source.exists():
        raise DomainError("E_SOURCE_NOT_DOWNLOADED", "wb.error.source_not_downloaded",
                          params={"path": local_path}, fix_key="wb.fix.redownload_source")
    archive_hash = sha256_file(source) if source.is_file() else ""
    content_hash = archive_hash or sha256_file(
        next((path for path in sorted(source.rglob("SKILL.md"))), source)
    )
    dest = unique_dir(DOWNLOADS, archive_hash[:16] if archive_hash else repo.replace("/", "__"))
    dest.mkdir(parents=True, exist_ok=True)
    if source.is_file() and source.suffix.lower() == ".zip":
        files, ignored = extract_zip(source, dest)
    elif source.is_dir():
        files, ignored = copy_tree(source, dest)
    else:
        raise DomainError("E_UNSUPPORTED_BINARY", "wb.error.unsupported_binary",
                          params={"path": local_path}, fix_key="wb.fix.check_input")
    entry = next((name for name in files if name.split("/")[-1].lower() == "skill.md"), "")
    ref = build(repo, str(payload.get("commit_sha", "")), str(payload.get("release_tag", "")),
                str(payload.get("pushed_at", "")), archive_hash, content_hash)
    record = append("downloads", {
        "repo_full_name": repo,
        "state": "downloaded",
        "dir_name": dest.name,
        "files": files,
        "ignored": ignored,
        "entry": entry,
        "source_ref": ref,
    })
    return {
        "record_id": str(record.get("created_at")),
        "dir_path": f"downloads/{dest.name}",
        "files": files,
        "ignored": ignored,
        "entry": entry,
        "source_ref": ref,
    }


def _download_live(payload: dict, repo: str, client=None) -> dict:
    client = client or get_client()
    owner, _sep, name = repo.partition("/")
    if not name:
        raise DomainError("E_BAD_REQUEST", "wb.error.bad_request",
                          params={"fields": ["repo_full_name"]}, fix_key="wb.fix.check_input")
    ref = str(payload.get("ref", "")).strip()
    path = f"/repos/{owner}/{name}/zipball" + (f"/{ref}" if ref else "")
    archive_bytes = client.download(path)
    archive_hash = hashlib.sha256(archive_bytes).hexdigest()
    dest = unique_dir(DOWNLOADS, archive_hash[:16])
    dest.mkdir(parents=True, exist_ok=True)
    zip_path = dest.with_name(dest.name + ".zip")
    zip_path.write_bytes(archive_bytes)
    try:
        files, ignored = extract_zip(zip_path, dest)
    finally:
        zip_path.unlink(missing_ok=True)
    entry = next((n for n in files if n.split("/")[-1].lower() == "skill.md"), "")
    ref_info = build(repo, str(payload.get("commit_sha", "")), str(payload.get("release_tag", "")),
                     str(payload.get("pushed_at", "")), archive_hash, archive_hash)
    record = append("downloads", {
        "repo_full_name": repo,
        "state": "downloaded",
        "dir_name": dest.name,
        "files": files,
        "ignored": ignored,
        "entry": entry,
        "source_ref": ref_info,
    })
    return {
        "record_id": str(record.get("created_at")),
        "dir_path": f"downloads/{dest.name}",
        "files": files,
        "ignored": ignored,
        "entry": entry,
        "source_ref": ref_info,
    }