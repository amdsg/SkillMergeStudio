from __future__ import annotations

from skillmerge.config import AIConfig
from skillmerge.services.classifier.classifier_service import ClassifierService
from tests.helpers import build_env, scan


def _env(tmp_path):
    env = build_env(tmp_path)
    scan(env, __import__("tests.helpers", fromlist=["ROOT"]).ROOT + "/tests/fixtures/skills")
    return env


def test_keyword_classification_and_manual_protection(tmp_path):
    env = build_env(tmp_path)
    from tests.helpers import ROOT

    scan(env, __import__("os").path.join(ROOT, "tests", "fixtures", "skills"))
    basic = env.db.query_one("SELECT * FROM skills WHERE name='basic'")
    assert basic is not None
    service = ClassifierService(env.db, env.config)
    result = service.classify()
    assert result["classified"] >= 1
    row = env.db.query_one("SELECT category, category_source, confidence FROM skills WHERE name='basic'")
    assert row["category"] == "数据分析"
    assert row["category_source"] == "keyword"
    env.repo.update_category(row["id"] if "id" in row.keys() else basic["id"], "医疗健康", "manual", 1.0)
    service.classify()
    manual = env.db.query_one("SELECT category, category_source FROM skills WHERE name='basic'")
    assert manual["category"] == "医疗健康"
    assert manual["category_source"] == "manual"
    env.db.close_all()


def test_ai_unavailable_falls_back_to_keyword(tmp_path):
    env = build_env(tmp_path)
    from tests.helpers import ROOT
    import os

    scan(env, os.path.join(ROOT, "tests", "fixtures", "skills"))
    config = env.config.with_changes(
        ai=AIConfig(
            enabled=True,
            base_url="http://127.0.0.1:1",
            model="test-model",
            api_key="sk-test",
            timeout=1,
        )
    )
    service = ClassifierService(env.db, config)
    result = service.classify(use_ai=True, confirm_ai=True)
    assert result["fallback_count"] >= 1
    row = env.db.query_one("SELECT category FROM skills WHERE name='basic'")
    assert row["category"] == "数据分析"
    env.db.close_all()