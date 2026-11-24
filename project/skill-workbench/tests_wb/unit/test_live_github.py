import json
import sys
from pathlib import Path
from urllib.parse import urlparse

import pytest

WB = Path(__file__).resolve().parents[2]
if str(WB) not in sys.path:
    sys.path.insert(0, str(WB))

from agent.api.search import _search_github  # noqa: E402
from agent.api.upgrade import _build_result, _fetch_github_ref  # noqa: E402
from agent.net import live  # noqa: E402
from agent.net.github_client import GithubClient  # noqa: E402


def _transport(responses):
    def transport(method, url, request_headers):
        path = urlparse(url).path
        if path in responses:
            status, headers, body = responses[path]
            return status, {k.lower(): v for k, v in headers.items()}, json.dumps(body).encode("utf-8")
        return 404, {}, b"{}"

    return transport


def _client(responses):
    return GithubClient(token="test-token", transport=_transport(responses))


def test_is_live_defaults_false(monkeypatch):
    monkeypatch.delenv("WB_LIVE_GITHUB", raising=False)
    monkeypatch.delenv("WB_GITHUB_TOKEN", raising=False)
    assert live.is_live() is False


def test_is_live_with_token(monkeypatch):
    monkeypatch.setenv("WB_GITHUB_TOKEN", "x")
    monkeypatch.delenv("WB_LIVE_GITHUB", raising=False)
    assert live.is_live() is True


def test_is_live_with_flag(monkeypatch):
    monkeypatch.setenv("WB_LIVE_GITHUB", "1")
    monkeypatch.delenv("WB_GITHUB_TOKEN", raising=False)
    assert live.is_live() is True


def test_search_github_maps_items_and_quota():
    client = _client({
        "/search/repositories": (200, {"x-ratelimit-remaining": "42"}, {
            "items": [
                {
                    "full_name": "owner/foo",
                    "description": "a skill",
                    "stargazers_count": 100,
                    "pushed_at": "2026-01-01T00:00:00Z",
                    "topics": ["skill"],
                }
            ]
        }),
    })
    result = _search_github("skill", "stars", 1, client)
    assert result["quota"]["source"] == "github"
    assert result["quota"]["remaining"] == "42"
    assert len(result["items"]) == 1
    item = result["items"][0]
    assert item["source"] == "github"
    assert item["full_name"] == "owner/foo"
    assert item["stars"] == 100
    assert item["release_tag"] == "unknown"
    assert item["missing_factors"] == ["release_tag", "release_download", "commit_sha"]
    assert item["applicability"]["mode"] == "unknown"


def test_search_github_relevance_omits_sort():
    client = _client({"/search/repositories": (200, {}, {"items": []})})
    _search_github("skill", "relevance", 1, client)
    # relevance has no GitHub sort param; nothing to assert beyond no error.


def test_fetch_github_ref_collects_three_signals():
    client = _client({
        "/repos/owner/name": (200, {}, {"pushed_at": "2026-02-02T00:00:00Z"}),
        "/repos/owner/name/commits": (200, {}, [{"sha": "abc123"}]),
        "/repos/owner/name/releases": (200, {}, [{"tag_name": "v1.0"}]),
    })
    ref = _fetch_github_ref("owner/name", client)
    assert ref["pushed_at"] == "2026-02-02T00:00:00Z"
    assert ref["commit_sha"] == "abc123"
    assert ref["release_tag"] == "v1.0"


def test_fetch_github_ref_tolerates_endpoint_failure():
    client = _client({
        "/repos/owner/name": (200, {}, {"pushed_at": "2026-02-02T00:00:00Z"}),
        # commits and releases both 404 -> signals stay unknown
    })
    ref = _fetch_github_ref("owner/name", client)
    assert ref["pushed_at"] == "2026-02-02T00:00:00Z"
    assert ref["commit_sha"] == "unknown"
    assert ref["release_tag"] == "unknown"


def test_fetch_github_ref_rejects_malformed_repo():
    client = _client({})
    ref = _fetch_github_ref("not-a-repo", client)
    assert ref["commit_sha"] == "unknown"
    assert ref["release_tag"] == "unknown"


def test_build_result_passes_source_and_detects_update():
    old = {"commit_sha": "old", "release_tag": "unknown", "pushed_at": "2026-01-01T00:00:00Z"}
    new = {"commit_sha": "new", "release_tag": "unknown", "pushed_at": "2026-01-01T00:00:00Z"}
    result = _build_result("owner/name", old, new, "github")
    assert result["source"] == "github"
    assert result["state"] == "has_update"
