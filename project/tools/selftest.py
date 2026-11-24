from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from skillmerge.services import fsops
from skillmerge.services.classifier.rules import classify_text
from skillmerge.services.exporter import namer
from skillmerge.services.exporter.validate import dedupe_checks, errors, run_preflight
from skillmerge.services.merger import conflict, paragraphs, plan
from skillmerge.services.parser.frontmatter import decode_bytes, parse_document, split_frontmatter
from skillmerge.services.parser.markdown import duplicate_heading_count, parse_markdown
from skillmerge.services.parser.yaml_subset import parse_yaml
from skillmerge.util import hashing, textnorm
from skillmerge.util.errors import DomainError

RULE = {
    "name": {"pattern": "^[^<>:\"/\\\\|?*]+$", "max_length": 120, "forbidden_parts": []},
    "description": {"max_chars": 1000},
    "skill_md": {"max_lines": 5000, "max_bytes": 10485760},
    "bundle": {"max_mb": 30, "max_files": 200, "max_file_mb": 10},
    "package": {"type": "dir"},
    "frontmatter": {"required": ["name", "description"]},
    "verification_status": "verified",
    "evidence_level": "verified",
    "source": "https://example.com",
    "verified_at": "2026-11-22",
    "kind": "skill",
}


def _spec(**overrides):
    spec = {
        "name": "demo-skill",
        "description": "demo",
        "text": "# demo-skill\n\nbody\n",
        "frontmatter": {"name": "demo-skill", "description": "demo"},
        "files": [{"rel_path": "SKILL.md", "size_bytes": 20}],
        "layout_name": "demo-skill",
        "mode": "dir",
    }
    spec.update(overrides)
    return spec


class TextNormTests(unittest.TestCase):
    def test_001_numbered_heading(self):
        self.assertEqual(textnorm.normalize_heading("## 1. 工作流程"), "工作流程")

    def test_002_colon_heading(self):
        self.assertEqual(textnorm.normalize_heading("工作流程："), "工作流程")

    def test_003_dash_heading(self):
        self.assertEqual(textnorm.normalize_heading("- 工作流程 "), "工作流程")

    def test_004_heading_idempotent(self):
        once = textnorm.normalize_heading("## 1. 流程")
        self.assertEqual(textnorm.normalize_heading(once), once)

    def test_005_heading_key(self):
        self.assertEqual(textnorm.heading_key("## 1. 工作流程"), "工作流程")

    def test_006_paragraph_whitespace(self):
        self.assertEqual(textnorm.normalize_paragraph("  a  b\n\nc  "), "a b c")

    def test_007_empty_paragraph(self):
        self.assertEqual(len(textnorm.normalize_paragraph("   \n  ")), 0)

    def test_008_collapse_newlines(self):
        self.assertEqual(textnorm.collapse("a  b\nc"), "a b c")

    def test_009_search_keeps_case(self):
        self.assertEqual(textnorm.normalize_search("A  B"), "A B")

    def test_010_search_limit(self):
        self.assertLessEqual(len(textnorm.normalize_search("x" * 100, limit=10)), 10)


class HashTests(unittest.TestCase):
    def test_011_sha256_known(self):
        self.assertEqual(
            hashing.sha256_text("abc"),
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        )

    def test_012_bytes_matches_text(self):
        self.assertEqual(hashing.sha256_bytes(b"abc"), hashing.sha256_text("abc"))

    def test_013_empty_hash_length(self):
        self.assertEqual(len(hashing.sha256_text("")), 64)

    def test_014_aggregate_length(self):
        self.assertEqual(len(hashing.aggregate_hash([("a", "1"), ("b", "2")])), 64)

    def test_015_aggregate_stable(self):
        first = hashing.aggregate_hash([("a", "1"), ("b", "2")])
        second = hashing.aggregate_hash([("a", "1"), ("b", "2")])
        self.assertEqual(first, second)

    def test_016_short_id_length(self):
        self.assertTrue(8 <= len(hashing.short_id("x" * 64, "C:/p")) <= 32)


