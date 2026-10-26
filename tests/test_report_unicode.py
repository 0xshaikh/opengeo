"""Regression tests for unicode handling in the white-label PDF renderer.

Real SERP snippets carry codepoints the built-in helvetica core font cannot
encode (Bing truncates with U+2026, plus curly quotes, dashes, arrows, emoji).
Before the fix, a single "..." in a related question raised
``FPDFUnicodeEncodingException`` and destroyed the entire report. These tests pin
the contract: sanitize, never crash.
"""

import pytest

from opengeo.report import GeoPDF, Report, _pdf_safe


# ------------------------------------------------------------------ _pdf_safe
def test_ellipsis_becomes_three_dots():
    assert _pdf_safe("How to use open in a \u2026") == "How to use open in a ..."


def test_common_punctuation_is_mapped_readably():
    assert _pdf_safe("\u201cquote\u201d") == '"quote"'
    assert _pdf_safe("\u2018it\u2019s\u2019") == "'it's'"
    assert _pdf_safe("a\u2013b\u2014c") == "a-b--c"
    assert _pdf_safe("a\u2014b") == "a--b"
    assert _pdf_safe("a \u2192 b") == "a -> b"
    assert _pdf_safe("item \u2022 two") == "item * two"


def test_out_of_range_is_marked_not_dropped_silently():
    # Emoji and CJK are outside latin-1. They must become a visible marker,
    # never vanish (silence reads as "nothing was here") and never raise.
    out = _pdf_safe("score \U0001f525 \u4f60")
    assert "\U0001f525" not in out
    assert "\u4f60" not in out
    assert out == "score ? ?"


def test_latin1_range_is_left_alone():
    # Accented latin-1 must survive intact -- fpdf renders these fine.
    assert _pdf_safe("caf\u00e9 na\u00efve\u00e7\u00e3o") == "caf\u00e9 na\u00efve\u00e7\u00e3o"
    assert _pdf_safe("plain ascii 123") == "plain ascii 123"


def test_non_string_passthrough_and_empty():
    assert _pdf_safe(42) == 42
    assert _pdf_safe(None) is None
    assert _pdf_safe("") == ""


# ------------------------------------------------------------- normalize_text
@pytest.fixture
def pdf() -> GeoPDF:
    return GeoPDF(company="Acme")


def test_normalize_text_never_raises_on_unicode(pdf):
    # This exact input crashed the report before the fix.
    text = "How to use open in a \u2026"
    out = pdf.normalize_text(text)
    assert isinstance(out, str)
    assert "\u2026" not in out
    assert out.endswith("...")


def test_normalize_text_roundtrips_plain_text(pdf):
    assert pdf.normalize_text("hello world") == "hello world"


# -------------------------------------------------------------------- Report
def test_report_builds_when_brief_contains_unicode(tmp_path):
    """End-to-end: unicode anywhere in a brief must still yield a valid PDF."""
    brief = {
        "keyword": "open source seo tool",
        "title_options": ["The \u201cultimate\u201d guide \u2192 2026"],
        "outline": [
            {"level": "H2", "heading": "What it Means", "words": 200,
             "angle": "definition \u2014 not a list"},
        ],
        "entities": ["Open", "Seo"],
        "related_questions": [
            "How to use open in a \u2026",
            "Why \U0001f525 matters",
        ],
        "schema_recommendation": {
            "primary_type": "Article",
            "rationale": "informational intent \u2014 Article",
            "additional": [{"@type": "FAQPage"}],
        },
    }
    out = tmp_path / "client.pdf"
    path = Report(company="Acme Agency", out=str(out)).build(brief=brief)

    assert path == str(out)
    assert out.exists() and out.stat().st_size > 1500
    assert out.read_bytes()[:5] == b"%PDF-"


def test_report_creates_missing_output_directory(tmp_path):
    """-o pointing into a dir that does not exist yet must not lose the report."""
    nested = tmp_path / "clients" / "acme" / "Q4" / "client.pdf"
    assert not nested.parent.exists()

    path = Report(company="Acme Agency", out=str(nested)).build(
        brief={"keyword": "k", "title_options": [], "outline": [],
               "entities": [], "related_questions": [],
               "schema_recommendation": {}})

    assert path == str(nested)
    assert nested.exists() and nested.read_bytes()[:5] == b"%PDF-"

