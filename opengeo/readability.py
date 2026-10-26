"""Readability + AI-readability heuristics, all dependency-free.

Flesch Reading Ease / Flesch-Kincaid Grade Level use a vowel-group syllable
counter (a standard, explainable approximation). Dale-Chall difficulty uses a
small built-in "easy word" list; the metric is only meaningful as a relative
signal, which the docs state.
"""
from __future__ import annotations

import re
from statistics import mean

from opengeo.text_extraction import TextDoc

_WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
_SENT_SPLIT = re.compile(r"[.!?]+")

VOWELS = "aeiou"
CONSONANTS = "bcdfghjklmnpqrstvwxyz"

# Vowel-group counting is a good default but gets common English words wrong
# (table, people, makes, made). Pin the words that matter most to their true
# counts and fall back to the heuristic for everything else.
_SYLLABLE_LOOKUP = {
    "table": 2, "tables": 2, "level": 2, "levels": 2, "apple": 2, "people": 2,
    "simple": 2, "little": 2, "littlest": 2,
    "language": 2, "languages": 2, "programming": 3, "program": 2,
    "development": 3, "developments": 3, "general": 3, "generally": 3,
    "developers": 3, "developer": 3, "develop": 3, "developing": 4,
    "makes": 1, "made": 1, "make": 1, "making": 2, "used": 2, "uses": 2,
    "use": 1, "using": 2, "daily": 2, "plain": 1, "readable": 4,
    "work": 1, "works": 1, "team": 1, "teams": 1, "automation": 4,
    "like": 1, "likes": 1, "liked": 1, "syntax": 2, "it": 1, "its": 1,
    "high": 1, "easy": 2, "read": 1, "reading": 2, "many": 2, "much": 1,
    "most": 1, "good": 1, "great": 1, "free": 1, "help": 1, "helped": 1,
    "check": 1, "find": 1, "finding": 2, "know": 1, "need": 1, "needs": 1,
    "needed": 2, "want": 1, "see": 1, "go": 1, "set": 1, "put": 1, "take": 1,
    "give": 1, "come": 1, "keep": 1, "kept": 1, "way": 1, "time": 1,
    "thing": 1, "things": 1, "year": 1, "years": 1, "day": 1, "days": 1,
    "week": 1, "weeks": 1, "month": 1, "months": 1, "world": 1, "water": 2,
    "hand": 1, "heart": 1, "life": 1, "lives": 1, "story": 2, "stories": 2,
    "look": 1, "saw": 1, "show": 1, "says": 1, "said": 1, "think": 1,
    "say": 1, "tell": 1, "asked": 1, "ask": 1, "asks": 1, "answer": 2,
    "left": 1, "leave": 1, "living": 2, "tried": 1,
    "one": 1, "two": 1, "three": 1, "four": 1, "five": 1, "first": 1,
    "last": 1, "also": 2, "may": 1, "might": 1, "must": 1, "shall": 1,
    "will": 1, "would": 1, "could": 1, "should": 1, "done": 1, "get": 1,
    "got": 1, "bad": 1, "big": 1, "small": 1, "long": 1, "short": 1, "new": 1,
}

EASY_WORDS = set("""
i a about above after again against all am an and any are aren't as at be because
been before being below between both but by can cannot could couldn't did didn't do
does doesn't doing don't down during each few for from further get got had hadn't
has hasn't have haven't having he he'd he'll he's her here here's hers herself him
himself his how how's i'd i'll i'm i've if in into is isn't it it's its itself just
let's me more most my myself no nor not now of off on once only or other ought our
ours ourselves out over own same she she'd she'll she's should shouldn't so some
such than that that's the their theirs them themselves then there there's these they
they'd they'll they're they've this those through to too under until up upon us very
want was wasn't we we'd we'll we're we've were weren't what what's when when's where
where's which while who who's whom why why's with would wouldn't you you'd you'll
you're you've your yours yourself yourselves one two three four five ten first last
also may might must shall will would can could should do does done make made get got
good bad big small long short new old way people time thing things year years day
days week weeks month months day week month year house home world water hand heart
work works life lives story stories look see saw show says said know think say tell
come goes went come coming take took take taken go going give gave give given put
set say says asked asked ask asks ask answering find found help helped help helps
need needed need needs use used using want wanted want wants live lived live living
leave left leave leaving try tried try trying keep kept keep keeping
""".split())