class ParagraphTests(unittest.TestCase):
    def test_017_two_paragraphs(self):
        self.assertEqual(len(paragraphs.split_paragraphs("段一\n\n段二")), 2)

    def test_018_fence_not_split(self):
        self.assertEqual(len(paragraphs.split_paragraphs("```\na\n\nb\n```")), 1)

    def test_019_paragraph_has_text(self):
        values = paragraphs.split_paragraphs("段一")
        self.assertEqual(values[0]["text"], "段一")

    def test_020_paragraph_has_hash(self):
        self.assertTrue(paragraphs.split_paragraphs("段一")[0]["hash"])

    def test_021_empty_body(self):
        self.assertEqual(len(paragraphs.split_paragraphs("   ")), 0)

    def test_022_dedupe_keys(self):
        result = paragraphs.dedupe_group([{"skill_id": "a", "paragraphs": []}])
        self.assertEqual(set(result.keys()), {"kept", "dropped", "near_dupes"})

    def test_023_dedupe_lists(self):
        result = paragraphs.dedupe_group([{"skill_id": "a", "paragraphs": []}])
        self.assertIsInstance(result["kept"], list)

    def test_024_paragraph_order(self):
        values = paragraphs.split_paragraphs("一\n\n二\n\n三")
        self.assertEqual([item["text"] for item in values], ["一", "二", "三"])


class ConflictTests(unittest.TestCase):
    def test_025_auto(self):
        self.assertEqual(conflict.decision_for(1.0), "auto")

    def test_026_suggest(self):
        self.assertEqual(conflict.decision_for(0.72), "suggest")

    def test_027_review_high(self):
        self.assertEqual(conflict.decision_for(0.5), "review")

    def test_028_review_boundary(self):
        self.assertEqual(conflict.decision_for(0.35), "review")

    def test_029_conflict(self):
        self.assertEqual(conflict.decision_for(0.2), "conflict")

    def test_030_sim_text(self):
        self.assertEqual(conflict.sim_text(0.5), "0.500")

    def test_031_sim_text_na(self):
        self.assertEqual(conflict.sim_text(None), "NA")

    def test_032_conflict_comment(self):
        self.assertEqual(
            conflict.format_conflict("s1", "n", 0.2),
            "<!-- conflict: source=s1:n, sim=0.200 -->",
        )


class PlanTests(unittest.TestCase):
    def test_033_canonical_sorted(self):
        self.assertEqual(plan.canonical_json({"b": 1, "a": 2}).strip(), '{"a":2,"b":1}')

    def test_034_canonical_list_order(self):
        self.assertEqual(plan.canonical_json([3, 1, 2]).strip(), "[3,1,2]")

    def test_035_canonical_unicode(self):
        self.assertEqual(json.loads(plan.canonical_json({"k": "中文"}))["k"], "中文")

    def test_036_plan_hash_length(self):
        self.assertEqual(len(plan.plan_hash({"a": 1})), 64)

    def test_037_plan_hash_stable(self):
        self.assertEqual(plan.plan_hash({"a": 1}), plan.plan_hash({"a": 1}))

    def test_038_canonical_nested(self):
        value = json.loads(plan.canonical_json({"z": {"b": 2, "a": 1}}))
        self.assertEqual(value["z"]["a"], 1)


