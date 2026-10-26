<div align="center">

<a href="https://github.com/0xshaikh/opengeo"><img src="icon.svg" alt="opengeo" width="150" height="150"></a>

<h1>opengeo</h1>

<p>
  <a href="https://pypi.org/project/opengeo/"><img src="favicon.svg" alt="" width="22" height="22" align="center"> pip install opengeo</a>
</p>

**Keyless AI-search visibility (GEO), SEO content briefs, on-page content quality,
and white-label PDF reports — one CLI, zero paid API keys.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/0xshaikh/opengeo/actions/workflows/ci.yml/badge.svg)](https://github.com/0xshaikh/opengeo/actions)

Every number `opengeo` prints comes from a real HTTP response. Nothing is
fabricated, and nothing requires an account, a credit card, or an API key.

</div>

---

## Why this exists

Search traffic is shifting to answer engines — ChatGPT, Perplexity, Gemini,
the Bing Copilot column, DuckDuckGo AI answers. The question nobody asks a
website yet is: **when a user asks that question, is *my* domain in the answer?**

`opengeo` answers that, plus the content work that drives it, without selling
you a seat.

It is deliberately narrow. Crawling, backlinks, rank tracking and analytics
already have their own tools — `opengeo` sits on top and covers the layer that
doesn't:

| Area | Tool |
| --- | --- |
| AI-search visibility (GEO) | **opengeo** |
| SEO content briefs | **opengeo** |
| On-page content quality | **opengeo** |
| White-label PDF reports | **opengeo** |
| Crawling & technical audits | openserp |
| Backlinks | openlink |
| Analytics | openanalytics |

## Install

```console
$ python -m pip install opengeo
$ opengeo --version
opengeo, version 0.1.0
```

Requires Python 3.10+. No credentials to configure.

## Commands

```console
$ opengeo --help
Usage: opengeo [OPTIONS] COMMAND [ARGS]...

  opengeo - keyless AI-search visibility (GEO), SEO content briefs, on-page
  content quality, and white-label PDF reports.

Options:
  --version   Show the version and exit.
  --db TEXT   SQLite history database path.
  -h, --help  Show this message and exit.

Commands:
  brief       Produce an AI/SEO content brief for KEYWORD from real SERP...
  history     Show stored visibility history and trends from the SQLite...
  quality     On-page readability + AI-readability + schema validation...
  report      Build a white-label PDF report combining the other three...
  visibility  Check whether DOMAIN is mentioned across public AI/SERP...
```

---

## 1. `visibility` — is my domain in the answer?

```console
$ opengeo visibility python.org -q "python programming"
Checking 1 query/q x 3 engine(s)...
╭────────────────────────────────────────────────────────────────────────── opengeo visibility ───────────────────────────────────────────────────────────────────────────╮
│ Brand: python.org                                                                                                                                                │
│ Queries: 1   Engines: google, bing, duckduckgo                                                                                                                  │
│ Visibility: 45.0  (partial visibility)                                                                                                                         │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
┏━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃Query              ┃ Engine     ┃ Coverage ┃ In answer ┃ In organic ┃ Notes                                       ┃
┡━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│python programming │ google     │ blocked  ┃    n/a    │     no     │ Google captcha/bot wall - results withheld, │
│python programming │ bing       │ ok       │    n/a    │     no     │ best-effort public SERP scrape              │
│python programming │ duckduckgo │ ok       │    yes    │    yes     │ best-effort public SERP scrape              │
└───────────────────┴────────────┴──────────┴───────────┴────────────┴───────────────────────────────────────────────┘
Coverage observed: blocked, ok
Best-effort, keyless. opengeo does not query ChatGPT/Perplexity/Gemini directly - no free API exists.
```

Flags: repeat `-q` for many queries, or `--queries-file queries.txt` (one per
line, `#` comments). `--engine google` narrows to one answer layer. `--save`
persists the run to the SQLite history DB.

### The honesty contract

There is no free API for ChatGPT, Perplexity or Gemini, and no keyless endpoint
that returns their citations. So `opengeo` does **not** pretend to query them.
It measures brand presence across the *public* SERP and answer-box layers that
are reachable without credentials, and reports each engine's state as `ok` or
`blocked`. A blocked engine yields `unknown` — never a fabricated zero. When
`google` is blocked by a captcha wall you see `blocked` in the table, and the
score is computed only over the engines that actually returned data.

```console
$ opengeo visibility python.org -q "python programming" --json
{
  "brand_domain": "python.org",
  "queries": ["python programming"],
  "engines_requested": ["google", "bing", "duckduckgo"],
  "coverage_summary": ["blocked", "ok"],
  "score": {
    "score": 45.0,
    "label": "partial visibility",
    "breakdown": {
      "engine_query_pairs": 2,
      "mentions_in_organic": 1,
      "mentions_in_answer": 1,
      "top5_placements": 1,
      "ai_overview_markers": 0,
      "weights": {"organic": 60, "answer": 30, "ai_marker": 10}
    },
    "reason": "scored only from engines that returned data"
  }
}
```

Note the `reason` field: the denominator is the two engines that actually
answered, not all three.

---

## 2. `brief` — content briefs from real SERP data

```console
$ opengeo brief "best electric cars 2026"
╭────────────────────────────────────────────────────────────────────────── opengeo brief ───────────────────────────────────────────────────────────────────────────╮
│ Keyword: best electric cars 2026                                                                                                                                  │
│ Intent: best_of (confidence 0.90)                                                                                                                             │
│ Word target: 1500-2500 (recommended 2000)                                                                                                                     │
│ Entities: 1   Related questions: 0   Featured snippet: list                                                                                                     │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯

Title options
  1. The Best best electric cars 2026 in 2026: Reviewed and Ranked
  2. Top best electric cars 2026 Options - How to Choose Wisely

Outline
┏━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃Level ┃ Heading                               ┃ Words ┃ Angle                                 ┃
┡━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ H2   │ Introduction                          │   120 │ hook + answer preview                 │
│ H2   │ What best electric cars 2026 Means    │   200 │ definition paragraph                  │
│ H2   │ How We Evaluated                      │   250 │ criteria table                        │
│ H2   │ Top Picks Compared                    │   500 │ list items                            │
│ H3   │ Oct in Depth                          │   150 │ entity deep-dive for 'Oct'            │
│ H2   │ Conclusion                            │   120 │ recap + CTA                           │
└──────┴───────────────────────────────────────┴───────┴───────────────────────────────────────┘

Entities  Oct

Schema  Article   'best_of' intent maps best to Article

Source: bing (ok), 10 results, Instant Answers: 0 topics
```

The keyword intent is inferred from the query string itself (commercial,
informational, `best_of`, how-to, comparative), which drives the word target
and the schema recommendation. Entity and question extraction is regex-based on
real SERP snippets — deliberately conservative. When the SERP gives no clean
entities, `opengeo` says so instead of inventing any: pass `--json` and inspect
`"entities": []` rather than an unprompted guess.

```console
$ opengeo brief "best electric cars 2026" --json | python -c "import json,sys; d=json.load(sys.stdin); print(list(d.keys()))"
['keyword', 'intent', 'title_options', 'outline', 'word_targets', 'entities', 'related_questions', 'featured_snippet', 'schema_recommendation', 'sources']
```

---

## 3. `quality` — on-page content quality

Real output against `https://www.python.org/`:

```console
$ opengeo quality https://www.python.org/
╭────────────────────────────────────────────────────────────────────────── opengeo quality ───────────────────────────────────────────────────────────────────────────╮
│ URL: https://www.python.org/                                                                                                                                         │
│ Title: Welcome to Python.org                                                                                                                                        │
│ Overall: 68.3 (C)                                                                                                                                                  │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
┏━━━━━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━┓
┃Dimension        ┃ Score ┃ Grade┃
┡━━━━━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━┩
│Readability      │  91.2 │   A  │
│Ai Readability   │  34.6 │   F  │
│Structure        │  76.0 │   B  │
│Internal Linking │  65.5 │   D  │
│Schema           │    80 │   B  │
└─────────────────┴───────┴──────┘

Readability  755 words / 59 sentences  Flesch 57.6 (fairly difficult (college))  grade 8.4
Paragraphs  17 paragraphs, median 17 words, 0% long
Lists  31.8 items per 1k words   Definition paragraphs  6%   Chunking  11.8
Headings  14 total, H1=5, level jumps=0 issues
Schema  JSON-LD blocks=1 types=WebSite  canonical=no  errors=0

Recommendations
  1. Readability is low (Flesch 57.6); target 60-70 by shortening sentences and trimming long words.
  2. Chunking friendliness is low; aim for 100-500 word paragraphs.
  3. Use exactly one H1 and do not skip heading levels (found 5 H1 tags and 0 level jumps).
  4. No <link rel="canonical"> found; add one so engines resolve the duplicate-free version of this URL.
```

Five dimensions:

| Dimension | What it measures |
| --- | --- |
| Readability | Flesch Reading Ease (rewarding the 55–70 window search content needs), Flesch-Kincaid grade, Dale-Chall |
| AI Readability | definition-paragraph ratio, enumerated-answer density, LLM chunking friendliness |
| Structure | exactly one H1, no skipped heading levels, paragraph-length variance |
| Internal Linking | internal vs external ratio, links per 1000 words |
| Schema | JSON-LD presence and validity, canonical, meta description |

Site chrome — `nav`, `footer`, `svg`, `iframe`, `template` — is stripped
*before* measuring, so a page with a 40-item mega menu does not score worse for
list density than the page with one. The full machine-readable form:

```console
$ opengeo quality https://www.python.org/ --json
{
  "url": "https://www.python.org/",
  "title": "Welcome to Python.org",
  "overall_score": 68.3,
  "overall_grade": "C",
  "scores": {
    "readability": 91.2,
    "ai_readability": 34.6,
    "structure": 76.0,
    "internal_linking": 65.5,
    "schema": 80
  },
  "readability": {
    "word_count": 755,
    "sentence_count": 59,
    "avg_words_per_sentence": 12.8,
    "flesch_reading_ease": 57.6,
    "flesch_kincaid_grade": 8.4,
    "reading_level": "fairly difficult (college)"
  },
  "schema": {
    "jsonld_count": 1,
    "types": ["WebSite"],
    "has_canonical": false,
    "has_meta_description": true
  },
  "links": {
    "link_count": 68,
    "internal_count": 21,
    "external_count": 47,
    "internal_ratio": 0.309,
    "links_per_1000_words": 69.8,
    "has_internal_links": true
  }
}
```

---

## 4. `report` — white-label PDFs

```console
$ opengeo report --company "Acme Growth Lab" \
    --page https://www.python.org/ \
    --keyword "python framework" \
    --domain python.org -q "python programming" -q "django" \
    -o report.pdf
Running visibility for python.org...
Building brief for python framework...
Rendering report.pdf...
Report written: report.pdf
$ file report.pdf
report.pdf: PDF document, version 1.3, 6 page(s)
```

The PDF is a real 6-page document generated with fpdf2, embedding your company
name on every page, your PNG logo if you pass `--logo`, and the live visibility
score, brief outline and quality breakdown. Feed it saved JSON to avoid
re-fetching:

```console
$ opengeo visibility python.org -q "python programming" --json > vis.json
$ opengeo brief "python framework" --json > brief.json
$ opengeo report --company "Acme Growth Lab" \
    --visibility-json vis.json --brief-json brief.json --logo brand.png \
    --page https://www.python.org/ -o report.pdf
```

---

## 5. `history` — track visibility over time

`--save` on `visibility` appends a run to a SQLite database
(`~/.opengeo/history.db` by default, override with `--db`).

```console
$ opengeo history --list
┏━━━━━━━━━━━━┳━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┓
┃Domain      ┃ Runs ┃ Latest                    ┃ Last score┃
┡━━━━━━━━━━━━╇━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━┩
│python.org  │ 3    │ 2026-10-26T16:20:06+00:00 │ 37.5      │
│example.com │ 2    │ 2026-10-26T15:59:47+00:00 │ 0.0       │
└────────────┴──────┴───────────────────────────┴───────────┘

$ opengeo history --domain python.org
┏━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━┓
┃Run ┃ Timestamp                 ┃ Query              ┃ Engine     ┃ Answer ┃ Organic ┃ Coverage┃
┡━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━┩
│#5  │ 2026-10-26T16:20:06+00:00 │ python programming │ google     │  n/a   │   no    │ blocked │
│#5  │ 2026-10-26T16:20:06+00:00 │ python programming │ bing       │  n/a   │   no    │ ok      │
│#5  │ 2026-10-26T16:20:06+00:00 │ python programming │ duckduckgo │  yes   │   yes   │ ok      │
│#5  │ 2026-10-26T16:20:06+00:00 │ django             │ google     │  n/a   │   no    │ blocked │
│#5  │ 2026-10-26T16:20:06+00:00 │ django             │ bing       │  n/a   │   no    │ ok      │
│#5  │ 2026-10-26T16:20:06+00:00 │ django             │ duckduckgo │   no   │   yes   │ ok      │
└────┴───────────────────────────┴────────────────────┴────────────┴────────┴─────────┴─────────┘
```

---

## What every number means (and what it doesn't)

**No paid API keys.** Everything runs against public endpoints: Bing and
DuckDuckGo HTML search, the DuckDuckGo Instant Answers endpoint, and the page
you pass to `quality`.

**No fabricated data.** If an engine returns a captcha wall, the row says
`blocked` with `in_answer: n/a`. The overall score is the mean over engines
that actually answered. A page with no JSON-LD reports `jsonld_count: 0`; it
is never given one synthetically. Entity extraction returns `[]` when the SERP
is too noisy to trust.

**Visibility is directional, not a Google rank.** A `45.0` means the brand
appeared in the answer box or organic results of some reachable layer for some
queries. It is not a citation score from ChatGPT or Perplexity — those require
paid APIs, and `opengeo` will not invent a proxy for them.

**Readability scores are text-level heuristics.** Flesch, Dale-Chall and the
chunking metric operate on extracted prose after chrome removal. They are
calibrated for search/answer content, not for medical or legal review.

**Entity extraction is deliberately conservative.** Regex-based, and biased
toward silence: a candidate entity that appears only once in a snippet is
dropped rather than reported, because SERP snippets contain a lot of
title-truncation noise.

## Extending

All of the above are importable, so `opengeo` doubles as a library:

```python
from opengeo.fetch import fetch_url
from opengeo.quality import analyze
from opengeo.text_extraction import extract_text

doc = extract_text(fetch_url("https://www.python.org/").html)
report = analyze(doc)
print(report["overall_score"], report["recommendations"])
```

To add a new answer layer, write a `query_<engine>(query, count)` function in
`opengeo/serp.py` that returns the same shape as the others —
`{"coverage", "notes", "results", "answer_box"}` — then branch on it in
`visibility._query_engine` and add it to `ENGINE_ORDER`. It then flows into
`visibility`, `history` and `report` with no other changes.

## Development

```console
$ pip install -e ".[dev]"
$ pytest -q
```

The test suite marks anything touching the network with `@pytest.mark.network`;
`pytest -m "not network"` runs the deterministic suite offline. CI
(`.github/workflows/ci.yml`) tests Python 3.10–3.13 on ubuntu-latest and
builds the wheel and sdist on every push.

## Roadmap

- **Real citation APIs.** If you have a paid LLM API key, `opengeo` should be able to
  feed your queries into it and record actual citations. This is the one thing the
  keyless build cannot do, and it is the highest-value extension.
- **Scheduler.** A cron-friendly `opengeo watch --schedule daily` that appends runs
  to the history DB automatically, so the trend table fills itself.
- **More answer layers.** Perplexity and Copilot columns are parseable HTML today
  in principle; they have not been validated against current markup yet.
- **Multi-page quality scans.** Accept a URL list or sitemap and produce a rollup
  rather than requiring one URL per invocation.
- **Markdown / HTML report output** alongside PDF, for teams that want to diff reports.

## Contributing

Issues and PRs are welcome. To work on it:

```console
$ git clone https://github.com/0xshaikh/opengeo
$ cd opengeo
$ python -m venv .venv && . .venv/bin/activate
$ pip install -e ".[dev]"
$ pytest -q
```

Guidelines:

- **Never fabricate data.** If a source is unreachable, return `null` / `unknown`
  with a reason string. The tests assert on real parsing and scoring behaviour —
  keep them green.
- Keep dependencies minimal and pure-Python; there is deliberately no ML framework.
- Network-dependent tests are marked `@pytest.mark.network`; add new ones the same
  way so the offline suite stays fast and deterministic.
- Prefer extending an existing command over adding a shallow new one.

## How each command gets its data

There are no paid APIs anywhere in this codebase. Here is the actual data path
for each command:

| Command | Data source | Mechanism |
| --- | --- | --- |
| `visibility` | Bing SERP, DuckDuckGo HTML SERP + Instant Answers, Google SERP | `requests` with an identifying User-Agent, parsed with BeautifulSoup |
| `brief` | same SERP layer + DuckDuckGo Instant Answers API | intent inferred from the query string, signals extracted from real snippets |
| `quality` | the single page you pass | HTML fetched, chrome removed, then measured locally |
| `report` | the other three commands | composes their real output into an fpdf2 document |
| `history` | `~/.opengeo/history.db` | plain SQLite, one file, created on first `--save` |

Request hygiene lives in `opengeo/fetch.py`: per-host timeouts, retry with
exponential backoff and jitter, and a User-Agent of
`opengeo/0.1.0 (+https://github.com/0xshaikh/opengeo)` so operators can tell
`opengeo` traffic apart from scrapers they don't know about.

Parsing order matters for `quality`. Site chrome (`nav`, `footer`, `svg`,
`iframe`, `template`) is decomposed *before* any metric is computed, so a page
with a 40-item mega menu does not lose readability points for list density.
JSON-LD and meta tags are captured from the original tree first, so stripping
chrome never discards structured data.

## License

MIT — see [LICENSE](LICENSE).
