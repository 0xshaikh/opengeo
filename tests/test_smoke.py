"""Network smoke tests: run each CLI command against a real public URL and
assert exit code 0. Marked `network` so CI can run them separately.

These tests deliberately tolerate flaky public endpoints for *data* but assert
that the CLI itself never crashes and always exits 0 - the contract is honest
output, not a guaranteed search hit.
"""
import json

import pytest

pytestmark = pytest.mark.network

REAL_URL = "https://www.python.org/"
REAL_QUERY = "python programming language"


def _reachable() -> bool:
    """True when a public SERP endpoint answers from this host."""
    from opengeo.fetch import get_text
    return get_text("https://html.duckduckgo.com/html/", timeout=10) is not None


REACHABLE = _reachable()


def test_fetch_real_page():
    from opengeo.fetch import get_text, title_of
    html = get_text(REAL_URL, timeout=25)
    assert html is not None
    assert title_of(html)


@pytest.mark.skipif(not REACHABLE, reason="public SERP endpoints unreachable from this host")
def test_visibility_smoke():
    from opengeo.visibility import check_visibility
    out = check_visibility("python.org", [REAL_QUERY], engines=["bing"], count=5)
    assert isinstance(out["results"], list)
    assert out["brand_domain"] == "python.org"
    assert isinstance(out["score"], dict)
    # coverage must be one of the honest values, never silent
    assert all(r["coverage"] in ("ok", "empty", "bot_blocked", "unreachable")
               for r in out["results"])


@pytest.mark.skipif(not REACHABLE, reason="public SERP endpoints unreachable from this host")
def test_brief_smoke():
    from opengeo import serp
    from opengeo.brief import build_brief
    res = serp.query_bing(REAL_QUERY, count=5) or serp.query_ddg_organic(REAL_QUERY, count=5)
    brief = build_brief(REAL_QUERY, res, include_instant=True)
    assert brief["outline"]
    assert brief["word_targets"]["min"] > 0


def test_quality_smoke(runner):
    from opengeo.cli import cli
    result = runner.invoke(cli, ["quality", REAL_URL, "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["url"] == REAL_URL
    assert data["recommendations"]


def test_cli_help_smoke(runner):
    from opengeo.cli import cli
    assert runner.invoke(cli, ["--help"]).exit_code == 0
