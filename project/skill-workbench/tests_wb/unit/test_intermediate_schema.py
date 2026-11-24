import json
import sys
from pathlib import Path

WB = Path(__file__).resolve().parents[2]
if str(WB) not in sys.path:
    sys.path.insert(0, str(WB))

from agent.core import intermediate  # noqa: E402
from agent.http.errors import DomainError  # noqa: E402

FIXTURES = WB / "tests_wb" / "fixtures" / "intermediate"


def sample(name="alpha"):
    return {
        "schema_version": 1,
        "identity": {"name": name, "id": f"skill-{name}", "version": "1.0.0", "tags": ["fixture"]},
        "intent": {"summary": f"{name} fixture intent", "source_kind": "skill_md"},
        "capabilities": [
            {"trigger": "when needed", "inputs": ["text"], "outputs": ["text"], "constraints": []}
        ],
        "instructions": [
            {"step": 1, "text": "Read the input."},
            {"step": 2, "text": "Produce the output."},
        ],
        "examples": [],
        "resources": [],
        "provenance": {
            "source": "fixture://alpha",
            "native_targets": ["unknown"],
            "import_id": "imp-001",
            "mapping_report_ref": "report-001",
        },
    }


def test_valid_sample():
    assert intermediate.validate(sample()) == []
    assert intermediate.load(intermediate.dump(sample()))["identity"]["name"] == "alpha"


def test_missing_key_and_empty_capabilities():
    doc = sample()
    del doc["resources"]
    assert any(issue["code"] == "missing_key" for issue in intermediate.validate(doc))
    doc = sample()
    doc["capabilities"] = []
    assert any(issue["code"] == "empty_not_allowed" for issue in intermediate.validate(doc))


def test_forbidden_field_and_value():
    doc = sample()
    doc["identity"]["openai_model"] = "gpt-4"
    assert any(issue["code"] == "forbidden_field_name" for issue in intermediate.validate(doc))
    doc = sample()
    doc["capabilities"][0]["constraints"] = ["最多 8000 字符"]
    assert any(issue["code"] == "forbidden_value_pattern" for issue in intermediate.validate(doc))


def test_unknown_is_not_empty():
    doc = sample()
    doc["provenance"]["native_targets"] = "unknown"
    assert any(issue["code"] == "not_an_array" for issue in intermediate.validate(doc))
    doc = sample()
    doc["provenance"]["native_targets"] = ["unknown"]
    assert intermediate.validate(doc) == []


def test_migrate_view_does_not_write_back():
    doc = sample()
    doc["schema_version"] = 0
    view = intermediate.migrate_view(doc)
    assert view["schema_version"] == intermediate.CURRENT_SCHEMA_VERSION
    assert doc["schema_version"] == 0


def test_require_intermediate_rejects_none():
    try:
        intermediate.require_intermediate(None)
    except DomainError as error:
        assert error.code == "E_INTERMEDIATE_REQUIRED"
    else:
        raise AssertionError("expected E_INTERMEDIATE_REQUIRED")


def test_three_sources_are_isomorphic():
    docs = []
    for name in ("vendor_a", "vendor_b", "generic_md"):
        payload = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
        docs.append(payload)
        assert intermediate.validate(payload) == []
    assert set(docs[0]) == set(docs[1]) == set(docs[2])
    assert set(docs[0]["identity"]) == set(docs[1]["identity"]) == set(docs[2]["identity"])


def test_dump_is_deterministic():
    doc = sample()
    assert intermediate.dump(doc) == intermediate.dump(sample())