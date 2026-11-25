"""GitHub 更新检测服务单元测试（mock transport，不联网）。

覆盖三种状态：has_update / up_to_date / check_failed，以及参数校验。
"""
from __future__ import annotations

import json
from urllib.parse import urlsplit

import pytest

from skillmerge.services.github.client import GithubClient
from skillmerge.services.github.upgrade import check_update
from skillmerge.util.errors import DomainError


def _routed_transport(routes):
    """按 URL path 子串路由返回 JSON；无匹配返回 404。

    routes: [(子串, status, payload_dict), ...]，按顺序取首个匹配。
    """

    def transport(method, url, headers):
        path = urlsplit(url).path
        for substring, status, payload in routes:
            if substring in path:
                return status, {"x-ratelimit-remaining": "59"}, json.dumps(payload).encode()
        return 404, {}, b'{"message": "Not Found"}'

    return transport


def _live_ref_transport(commit="sha-new", tag="v1.1.0", pushed="2026-11-24T00:00:00Z"):
    return _routed_transport(
        [
            ("/commits", 200, [{"sha": commit}]),
            ("/releases", 200, [{"tag_name": tag}]),
            ("/repos/", 200, {"pushed_at": pushed}),
        ]
    )


def test_check_update_has_update():
    client = GithubClient(transport=_live_ref_transport())
    result = check_update(
        client,
        {
            "repo_full_name": "owner/awesome-skill",
            "local_ref": {
                "commit_sha": "sha-old",
                "release_tag": "v1.0.0",
                "pushed_at": "2026-11-01T00:00:00Z",
            },
        },
    )
    assert result["state"] == "has_update"
    assert result["signals"]["commit_sha"]["new"] == "sha-new"
    assert result["signals"]["commit_sha"]["old"] == "sha-old"
    assert result["source"] == "github"


def test_check_update_up_to_date():
    client = GithubClient(transport=_live_ref_transport())
    result = check_update(
        client,
        {
            "repo_full_name": "owner/awesome-skill",
            "local_ref": {
                "commit_sha": "sha-new",
                "release_tag": "v1.1.0",
                "pushed_at": "2026-11-24T00:00:00Z",
            },
        },
    )
    assert result["state"] == "up_to_date"
    assert result["signals"]["release_tag"]["old"] == result["signals"]["release_tag"]["new"]


def test_check_update_check_failed():
    client = GithubClient(transport=_routed_transport([]))
    result = check_update(
        client,
        {
            "repo_full_name": "owner/missing-skill",
            "local_ref": {"commit_sha": "sha-old", "release_tag": "v1.0.0", "pushed_at": "2026-11-01T00:00:00Z"},
        },
    )
    assert result["state"] == "check_failed"
    assert result["signals"]["commit_sha"]["new"] == "unknown"


def test_check_update_requires_repo():
    client = GithubClient(transport=_live_ref_transport())
    with pytest.raises(DomainError) as info:
        check_update(client, {"repo_full_name": "norepo"})
    assert info.value.code == "BAD_REQUEST"
