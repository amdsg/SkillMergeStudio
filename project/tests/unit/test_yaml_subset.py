from __future__ import annotations

import os

import pytest

from skillmerge.services.parser.frontmatter import parse_document, split_frontmatter
from skillmerge.services.parser.yaml_subset import WARN_DUP_KEY, parse_yaml

FIXTURES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fixtures")


def test_bom_crlf_and_chinese():
    text = "\ufeffname: 数据分析\r\ndescription: 生成统计报告和数据图表\r\n"
    result = parse_yaml(text)
    assert result.ok
    assert result.data["name"] == "数据分析"
    assert result.data["description"] == "生成统计报告和数据图表"


def test_quotes_and_inline_comment():
    text = 'name: "a: b"\nauthor: \'张三\'\nnote: C# 开发 # 保留井号在值内\nempty: ""\n'
    result = parse_yaml(text)
    assert result.data["name"] == "a: b"
    assert result.data["author"] == "张三"
    assert result.data["note"] == "C# 开发"
    assert result.data["empty"] == ""


def test_nested_map_and_list():
    text = "metadata:\n  name: demo\n  tags:\n    - 数据分析\n    - 图表\nauthors:\n  - name: 张三\n    role: owner\n"
    result = parse_yaml(text)
    assert result.data["metadata"]["name"] == "demo"
    assert result.data["metadata"]["tags"] == ["数据分析", "图表"]
    assert result.data["authors"][0]["name"] == "张三"
    assert result.data["authors"][0]["role"] == "owner"


def test_block_scalars():
    literal = "description: |\n  第一行\n  第二行\n"
    folded = "summary: >\n  第一行\n  第二行\n\n  新段落\n"
    assert parse_yaml(literal).data["description"] == "第一行\n第二行\n"
    assert parse_yaml(folded).data["summary"].startswith("第一行 第二行")


def test_flow_list_and_unsupported_map():
    result = parse_yaml("tags: [a, b, \"c d\"]\nextra: {a: b}\n")
    assert result.data["tags"] == ["a", "b", "c d"]
    assert isinstance(result.data["extra"], str)
    assert any(item["code"] == "UNSUPPORTED_SYNTAX" for item in result.warnings)


def test_duplicate_key_keeps_last_and_warns():
    result = parse_yaml("name: first\nname: second\n")
    assert result.data["name"] == "second"
    assert any(item["code"] == WARN_DUP_KEY for item in result.warnings)


def test_frontmatter_split_bom_crlf():
    text = "\ufeff---\r\nname: demo\r\n---\r\n# 标题\r\n正文\r\n"
    fm, body, has_fm, warnings = split_frontmatter(text)
    assert has_fm
    assert "name: demo" in fm
    assert body.startswith("# 标题")
    assert not warnings


def test_unclosed_frontmatter_keeps_body():
    text = "---\nname: demo\n# 标题\n正文\n"
    document = parse_document(text)
    assert document.has_frontmatter is False
    assert document.body == text
    assert any(item["code"] == "FM_UNCLOSED" for item in document.warnings)


def test_broken_yaml_keeps_record_with_warning():
    text = "---\nname: demo\nbad: [unclosed\n---\n正文\n"
    document = parse_document(text)
    assert document.has_frontmatter is True
    assert document.body.strip() == "正文"
    assert any(item["code"] in ("UNSUPPORTED_SYNTAX", "YAML_SYNTAX") for item in document.warnings)


@pytest.mark.parametrize("folder", ["bom", "crlf", "zh", "nested", "broken"])
def test_fixture_documents(folder):
    path = os.path.join(FIXTURES, "parser", folder, "SKILL.md")
    assert os.path.isfile(path)
    from skillmerge.services.parser.frontmatter import read_document

    document = read_document(path)
    assert document.body
    assert isinstance(document.warnings, list)