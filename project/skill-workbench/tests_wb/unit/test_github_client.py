import sys
from pathlib import Path

import pytest

WB = Path(__file__).resolve().parents[2]
if str(WB) not in sys.path:
    sys.path.insert(0, str(WB))

from agent.http.errors import DomainError  # noqa: E402
from agent.net.github_client import GithubClient, load_endpoints  # noqa: E402


def make_client(status=200, headers=None, body=b'{"items":[]}'):
    calls = []

    def transport(method, url, request_headers):
        calls.append({"method": method, "url": url, "headers": request_headers})
        return status, {k.lower(): v for k, v in (headers or {"x-ratelimit-remaining": "42"}).items()}, body

    client = GithubClient(token="test-token", transport=transport)
    return client, calls


def test_endpoint_whitelist_has_seven_and_ledger_is_read_only():
    endpoints = load_endpoints()
    assert len(endpoints) == 7
    assert all(endpoint["method"] in ("GET", "HEAD") for endpoint in endpoints)


def test_write_intent_is_rejected_with_zero_transport_calls():
    client, calls = make_client()
    try:
        client.request("POST", "/repos/owner/repo")
    except DomainError as error:
        assert error.code == "E_GITHUB_WRITE_FORBIDDEN"
    else:
        raise AssertionError("expected E_GITHUB_WRITE_FORBIDDEN")
    assert calls == []
    assert client.calls == 0


def test_unknown_endpoint_is_rejected_with_zero_transport_calls():
    client, calls = make_client()
    try:
        client.request("GET", "/user/emails")
    except DomainError as error:
        assert error.code == "E_GITHUB_ENDPOINT_DENIED"
    else:
        raise AssertionError("expected E_GITHUB_ENDPOINT_DENIED")
    assert calls == []
    assert client.calls == 0


def test_success_carries_quota_metadata():
    client, calls = make_client()
    result = client.request("GET", "/search/repositories", {"q": "skill"})
    assert result["ok"] is True
    assert result["meta"]["remaining"] == "42"
    assert result["endpoint"] == "repo_search"
    assert calls[0]["headers"]["Authorization"] == "Bearer test-token"


def test_token_never_appears_in_health_or_repr():
    client = GithubClient(token="super-secret-token", transport=lambda *args: (200, {}, b"{}"))
    assert "super-secret-token" not in repr(client)
    assert "token" not in client.health()
    assert client.health()["writes_allowed"] is False


@pytest.mark.parametrize(
    "status,headers,code",
    [
        (401, {"x-ratelimit-remaining": "10"}, "E_GITHUB_AUTH_INVALID"),
        (403, {"x-ratelimit-remaining": "0", "x-ratelimit-reset": "999"}, "E_GITHUB_RATE_LIMIT"),
        (429, {"x-ratelimit-remaining": "0", "retry-after": "60"}, "E_GITHUB_RATE_LIMIT"),
        (500, {"x-ratelimit-remaining": "10"}, "E_GITHUB_UPSTREAM"),
    ],
)
def test_error_mapping(status, headers, code):
    client, _ = make_client(status=status, headers=headers, body=b'{"message":"x"}')
    try:
        client.request("GET", "/repos/owner/repo")
    except DomainError as error:
        assert error.code == code
    else:
        raise AssertionError(f"expected {code}")