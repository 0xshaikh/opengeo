"""Public-SERP and public-answer-box queries.

These are the *real, keyless* data sources opengeo uses in place of paid
citation APIs. Bing and DuckDuckGo are parseable without an API key; Google is
fetched on a best-effort basis and frequently returns a captcha, which is
reported honestly rather than worked around.

Nothing here invents data: if a parser finds nothing, the caller gets an empty
result plus a coverage note.
"""
from __future__ import annotations

import re
from typing import Optional
from urllib.parse import parse_qsl, unquote, urlencode

from opengeo import fetch

BING_URL = "https://www.bing.com/search"
DDG_URL = "https://html.duckduckgo.com/html/"
DDG_IA_URL = "https://api.duckduckgo.com/"
GOOGLE_URL = "https://www.google.com/search"

_BING_RETRIES = ("captcha", "unusual traffic", "access denied")


def _domain_from_url(url: str) -> str:
    m = re.match(r"https?://([^/]+)", url)
    return m.group(1).lower().replace("www.", "") if m else ""


def _visible_text(element) -> str:
    return element.get_text(" ", strip=True) if element is not None else ""


def query_bing(query: str, count: int = 10) -> dict:
    """Bing SERP: answer-box text plus organic results. Best-effort."""
    url = f"{BING_URL}?{urlencode({'q': query, 'setlang': 'en-US', 'count': count})}"
    html = fetch.get_text(url, headers={"Accept": "text/html"})
    if html is None:
        return {"engine": "bing", "query": query, "organic": [], "answer": None,
                "coverage": "unreachable", "notes": ["Bing request failed"]}

    soup = fetch.BeautifulSoup(html, "html.parser") if fetch.BeautifulSoup else None
    organic: list[dict] = []
    if soup is not None:
        for li in soup.select("li.b_algo"):
            a = li.find("a", href=True)
            if a is None:
                continue
            title = _visible_text(a)
            if not title:
                continue
            href = a["href"]
            p = li.find("p")
            snippet = _visible_text(p)
            organic.append({"rank": len(organic) + 1, "title": title,
                            "url": href, "domain": _domain_from_url(href),
                            "snippet": snippet})
            if len(organic) >= count:
                break

        answer = None
        for sel in ("#b_ans", ".b_caption .b_titletext", ".b_ansHeader .b_titletext"):
            node = soup.select_one(sel)
            if node is not None:
                txt = _visible_text(node)
                if txt:
                    answer = txt
                    break

    notes: list[str] = []
    if not organic:
        lower = html[:4000].lower()
        if any(b in lower for b in _BING_RETRIES):
            notes.append("Bing served a captcha/bot wall; results withheld")
            organic = []
            answer = None
            coverage = "bot_blocked"
        else:
            notes.append("Bing returned no parseable organic results")
            coverage = "empty"
    else:
        coverage = "ok"
    return {"engine": "bing", "query": query, "organic": organic, "answer": answer,
            "coverage": coverage, "notes": notes or ["best-effort public SERP scrape"]}


def query_ddg_organic(query: str, count: int = 10) -> dict:
    """DuckDuckGo HTML endpoint (POST). Best-effort."""
    body = urlencode({"q": query, "kl": "wt-wt"}).encode("utf-8")
    html = fetch.post_text(DDG_URL, body, headers={"Content-Type": "application/x-www-form-urlencoded"})
    organic: list[dict] = []
    answer = None
    if html is None:
        return {"engine": "duckduckgo", "query": query, "organic": [], "answer": None,
                "coverage": "unreachable", "notes": ["DuckDuckGo request failed"]}

    soup = fetch.BeautifulSoup(html, "html.parser") if fetch.BeautifulSoup else None
    if soup is not None:
        for row in soup.select(".result"):
            a = row.select_one(".result__a")
            if a is None or not a.get("href"):
                continue
            href = a["href"]
            if "uddg=" in href:
                parts = parse_qsl(href.split("?", 1)[1], keep_blank_values=True)
                decoded = [unquote(v) for k, v in parts if k == "uddg"]
                href = decoded[0] if decoded else href
            href = href.split("&")[0]
            if not href.startswith("http"):
                continue
            snippet_el = row.select_one(".result__snippet")
            snippet = _visible_text(snippet_el)
            domain_el = row.select_one(".result__domain")
            organic.append({
                "rank": len(organic) + 1,
                "title": _visible_text(a),
                "url": href,
                "domain": _domain_from_url(href),
                "snippet": snippet or (_visible_text(domain_el) if domain_el else ""),
            })
            if len(organic) >= count:
                break

    notes: list[str] = []
    if not organic:
        notes.append("DuckDuckGo returned no parseable organic results")
        coverage = "empty"
    else:
        coverage = "ok"
    return {"engine": "duckduckgo", "query": query, "organic": organic, "answer": answer,
            "coverage": coverage, "notes": notes or ["best-effort public SERP scrape"]}


