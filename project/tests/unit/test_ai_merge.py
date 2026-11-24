from __future__ import annotations

import pytest

from skillmerge.api.schemas import merge_params
from skillmerge.services.merger import ai_suggest
from skillmerge.services.merger.merge_service import MergeOptions, MergeService
from skillmerge.util.errors import DomainError


class _AI:
    enabled = True
    base_url = "http://127.0.0.1:9/v1"
    model = "test-model"
    api_key = ""
    timeout = 1


class _Config:
    ai = _AI()


class _DisabledAI:
    enabled = False
    base_url = ""
    model = ""


def test_prompt_forbids_summary_and_compression():
    prompt = ai_suggest.build_prompt("demo", [{"key": "k1", "title": "流程", "text": "步骤"}])
    assert "禁止摘要" in prompt
    assert "禁止压缩" in prompt
    assert "k1" in prompt


def test_parse_rejects_compressed_suggestion():
    chapters = {"k1": {"title": "流程", "text": "步骤一\n步骤二\n步骤三\n步骤四"}}
    raw = '{"suggestions":[{"key":"k1","text":"略"}]}'
    assert ai_suggest.parse_suggestions(raw, chapters) == []


def test_parse_accepts_and_builds_diff():
    chapters = {"k1": {"title": "流程", "text": "步骤一\n步骤二"}}
    raw = '{"suggestions":[{"key":"k1","text":"步骤一\\n步骤二（补充说明）"}]}'
    result = ai_suggest.parse_suggestions(raw, chapters)
    assert len(result) == 1
    assert result[0]["key"] == "k1"
    assert result[0]["diff"]
    assert result[0]["after_chars"] >= result[0]["before_chars"] * 0.5


def test_parse_ignores_unknown_key():
    chapters = {"k1": {"title": "流程", "text": "步骤"}}
    raw = '{"suggestions":[{"key":"missing","text":"步骤步骤"}]}'
    assert ai_suggest.parse_suggestions(raw, chapters) == []


def test_merge_requires_ai_confirmation():
    with pytest.raises(DomainError) as exc:
        merge_params({"sources": ["a"], "name": "demo", "use_ai": True}, None)
    assert exc.value.code == "AI_NOT_CONFIRMED"
    params = merge_params({"sources": ["a"], "name": "demo", "use_ai": True, "confirm_ai": True}, None)
    assert params["confirm_ai"] is True
    assert params["ai_confirm_keys"] == []


def test_ai_suggest_without_config_falls_back():
    service = MergeService.__new__(MergeService)
    service.config = type("Config", (), {"ai": _DisabledAI()})()
    built = {"prepared": {"chapters": [{"key": "k1", "title": "流程", "members": [{"paragraphs": ["步骤"]}]}]}}
    result = MergeService._ai_suggest(service, MergeOptions(name="demo"), built)
    assert result["ok"] is False
    assert result["reason"]
    assert result["applied"] is False