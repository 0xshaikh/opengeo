"""CLI wiring tests. SERP endpoints are pinned by the autouse fixture in
conftest.py, so these are hermetic and only exercise click/rich/output logic."""
import json
import pytest

from opengeo.cli import cli
from opengeo.report import generate_report


FIXED = {
    "engine": "bing",
    "coverage": "ok",
    "notes": ["unit fixture"],
    "answer": None,
    "organic": [
        {"rank": 1, "title": "Python is a high-level language", "url": "https://docs.python.org/3/",
         "domain": "docs.python.org",
         "snippet": "Python is a high-level, general-purpose programming language. What is python?"},
        {"rank": 2, "title": "The best 5 ways to learn python", "url": "https://learn.example.org/",
         "domain": "learn.example.org",
         "snippet": "A list of the best ways to learn python, step by step."},
        {"rank": 3, "title": "Python official site", "url": "https://www.python.org/",
         "domain": "python.org",
         "snippet": "The Python Programming Language. Why use python?"},
    ],
    "ai_signals": {},
}

FIXED_IA = {"query": "python", "answer_type": "ABSTRACT",
            "body": "Python is a programming language used for web development.",
            "definition": None, "related_topics": [], "sources": []}


def test_cli_help(runner):
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "opengeo" in result.output


def test_cli_version(runner):
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_visibility_command_json(runner):
    result = runner.invoke(cli, ["visibility", "example.com", "-q", "example python", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["brand_domain"] == "example.com"
    assert data["queries"] == ["example python"]
    assert data["results"]
    assert data["score"]["label"]
    assert data["coverage_summary"]


def test_visibility_command_table(runner):
    result = runner.invoke(cli, ["visibility", "example.com", "-q", "example python"])
    assert result.exit_code == 0, result.output
    assert "Visibility" in result.output


def test_visibility_queries_file(runner, tmp_path):
    qf = tmp_path / "queries.txt"
    qf.write_text("# one query per line\nexample python\npython tutorial\n")
    result = runner.invoke(cli, ["visibility", "example.com", "--queries-file", str(qf), "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert set(data["queries"]) == {"example python", "python tutorial"}


def test_visibility_requires_queries(runner):
    result = runner.invoke(cli, ["visibility", "example.com"])
    assert result.exit_code == 2


def test_visibility_save_to_db(runner, tmp_path):
    db = str(tmp_path / "h.sqlite")
    result = runner.invoke(cli, ["--db", db, "visibility", "example.com",
                                 "-q", "example python", "--save", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["saved_run_id"] == 1
    hist = runner.invoke(cli, ["--db", db, "history", "--json"])
    assert hist.exit_code == 0
    assert json.loads(hist.output)["rows"]


def test_brief_command_json(runner):
    result = runner.invoke(cli, ["brief", "python", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["keyword"] == "python"
    assert data["outline"]
    assert data["title_options"]
    assert data["schema_recommendation"]["primary_type"]
    assert data["sources"]["results_used"] == 3


def test_brief_command_table(runner):
    result = runner.invoke(cli, ["brief", "python"])
    assert result.exit_code == 0, result.output
    assert "Title options" in result.output
    assert "Outline" in result.output


def test_quality_command_offline(runner, monkeypatch):
    from tests.fixtures import WIKI_LIKE
    import opengeo.cli as cli_mod
    monkeypatch.setattr(cli_mod.fetch, "get_text", lambda *a, **k: WIKI_LIKE)
    result = runner.invoke(cli, ["quality", "https://example.org/python", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert 0 <= data["overall_score"] <= 100
    assert data["heading_structure"]["h1_count"] == 1
    assert data["recommendations"]


def test_report_command_writes_pdf(runner, tmp_path):
    out = tmp_path / "r.pdf"
    result = runner.invoke(cli, ["report", "-o", str(out), "--company", "Acme SEO",
                                 "--domain", "example.com", "-q", "example python",
                                 "--keyword", "python"])
    assert result.exit_code == 0, result.output
    assert out.exists() and out.stat().st_size > 1000
    assert result.output.splitlines()[-1].endswith("r.pdf")


def test_report_command_json_inputs(runner, tmp_path):
    vis = json.loads(runner.invoke(
        cli, ["visibility", "example.com", "-q", "example python", "--json"]).output)
    br = json.loads(runner.invoke(cli, ["brief", "python", "--json"]).output)
    vis_file = tmp_path / "v.json"
    br_file = tmp_path / "b.json"
    vis_file.write_text(json.dumps(vis))
    br_file.write_text(json.dumps(br))
    out = tmp_path / "combo.pdf"
    result = runner.invoke(cli, ["report", "-o", str(out), "--company", "Acme",
                                 "--visibility-json", str(vis_file),
                                 "--brief-json", str(br_file)])
    assert result.exit_code == 0, result.output
    assert out.stat().st_size > 1000


def test_report_requires_input(runner, tmp_path):
    result = runner.invoke(cli, ["report", "-o", str(tmp_path / "x.pdf")])
    assert result.exit_code == 2


def test_report_with_bad_logo_does_not_crash(runner, tmp_path):
    bad = tmp_path / "logo.png"
    bad.write_bytes(b"not a png at all")
    out = tmp_path / "nologo.pdf"
    result = runner.invoke(cli, ["report", "-o", str(out), "--logo", str(bad),
                                 "--keyword", "python"])
    assert result.exit_code == 0, result.output
    assert out.exists()


def test_generate_report_minimal(tmp_path):
    out = generate_report(out=str(tmp_path / "m.pdf"), company="Acme",
                          visibility=None, brief=None, page=None)
    assert out.startswith(str(tmp_path))
