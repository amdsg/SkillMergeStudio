"""从 GitHub 下载 Skill 仓库（zipball）到本地 data 目录。"""
from __future__ import annotations

import hashlib
import io
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from ...config.paths import data_dir
from ...util.errors import DomainError
from .client import GithubClient

DOWNLOADS = Path(data_dir()) / "downloads"


def _safe_extract(zip_bytes: bytes, dest: Path) -> list[str]:
    """安全解压 zip：阻止绝对路径与 ``..`` 穿越，返回相对文件路径列表。"""
    files: list[str] = []
    dest.mkdir(parents=True, exist_ok=True)
    dest_root = dest.resolve()
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for info in zf.infolist():
            name = info.filename.replace("\\", "/")
            if name.startswith("/") or any(part == ".." for part in name.split("/")):
                continue
            target = (dest / name).resolve()
            if not str(target).startswith(str(dest_root)):
                continue
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(info))
            files.append(name)
    return files


def download(client: GithubClient, payload: dict) -> dict:
    repo = str(payload.get("repo_full_name", "")).strip()
    if not repo or "/" not in repo:
        raise DomainError("BAD_REQUEST", "请提供 repo_full_name（owner/repo）", "检查仓库名", 400)
    owner, _, name = repo.partition("/")
    if not name:
        raise DomainError("BAD_REQUEST", "仓库名格式应为 owner/repo", "检查仓库名", 400)
    ref = str(payload.get("ref", "")).strip()
    path = f"/repos/{owner}/{name}/zipball" + (f"/{ref}" if ref else "")
    archive_bytes = client.download(path)
    archive_hash = hashlib.sha256(archive_bytes).hexdigest()
    dest = DOWNLOADS / archive_hash[:16]
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    files = _safe_extract(archive_bytes, dest)
    entry = next((n for n in files if n.split("/")[-1].lower() == "skill.md"), "")
    return {
        "repo_full_name": repo,
        "ref": ref,
        "dir_path": str(dest),
        "files": files,
        "entry": entry,
        "archive_sha256": archive_hash,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
    }
