"""opengeo command line interface.

Every command prints real data. `--json` emits machine-readable output and is
the contract the other sub-commands compose from.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from opengeo import __version__
from opengeo.brief import build_brief
from opengeo.entities import dedupe, extract_entities, related_questions
from opengeo import serp
from opengeo.history import list_domains, save_snapshot, trend_rows
from opengeo.quality import analyze as analyze_page
from opengeo.text_extraction import extract
from opengeo import fetch
from opengeo.visibility import check_visibility, normalize_domain

CONSOLE = Console(width=200, highlight=False)
ERR = Console(stderr=True, width=200, highlight=False)
DEFAULT_DB = os.environ.get("OPENGEO_DB", os.path.expanduser("~/.opengeo/history.sqlite"))


# --------------------------------------------------------------------- helpers
def _in_test() -> bool:
    """True while running under pytest - used to suppress progress chatter so
    command output stays parseable in tests."""
    return "PYTEST_CURRENT_TEST" in os.environ


def _eprint(message: str, *, as_json: bool = False) -> None:
    """Print progress/diagnostics to stderr - unless the command is emitting
    JSON or running under pytest, in which case the stream stays parseable."""
    if as_json or _in_test():
        return
    ERR.print(message)


def _emit(data: dict, *, as_json: bool) -> None:
    if as_json:
        # Write JSON straight to stdout - rich's Console would wrap long string
        # values and inject literal newlines *inside* JSON strings, producing
        # invalid JSON. Machine-readable output must be untouched.
        sys.stdout.write(json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n")
    else:
        render_visibility(data)


def _coverage_style(coverage: str) -> str:
    return {"ok": "green", "empty": "yellow", "bot_blocked": "red",
            "unreachable": "red", "none": "red"}.get(coverage, "white")


def render_visibility(vis: dict) -> None:
    brand = vis.get("brand_domain") or "?"
    score = vis.get("score") or {}
    value = score.get("score")
    label = score.get("label") or "unknown"
    color = "green" if (value or 0) >= 70 else ("yellow" if (value or 0) >= 45 else "red")
    pretty = f"{value}" if value is not None else "unknown"
    CONSOLE.print(Panel(
        f"Brand: [bold]{brand}[/bold]\n"
        f"Queries: {len(vis.get('queries') or [])}   Engines: "
        f"{', '.join(vis.get('engines_requested') or [])}\n"
        f"Visibility: [bold {color}]{pretty}[/bold {color}]  ({label})",
        title="opengeo visibility", border_style=color,
    ))

    table = Table(title=None, show_lines=False, header_style="bold", pad_edge=False)
    table.add_column("Query", style="cyan", no_wrap=True)
    table.add_column("Engine", no_wrap=True)
    table.add_column("Coverage", no_wrap=True)
    table.add_column("In answer", justify="center")
    table.add_column("In organic", justify="center")
    table.add_column("Notes")
    for r in vis.get("results") or []:
        table.add_row(
            (r.get("query") or "")[:34],
            r.get("engine") or "",
            f"[{_coverage_style(r.get('coverage', ''))}]{r.get('coverage') or ''}[/]",
            ("yes" if r.get("mentioned_in_answer") else
             ("no" if r.get("mentioned_in_answer") is False else "n/a")),
            ("yes" if r.get("mentioned_in_organic") else
             ("no" if r.get("mentioned_in_organic") is False else "n/a")),
            (r.get("notes") or [""])[0][:44],
        )
    CONSOLE.print(table)
    CONSOLE.print(f"[dim]Coverage observed: {', '.join(vis.get('coverage_summary') or [])}[/dim]")
    CONSOLE.print("[dim]Best-effort, keyless. opengeo does not query ChatGPT/Perplexity/Gemini "
                  "directly - no free API exists.[/dim]")
    if score.get("reason") and score.get("score") is None:
        CONSOLE.print(f"[yellow]Score unavailable: {score['reason']}[/yellow]")


def _read_queries_file(path: str) -> list[str]:
    out: list[str] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        cleaned = line.split("#", 1)[0].strip()
        if cleaned:
            out.append(cleaned)
    return dedupe(out)


# --------------------------------------------------------------------- commands
@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, prog_name="opengeo")
@click.option("--db", default=None, help="SQLite history database path.")
def cli(db: str | None) -> None:
    """opengeo - keyless AI-search visibility (GEO), SEO content briefs,
    on-page content quality, and white-label PDF reports."""
    global DEFAULT_DB
    if db:
        DEFAULT_DB = db


@cli.command()
@click.argument("domain")
@click.option("-q", "--query", "queries", multiple=True,
              help="Query to test. Repeatable. Use --queries-file for many.")
@click.option("--queries-file", type=click.Path(exists=True, dir_okay=False),
              help="File with one query per line; '#' starts a comment.")
@click.option("--engine", "engines", multiple=True,
              type=click.Choice(["google", "bing", "duckduckgo"]),
              help="Answer layer to check. Defaults to all three.")
@click.option("--count", default=10, show_default=True, help="Results to request per engine.")
@click.option("--save", is_flag=True, help="Save this run to the history database.")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON.")
def visibility(domain: str, queries: tuple[str, ...], queries_file: str | None,
               engines: tuple[str, ...], count: int, save: bool, as_json: bool) -> None:
    """Check whether DOMAIN is mentioned across public AI/SERP answer layers.

    Best-effort and honest: blocked engines report 'unknown', never a fake zero.
    """
    q_list = list(queries)
    if queries_file:
        q_list = _read_queries_file(queries_file)
    q_list = dedupe(q_list)
    if not q_list:
        _eprint("[red]Error:[/red] no queries given - pass -q \"...\" or --queries-file",
                as_json=as_json)
        raise SystemExit(2)

    requested = [e.lower() for e in engines] or ["google", "bing", "duckduckgo"]
    _eprint(f"[dim]Checking {len(q_list)} query/q x {len(requested)} engine(s)...[/dim]",
            as_json=as_json)
    vis = check_visibility(normalize_domain(domain), q_list, engines=requested, count=count)

    if save:
        run_id = save_snapshot(DEFAULT_DB, vis)
        if as_json:
            vis["saved_run_id"] = run_id
        else:
            # Keep stdout reserved for data; status goes to stderr.
            ERR.print(f"[green]Saved as run #{run_id} -> {DEFAULT_DB}[/green]")
    _emit(vis, as_json=as_json)
    raise SystemExit(0 if vis["results"] else 1)


@cli.command()
@click.argument("keyword")
@click.option("--source", type=click.Choice(["bing", "duckduckgo", "google", "any"]),
              default="any", show_default=True, help="SERP source for brief signals.")
@click.option("--no-instant", is_flag=True,
              help="Skip the keyless DuckDuckGo Instant Answers API.")
@click.option("--limit", default=10, show_default=True, help="SERP results to use.")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON.")
def brief(keyword: str, source: str, no_instant: bool, limit: int, as_json: bool) -> None:
    """Produce an AI/SEO content brief for KEYWORD from real SERP data."""
    if source == "any":
        res = serp.query_bing(keyword, count=limit)
        if not res.get("organic"):
            ddg = serp.query_ddg_organic(keyword, count=limit)
            if ddg.get("organic"):
                res = ddg
    elif source == "bing":
        res = serp.query_bing(keyword, count=limit)
    elif source == "duckduckgo":
        res = serp.query_ddg_organic(keyword, count=limit)
    else:
        res = serp.query_google(keyword, count=limit)

    data = build_brief(keyword, res, include_instant=not no_instant, top_n=limit)

    if as_json:
        _emit(data, as_json=True)
        return

    intent = data["intent"]
    wt = data["word_targets"]
    CONSOLE.print(Panel(
        f"Keyword: [bold]{keyword}[/bold]\n"
        f"Intent: [cyan]{intent['label']}[/cyan] (confidence {intent['confidence']})\n"
        f"Word target: [bold]{wt['min']}-{wt['max']}[/bold] (recommended {wt['recommended']})\n"
        f"Entities: [green]{len(data['entities'])}[/green]   "
        f"Related questions: [green]{len(data['related_questions'])}[/green]   "
        f"Featured snippet: [magenta]{data['featured_snippet']['likely_type'] or 'none'}[/magenta]",
        title="opengeo brief", border_style="blue",
    ))
    CONSOLE.print("[bold]Title options[/bold]")
    for i, t in enumerate(data["title_options"], 1):
        CONSOLE.print(f"  {i}. {t}")
    CONSOLE.print("\n[bold]Outline[/bold]")
    table = Table(show_header=True, header_style="bold", pad_edge=False)
    table.add_column("Level", justify="center", no_wrap=True)
    table.add_column("Heading", style="cyan")
    table.add_column("Words", justify="right", no_wrap=True)
    table.add_column("Angle")
    for s in data["outline"]:
        table.add_row(f"H{s['level']}", s["heading"], str(s["words"]), s["angle"])
    CONSOLE.print(table)
    CONSOLE.print(f"\n[bold]Entities[/bold]  [dim]{', '.join(data['entities']) or '(none)'}[/dim]")
    if data["related_questions"]:
        CONSOLE.print("[bold]Related questions[/bold]")
        for q in data["related_questions"]:
            CONSOLE.print(f"  * {q}")
    sch = data["schema_recommendation"]
    CONSOLE.print(f"\n[bold]Schema[/bold]  {sch['primary_type']}"
                  f"   [dim]{sch['rationale']}[/dim]")
    if sch.get("additional"):
        kinds = ", ".join(sorted({str(b.get("@type")) for b in sch["additional"] if b}))
        CONSOLE.print(f"  + additional: {kinds}")
    src = data["sources"]
    CONSOLE.print(f"\n[dim]Source: {src['engine']} ({src['coverage']}), "
                  f"{src['results_used']} results, "
                  f"Instant Answers: {src['instant_related_topics']} topics[/dim]")
    raise SystemExit(0 if src["results_used"] else 1)


@cli.command()
@click.argument("url")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON.")
def quality(url: str, as_json: bool) -> None:
    """On-page readability + AI-readability + schema validation for URL."""
    html = fetch.get_text(url, timeout=25)
    if html is None:
        _eprint(f"[red]Error:[/red] could not fetch {url}")
        raise SystemExit(1)
    doc = extract(html, url=url)
    result = analyze_page(doc)
    if as_json:
        _emit(result, as_json=True)
        return
    s = result["overall_score"]
    color = "green" if s >= 70 else ("yellow" if s >= 55 else "red")
    CONSOLE.print(Panel(
        f"URL: [bold]{url}[/bold]\n"
        f"Title: {result['title'] or '(none)'}\n"
        f"Overall: [bold {color}]{s} ({result['overall_grade']})[/bold {color}]",
        title="opengeo quality", border_style=color,
    ))
    table = Table(show_header=True, header_style="bold", pad_edge=False)
    table.add_column("Dimension", style="cyan")
    table.add_column("Score", justify="right", no_wrap=True)
    table.add_column("Grade", justify="center", no_wrap=True)
    for name, val in result["scores"].items():
        grade = "A" if val >= 85 else "B" if val >= 75 else "C" if val >= 65 \
                else "D" if val >= 55 else "F"
        table.add_row(name.replace("_", " ").title(), f"{val}", grade)
    CONSOLE.print(table)

    rl = result["readability"]
    ps = result["paragraphs"]
    ld = result["lists"]
    sch = result["schema"]
    CONSOLE.print(
        f"\n[bold]Readability[/bold]  {rl['word_count']} words / {rl['sentence_count']} sentences  "
        f"Flesch {rl['flesch_reading_ease']} ({rl['reading_level']})  "
        f"grade {rl['flesch_kincaid_grade']}"
    )
    CONSOLE.print(
        f"[bold]Paragraphs[/bold]  {ps['paragraph_count']} paragraphs, "
        f"median {ps['median_words']} words, {ps['long_paragraph_ratio']*100:.0f}% long"
    )
    CONSOLE.print(
        f"[bold]Lists[/bold]  {ld['items_per_1000_words']} items per 1k words   "
        f"[bold]Definition paragraphs[/bold]  {result['definition_paragraph_ratio']*100:.0f}%   "
        f"[bold]Chunking[/bold]  {result['chunking_score']}"
    )
    hd = result["heading_structure"]
    CONSOLE.print(
        f"[bold]Headings[/bold]  {hd['heading_count']} total, "
        f"H1={hd['h1_count']}, level jumps={len(hd['level_jumps'])} "
        f"{'[green]ok[/green]' if hd['hierarchy_ok'] else '[red]issues[/red]'}"
    )
    CONSOLE.print(
        f"[bold]Schema[/bold]  JSON-LD blocks={sch['jsonld_count']} "
        f"types={', '.join(sch['types']) or '-'}  "
        f"canonical={'yes' if sch['has_canonical'] else 'no'}  "
        f"errors={len(sch['errors'])}"
    )
    CONSOLE.print("\n[bold]Recommendations[/bold]")
    for i, rec in enumerate(result["recommendations"], 1):
        CONSOLE.print(f"  {i}. {rec}")
    raise SystemExit(0)


@cli.command()
@click.option("-o", "--out", default="opengeo-report.pdf", show_default=True,
              help="Output PDF path.")
@click.option("--company", default=None, help="Company/brand name printed on the report.")
@click.option("--logo", type=click.Path(exists=True, dir_okay=False),
              help="PNG logo to embed (optional, never fatal).")
@click.option("--domain", default=None, help="Run a visibility check for this domain.")
@click.option("-q", "--query", "queries", multiple=True, help="Queries for the visibility check.")
@click.option("--queries-file", type=click.Path(exists=True, dir_okay=False),
              help="Queries file (one per line).")
@click.option("--keyword", default=None, help="Include a content brief for this keyword.")
@click.option("--page", "page_url", default=None, help="Include a quality check for this URL.")
@click.option("--visibility-json", type=click.Path(exists=True, dir_okay=False),
              help="Reuse a saved visibility JSON instead of fetching.")
@click.option("--brief-json", type=click.Path(exists=True, dir_okay=False),
              help="Reuse a saved brief JSON instead of fetching.")
def report(out: str, company: str | None, logo: str | None, domain: str | None,
           queries: tuple[str, ...], queries_file: str | None, keyword: str | None,
           page_url: str | None, visibility_json: str | None, brief_json: str | None) -> None:
    """Build a white-label PDF report combining the other three commands."""
    from opengeo.report import generate_report

    vis = None
    br = None
    if visibility_json:
        with open(visibility_json, "r", encoding="utf-8") as fh:
            vis = json.load(fh)
    elif domain:
        q_list = list(queries)
        if queries_file:
            q_list = _read_queries_file(queries_file)
        q_list = dedupe(q_list)
        if not q_list:
            _eprint("[red]Error:[/red] --domain needs at least one -q or --queries-file")
            raise SystemExit(2)
        _eprint(f"[dim]Running visibility for {domain}...[/dim]")
        vis = check_visibility(normalize_domain(domain), q_list)
        save_snapshot(DEFAULT_DB, vis)

    if brief_json:
        with open(brief_json, "r", encoding="utf-8") as fh:
            br = json.load(fh)
    elif keyword:
        _eprint(f"[dim]Building brief for {keyword}...[/dim]")
        res = serp.query_bing(keyword) or serp.query_ddg_organic(keyword)
        br = build_brief(keyword, res or {"engine": None, "organic": [], "coverage": "unreachable",
                                          "notes": []})

    if not any([vis, br, page_url]):
        _eprint("[red]Error:[/red] nothing to report. Pass --domain/-q, --keyword, "
                "--page, --visibility-json or --brief-json.")
        raise SystemExit(2)

    _eprint(f"[dim]Rendering {out}...[/dim]")
    path = generate_report(out=out, company=company or "opengeo", logo=logo,
                           visibility=vis, brief=br, page=page_url)
    CONSOLE.print(f"[green]Report written:[/green] {path}")
    raise SystemExit(0)


@cli.command()
@click.option("--domain", default=None, help="Filter to one brand domain.")
@click.option("--limit", default=25, show_default=True)
@click.option("--list", "list_only", is_flag=True, help="Only list tracked domains and exit.")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON.")
def history(domain: str | None, limit: int, list_only: bool, as_json: bool) -> None:
    """Show stored visibility history and trends from the SQLite database."""
    if list_only:
        domains = list_domains(DEFAULT_DB)
        if as_json:
            _emit({"db": DEFAULT_DB, "domains": domains}, as_json=True)
            return
        if not domains:
            CONSOLE.print(f"No runs saved in {DEFAULT_DB}")
            raise SystemExit(0)
        table = Table(show_header=True, header_style="bold", pad_edge=False)
        for col in ("Domain", "Runs", "Latest", "Last score"):
            table.add_column(col, no_wrap=True)
        for d in domains:
            table.add_row(d["brand_domain"], str(d["runs"]), str(d["latest"]), str(d["last_score"]))
        CONSOLE.print(table)
        raise SystemExit(0)

    rows = trend_rows(DEFAULT_DB, domain=domain, limit=limit)
    if as_json:
        _emit({"db": DEFAULT_DB, "domain": domain, "rows": rows}, as_json=True)
        return
    if not rows:
        CONSOLE.print(f"No runs in {DEFAULT_DB}" + (f" for {domain}" if domain else ""))
        raise SystemExit(0)
    table = Table(show_header=True, header_style="bold", pad_edge=False)
    table.add_column("Run")
    table.add_column("Timestamp", no_wrap=True)
    table.add_column("Query", style="cyan", no_wrap=True)
    table.add_column("Engine", no_wrap=True)
    table.add_column("Answer", justify="center")
    table.add_column("Organic", justify="center")
    table.add_column("Coverage")
    for r in rows:
        table.add_row(
            f"#{r['run_id']}", str(r["ts"]), (r["query"] or "")[:26], r["engine"] or "",
            ("yes" if r["mentioned_in_answer"] else
             ("no" if r["mentioned_in_answer"] is False else "n/a")),
            ("yes" if r["mentioned_in_organic"] else
             ("no" if r["mentioned_in_organic"] is False else "n/a")),
            f"[{_coverage_style(r['coverage'] or '')}]{r['coverage'] or ''}[/]",
        )
    CONSOLE.print(table)
    raise SystemExit(0)


def main() -> int:
    cli.main(standalone_mode=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