class FsopsTests(unittest.TestCase):
    def test_039_safe_slash(self):
        self.assertEqual(fsops.safe_component("a/b"), "a-b")

    def test_040_safe_colon(self):
        self.assertEqual(fsops.safe_component("a:b"), "a-b")

    def test_041_safe_no_forbidden(self):
        value = fsops.safe_component('a<>:"/\\|?*b')
        for char in '<>:"/\\|?*':
            self.assertNotIn(char, value)

    def test_042_is_within_true(self):
        with tempfile.TemporaryDirectory() as root:
            child = str(Path(root) / "child")
            self.assertTrue(fsops.is_within(child, root))

    def test_043_is_within_false(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as other:
            self.assertFalse(fsops.is_within(other, root))

    def test_044_system_path(self):
        self.assertTrue(fsops.is_system_path("C:/Windows"))

    def test_045_normal_path_not_system(self):
        self.assertFalse(fsops.is_system_path("D:/projects/skills"))

    def test_046_assert_inside_raises(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(DomainError):
                fsops.assert_inside(str(Path(root).parent / "escape"), root)


class NamerTests(unittest.TestCase):
    def test_047_slugify_basic(self):
        self.assertEqual(namer.slugify("Hello World"), "hello-world")

    def test_048_slugify_chinese(self):
        self.assertEqual(namer.slugify("中文名"), "")

    def test_049_slugify_max_length(self):
        self.assertLessEqual(len(namer.slugify("a" * 200, add_hash=True)), 64)

    def test_050_forbidden_hit(self):
        self.assertEqual(namer.forbidden_hits("claude-helper", RULE | {"name": {"forbidden_parts": ["claude"]}}), ["claude"])

    def test_051_forbidden_none(self):
        self.assertEqual(namer.forbidden_hits("helper", RULE), [])

    def test_052_slugify_lowercases(self):
        self.assertEqual(namer.slugify("ABC"), "abc")


class ValidateTests(unittest.TestCase):
    def test_053_compliant_has_no_errors(self):
        self.assertEqual(errors(run_preflight(RULE, _spec())), [])

    def test_054_checks_is_list(self):
        self.assertIsInstance(run_preflight(RULE, _spec()), list)

    def test_055_long_name(self):
        found = errors(run_preflight(RULE, _spec(name="a" * 130, layout_name="a" * 130)))
        self.assertTrue(any(item["id"] == "V-NAME-01" for item in found))

    def test_056_long_description(self):
        found = errors(run_preflight(RULE, _spec(description="x" * 2000)))
        self.assertTrue(any(item["id"] == "V-DESC-01" for item in found))

    def test_057_missing_h1(self):
        found = errors(run_preflight(RULE, _spec(text="body only")))
        self.assertTrue(any(item["id"] == "V-MD-03" for item in found))

    def test_058_dedupe_checks(self):
        checks = [{"id": "V-NAME-01", "level": "error", "message": "x", "fix": "y", "phase": "preflight"}]
        self.assertEqual(len(dedupe_checks(checks + checks)), 1)


class ParserTests(unittest.TestCase):
    def test_059_markdown_headings(self):
        info = parse_markdown("# Title\n\n## A\n\ntext\n\n## B\n")
        self.assertEqual(len(info.headings), 3)

    def test_060_duplicate_heading_count(self):
        info = parse_markdown("# Title\n\n## A\n\nx\n\n## A\n\ny\n")
        self.assertEqual(duplicate_heading_count(info.headings), 1)

    def test_061_frontmatter_split(self):
        frontmatter, body, ok, warns = split_frontmatter("---\nname: x\n---\n# T\n")
        self.assertIn("name: x", frontmatter)
        self.assertTrue(ok)
        self.assertEqual(warns, [])

    def test_062_document_description(self):
        document = parse_document("---\nname: x\ndescription: d\n---\n# T\n")
        self.assertEqual(document.description(), "d")

    def test_063_decode_bom(self):
        text, _has_bom, _warnings = decode_bytes(b"\xef\xbb\xbfhello")
        self.assertEqual(text, "hello")

    def test_064_yaml_nested(self):
        result = parse_yaml("a: 1\nb:\n  - x\n  - y\nc: true\n")
        self.assertEqual(result.data["b"], ["x", "y"])
        self.assertIs(result.data["c"], True)


class ClassifyTests(unittest.TestCase):
    def test_065_data_analysis(self):
        config = SimpleNamespace(categories=(), slug_map={})
        result = classify_text("报表助手", "生成统计报告和数据图表", config)
        self.assertEqual(result["category"], "数据分析")

    def test_066_unknown_category(self):
        config = SimpleNamespace(categories=(), slug_map={})
        result = classify_text("zzz", "qqq", config)
        self.assertEqual(result["category"], "未分类")
        self.assertLess(result["confidence"], 0.5)


def main() -> int:
    suite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    total = result.testsRun
    failed = len(result.failures) + len(result.errors)
    print(f"selftest: {total} 项，失败 {failed} 项", file=sys.stderr)
    if failed or total < 60:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())