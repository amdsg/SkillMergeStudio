"""Convert: source structure is parsed, mapped and re-rendered (not copied verbatim)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

WB = Path(__file__).resolve().parents[2]
if str(WB) not in sys.path:
    sys.path.insert(0, str(WB))

from agent.core.import_detect import detect  # noqa: E402
from agent.core.import_map import build  # noqa: E402
from agent.core.render import load_template, render  # noqa: E402

GPT_SKILL = """# Translator

## Role

You are a translator.

## Instructions

1. Read the input.
2. Return the translation.
"""


def test_detect_gpt_profile():
    detected = detect(GPT_SKILL)
    assert detected["profile_id"] == "gpt"
    assert detected["format_recognized"] is True


def test_build_extracts_structure():
    detected = detect(GPT_SKILL)
    doc, report = build(GPT_SKILL, detected["profile_id"], detected["format_recognized"])
    assert doc["identity"]["name"] == "Translator"
    assert doc["intent"]["summary"] == "You are a translator."
    assert doc["instructions"][0]["text"] == "Read the input."
    assert report["summary"]["mapped"] >= 2


def test_render_generic_restructures():
    detected = detect(GPT_SKILL)
    doc, _report = build(GPT_SKILL, detected["profile_id"], detected["format_recognized"])
    template = load_template("generic")
    out = render(doc, template)
    assert "# Translator" in out
    assert "## Overview" in out
    assert "## Instructions" in out
    # source headings are replaced, not copied verbatim
    assert "## Role" not in out
