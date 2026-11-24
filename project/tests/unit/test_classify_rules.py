from __future__ import annotations

from skillmerge.config.loader import load_config
from skillmerge.services.classifier.rules import classify_text
from skillmerge.services.classifier.slugify import slugify, unique_slug


def test_statistics_report_maps_to_data_analysis(tmp_path):
    config, _ = load_config(str(tmp_path / "data"))
    result = classify_text("技能", "生成统计报告和数据图表", config)
    assert result["category"] == "数据分析"
    assert result["confidence"] >= 0.60
    assert any(item["field"] == "description" for item in result["hits"])
    assert any(item["word"] in ("统计", "数据", "图表", "报告") for item in result["hits"])


def test_description_weight_is_double_name(tmp_path):
    config, _ = load_config(str(tmp_path / "data"))
    name_only = classify_text("统计", "", config)
    description_only = classify_text("技能", "统计", config)
    assert description_only["confidence"] > name_only["confidence"]
    assert description_only["category"] == "数据分析"


def test_no_keyword_returns_uncategorized(tmp_path):
    config, _ = load_config(str(tmp_path / "data"))
    result = classify_text("zzz", "qqq", config)
    assert result["category"] == "未分类"
    assert result["confidence"] == 0.10
    assert result["hits"] == []


def test_slug_fallback_and_uniqueness():
    assert slugify("My Category!") == "my-category"
    assert slugify("中文分类") == ""
    assert unique_slug("中文分类", []) == "category"
    assert unique_slug("My Category", ["my-category"]) == "my-category-2"