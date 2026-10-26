"""AI/SEO content briefs.

Inputs are *real* search results plus the keyless DuckDuckGo Instant Answers
API. Output is titles, a heading outline with word targets, entities, related
questions, featured-snippet / PAA intent signals and a JSON-LD recommendation.

No LLM is called: the brief is assembled deterministically from real SERP data
so the output is reproducible and there is nothing to fabricate.
"""
from __future__ import annotations

import re
from typing import Iterable, Optional

from opengeo import serp
from opengeo.entities import dedupe, extract_entities, related_questions

INTENT_RULES: list[tuple[str, re.Pattern]] = [
    ("comparison", re.compile(r"\b(vs\.?|versus|compare[ds]?|comparison|differences?|which is better)\b", re.I)),
    ("best_of", re.compile(r"\b(best|top|cheapest|affordable|recommended|worth it)\b", re.I)),
    ("how_to", re.compile(r"\bhow\s+(do\s+i|can\s+i|to\s+do)\b|how to\b|step-by-step", re.I)),
    ("what", re.compile(r"^what\b|\bwhat is\b|\bwhat are\b", re.I)),
    ("why", re.compile(r"^why\b|\bwhy do\b|\bwhy is\b", re.I)),
    ("who_where", re.compile(r"^(who|where)\b|\bwho does\b|\bwhere to\b", re.I)),
    ("how_much", re.compile(r"\bhow much\b|\bprice|pricing|cost(s)?|free\b", re.I)),
]

WORD_TARGETS = {
    "how_to": (1200, 1800),
    "best_of": (1500, 2500),
    "comparison": (1200, 2000),
    "what": (700, 1100),
    "why": (900, 1400),
    "who_where": (700, 1100),
    "how_much": (800, 1300),
    "informational": (1000, 1600),
}

TITLE_TEMPLATES = {
    "how_to": [
        "How to {kw}: A Complete Step-by-Step Guide",
        "{Kw} - The Definitive Step-by-Step Guide",
    ],
    "best_of": [
        "The Best {kw} in {year}: Reviewed and Ranked",
        "Top {Kw} Options - How to Choose Wisely",
    ],
    "comparison": [
        "{Kw}: A Detailed Comparison and Verdict",
        "Which {kw} Should You Choose? Side-by-Side Comparison",
    ],
    "what": [
        "What Is {kw}? A Clear Explanation",
        "{Kw} Explained: Everything You Need to Know",
    ],
    "why": [
        "Why {kw}? The Evidence Explained",
        "The Real Reason {kw}",
    ],
    "who_where": [
        "{Kw}: Who, Where, and Why It Matters",
        "Where to Find {kw} and Who to Ask",
    ],
    "how_much": [
        "{Kw}: Real Costs and Pricing Explained",
        "How Much Does {kw} Cost? A Pricing Guide",
    ],
    "informational": [
        "{Kw}: The Complete Guide",
        "Everything You Need to Know About {kw}",
    ],
}


def detect_intent(query: str) -> tuple[str, float]:
    """Return (intent, confidence). Highest-scoring rule wins."""
    best = ("informational", 0.0)
    for name, pattern in INTENT_RULES:
        if pattern.search(query):
            conf = 0.9 if name != "informational" else 0.4
            if conf > best[1]:
                best = (name, conf)
    return best


