"""GitHub 搜索 / 推荐 / 下载服务单元测试（mock transport，不联网）。"""
from __future__ import annotations

import importlib
import io
import json
import zipfile

import pytest

from skillmerge.services.github.client import GithubClient, match_endpoint
from skillmerge.services.github.download import download
from skillmerge.services.github.search import search, trending
from skillmerge.util.errors import DomainError


def _json_transport(payload):
    def transport(method, url, headers):
        return 200, {"x-ratelimit-remaining": "59"}, json.dumps(payload).encode()
    return transport


def _bytes_transport(body):
    def transport(method, url, headers):
        return 200, {}, body
    return transport


def test_match_endpoint():
    assert match_endpoint("GET", "/search/repositories")["id"] == "repo_search"
    assert match_endpoint("GET", "/repos/a/b/zipball")["id"] == "repo_zipball"
    assert match_endpoint("GET", "/repos/a/b")["id"] == "repo_detail"
    assert match_endpoint("POST", "/search/repositories") is None
    assert match_endpoint("GET", "/user") is None


def test_client_rejects_write():
    client = GithubClient()
    with pytest.raises(DomainError) as info:
        client.request("POST", "/search/repositories")
    assert info.value.code == "GITHUB_WRITE_FORBIDDEN"


def test_search_maps_fields():
    client = GithubClient(transport=_json_transport({
        "items": [
            {
                "full_name": "owner/awesome-skill",
                "name": "awesome-skill",
                "owner": {"login": "owner"},
                "html_url": "https://github.com/owner/awesome-skill",
                "description": "一个测试 skill",
                "stargazers_count": 1234,
                "pushed_at": "2026-11-20",
                "language": "Markdown",
                "topics": ["skill", "agent"],
            }
        ],
        "total_count": 1,
    }))
    result = search(client, {"query": "awesome", "sort": "stars"})
    assert result["total_count"] == 1
    item = result["items"][0]
    assert item["full_name"] == "owner/awesome-skill"
    assert item["stars"] == 1234
    assert item["source"] == "github"
    assert result["quota"]["remaining"] == "59"


def test_trending_generates_created_window():
    urls = []

    def record(method, url, headers):
        urls.append(url)
        return 200, {}, json.dumps({"items": [], "total_count": 0}).encode()

    client = GithubClient(transport=record)
    trending(client, {"window": "week"})
    trending(client, {"window": "month"})
    assert len(urls) == 2
    assert "created%3A%3E" in urls[0] and "created%3A%3E" in urls[1]
    assert "sort=stars" in urls[0] and "order=desc" in urls[0]
    assert urls[0] != urls[1]  # week 与 month 的 since 日期不同


def test_download_extracts_skill_md(tmp_path, monkeypatch):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("owner-repo-abc/SKILL.md", "---\nname: test\n---\nbody")
        zf.writestr("owner-repo-abc/readme.md", "hi")
    zip_bytes = buf.getvalue()

    dl = importlib.import_module("skillmerge.services.github.download")

    monkeypatch.setattr(dl, "DOWNLOADS", tmp_path)
    client = GithubClient(transport=_bytes_transport(zip_bytes))
    result = download(client, {"repo_full_name": "owner/repo"})
    assert result["entry"].endswith("SKILL.md")
    assert len(result["files"]) == 2
    assert result["archive_sha256"]


def test_download_blocks_zip_slip(tmp_path, monkeypatch):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../evil.txt", "bad")
        zf.writestr("ok/SKILL.md", "---\nname: t\n---\n")
    zip_bytes = buf.getvalue()

    dl = importlib.import_module("skillmerge.services.github.download")

    monkeypatch.setattr(dl, "DOWNLOADS", tmp_path)
    client = GithubClient(transport=_bytes_transport(zip_bytes))
    result = download(client, {"repo_full_name": "owner/repo"})
    assert not any(".." in f for f in result["files"])
    assert any(f.endswith("SKILL.md") for f in result["files"])


def test_download_requires_repo():
    client = GithubClient()
    with pytest.raises(DomainError) as info:
        download(client, {"repo_full_name": "norepo"})
    assert info.value.code == "BAD_REQUEST"
