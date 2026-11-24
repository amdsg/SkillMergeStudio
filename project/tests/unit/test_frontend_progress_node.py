from __future__ import annotations

import os
import shutil
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(ROOT, "web", "js", "util", "progress-model.test.mjs")


def test_progress_model_node_tests():
    node = shutil.which("node")
    if not node:
        pytest.skip("node 不可用")
    result = subprocess.run(
        [node, "--test", SCRIPT],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        cwd=ROOT,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "fail 0" in result.stdout