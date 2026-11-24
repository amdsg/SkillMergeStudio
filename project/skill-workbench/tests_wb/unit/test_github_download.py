import io
import sys
import zipfile
from pathlib import Path

import pytest

WB = Path(__file__).resolve().parents[2]
if str(WB) not in sys.path:
    sys.path.insert(0, str(WB))

from agent.api import download as download_mod  # noqa: E402
from agent.core import records as records_mod  # noqa: E402
from agent.http.errors import DomainError  # noqa: E402
from agent.net.github_client import GithubClient  # noqa: E402


def _zip_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as bundle:
        bundle.writestr("owner-repo-abc/SKILL.md", "---\nname: demo\n---\n# Demo\n")
    return buffer.getvalue()


def _client(body):
    def transport(method, url, request_headers):
        return 200, {}, body
    return GithubClient(token="t", transport=transport)


def test_download_returns_raw_bytes():
    payload = b"PK\x03\x04fake-zip"
    client = _client(payload)
    assert client.download("/repos/owner/name/zipball/main") == payload


def test_download_404_maps_to_not_found():
    def transport(method, url, headers):
        return 404, {}, b'{"message":"Not Found"}'
    client = GithubClient(token="t", transport=transport)
    with pytest.raises(DomainError) as exc:
        client.download("/repos/owner/name/zipball/main")
    assert exc.value.code == "E_GITHUB_NOT_FOUND"


def test_download_live_extracts_skill(tmp_path, monkeypatch):
    monkeypatch.setattr(download_mod, "DOWNLOADS", tmp_path / "downloads")
    monkeypatch.setattr(records_mod, "RECORDS_DIR", tmp_path / "records")
    client = _client(_zip_bytes())
    result = download_mod._download_live({"repo_full_name": "owner/name"}, "owner/name", client=client)
    assert result["entry"].endswith("SKILL.md")
    assert any(f.endswith("SKILL.md") for f in result["files"])
    assert result["source_ref"]