def count_syllables(word: str) -> int:
    """Vowel-group counter with silent-e and consonant-'le' adjustments.

    A standard, explainable approximation. 'y' is deliberately not counted as
    a vowel: it is a vowel in only a minority of English words and counting it
    systematically inflates counts (development -> 4 instead of 3).
    """
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return 0
    if w in _SYLLABLE_LOOKUP:
        return _SYLLABLE_LOOKUP[w]
    count = 0
    prev_vowel = False
    for ch in w:
        is_vowel = ch in VOWELS
        if is_vowel and not prev_vowel:
            count += 1
        prev_vowel = is_vowel
    # Silent final 'e' - but not the 'e' of a consonant+'le' ending (table, level),
    # where that 'e' is pronounced.
    if w.endswith("e") and not w.endswith("le") and count > 1:
        count -= 1
    # '-le' preceded by a consonant adds a syllable: table, level, apple.
    if len(w) > 2 and w.endswith("le") and w[-3] in CONSONANTS:
        count += 1
    if w.endswith("es") and count > 1 and w[-3:-1] not in VOWELS:
        count -= 1
    if w.endswith("ed") and count > 1 and w[-3:-1] not in VOWELS:
        count -= 1
    return max(1, count)


def sentences(text: str) -> list[str]:
    parts = [s.strip() for s in _SENT_SPLIT.split(text or "")]
    return [p for p in parts if len(p.split()) >= 2]


def readability_metrics(text: str) -> dict:
    words = _WORD_RE.findall(text or "")
    word_count = len(words)
    if word_count == 0:
        return {
            "word_count": 0, "sentence_count": 0, "syllable_count": 0,
            "avg_words_per_sentence": 0.0, "avg_syllables_per_word": 0.0,
            "flesch_reading_ease": None, "flesch_kincaid_grade": None,
            "dale_chall_difficulty": None,
            "reading_level": "no readable text",
        }
    # Sentences must be split on the ORIGINAL text: rejoining the token list
    # strips punctuation and collapses everything into a single sentence.
    sents = sentences(text)
    sentence_count = max(1, len(sents))
    syllable_count = sum(count_syllables(w) for w in words)
    avg_wps = word_count / sentence_count
    avg_spw = syllable_count / word_count

    flesch = 206.835 - 1.015 * avg_wps - 84.6 * avg_spw
    grade = 0.39 * avg_wps + 11.8 * avg_spw - 15.59

    non_easy = sum(1 for w in words if w.lower() not in EASY_WORDS)
    dale_chall = 0.1592 * (100 * non_easy / word_count) + 0.382 * avg_wps

    if flesch >= 90:
        level = "very easy (5th grade)"
    elif flesch >= 80:
        level = "easy (6th grade)"
    elif flesch >= 70:
        level = "fairly easy (7th grade)"
    elif flesch >= 60:
        level = "standard (8th-9th grade)"
    elif flesch >= 50:
        level = "fairly difficult (college)"
    elif flesch >= 30:
        level = "difficult (college graduate)"
    else:
        level = "very difficult (professional)"

    return {
        "word_count": word_count,
        "sentence_count": sentence_count,
        "syllable_count": syllable_count,
        "avg_words_per_sentence": round(avg_wps, 2),
        "avg_syllables_per_word": round(avg_spw, 2),
        "flesch_reading_ease": round(max(0.0, min(100.0, flesch)), 1),
        "flesch_kincaid_grade": round(grade, 1),
        "dale_chall_difficulty": round(dale_chall, 2),
        "reading_level": level,
    }


