"""Dependency-free entity / question extraction.

opengeo deliberately ships no NLP framework. Entity extraction is a
transparent heuristic: keep multi-word capitalised sequences and filter an
explicit stop-word / common-word list. It is *good enough and honest* - the
result is labelled as a heuristic in the docs and the output.
"""
from __future__ import annotations

import re
from typing import Iterable

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "of", "at", "by", "for", "with",
    "about", "against", "between", "into", "through", "during", "before", "after",
    "above", "below", "to", "from", "up", "down", "in", "out", "on", "off", "over",
    "under", "again", "further", "then", "once", "here", "there", "when", "where",
    "why", "how", "all", "any", "both", "each", "few", "more", "most", "other",
    "some", "such", "no", "nor", "not", "only", "own", "same", "so", "than", "too",
    "very", "s", "t", "can", "will", "just", "don", "should", "now", "is", "are",
    "was", "were", "be", "been", "being", "have", "has", "had", "having", "do",
    "does", "did", "doing", "would", "could", "should", "may", "might", "shall",
    "what", "which", "who", "whom", "whose", "this", "that", "these", "those",
    "it", "its", "as", "also", "using", "use", "used", "new", "one", "two",
    "http", "https", "www", "com", "net", "org", "your", "you", "our", "their",
    "its", "his", "her", "they", "them", "she", "he", "we", "us", "me", "him",
    "per", "via", "than", "both", "yet", "still", "even", "however", "therefore",
    "because", "while", "since", "until", "along", "across", "around", "within",
    "without", "whether", "although", "though", "despite", "according", "get",
    "got", "make", "made", "like", "well", "back", "way", "ways", "best", "good",
    "great", "free", "easy", "help", "check", "find", "know", "need", "want",
    "see", "let", "go", "see", "set", "put", "take", "give", "come", "keep",
}

_CAP_SEQ = re.compile(r"[A-Z][a-zA-Z0-9']+(?:\s+[A-Z][a-zA-Z0-9']+)*")
_QRE = re.compile(r"[^.!?\n]+")


def clean_phrase(phrase: str) -> str:
    return re.sub(r"\s+", " ", phrase).strip(" .,:;-'\"()[]")


# Words that look like entities but are almost always noise in SERP snippets:
# truncated titles, UI chrome ("View"), gerunds, and generic qualifiers.
_NOISE = {
    "view", "views", "opens", "afford", "affording", "read", "reading",
    "home", "more", "new", "old", "free", "buy", "download", "login",
    "sign", "search", "menu", "latest", "popular", "related", "featured",
    "trending", "recent", "today", "yesterday", "tomorrow", "all", "none",
    "cheap", "cheaply", "slow", "big", "small", "long", "short",
}
# A single capitalised word needs more evidence than a phrase to be trusted as
# an entity: one-off hits are usually SERP title-truncation artefacts.
_SINGLE_WORD_MIN = 3


def extract_entities(texts: Iterable[str], limit: int = 20,
                     min_count: int = 1) -> list[str]:
    """Extract candidate entities from *texts*.

    Keeps capitalised multi-word sequences, then strips phrases that still
    contain a stop-word (which almost always means they are ordinary prose
    rather than a named thing) and phrases containing a known noise word
    ("View", "Open", ...). Requiring *min_count* occurrences cuts the noise
    that a single off-hand mention in one SERP snippet introduces; a lone
    capitalised word needs at least *max(min_count, _SINGLE_WORD_MIN)*.
    """
    spelling: dict[str, str] = {}
    hits: dict[str, int] = {}
    for chunk in texts:
        for raw in _CAP_SEQ.findall(chunk or ""):
            phrase = clean_phrase(raw)
            if len(phrase) < 2:
                continue
            words = phrase.split()
            if any(w.lower() in STOPWORDS for w in words):
                continue
            if any(w.lower() in _NOISE for w in words):
                continue
            # Short ALL-CAPS tokens are SERP title-truncation artefacts, not
            # real named things ("OPEN", "PDF", "FAQ").
            if all(w == w.upper() and w.isalpha() and len(w) <= 6
                   for w in words):
                continue
            key = phrase.lower()
            spelling.setdefault(key, phrase)
            hits[key] = hits.get(key, 0) + 1
    kept = []
    for key in hits:
        need = max(min_count, _SINGLE_WORD_MIN) if len(spelling[key].split()) == 1 \
            else min_count
        if hits[key] >= need:
            kept.append(key)
    ranked = sorted(kept, key=lambda k: (-hits[k], -len(spelling[k].split()), k))
    return [spelling[k] for k in ranked][:limit]


def related_questions(texts: Iterable[str], limit: int = 8) -> list[str]:
    """Pull out question-shaped sentences (ends with '?' or starts with a
    question word) from *texts*. Honest about being sentence-shaped, not
    guaranteed to be canonical PAA entries."""
    out: list[str] = []
    qwords = ("how", "what", "why", "when", "where", "which", "who", "can", "should", "does", "is", "are")
    for chunk in texts:
        for sent in _QRE.findall(chunk or ""):
            s = clean_phrase(sent).strip()
            if len(s) < 8 or len(s) > 160:
                continue
            lower = s.lower()
            is_question = s.rstrip().endswith("?") or lower.startswith(qwords)
            if is_question:
                if s not in out:
                    out.append(s)
            if len(out) >= limit:
                return out
    return out


def dedupe(items: Iterable[str]) -> list[str]:
    out: list[str] = []
    for item in items:
        if item and item.lower() not in {x.lower() for x in out}:
            out.append(item)
    return out