def word_targets(intent: str) -> dict:
    lo, hi = WORD_TARGETS.get(intent, WORD_TARGETS["informational"])
    return {"min": lo, "max": hi, "recommended": (lo + hi) // 2}


def title_options(keyword: str, intent: str) -> list[str]:
    templates = TITLE_TEMPLATES.get(intent, TITLE_TEMPLATES["informational"])
    year = "2026"
    out: list[str] = []
    for tpl in templates:
        out.append(tpl.format(kw=keyword, Kw=keyword, year=year))
    return out


def outline_sections(intent: str, entities: list[str], questions: list[str],
                     keyword: str = "") -> list[dict]:
    ents = entities[:6]
    qs = questions[:5]
    sections: list[dict] = [
        {"heading": "Introduction", "level": 2, "words": 120, "angle": "hook + answer preview"},
        {"heading": "What {kw} Means", "level": 2, "words": 200, "angle": "definition paragraph"},
    ]
    if intent in ("how_to",):
        sections += [
            {"heading": "Step-by-Step Walkthrough", "level": 2, "words": 450, "angle": "numbered steps"},
            {"heading": "Common Mistakes to Avoid", "level": 2, "words": 200, "angle": "pitfalls list"},
        ]
    elif intent == "best_of":
        sections += [
            {"heading": "How We Evaluated", "level": 2, "words": 250, "angle": "criteria table"},
            {"heading": "Top Picks Compared", "level": 2, "words": 500, "angle": "list items"},
        ]
    elif intent == "comparison":
        sections += [
            {"heading": "Side-by-Side Comparison", "level": 2, "words": 400, "angle": "comparison table"},
            {"heading": "Verdict: Which Should You Pick", "level": 2, "words": 200, "angle": "recommendation"},
        ]
    else:
        sections += [
            {"heading": "Key Facts and Evidence", "level": 2, "words": 350, "angle": "bulleted facts"},
            {"heading": "How It Works in Practice", "level": 2, "words": 300, "angle": "example"},
        ]

    for ent in ents:
        sections.append({"heading": f"{ent} in Depth", "level": 3, "words": 150,
                         "angle": f"entity deep-dive for '{ent}'"})
    if qs:
        sections.append({"heading": "Frequently Asked Questions", "level": 2, "words": 300,
                         "angle": "answer each question with an H3"})
    sections += [
        {"heading": "Conclusion", "level": 2, "words": 120, "angle": "recap + CTA"},
    ]
    return [_fill(s, keyword=keyword or "{kw}") for s in sections]


def _fill(section: dict, keyword: str = "{kw}", year: str = "2026") -> dict:
    """Substitute {kw}/{Kw}/{year} placeholders left in outline text."""
    return {k: str(v).format(kw=keyword, Kw=keyword, year=year)
            if isinstance(v, str) and "{" in v else v
            for k, v in section.items()}


def _snippet_of(result) -> str:
    """Accept either a parsed result dict or a raw snippet string."""
    if isinstance(result, dict):
        return result.get("snippet") or ""
    return str(result or "")


LIST_PAT = re.compile(r"\b(list|lists|listed|step-by-step|steps|ways|types|kinds|best|top)\b", re.I)
DEF_PAT = re.compile(r"\b(?:is|are|refers to|means)\b", re.I)
NUM_PAT = re.compile(r"\b\d+\.\s")


def detect_featured_snippet(results: Iterable) -> dict:
    """Detect list/definition/how-to intent from real snippets.

    Signal-weighted rather than count-based: several different markers
    ("ways", "list", "step by step") each add points to the list bucket, so a
    page that talks about "5 ways" and "a list of" reads as list intent even
    when only one snippet carries the exact word "list".
    """
    snippets = [_snippet_of(r) for r in results]
    n = len(snippets)
    listish = sum(1 for s in snippets if LIST_PAT.search(s))
    definitionish = sum(1 for s in snippets if DEF_PAT.search(s))
    numbered = sum(1 for s in snippets if NUM_PAT.search(s))
    paa_like = sum(1 for s in snippets if "?" in s)

    list_score = listish + sum(1 for s in snippets
                               if re.search(r"\bstep[s]? by step\b", s, re.I))
    kind: Optional[str] = None
    if definitionish >= max(2, (n + 1) // 2) and definitionish > list_score:
        kind = "definition"
    elif list_score >= max(2, (n + 1) // 2):
        kind = "list"
    elif numbered >= max(1, n // 4):
        kind = "how-to"
    elif paa_like >= max(1, n // 3):
        kind = "faq"

    return {
        "likely_type": kind,
        "evidence": {
            "snippets_scanned": n,
            "list_signals": listish,
            "definition_signals": definitionish,
            "numbered_signals": numbered,
            "question_signals": paa_like,
        },
        "snippet_style_words": "40-60 words, first sentence answers the query",
        "paa_detected": bool(paa_like),
    }


def intent_from_snippets(snippets: Iterable[str]) -> Optional[str]:
    """Refine an intent guess from the SERP snippets actually returned.

    Position-aware: the top-ranked result carries the most signal, so a single
    "best / top / ways" hit in rank one is enough to promote an informational
    query to ``best_of``; further down the list a majority is required.
    """
    snips = [s for s in snippets if s]
    if not snips:
        return None
    best = [bool(re.search(r"\b(best|top|cheapest|recommended|ways)\b", s, re.I))
            for s in snips]
    how = [bool(re.search(r"\b(how to|step-by-step|steps)\b", s, re.I)) for s in snips]
    what = [bool(re.search(r"\bwhat is\b", s, re.I)) for s in snips]
    half = max(2, len(snips) // 2)
    if best[0] or sum(best) >= half:
        return "best_of"
    if how[0] or sum(how) >= half:
        return "how_to"
    if what[0] or sum(what) >= half:
        return "what"
    return None


def schema_recommendation(intent: str, keyword: str, questions: list[str], entities: list[str]) -> dict:
    if intent == "how_to":
        primary = "HowTo"
        ld = {
            "@context": "https://schema.org",
            "@type": "HowTo",
            "name": keyword,
            "step": [{"@type": "HowToStep", "name": "Step 1", "text": "..."}],
        }
    elif intent == "best_of" or intent == "comparison":
        primary = "Article"
        ld = {
            "@context": "https://schema.org",
            "@type": "Review",
            "itemReviewed": {"@type": "Product", "name": keyword},
            "reviewRating": {"@type": "Rating", "ratingValue": "0", "bestRating": "5"},
        }
    elif intent in ("what", "why", "who_where", "how_much"):
        primary = "Article"
        ld = {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": keyword,
            "description": "...",
            "keywords": ", ".join(entities[:5]),
        }
    else:
        primary = "Article"
        ld = {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": keyword,
            "keywords": ", ".join(entities[:5]),
        }
    extras: list[dict] = []
    if questions:
        extras.append({
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": "..."}}
                           for q in questions[:5]],
        })
    if intent == "how_to":
        extras.append({
            "@context": "https://schema.org",
            "@type": "HowTo",
            "name": keyword,
            "totalTime": "PT10M",
        })
    return {"primary_type": primary, "jsonld": ld, "additional": extras,
            "rationale": f"'{intent}' intent maps best to {primary}"}


def build_brief(query: str, results: dict, *, include_instant: bool = True,
                top_n: int = 10) -> dict:
    intent, conf = detect_intent(query)
    organic = (results.get("organic") or [])[:top_n]
    snippets = [r.get("snippet") or "" for r in organic]
    titles = [r.get("title") or "" for r in organic]

    # SERP snippets can upgrade an informational query to best_of / how_to when
    # the returned pages are clearly list or tutorial content.
    refined = intent_from_snippets(snippets)
    if refined and intent == "informational":
        intent = refined
        conf = 0.7

    ddg = serp.query_ddg_instant(query) if include_instant else {}
    instant_texts = ([ddg.get("body")] if ddg.get("body") else []) + \
                    [t.get("text") or "" for t in ddg.get("related_topics") or []] + \
                    [s.get("text") or "" for s in ddg.get("sources") or []]

    # Frequency >= 2 keeps SERP snippets from injecting one-off noise phrases.
    entities = dedupe(extract_entities(titles + snippets + instant_texts,
                                       min_count=2))[:15]
    questions = dedupe(related_questions(snippets + instant_texts))[:8]
    snippet_info = detect_featured_snippet(organic)
    schema = schema_recommendation(intent, query, questions, entities)
    outline = outline_sections(intent, entities, questions, keyword=query)

    return {
        "keyword": query,
        "intent": {"label": intent, "confidence": round(conf, 2)},
        "title_options": title_options(query, intent),
        "outline": outline,
        "word_targets": word_targets(intent),
        "entities": entities,
        "related_questions": questions,
        "featured_snippet": snippet_info,
        "schema_recommendation": schema,
        "sources": {
            "engine": results.get("engine"),
            "coverage": results.get("coverage"),
            "results_used": len(organic),
            "instant_answers_type": ddg.get("answer_type"),
            "instant_related_topics": len(ddg.get("related_topics") or []),
            "notes": results.get("notes") or [],
        },
    }
