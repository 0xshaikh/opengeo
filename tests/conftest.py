"""Shared test fixtures.

Tests are split two ways:
  * anything marked `offline` gets every SERP endpoint pinned to a fixed
    fixture via the autouse `_fake_network` fixture, so unit and CLI tests are
    hermetic and fast;
  * `test_smoke.py` is marked `network` and deliberately makes real requests.
"""
import pytest


pytestmark = None  # module-level marks belong in individual test modules


def pytest_configure(config):
    config.addinivalue_line("markers", "offline: hermetic test using pinned SERP fixtures")
    config.addinivalue_line("markers", "network: test that requires outbound internet access")


def pytest_collection_modifyitems(config, items):
    """Auto-apply `offline` to every test module except the network smoke tests."""
    skip_markers = {"test_smoke"}
    for item in items:
        if "network" in item.keywords:
            continue
        if item.fspath.basename.split("test_")[-1].replace(".py", "") in skip_markers:
            continue
        item.add_marker(pytest.mark.offline)


@pytest.fixture
def runner():
    """Click >= 8.4 removed `CliRunner(mix_stderr=...)`, so fall back
    gracefully and keep the suite green on old and new Click alike."""
    from click.testing import CliRunner
    try:
        return CliRunner(mix_stderr=False)
    except TypeError:
        return CliRunner()


@pytest.fixture(autouse=True)
def _fake_network(request, monkeypatch):
    """Pin SERP endpoints for hermetic tests only."""
    if request.node.get_closest_marker("network") is not None:
        yield
        return

    import opengeo.serp as serp_mod
    import opengeo.brief as brief_mod

    fixed = {
        "engine": "bing", "coverage": "ok", "notes": ["unit fixture"], "answer": None,
        "organic": [
            {"rank": 1, "title": "Python is a high-level language",
             "url": "https://docs.python.org/3/", "domain": "docs.python.org",
             "snippet": "Python is a high-level, general-purpose programming language. What is python?"},
            {"rank": 2, "title": "The best 5 ways to learn python",
             "url": "https://learn.example.org/", "domain": "learn.example.org",
             "snippet": "A list of the best ways to learn python, step by step."},
            {"rank": 3, "title": "Python official site", "url": "https://www.python.org/",
             "domain": "python.org", "snippet": "The Python Programming Language. Why use python?"},
        ],
        "ai_signals": {},
    }
    fixed_ia = {"query": "python", "answer_type": "ABSTRACT",
                "body": "Python is a programming language used for web development.",
                "definition": None, "related_topics": [], "sources": []}
    monkeypatch.setattr(serp_mod, "query_bing", lambda q, count=10: fixed)
    monkeypatch.setattr(serp_mod, "query_ddg_organic", lambda q, count=10: dict(fixed))
    monkeypatch.setattr(serp_mod, "query_ddg_instant", lambda q: fixed_ia)
    monkeypatch.setattr(serp_mod, "query_google", lambda q, count=10: {
        "engine": "google", "query": q, "organic": fixed["organic"], "answer": None,
        "ai_signals": {"ai_overview_marker": False, "blocked": False},
        "coverage": "ok", "notes": []})
    monkeypatch.setattr(brief_mod.serp, "query_ddg_instant", lambda q: fixed_ia)
    yield
