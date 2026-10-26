from opengeo.history import list_domains, save_snapshot, trend_rows
from opengeo.visibility import _brand_rank, check_visibility, normalize_domain, score_visibility


def _payload(domain="example.com", query="example python"):
    return {
        "brand_domain": domain,
        "queries": [query],
        "engines_requested": ["bing"],
        "coverage_summary": ["ok"],
        "results": [
            {"query": query, "engine": "bing", "brand_domain": domain,
             "coverage": "ok", "mentioned_in_answer": False, "mentioned_in_organic": True,
             "answer_text": None, "brand_rank": 2, "ai_signals": {},
             "notes": ["ok"], "results": []},
        ],
        "score": {"score": 50.0, "label": "partial visibility",
                  "breakdown": {"engines_usable": 1}, "reason": "unit fixture"},
        "disclaimer": "test",
    }


def test_history_roundtrip(tmp_path):
    db = str(tmp_path / "hist.sqlite")
    assert list_domains(db) == []
    rid = save_snapshot(db, _payload())
    assert rid == 1
    rid2 = save_snapshot(db, _payload(domain="other.net", query="other query"))
    assert rid2 == 2

    domains = list_domains(db)
    assert len(domains) == 2
    assert {d["brand_domain"] for d in domains} == {"example.com", "other.net"}

    rows = trend_rows(db)
    assert len(rows) == 2
    assert all("mentioned_in_organic" in r for r in rows)

    filtered = trend_rows(db, domain="example.com")
    assert len(filtered) == 1
    assert filtered[0]["brand_domain"] == "example.com"
    assert filtered[0]["brand_rank"] == 2


def test_score_visibility_returns_unknown_when_no_data():
    from opengeo.visibility import VisibilityResult
    results = [
        VisibilityResult(query="q", engine="bing", brand_domain="x.com",
                         coverage="bot_blocked"),
        VisibilityResult(query="q", engine="google", brand_domain="x.com",
                         coverage="unreachable"),
    ]
    score = score_visibility(results)
    assert score["score"] is None
    assert score["label"] == "unknown"
    assert "no engine returned data" in score["reason"]


def test_score_visibility_rewards_mentions():
    from opengeo.visibility import VisibilityResult
    hit = VisibilityResult(query="q", engine="bing", brand_domain="x.com", coverage="ok",
                           mentioned_in_organic=True, mentioned_in_answer=True,
                           brand_rank=1)
    miss = VisibilityResult(query="q", engine="bing", brand_domain="x.com", coverage="ok",
                            mentioned_in_organic=False, mentioned_in_answer=False)
    assert score_visibility([hit])["score"] > score_visibility([miss])["score"]
    # Full organic + answer presence: 60 + 30 = 90 out of the 100 available.
    assert score_visibility([hit])["score"] == 90.0


def test_brand_rank_finds_own_domain_only():
    results = [
        {"rank": 1, "url": "https://blog.google/ai"},
        {"rank": 2, "url": "https://www.example.com/about"},
        {"rank": 3, "url": "https://example.co.uk/x"},
    ]
    assert _brand_rank(results, "example.com") == 2
    assert _brand_rank(results, "example.co.uk") == 3
    assert _brand_rank(results, "wikipedia.org") is None


def test_check_visibility_with_no_engines_selected():
    out = check_visibility("example.com", ["example python"], engines=[])
    assert out["results"] == []
    assert out["brand_domain"] == "example.com"
    assert out["score"]["score"] is None
    assert out["score"]["label"] == "unknown"


def test_normalize_domain():
    assert normalize_domain("https://www.example.com/path?q=1") == "example.com"
    assert normalize_domain("WWW.Example.COM") == "example.com"
    assert normalize_domain("example.com:8080") == "example.com"
