"""GitHub Skill 搜索与推荐（trending）。

搜索：按项目名 / 描述 / topic 匹配，等价于 GitHub 搜索框。
推荐：按创建时间窗口（本周 / 本月）过滤，按 stars 降序，返回当前最火的 Skill 仓库。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .client import GithubClient


def _map_item(item: dict) -> dict:
    owner = (item.get("owner") or {})
    return {
        "full_name": item.get("full_name"),
        "name": item.get("name"),
        "owner": owner.get("login"),
        "owner_avatar": owner.get("avatar_url"),
        "html_url": item.get("html_url"),
        "description": item.get("description"),
        "stars": item.get("stargazers_count"),
        "forks": item.get("forks_count"),
        "pushed_at": item.get("pushed_at"),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
        "language": item.get("language"),
        "topics": item.get("topics") or [],
        "default_branch": item.get("default_branch"),
        "has_skill_md": None,
        "source": "github",
    }


def _search_repositories(client: GithubClient, params: dict) -> dict:
    result = client.request("GET", "/search/repositories", params)
    meta = result.get("meta") or {}
    data = result.get("data") or {}
    return {
        "items": [_map_item(item) for item in (data.get("items") or [])],
        "total_count": data.get("total_count", 0),
        "quota": {
            "remaining": meta.get("remaining"),
            "reset_at": meta.get("reset_at"),
            "mode": meta.get("mode"),
        },
    }


def search(client: GithubClient, payload: dict) -> dict:
    """按关键词搜索 Skill 仓库。

    query 为空时回退到 `skill` 主题；支持 sort=stars / updated / relevance。
    """
    query = str(payload.get("query", "")).strip() or "skill"
    sort = str(payload.get("sort", "relevance")).strip()
    page = int(payload.get("page", 1) or 1)
    params = {"q": query, "per_page": "20", "page": str(page)}
    gh_sort = {"stars": "stars", "updated": "updated"}.get(sort)
    if gh_sort:
        params["sort"] = gh_sort
        params["order"] = "desc"
    return _search_repositories(client, params)


def trending(client: GithubClient, payload: dict) -> dict:
    """推荐当前最火的 Skill 仓库。

    window: week（最近 7 天）/ month（最近 30 天），按 stars 降序。
    通过 GitHub 的 `created:>YYYY-MM-DD` 限定创建时间窗口。
    """
    window = str(payload.get("window", "week")).strip()
    page = int(payload.get("page", 1) or 1)
    days = 7 if window == "week" else 30
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    query = f"skill created:>{since}"
    params = {
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": "20",
        "page": str(page),
    }
    return _search_repositories(client, params)
