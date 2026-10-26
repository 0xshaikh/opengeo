"""On-page content quality: readability + AI-readability + schema + linking."""
from __future__ import annotations

from urllib.parse import urlparse

from opengeo import readability, schema
from opengeo.text_extraction import TextDoc


def internal_linking(doc: TextDoc) -> dict:
    """Split links into internal (same host, or no host at all) and external.

    A link with no host - a bare relative path or anchor - is by definition
    internal to the current site, so it is never counted as external.
    """
    page_host = urlparse(doc.url).netloc.lower().replace("www.", "") if doc.url else ""
    internal: list[str] = []
    external: list[str] = []
    for _, href in doc.links:
        if href.startswith("#"):
            internal.append(href)
            continue
        host = urlparse(href).netloc.lower().replace("www.", "")
        if host and page_host and host != page_host:
            external.append(href)
        else:
            internal.append(href)
    words = len(doc.words)
    return {
        "link_count": len(doc.links),
        "internal_count": len(internal),
        "external_count": len(external),
        "internal_ratio": round(len(internal) / len(doc.links), 3) if doc.links else 0.0,
        "links_per_1000_words": round(1000 * len(doc.links) / words, 1) if words else 0.0,
        "has_internal_links": bool(internal),
    }


def grade(score: float) -> str:
    if score >= 85:
        return "A"
    if score >= 75:
        return "B"
    if score >= 65:
        return "C"
    if score >= 55:
        return "D"
    return "F"


def _recommendations(rl: dict, ps: dict, hd: dict, ld: dict, links: dict,
                     schema_r: dict, def_ratio: float, chunk: float) -> list[str]:
    recs: list[str] = []
    flesch = rl.get("flesch_reading_ease")
    if flesch is not None and flesch < 60:
        recs.append(f"Readability is low (Flesch {flesch}); target 60-70 by shortening "
                    "sentences and trimming long words.")
    if ps.get("long_paragraph_ratio", 0) > 0.3:
        recs.append("More than 30% of paragraphs are long (>80 words); split them so "
                    "LLMs can cite a single block cleanly.")
    if ld.get("items_per_1000_words", 0) < 3:
        recs.append("Add a bulleted list: LLMs preferentially cite enumerated answers.")
    if def_ratio < 0.05:
        recs.append("Open with a definition-style paragraph ('X is a ...') - this is the "
                    "sentence answer engines quote verbatim.")
    if chunk < 60:
        recs.append("Chunking friendliness is low; aim for 100-500 word paragraphs.")
    if hd.get("h1_count", 0) != 1:
        recs.append(f"Use exactly one H1 and do not skip heading levels "
                    f"(found {hd.get('h1_count', 0)} H1 tags and "
                    f"{len(hd.get('level_jumps', []))} level jumps).")
    if not schema_r.get("has_jsonld"):
        recs.append("No JSON-LD found; add schema.org structured data to help both "
                    "search engines and answer engines parse intent.")
    elif schema_r.get("errors"):
        recs.append(f"JSON-LD present but invalid ({len(schema_r['errors'])} issues).")
    if not schema_r.get("has_meta_description"):
        recs.append("Add a meta description (roughly 150-160 characters).")
    if not schema_r.get("has_canonical"):
        recs.append("No <link rel=\"canonical\"> found; add one so engines resolve "
                    "the duplicate-free version of this URL.")
    if not links.get("has_internal_links"):
        recs.append("No internal links found; add links to related pages so crawlers "
                    "and answer engines can distribute authority.")
    elif links.get("internal_ratio", 0) < 0.25:
        recs.append("Most links are external "
                    f"({links.get('internal_ratio', 0):.0%} internal); add internal "
                    "links to related pages.")
    if not recs:
        recs.append("No blocking issues found - keep maintaining definition-first "
                    "paragraphs and a clean heading hierarchy.")
    return recs


def analyze(doc: TextDoc) -> dict:
    text = " ".join(doc.words)
    rl = readability.readability_metrics(text)
    ps = readability.paragraph_stats(doc.paragraphs)
    hd = readability.heading_structure(doc.headings)
    ld = readability.list_density(doc)
    schema_r = schema.validate_schema(doc)
    def_ratio = readability.definition_paragraph_ratio(doc.paragraphs)
    chunk = readability.chunking_score(doc)
    links = internal_linking(doc)

    # Reward the 55-70 Flesch window most suited to search/answer content.
    f = rl.get("flesch_reading_ease")
    if f is None:
        readability_score = 50.0
    else:
        readability_score = max(0.0, 100.0 - abs(f - 62.5) * 1.8)

    ai_score = (min(100.0, rl.get("word_count", 0) / 40.0) * 0.1 +
                min(1.0, def_ratio / 0.2) * 25.0 +
                min(1.0, ld.get("items_per_1000_words", 0) / 10.0) * 20.0 +
                chunk * 0.45)
    ai_score = round(max(0.0, min(100.0, ai_score)), 1)

    structure_score = min(100.0,
                          (100 if hd.get("has_h1") else 40) * 0.4 +
                          (100 - min(100, len(hd.get("level_jumps", [])) * 25)) * 0.3 +
                          (100 - min(100, ps.get("long_paragraph_ratio", 0) * 200)) * 0.3)
    structure_score = round(max(0.0, min(100.0, structure_score)), 1)

    # Internal link density: 5+ links per 1000 words is plenty for a content
    # page. Half the score comes from having *any* internal links, half from
    # how many there are - so a page with one internal link in 3000 words does
    # not silently score a perfect 100.
    link_score = round(
        min(100.0,
            min(1.0, links.get("internal_ratio", 0)) * 50.0 +
            min(1.0, links.get("links_per_1000_words", 0) / 5.0) * 50.0), 1)

    schema_score = round(
        (40 if schema_r.get("has_jsonld") else 0) +
        (25 if not schema_r.get("errors") else 0) +
        (20 if schema_r.get("has_canonical") else 0) +
        (15 if schema_r.get("has_meta_description") else 0), 1)

    overall = round(readability_score * 0.25 + ai_score * 0.25 + structure_score * 0.25 +
                    link_score * 0.15 + schema_score * 0.10, 1)
    overall = max(0.0, min(100.0, overall))

    recs = _recommendations(rl, ps, hd, ld, links, schema_r, def_ratio, chunk)

    return {
        "url": doc.url,
        "title": doc.title,
        "overall_score": overall,
        "overall_grade": grade(overall),
        "scores": {
            "readability": round(readability_score, 1),
            "ai_readability": ai_score,
            "structure": structure_score,
            "internal_linking": link_score,
            "schema": schema_score,
        },
        "readability": rl,
        "paragraphs": ps,
        "heading_structure": hd,
        "lists": ld,
        "definition_paragraph_ratio": def_ratio,
        "chunking_score": chunk,
        "schema": schema_r,
        "links": links,
        "recommendations": recs,
    }