def query_google(query: str, count: int = 10) -> dict:
    """Google SERP with AI Overviews detection. Very best-effort: Google usually
    captcha-walls unauthenticated clients, which is reported, never bypassed."""
    url = f"{GOOGLE_URL}?{urlencode({'q': query, 'num': count, 'hl': 'en'})}"
    html = fetch.get_text(url, headers={"Accept": "text/html"}, timeout=12)
    if html is None:
        return {"engine": "google", "query": query, "organic": [], "answer": None,
                "ai_signals": {}, "coverage": "unreachable",
                "notes": ["Google request failed"]}

    lower = html.lower()
    ai_signals = {
        "ai_overview_marker": ("ai_overview" in lower or "data-attrid=\"ai-overview\"" in lower
                               or "generative ai" in lower),
        "blocked": ("unusual traffic" in lower or "/sorry/index" in lower
                    or "enablejs" in lower or "recaptcha" in lower),
    }
    organic: list[dict] = []
    soup = fetch.BeautifulSoup(html, "html.parser") if fetch.BeautifulSoup else None
    if soup is not None and not ai_signals["blocked"]:
        for div in soup.select("div.g"):
            a = div.find("a", href=True)
            if a is None:
                continue
            href = a["href"]
            if not href.startswith("http") or href.startswith("https://www.google.com"):
                continue
            snippet_el = div.find("div", attrs={"data-attrid": "t"}) or \
                         div.select_one(".VwiC3b") or div.find("span")
            organic.append({
                "rank": len(organic) + 1,
                "title": _visible_text(a),
                "url": href,
                "domain": _domain_from_url(href),
                "snippet": _visible_text(snippet_el),
            })
            if len(organic) >= count:
                break

    if ai_signals["blocked"]:
        coverage = "blocked"
        notes = ["Google captcha/bot wall - results withheld, not bypassed"]
        organic = []
    elif not organic:
        coverage = "empty"
        notes = ["Google returned no parseable organic results"]
    else:
        coverage = "ok"
        notes = []
    if ai_signals["ai_overview_marker"]:
        notes.append("AI Overviews marker detected in response HTML")
    return {"engine": "google", "query": query, "organic": organic, "answer": None,
            "ai_signals": ai_signals, "coverage": coverage,
            "notes": notes or ["best-effort; Google rarely serves organic HTML to bots"]}


def query_ddg_instant(query: str) -> dict:
    """DuckDuckGo Instant Answers (real keyless JSON API). Returns related
    topics / definitions - a genuine answer-layer source."""
    data = fetch.get_json(f"{DDG_IA_URL}?{urlencode({'q': query, 'format': 'json',
                                                      'no_redirect': 1, 'no_html': 1})}")
    if not data:
        return {"query": query, "answer_type": None, "body": None,
                "related_topics": [], "definition": None, "sources": []}
    related = []
    for topic in data.get("RelatedTopics") or []:
        if isinstance(topic, dict) and topic.get("Text"):
            related.append({"text": topic.get("Text"),
                            "first_url": topic.get("FirstURL", "")})
            if len(related) >= 12:
                break
    sources = []
    for src in data.get("Results") or []:
        if isinstance(src, dict) and src.get("Text"):
            sources.append({"text": src.get("Text"), "url": src.get("Source", "")})
    body = data.get("AbstractText") or data.get("Definition") or None
    return {
        "query": query,
        "answer_type": data.get("Type") or None,
        "heading": data.get("Heading") or None,
        "body": body,
        "definition": data.get("Definition") or None,
        "definition_source": data.get("DefinitionSource") or None,
        "abstract_source": data.get("AbstractURL") or None,
        "related_topics": related,
        "sources": sources,
        "infobox": data.get("Infobox") or None,
    }
