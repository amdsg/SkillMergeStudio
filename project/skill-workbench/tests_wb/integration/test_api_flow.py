import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

import pytest

WB_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = WB_ROOT / "tests_wb" / "fixtures"
TMP = Path(tempfile.mkdtemp(prefix="wb-test-"))
os.environ["WB_DATA_DIR"] = str(TMP / "data")
os.environ["WB_STORE_DIR"] = str(TMP / "store")

if str(WB_ROOT) not in sys.path:
    sys.path.insert(0, str(WB_ROOT))

from agent.wb_agent import build_router  # noqa: E402
from agent.http.server import WorkbenchServer  # noqa: E402


@pytest.fixture(scope="module")
def server():
    instance = WorkbenchServer(build_router(), port=0)
    info = instance.start()
    yield f"http://127.0.0.1:{info['port']}"
    instance.stop()


def call(base, method, path, payload=None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(base + path, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def test_health(server):
    payload = call(server, "GET", "/health")
    assert payload["ok"] is True
    capabilities = {item["capability_id"]: item["enabled"] for item in payload["data"]["capabilities"]}
    assert all(value is False for value in capabilities.values())
    assert payload["data"]["inheritance"]["state"] == "blocked"


def test_targets(server):
    payload = call(server, "GET", "/targets")
    data = payload["data"]
    assert data["counts"]["total"] == 25
    assert data["counts"]["verified"] == 3
    assert data["counts"]["unknown"] == 22
    assert len(data["sample_ids"]) <= 5
    assert data["diagnostics"] == []


def test_target_tools(server):
    payload = call(server, "GET", "/targets/claude/tools")
    data = payload["data"]
    assert data["recommended_tool_id"] is None
    assert data["reason_code"] == "tool_evidence_unknown"


def test_unregistered_target_returns_409(server):
    with pytest.raises(urllib.error.HTTPError) as error:
        call(server, "GET", "/targets/not_a_target/tools")
    assert error.value.code == 409


def test_applicability_resolve(server):
    payload = call(server, "POST", "/applicability/resolve", {"target_id": "deepseek"})
    data = payload["data"]
    assert data["mode"] == "unknown"
    assert data["reason_code"] == "not_fetched"
    assert data["reason_key"] == "wb.reason.not_fetched"


def test_search_fixture(server):
    payload = call(server, "POST", "/search", {"query": "fixture"})
    items = payload["data"]["items"]
    assert len(items) == 3
    assert all(item["applicability"]["mode"] == "unknown" for item in items)
    assert all(item["applicability"]["reason_code"] == "not_fetched" for item in items)


def test_download_preview_convert_merge_upgrade(server):
    download = call(server, "POST", "/download", {
        "repo_full_name": "fixture/skill-alpha",
        "local_path": str(FIXTURES / "repos" / "skill-alpha"),
        "commit_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    })["data"]
    assert download["entry"] == "SKILL.md"
    assert download["source_ref"]["commit_sha"].startswith("aaaa")

    preview = call(server, "POST", "/install/preview", {
        "files": download["files"],
        "target_tool": "claude_code",
        "target_path": str(TMP / "target" / "skills"),
    })["data"]
    assert preview["dry_run"] is True
    assert preview["writes"] == 0
    assert preview["plan_hash"]

    converted = call(server, "POST", "/convert", {
        "target_id": "chatgpt",
        "source_path": str(TMP / "data" / "downloads" / download["dir_path"].split("/")[-1]),
        "source_kind": "skill",
    })["data"]
    assert converted["tier"] == "generic"
    assert converted["lost_chapters"] == []
    assert "target not verified" in converted["head"]

    generic = call(server, "POST", "/convert", {
        "target_id": "agent_skills_generic",
        "source_path": str(TMP / "data" / "downloads" / download["dir_path"].split("/")[-1]),
        "source_kind": "skill",
    })["data"]
    assert generic["tier"] == "local_contract"

    beta = call(server, "POST", "/download", {
        "repo_full_name": "fixture/skill-beta",
        "local_path": str(FIXTURES / "repos" / "skill-beta"),
        "commit_sha": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    })["data"]

    merged = call(server, "POST", "/merge", {
        "sources": [download["dir_path"].split("/")[-1], beta["dir_path"].split("/")[-1]],
    })["data"]
    assert merged["merge_plan"]["conflict_count"] >= 1
    assert merged["writes"] == 0

    upgraded = call(server, "POST", "/upgrade/check", {
        "repo_full_name": "fixture/skill-beta",
        "local_ref": {"commit_sha": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", "release_tag": "v1.0.0", "pushed_at": "2026-11-18T10:00:00Z"},
    })["data"]
    assert upgraded["state"] == "has_update"
    assert upgraded["declaration_diff"]["legacy_missing"] is True
    assert upgraded["source"] == "fixture"


def test_records(server):
    payload = call(server, "GET", "/records/downloads")
    assert payload["data"]["name"] == "downloads"
    assert len(payload["data"]["items"]) >= 2