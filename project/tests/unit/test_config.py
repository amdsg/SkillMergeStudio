from __future__ import annotations

import json
import os

from skillmerge.config.loader import load_config, save_config


def test_defaults_and_roundtrip(tmp_path):
    data_dir = str(tmp_path / "data")
    config, warnings = load_config(data_dir)
    assert config.scan_depth == 10
    assert len(config.categories) >= 40
    assert config.save_dir.startswith(data_dir)
    assert isinstance(warnings, list)

    root = str(tmp_path / "skills")
    os.makedirs(root, exist_ok=True)
    updated, _ = save_config(data_dir, {"roots": [root], "scan_depth": 7})
    assert str(updated.scan_depth) == "7"
    reloaded, _ = load_config(data_dir)
    assert root in reloaded.roots
    assert reloaded.scan_depth == 7


def test_api_key_write_only(tmp_path):
    data_dir = str(tmp_path / "data")
    os.makedirs(data_dir, exist_ok=True)
    secret = "sk-test-secret-value"
    save_config(data_dir, {"ai": {"enabled": True, "base_url": "http://127.0.0.1:1", "model": "m", "api_key": secret}})
    config, _ = load_config(data_dir)
    public = config.public()
    assert public["ai"]["api_key_set"] is True
    assert secret not in json.dumps(public, ensure_ascii=False)
    raw = open(os.path.join(data_dir, "config.json"), "r", encoding="utf-8").read()
    assert secret in raw

    config_env, _ = load_config(data_dir, {"SKILLMERGE_API_KEY": "sk-from-env"})
    assert config_env.ai.api_key == "sk-from-env"
    raw_after = open(os.path.join(data_dir, "config.json"), "r", encoding="utf-8").read()
    assert "sk-from-env" not in raw_after


def test_env_data_dir_override(tmp_path):
    env_dir = str(tmp_path / "envdata")
    config, _ = load_config(None, {"SKILLMERGE_DATA_DIR": env_dir})
    assert config.data_dir == os.path.abspath(env_dir)


def test_corrupt_config_backs_up_and_warns(tmp_path):
    data_dir = str(tmp_path / "data")
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, "config.json")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("{not-json")
    config, warnings = load_config(data_dir)
    assert config.scan_depth == 10
    assert any(item["code"] == "CONFIG_CORRUPT" for item in warnings)
    assert os.path.isfile(path + ".bak")