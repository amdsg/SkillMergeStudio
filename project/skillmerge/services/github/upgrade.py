"""自动检测已安装 Skill 的 GitHub 更新。

给定 ``repo_full_name`` 与本地记录（``local_ref``），读取远端最新的
commit / release / pushed_at，与本地记录对比，返回三种状态之一：

- ``has_update``：远端有比本地更新的 commit 或 release。
- ``up_to_date``：本地已是最新。
- ``check_failed``：无法读取远端信息（仓库不存在 / 网络失败）。

仅依赖标准库与只读的 :class:`GithubClient`，Token 只保存在内存。
"""
from __future__ import annotations

from ...util.errors import DomainError
from .client import GithubClient

_SIGNALS = ("commit_sha", "release_tag", "pushed_at")
_UNKNOWN = "unknown"


def _fetch_github_ref(client: GithubClient, repo: str) -> dict:
    """读取远端最新 ref；单个端点失败不影响其余信号。"""
    ref = {"commit_sha": _UNKNOWN, "release_tag": _UNKNOWN, "pushed_at": _UNKNOWN}
    if not repo or "/" not in repo:
        return ref
    owner, name = repo.split("/", 1)
    try:
        detail = client.request("GET", f"/repos/{owner}/{name}")
        ref["pushed_at"] = (detail.get("data") or {}).get("pushed_at", _UNKNOWN)
    except DomainError:
        pass
    try:
        commits = client.request("GET", f"/repos/{owner}/{name}/commits", {"per_page": "1"})
        items = commits.get("data") or []
        if items:
            ref["commit_sha"] = items[0].get("sha", _UNKNOWN)
    except DomainError:
        pass
    try:
        releases = client.request("GET", f"/repos/{owner}/{name}/releases", {"per_page": "1"})
        items = releases.get("data") or []
        if items:
            ref["release_tag"] = items[0].get("tag_name", _UNKNOWN)
    except DomainError:
        pass
    return ref


def _compare(old: dict, new: dict) -> str:
    """比较本地与远端 ref；任一可比信号不同即判定有更新。"""
    known = [
        signal
        for signal in _SIGNALS
        if str(old.get(signal, _UNKNOWN)) != _UNKNOWN and str(new.get(signal, _UNKNOWN)) != _UNKNOWN
    ]
    if not known:
        return "unknown"
    for signal in _SIGNALS:
        if str(old.get(signal, _UNKNOWN)) == _UNKNOWN or str(new.get(signal, _UNKNOWN)) == _UNKNOWN:
            continue
        if str(new.get(signal)) != str(old.get(signal)):
            return "has_update"
    return "up_to_date"


def _signals(old: dict, new: dict) -> dict:
    return {
        signal: {"old": old.get(signal, _UNKNOWN), "new": new.get(signal, _UNKNOWN)}
        for signal in _SIGNALS
    }


def check_update(client: GithubClient, payload: dict) -> dict:
    """检测 ``repo_full_name`` 相对 ``local_ref`` 是否有新版本。

    ``local_ref`` 形如 ``{"commit_sha": "...", "release_tag": "...", "pushed_at": "..."}``，
    是本地安装时记录的远端基准；为空时无法比较，状态为 ``unknown``。
    """
    repo = str(payload.get("repo_full_name", "")).strip()
    if not repo or "/" not in repo:
        raise DomainError("BAD_REQUEST", "请提供 repo_full_name（owner/repo）", "检查仓库名", 400)
    old = payload.get("local_ref") if isinstance(payload.get("local_ref"), dict) else {}
    new = _fetch_github_ref(client, repo)
    if all(str(new.get(signal, _UNKNOWN)) == _UNKNOWN for signal in _SIGNALS):
        state = "check_failed"
    else:
        state = _compare(old, new)
    return {
        "repo_full_name": repo,
        "state": state,
        "signals": _signals(old, new),
        "source": "github",
    }
