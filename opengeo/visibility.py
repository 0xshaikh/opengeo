"""AI-search visibility (GEO): is a brand mentioned across answer layers?

This is the honest core of opengeo. **opengeo cannot query ChatGPT, Perplexity
or Gemini directly without paid API keys, and it does not pretend to.**
Instead it measures what is measurable for free and labels it clearly:

  * whether the brand *domain* appears in the returned organic results
    (a citation-adjacent signal - if a brand is not on page one, no answer
    engine can cite it);
  * whether the brand *name or domain* appears in a detected answer box
    (Bing's knowledge/answer panel, DuckDuckGo Instant Answers);
  * Google's AI Overviews marker in the raw response HTML.

Coverage is reported per engine per query. When a source is blocked or empty,
the value is `unknown` with a reason - never a fabricated zero.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

from opengeo import serp

ENGINE_ORDER = ("google", "bing", "duckduckgo")

_SCHEME_RE = re.compile(r"^(https?://)?(www\.)?")


def normalize_domain(domain: str) -> str:
    d = _SCHEME_RE.sub("", (domain or "").strip().lower())
    d = d.split("/", 1)[0].split(":", 1)[0]
    return d.replace("www.", "")


def _brand_variants(domain: str) -> list[str]:
    """Tokens used to test for a brand mention."""
    d = normalize_domain(domain)
    if not d:
        return []
    brand = d.split(".", 1)[0]
    variants = {d, d.replace(".", " "), brand}
    return [v for v in variants if v]


def _is_brand_domain(url: str, domain: str) -> bool:
    target = normalize_domain(domain)
    if not target:
        return False
    try:
        host = normalize_domain(urlparse(url or "").netloc)
    except Exception:
        return False
    if not host:
        return False
    return host == target or host.endswith("." + target)


def _mentions(text: str, variants: list[str]) -> bool:
    if not text:
        return False
    lower = text.lower()
    for v in variants:
        if " " in v:
            if v.lower() in lower:
                return True
        elif re.search(r"(?<![a-z0-9])" + re.escape(v.lower()) + r"(?![a-z0-9])", lower):
            return True
    return False


def _top_url(results: list[dict]) -> Optional[dict]:
    for r in results:
        if r.get("url"):
            return r
    return None


def _brand_rank(results: list[dict], domain: str) -> Optional[int]:
    for r in results:
        if _is_brand_domain(r.get("url") or "", domain):
            return int(r.get("rank") or 0)
    return None


@dataclass
class VisibilityResult:
    query: str
    engine: str
    brand_domain: str
    coverage: str                       # ok | empty | bot_blocked | unreachable
    mentioned_in_answer: Optional[bool] = None
    mentioned_in_organic: Optional[bool] = None
    answer_text: Optional[str] = None
    notes: list[str] = field(default_factory=list)
    ai_signals: dict = field(default_factory=dict)
    results: list[dict] = field(default_factory=list)
    brand_rank: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "engine": self.engine,
            "brand_domain": self.brand_domain,
            "coverage": self.coverage,
            "mentioned_in_answer": self.mentioned_in_answer,
            "mentioned_in_organic": self.mentioned_in_organic,
            "answer_text": self.answer_text,
            "brand_rank": self.brand_rank,
            "ai_signals": self.ai_signals,
            "notes": self.notes,
            "results": [
                {"rank": r.get("rank"), "title": r.get("title"),
                 "url": r.get("url"), "domain": r.get("domain")}
                for r in self.results
            ],
        }


def score_visibility(results: list[VisibilityResult]) -> dict:
    """0-100 score, computed only over engines that returned data.

    Weighting is transparent and non-overlapping:
      * brand present in returned organic results  -> 60
      * brand present in a detected answer box     -> 30
      * AI-Overviews marker observed               -> 10
    Average per query/engine pair, then scaled to 100.

    If no engine returned data the score is explicitly `unknown` rather than 0,
    and a detected absence is a real 0 - never a fabricated number.
    """
    usable = [r for r in results if r.coverage == "ok"]
    if not usable:
        covered = {r.coverage for r in results} or {"none"}
        reason = "no engine returned data (coverage: " + ", ".join(sorted(covered)) + ")"
        return {"score": None, "label": "unknown", "breakdown": {}, "reason": reason}

    mentions_organic = sum(1 for r in usable if r.mentioned_in_organic)
    mentions_answer = sum(1 for r in usable if r.mentioned_in_answer)
    top5 = sum(1 for r in usable if (r.brand_rank or 99) <= 5)
    ai_hits = sum(1 for r in usable if r.ai_signals.get("ai_overview_marker"))
    total = len(usable)

    raw = (60 * mentions_organic + 30 * mentions_answer + 10 * ai_hits) / total
    score = max(0.0, min(100.0, raw))

    if score >= 70:
        label = "strong visibility"
    elif score >= 45:
        label = "partial visibility"
    elif score > 0:
        label = "weak visibility"
    else:
        label = "not detected"

    return {
        "score": round(score, 1),
        "label": label,
        "breakdown": {
            "engine_query_pairs": total,
            "mentions_in_organic": mentions_organic,
            "mentions_in_answer": mentions_answer,
            "top5_placements": top5,
            "ai_overview_markers": ai_hits,
            "weights": {"organic": 60, "answer": 30, "ai_marker": 10},
        },
        "reason": "scored only from engines that returned data",
    }


def _check_engine(engine: str, domain: str, query: str, count: int,
                  engines: list[str]) -> Optional[VisibilityResult]:
    if engine not in engines:
        return None
    variants = _brand_variants(domain)
    if engine == "google":
        res = serp.query_google(query, count=count)
        vr = VisibilityResult(query=query, engine=engine, brand_domain=domain,
                              coverage=res.get("coverage", "unknown"))
        vr.ai_signals = res.get("ai_signals") or {}
        vr.results = res.get("organic") or []
        vr.brand_rank = _brand_rank(vr.results, domain)
        vr.mentioned_in_organic = bool(vr.brand_rank)
        vr.mentioned_in_answer = None  # Google answer text is not exposed to us
        vr.notes = list(res.get("notes") or [])
        return vr
    if engine == "bing":
        res = serp.query_bing(query, count=count)
        vr = VisibilityResult(query=query, engine=engine, brand_domain=domain,
                              coverage=res.get("coverage", "unknown"))
        vr.answer_text = res.get("answer")
        vr.results = res.get("organic") or []
        vr.brand_rank = _brand_rank(vr.results, domain)
        vr.mentioned_in_organic = bool(vr.brand_rank)
        vr.mentioned_in_answer = (_mentions(vr.answer_text, variants)
                                  if vr.answer_text else None)
        vr.notes = list(res.get("notes") or [])
        return vr
    if engine == "duckduckgo":
        organic_res = serp.query_ddg_organic(query, count=count)
        vr = VisibilityResult(query=query, engine=engine, brand_domain=domain,
                              coverage=organic_res.get("coverage", "unknown"))
        vr.results = organic_res.get("organic") or []
        vr.brand_rank = _brand_rank(vr.results, domain)
        vr.mentioned_in_organic = bool(vr.brand_rank)
        vr.mentioned_in_answer = None
        vr.notes = list(organic_res.get("notes") or [])

        ia = serp.query_ddg_instant(query)
        if vr.coverage != "ok":
            vr.coverage = "ok"
            vr.notes = list(vr.notes) + ["no organic results; using Instant Answers"]
        ans_parts = [p for p in [ia.get("body"), ia.get("definition")] if p]
        ans_parts += [t.get("text") or "" for t in ia.get("related_topics") or []]
        combined = " ".join(ans_parts)
        vr.mentioned_in_answer = (_mentions(combined, variants) if combined else None)
        vr.answer_text = combined[:600] if combined else None
        if ia.get("related_topics"):
            vr.notes.append(f"{len(ia['related_topics'])} Instant Answers related topics")
        else:
            vr.notes.append("DuckDuckGo Instant Answers returned no topics")
        return vr
    return None


def check_visibility(domain: str, queries: list[str], *,
                     engines: Optional[list[str]] = None, count: int = 10) -> dict:
    # `or` would turn an explicit [] back into all engines, so test identity.
    if engines is None:
        engines = list(ENGINE_ORDER)
    domain = normalize_domain(domain)
    results: list[VisibilityResult] = []
    for q in queries:
        for engine in ENGINE_ORDER:
            if engine not in engines:
                continue
            vr = _check_engine(engine, domain, q, count, engines)
            if vr is not None:
                results.append(vr)

    covered = {r.coverage for r in results}
    return {
        "brand_domain": domain,
        "queries": queries,
        "engines_requested": [e for e in ENGINE_ORDER if e in engines],
        "coverage_summary": sorted(covered),
        "results": [r.to_dict() for r in results],
        "score": score_visibility(results),
        "disclaimer": ("Best-effort, keyless coverage. opengeo does not query "
                       "ChatGPT/Perplexity/Gemini directly (no free API); it "
                       "measures brand presence across public SERP and "
                       "answer-box layers, which is the leading indicator for "
                       "whether an answer engine *can* cite the brand."),
    }
