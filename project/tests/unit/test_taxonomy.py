from __future__ import annotations

from skillmerge.config.loader import load_config
from skillmerge.services.classifier.keywords import for_category
from skillmerge.services.classifier.taxonomy import (
    REQUIRED_DIRECTIONS,
    builtin_categories,
    has_keyword_table,
    merge_categories,
)


def test_builtin_has_at_least_40_and_required_directions():
    categories = builtin_categories()
    assert len(categories) >= 40
    names = {item["name"] for item in categories}
    for category in REQUIRED_DIRECTIONS.values():
        assert category in names
    assert [item["index"] for item in categories] == list(range(len(categories)))


def test_data_analysis_keywords():
    words = for_category("数据分析")
    for required in ("统计", "数据", "图表", "报告"):
        assert required in words
    assert has_keyword_table("数据分析")


def test_custom_category_and_slug_merge(tmp_path):
    config, _ = load_config(str(tmp_path / "data"))
    custom = list(config.categories) + [{"name": "宠物护理", "slug": "pet-care"}]
    config = config.with_changes(categories=tuple(custom), slug_map={"宠物护理": "pet-care"})
    merged = merge_categories(config)
    names = [item["name"] for item in merged]
    assert "宠物护理" in names
    item = [entry for entry in merged if entry["name"] == "宠物护理"][0]
    assert item["builtin"] is False
    assert item["slug"] == "pet-care"