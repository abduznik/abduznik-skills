"""
Tests for tools/publish.py — the fail-closed scrub gate and pack builder.

Run with: pytest tests/
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("publish", REPO_ROOT / "tools" / "publish.py")
publish = importlib.util.module_from_spec(SPEC)
sys.modules["publish"] = publish
SPEC.loader.exec_module(publish)


# ---------------------------------------------------------------------------
# extract_frontmatter
# ---------------------------------------------------------------------------

def test_extract_frontmatter_basic():
    text = "---\nname: foo\ndescription: bar\n---\nbody text\n"
    result = publish.extract_frontmatter(text)
    assert result is not None
    fm, body, _ = result
    assert "name: foo" in fm
    assert body == "\nbody text\n"


def test_extract_frontmatter_missing_leading_dashes():
    assert publish.extract_frontmatter("no frontmatter here") is None


def test_extract_frontmatter_unclosed_block():
    assert publish.extract_frontmatter("---\nname: foo\nno closing dashes") is None


# ---------------------------------------------------------------------------
# parse_fm_lines
# ---------------------------------------------------------------------------

def test_parse_fm_lines_simple_scalars():
    fm = "name: foo\ndescription: bar baz"
    entries = publish.parse_fm_lines(fm)
    keys = {e["key"] for e in entries}
    assert keys == {"name", "description"}
    desc = next(e for e in entries if e["key"] == "description")
    assert desc["clean_val"] == "bar baz"


def test_parse_fm_lines_quoted_value():
    fm = 'description: "quoted value"'
    entries = publish.parse_fm_lines(fm)
    assert entries[0]["clean_val"] == "quoted value"


def test_parse_fm_lines_block_list_continuation():
    fm = "metadata:\n  hermes:\n    tags: [a, b]\n    category: devops"
    entries = publish.parse_fm_lines(fm)
    assert len(entries) == 1
    assert entries[0]["key"] == "metadata"
    assert "tags: [a, b]" in entries[0]["val"]


# ---------------------------------------------------------------------------
# normalize_frontmatter
# ---------------------------------------------------------------------------

def test_normalize_frontmatter_inserts_missing_fields():
    fm = "name: foo\ndescription: bar"
    normalized = publish.normalize_frontmatter(fm, "foo", "devops", ["tag1"], {"foo"})
    assert "version: 1.0.0" in normalized
    assert f"author: {publish.PACK_AUTHOR}" in normalized
    assert f"license: {publish.PACK_LICENSE}" in normalized
    assert "category: devops" in normalized


def test_normalize_frontmatter_preserves_existing_fields():
    fm = "name: foo\ndescription: bar\nversion: 2.5.0\nauthor: Someone Else"
    normalized = publish.normalize_frontmatter(fm, "foo", "devops", [], {"foo"})
    assert "version: 2.5.0" in normalized
    assert "author: Someone Else" in normalized
    # must not also insert the pack defaults for fields already present
    assert normalized.count("version:") == 1
    assert normalized.count("author:") == 1


def test_normalize_frontmatter_filters_related_skills_to_pack_internal():
    fm = "name: foo\ndescription: bar\nrelated_skills: [foo, external-only, bar]"
    normalized = publish.normalize_frontmatter(fm, "foo", "devops", [], {"foo", "bar"})
    assert "related_skills: [foo, bar]" in normalized
    assert "external-only" not in normalized


def test_normalize_frontmatter_drops_related_skills_if_all_external():
    fm = "name: foo\ndescription: bar\nrelated_skills: [nowhere-in-pack]"
    normalized = publish.normalize_frontmatter(fm, "foo", "devops", [], {"foo"})
    assert "related_skills" not in normalized


# ---------------------------------------------------------------------------
# run_scrub — the fail-closed privacy gate
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("needle", ["duckdns", "abduznik", "C:\\Users\\someone", "campus", "semester"])
def test_run_scrub_catches_denylisted_terms(needle):
    hits = publish.run_scrub(f"some text with {needle} in it", "test.md")
    assert hits, f"expected a scrub hit for {needle!r}"


def test_run_scrub_case_insensitive_list_is_case_insensitive():
    hits_lower = publish.run_scrub("hosted on duckdns.org", "test.md")
    hits_upper = publish.run_scrub("hosted on DUCKDNS.org", "test.md")
    assert hits_lower and hits_upper


def test_run_scrub_case_sensitive_list_respects_case():
    # "exam" (lowercase, in DENYLIST_CS) should hit; "Exam" should not,
    # since DENYLIST_CS entries are matched case-sensitively by design.
    hits_lower = publish.run_scrub("failed the exam yesterday", "test.md")
    hits_upper = publish.run_scrub("failed the Exam yesterday", "test.md")
    assert hits_lower
    assert not hits_upper


def test_run_scrub_clean_text_has_no_hits():
    hits = publish.run_scrub("This skill helps you debug Docker containers.", "test.md")
    assert hits == []


def test_run_scrub_respects_exclusions():
    hits = publish.run_scrub("sponsor link: abduznik", "test.md", exclusions=("abduznik",))
    assert hits == []


# ---------------------------------------------------------------------------
# md_to_html — minimal markdown renderer
# ---------------------------------------------------------------------------

def test_md_to_html_escapes_html_in_text():
    out = publish.md_to_html("some <script>alert(1)</script> text")
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_md_to_html_renders_code_fence_without_double_escaping():
    out = publish.md_to_html("```\nx = 1 < 2\n```")
    assert "<pre class='code'>" in out
    assert "&lt;" in out


def test_md_to_html_renders_headings():
    out = publish.md_to_html("## Section Title")
    assert "<h2>Section Title</h2>" in out


# ---------------------------------------------------------------------------
# End-to-end: main() against a small fixture skills tree
# ---------------------------------------------------------------------------

@pytest.fixture
def fixture_source(tmp_path):
    src = tmp_path / "source_skills"
    skill_dir = src / "devops" / "sample-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: sample-skill\ndescription: Use when testing the publish pipeline.\n---\n\n"
        "# Sample Skill\n\nBody text with no denylisted terms.\n",
        encoding="utf-8",
    )
    return src


@pytest.fixture
def fixture_manifest(tmp_path, fixture_source):
    manifest_path = tmp_path / "pack_manifest.json"
    manifest_path.write_text(
        json.dumps({
            "repo": "test-pack",
            "skills": [
                {"name": "sample-skill", "rel": "devops/sample-skill", "category": "devops", "tags": ["test"]},
            ],
        }),
        encoding="utf-8",
    )
    return manifest_path


def test_main_builds_pack_from_clean_fixture(tmp_path, fixture_source, fixture_manifest, monkeypatch):
    dest = tmp_path / "dest"
    argv = ["publish.py", "--source", str(fixture_source), "--dest", str(dest), "--manifest", str(fixture_manifest)]
    monkeypatch.setattr(sys, "argv", argv)
    rc = publish.main()
    assert rc == 0
    assert (dest / "skills" / "sample-skill" / "SKILL.md").is_file()
    assert (dest / "README.md").is_file()
    assert (dest / "LICENSE").is_file()
    assert (dest / "docs" / "index.html").is_file()
    assert (dest / "docs" / "skills" / "sample-skill.html").is_file()


def test_main_aborts_build_on_denylisted_content(tmp_path, fixture_source, fixture_manifest, monkeypatch):
    skill_md = fixture_source / "devops" / "sample-skill" / "SKILL.md"
    skill_md.write_text(
        skill_md.read_text(encoding="utf-8") + "\nSecret host: duckdns.org\n",
        encoding="utf-8",
    )
    dest = tmp_path / "dest"
    argv = ["publish.py", "--source", str(fixture_source), "--dest", str(dest), "--manifest", str(fixture_manifest)]
    monkeypatch.setattr(sys, "argv", argv)
    rc = publish.main()
    assert rc == 1
    assert not (dest / "skills").exists()


def test_main_rejects_description_over_1024_chars(tmp_path, fixture_source, fixture_manifest, monkeypatch):
    skill_md = fixture_source / "devops" / "sample-skill" / "SKILL.md"
    long_desc = "x" * 1100
    skill_md.write_text(
        f"---\nname: sample-skill\ndescription: {long_desc}\n---\n\nBody.\n",
        encoding="utf-8",
    )
    dest = tmp_path / "dest"
    argv = ["publish.py", "--source", str(fixture_source), "--dest", str(dest), "--manifest", str(fixture_manifest)]
    monkeypatch.setattr(sys, "argv", argv)
    rc = publish.main()
    assert rc == 1
    assert not (dest / "skills").exists()


def test_main_requires_force_to_overwrite_existing_dest(tmp_path, fixture_source, fixture_manifest, monkeypatch):
    dest = tmp_path / "dest"
    argv = ["publish.py", "--source", str(fixture_source), "--dest", str(dest), "--manifest", str(fixture_manifest)]
    monkeypatch.setattr(sys, "argv", argv)
    assert publish.main() == 0

    # second run without --force must refuse to clobber
    rc = publish.main()
    assert rc == 1
