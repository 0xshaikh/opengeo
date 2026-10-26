from opengeo.text_extraction import extract, normalize_url
from opengeo.schema import extract_jsonld, validate_jsonld, validate_schema, canonical_url
from opengeo.quality import analyze, grade, internal_linking

from tests.fixtures import WIKI_LIKE, NO_JSONLD, EMPTY_JSONLD


def test_extract_pulls_structured_text():
    doc = extract(WIKI_LIKE, "https://example.org/python")
    assert doc.title == "Python explained"
    assert "Python is a high-level" in (doc.meta_description or "")
    levels = [lvl for lvl, _ in doc.headings]
    assert levels == [1, 2, 2]
    assert len(doc.list_items) == 4
    assert len(doc.links) == 5


def test_normalize_url_makes_absolute_and_strips_query():
    assert normalize_url("/docs/intro.html", "https://x.com/a?b=1") == "https://x.com/docs/intro.html"
    assert normalize_url("https://x.com/p?ref=1", "https://x.com") == "https://x.com/p"
    assert normalize_url("javascript:void(0)", "https://x.com") == "javascript:void(0)"


def test_jsonld_validation_passes_for_well_formed():
    doc = extract(WIKI_LIKE, "https://example.org/python")
    blocks = extract_jsonld(doc.scripts)
    assert len(blocks) == 1
    assert validate_jsonld(blocks[0]) == []
    v = validate_schema(doc)
    assert v["ok"] is True
    assert "Article" in v["types"]
    assert v["has_canonical"] is True


def test_jsonld_validation_reports_missing_context():
    doc = extract(EMPTY_JSONLD, "https://example.org")
    blocks = extract_jsonld(doc.scripts)
    assert len(blocks) == 1
    errors = validate_jsonld(blocks[0])
    assert any("missing required field '@context'" in e for e in errors)
    assert validate_schema(doc)["ok"] is False


def test_missing_jsonld_detected():
    v = validate_schema(extract(NO_JSONLD, "https://example.org"))
    assert v["has_jsonld"] is False
    assert v["jsonld_count"] == 0
    assert canonical_url(extract(NO_JSONLD, "https://example.org")) is None


def test_quality_analyze_produces_scores_and_recs():
    doc = extract(WIKI_LIKE, "https://example.org/python")
    q = analyze(doc)
    assert 0 <= q["overall_score"] <= 100
    assert q["overall_grade"] in ("A", "B", "C", "D", "F")
    assert q["scores"]["readability"] >= 0
    assert q["heading_structure"]["h1_count"] == 1
    assert len(q["recommendations"]) >= 1


def test_quality_flags_heading_hierarchy_problems():
    # NO_JSONLD has one H1 but jumps straight to H3, so the hierarchy is broken
    # even though the H1 count is right.
    doc = extract(NO_JSONLD, "https://example.org")
    q = analyze(doc)
    hd = q["heading_structure"]
    assert hd["hierarchy_ok"] is False
    assert hd["has_h1"] is True
    assert len(hd["level_jumps"]) >= 1


def test_internal_linking_counts_internal_and_external():
    doc = extract(WIKI_LIKE, "https://example.org/python")
    links = internal_linking(doc)
    assert links["link_count"] == 5
    # relative path + two same-host links are internal; the other two are external
    assert links["internal_count"] == 3
    assert links["external_count"] == 2
    assert links["has_internal_links"] is True


def test_grade_boundaries():
    assert grade(90) == "A"
    assert grade(78) == "B"
    assert grade(66) == "C"
    assert grade(56) == "D"
    assert grade(10) == "F"
