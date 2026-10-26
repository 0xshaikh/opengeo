from opengeo.brief import (build_brief, detect_featured_snippet, detect_intent,
                           outline_sections, schema_recommendation, title_options,
                           word_targets)


def _results(snippets, titles=None):
    return {"engine": "bing", "coverage": "ok", "notes": [],
            "organic": [{"rank": i + 1, "title": t, "snippet": s,
                         "url": f"https://x{i}.com/", "domain": f"x{i}.com"}
                        for i, (s, t) in enumerate(zip(snippets, titles or snippets))]}


def test_intent_detection():
    assert detect_intent("how to reset a wifi router")[0] == "how_to"
    assert detect_intent("best project management software")[0] == "best_of"
    assert detect_intent("django vs flask")[0] == "comparison"
    assert detect_intent("what is python")[0] == "what"
    assert detect_intent("why is the sky blue")[0] == "why"
    assert detect_intent("how much does it cost")[0] == "how_much"
    assert detect_intent("quantum entanglement")[0] == "informational"
    assert 0 < detect_intent("how to reset a wifi router")[1] <= 1


def test_word_targets_match_intent():
    assert word_targets("how_to") == {"min": 1200, "max": 1800, "recommended": 1500}
    assert word_targets("best_of")["max"] > word_targets("what")["max"]


def test_title_options_substitute_keyword():
    opts = title_options("python", "how_to")
    assert opts
    assert all("python" in o or "Python" in o for o in opts)


def test_featured_snippet_list_intent():
    res = _results([
        "The best 5 ways to learn python include the interactive method, reading real code, joining a community, and building projects from day one.",
        "A list of the best ways to learn python, step by step, with exercises.",
        "Step by step guide with numbered steps.",
        "Types of python jobs you can get.",
    ])
    info = detect_featured_snippet(res["organic"])
    assert info["likely_type"] in ("list", "how-to")
    assert info["evidence"]["snippets_scanned"] == 4


def test_featured_snippet_definition_intent():
    res = _results([
        "Python is a high-level programming language.",
        "It refers to a tool for scripting tasks.",
        "Python means a lot to beginners.",
    ])
    info = detect_featured_snippet(res["organic"])
    assert info["likely_type"] == "definition"


def test_schema_recommendation_maps_intent():
    s = schema_recommendation("how_to", "learn python", ["Is python free?"], ["Python"])
    assert s["primary_type"] == "HowTo"
    assert s["jsonld"]["@context"] == "https://schema.org"
    assert any(b.get("@type") == "FAQPage" for b in s["additional"])
    s2 = schema_recommendation("comparison", "django vs flask", [], [])
    assert s2["primary_type"] == "Article"


def test_outline_shape():
    secs = outline_sections("how_to", ["Python", "Jinja"], ["Is python free?"])
    assert secs[0]["level"] == 2
    assert all("words" in s and s["words"] > 0 for s in secs)
    assert any(s["level"] == 3 for s in secs)
    assert secs[-1]["heading"] == "Conclusion"


def test_build_brief_without_network():
    res = _results([
        "The best 3 ways to learn python in 2026 are listed here.",
        "Python is a high-level general purpose programming language.",
        "Where can you use python? Use python for web apps and data.",
    ])
    b = build_brief("python", res, include_instant=False)
    assert b["keyword"] == "python"
    assert b["intent"]["label"] in ("best_of", "what")
    assert b["outline"]
    assert b["word_targets"]["recommended"] > 0
    assert isinstance(b["featured_snippet"]["evidence"]["snippets_scanned"], int)
    assert b["sources"]["results_used"] == 3