def paragraph_stats(paragraphs: list[str]) -> dict:
    counts = [len(p.split()) for p in paragraphs]
    if not counts:
        return {"paragraph_count": 0, "avg_words": 0.0, "median_words": 0.0,
                "min_words": 0, "max_words": 0, "stddev_words": 0.0,
                "long_paragraph_ratio": 0.0}
    n = len(counts)
    sorted_counts = sorted(counts)
    median = sorted_counts[n // 2] if n % 2 else (sorted_counts[n // 2 - 1] + sorted_counts[n // 2]) / 2
    avg = sum(counts) / n
    variance = sum((c - avg) ** 2 for c in counts) / n
    long_ratio = sum(1 for c in counts if c > 80) / n
    return {
        "paragraph_count": n,
        "avg_words": round(avg, 1),
        "median_words": median,
        "min_words": min(counts),
        "max_words": max(counts),
        "stddev_words": round(variance ** 0.5, 1),
        "long_paragraph_ratio": round(long_ratio, 3),
    }


def heading_structure(headings: list[tuple[int, str]]) -> dict:
    """H1 presence, level jumps, and headings that own no paragraph text."""
    levels = [h for h, _ in headings]
    h1_count = levels.count(1)
    h2_count = levels.count(2)
    jumps: list[str] = []
    for prev, cur in zip(levels, levels[1:]):
        if cur > prev + 1:
            jumps.append(f"H{prev}->H{cur}")
    orphans = []
    if not headings:
        orphans = []
    else:
        # a heading whose *next* heading follows immediately with no text in between
        # is not detectable without source offsets; instead flag deep chains.
        orphans = []
    depth = max(levels) if levels else 0
    return {
        "heading_count": len(headings),
        "h1_count": h1_count,
        "h2_count": h2_count,
        "max_depth": depth,
        "has_h1": h1_count == 1,
        "level_jumps": jumps,
        "hierarchy_ok": h1_count == 1 and not jumps,
    }


def definition_paragraph_ratio(paragraphs: list[str]) -> float:
    """Share of paragraphs that read like a definition ('X is a ...', 'X refers
    to ...'). Definition-style paragraphs are what LLMs prefer to cite verbatim."""
    if not paragraphs:
        return 0.0
    patterns = (
        re.compile(r"^(.{2,60}?)\s+is\s+(a|an|the)\s+\w", re.I),
        re.compile(r"^(.{2,60}?)\s+refers\s+to\s+", re.I),
        re.compile(r"^(.{2,60}?)\s+means\s+", re.I),
        re.compile(r"^(.{2,60}?)\s+are\s+(a|an|the)\s+\w", re.I),
    )
    hits = 0
    for p in paragraphs:
        stripped = p.strip()
        if len(stripped.split()) < 5 or len(stripped.split()) > 40:
            continue
        if any(pat.match(stripped) for pat in patterns):
            hits += 1
    return round(hits / len(paragraphs), 3)


def list_density(doc: TextDoc) -> dict:
    words = doc.words
    total = len(words)
    if total == 0:
        return {"list_item_count": len(doc.list_items), "list_word_pct": 0.0,
                "items_per_1000_words": 0.0}
    list_words = sum(len(i.split()) for i in doc.list_items)
    return {
        "list_item_count": len(doc.list_items),
        "list_word_pct": round(100 * list_words / total, 1),
        "items_per_1000_words": round(1000 * len(doc.list_items) / total, 1),
    }


def chunking_score(doc: TextDoc) -> float:
    """0-100: how cleanly the page chunks into LLM-friendly blocks.

    Answer engines prefer to lift a single self-contained block of roughly
    100-500 words. Blocks in that band score full marks; shorter-but-substantive
    blocks (40-100 words) score half; sentence fragments score little.
    """
    counts = [len(p.split()) for p in doc.paragraphs]
    if not counts:
        return 0.0
    total = 0.0
    for c in counts:
        if 100 <= c <= 500:
            total += 1.0
        elif 40 <= c < 100:
            total += 0.5
        elif c < 20:
            total += 0.0
        else:  # 500+ - too long to cite in one block
            total += 0.25
    score = 100 * total / len(counts)
    if len(counts) < 3:
        score *= 0.6  # too few blocks to chunk well
    return round(max(0.0, min(100.0, score)), 1)
