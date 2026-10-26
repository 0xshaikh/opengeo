"""White-label PDF reports.

Branding is text-first: company name, optional logo PNG. If logo embedding
fails for any reason the report still renders (the logo is optional, never a
hard dependency). No fonts or images are fabricated.
"""
from __future__ import annotations

import io
import os
from datetime import datetime
from typing import Optional

from fpdf import FPDF

from opengeo import brief as brief_mod
from opengeo import fetch, quality as quality_mod, schema as schema_mod
from opengeo.readability import definition_paragraph_ratio, list_density
from opengeo.text_extraction import extract

_ACCENT = (37, 99, 235)      # blue-600
_ACCENT_DARK = (30, 64, 175)
_MUTED = (100, 116, 139)
_PANEL = (241, 245, 249)
_OK = (22, 163, 74)
_WARN = (217, 119, 6)
_BAD = (220, 38, 38)


def _safe_logo(pdf: "PDF", path: str) -> bool:
    """Embed a PNG logo. Returns False if the file is unreadable/wrong format;
    callers must not crash the report on failure."""
    try:
        with open(path, "rb") as fh:
            data = fh.read()
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            return False
        buf = io.BytesIO(data)
        pdf.image(buf, x=pdf.l_margin, y=pdf.t_margin, w=52)
        pdf.ln(22)
        return True
    except Exception:
        return False


# Built-in core fonts are latin-1 only. Real SERP snippets routinely carry
# unicode (Bing truncates with U+2026, quotes, dashes, arrows), and fpdf2
# raises FPDFUnicodeEncodingException on any codepoint outside latin-1 -- which
# crashed the whole report over one ellipsis. Map the common ones to readable
# latin-1 equivalents, then replace anything still out of range with '?' so we
# degrade instead of dying. Never drop silently: '?' marks a visible loss.
_PDF_SAFE_MAP = {
    0x00A0: " ",    # nbsp
    0x2013: "-",    # en dash
    0x2014: "--",   # em dash
    0x2018: "'",    # left single quote
    0x2019: "'",    # right single quote / apostrophe
    0x201C: '"',    # left double quote
    0x201D: '"',    # right double quote
    0x201E: '"',    # low double quote
    0x2022: "*",    # bullet
    0x2026: "...",  # horizontal ellipsis
    0x2032: "'",    # prime
    0x2033: '""',   # double prime
    0x2192: "->",   # right arrow
    0x2190: "<-",   # left arrow
    0x25CF: "*",    # black circle
    0x2713: "[ok]", # check mark
    0x2717: "[x]",  # ballot x
    0x2794: "->",   # long right arrow
}


def _pdf_safe(text) -> str:
    """Make *text* renderable by a latin-1 core font without raising."""
    if not isinstance(text, str):
        return text
    for code, repl in _PDF_SAFE_MAP.items():
        if chr(code) in text:
            text = text.replace(chr(code), repl)
    return "".join(ch if (9 <= ord(ch) < 256) else "?" for ch in text)


class GeoPDF(FPDF):
    def __init__(self, company: str = "opengeo", footer_right: str = ""):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.company = company
        self.footer_right = footer_right
        self.set_auto_page_break(True, margin=22)
        self.set_left_margin(20)
        self.set_right_margin(20)
        self.set_top_margin(20)
        self.set_font("Helvetica", size=11)

    def normalize_text(self, text: str) -> str:
        # Every cell()/multi_cell()/write() funnels through here, so this is the
        # single choke point that keeps unicode from crashing the report.
        return super().normalize_text(_pdf_safe(text))

    def header(self):
        if self.page_no() > 1:
            self.set_font("Helvetica", "B", 10)
            self.set_text_color(*_ACCENT_DARK)
            self.cell(0, 8, self.company, align="L")
            self.ln(11)

    def footer(self):
        self.set_y(-16)
        self.set_font("Helvetica", size=8)
        self.set_text_color(*_MUTED)
        self.cell(0, 6, f"{self.footer_right}  |  page {self.page_no()}/{{nb}}", align="C")


def _color_for(score: Optional[float]) -> tuple:
    if score is None:
        return _MUTED
    if score >= 70:
        return _OK
    if score >= 45:
        return _WARN
    return _BAD


class Report:
    def __init__(self, company: str = "opengeo", logo: Optional[str] = None,
                 out: str = "report.pdf"):
        self.company = company or "opengeo"
        self.logo = logo
        self.out = out

    # ------------------------------------------------------------------ build
    def build(self, *, visibility: Optional[dict] = None, brief: Optional[dict] = None,
              page: Optional[str] = None, title: Optional[str] = None) -> str:
        now = datetime.now().strftime("%Y-%m-%d %H:%M UTC")
        pdf = GeoPDF(company=self.company, footer_right=f"{self.company} - opengeo report")
        pdf.alias_nb_pages()

        pdf.add_page()
        pdf.set_fill_color(*_ACCENT)
        pdf.rect(0, 0, 210, 34, style="F")
        pdf.set_xy(20, 10)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 20)
        pdf.cell(0, 10, self.company)
        pdf.set_xy(20, 20)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, "AI Search Visibility & SEO Content Report")
        pdf.ln(10)

        pdf.set_text_color(30, 41, 59)
        if self.logo:
            _safe_logo(pdf, self.logo)
        pdf.set_x(20)
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 5, f"Generated {now} with opengeo. "
                            "Keyless, best-effort data - see the limitations section "
                            "of the opengeo README for what each number means.")
        pdf.ln(4)
        pdf.set_draw_color(*_ACCENT)
        pdf.line(20, pdf.get_y(), 190, pdf.get_y())
        pdf.ln(8)

        if visibility:
            self._visibility_section(pdf, visibility)
        if brief:
            self._brief_section(pdf, brief)
        if page:
            self._quality_section(pdf, page)

        self._sources_section(pdf, visibility, brief)

        # A missing output directory must not be a reason to lose a report you
        # just spent a few minutes fetching. Create it, don't crash.
        parent = os.path.dirname(os.path.abspath(self.out))
        os.makedirs(parent, exist_ok=True)
        pdf.output(self.out)
        return self.out

    # --------------------------------------------------------------- sections
    def _h1(self, pdf: PDF, text: str):
        pdf.set_font("Helvetica", "B", 15)
        pdf.set_text_color(*_ACCENT_DARK)
        pdf.cell(0, 9, text)
        pdf.ln(11)
        pdf.set_text_color(30, 41, 59)

    def _h2(self, pdf: PDF, text: str):
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(0, 7, text)
        pdf.ln(8)
        pdf.set_text_color(30, 41, 59)

    def _kv(self, pdf: PDF, key: str, value):
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*_MUTED)
        pdf.cell(50, 5, key)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(30, 41, 59)
        pdf.multi_cell(0, 5, str(value))

    def _visibility_section(self, pdf: PDF, vis: dict):
        pdf.add_page()
        self._h1(pdf, "1. AI Search Visibility")
        score = vis.get("score") or {}
        s = score.get("score")
        pdf.set_font("Helvetica", "B", 24)
        pdf.set_text_color(*_color_for(s))
        pdf.cell(0, 12, "unknown" if s is None else str(s))
        pdf.set_font("Helvetica", "", 11)
        pdf.cell(0, 6, score.get("label") or "unknown")
        pdf.ln(14)
        pdf.set_text_color(30, 41, 59)
        self._kv(pdf, "Brand domain", vis.get("brand_domain"))
        pdf.ln(1)
        self._kv(pdf, "Queries", ", ".join(vis.get("queries") or []))
        pdf.ln(1)
        self._kv(pdf, "Engines", ", ".join(vis.get("engines_requested") or []))
        pdf.ln(1)
        self._kv(pdf, "Coverage", ", ".join(vis.get("coverage_summary") or []))
        pdf.ln(2)

        pdf.set_font("Helvetica", "", 8)
        pdf.set_fill_color(*_PANEL)
        pdf.multi_cell(0, 4.5, vis.get("disclaimer") or "", fill=True)
        pdf.ln(6)

        self._h2(pdf, "Per-query results")
        cols = [30, 22, 20, 24, 20, 34]
        headers = ["Query", "Engine", "Coverage", "In answer", "In organic", "Notes"]
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_fill_color(226, 232, 240)
        for i, h in enumerate(headers):
            pdf.cell(cols[i], 6, h, border=1, fill=True)
        pdf.ln(7)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(30, 41, 59)
        for r in vis.get("results") or []:
            row = [
                (r.get("query") or "")[:24],
                r.get("engine") or "",
                r.get("coverage") or "",
                ("yes" if r.get("mentioned_in_answer") else
                 ("no" if r.get("mentioned_in_answer") is False else "n/a")),
                ("yes" if r.get("mentioned_in_organic") else
                 ("no" if r.get("mentioned_in_organic") is False else "n/a")),
                ((r.get("notes") or [""])[0])[:30],
            ]
            max_h = 5
            for i, val in enumerate(row):
                pdf.multi_cell(cols[i], 4, val, border=1, max_line_height=max_h)
            pdf.ln(0)

    def _brief_section(self, pdf: PDF, br: dict):
        pdf.add_page()
        self._h1(pdf, "2. Content Brief")
        intent = br.get("intent") or {}
        wt = br.get("word_targets") or {}
        self._kv(pdf, "Keyword", br.get("keyword"))
        pdf.ln(1)
        self._kv(pdf, "Intent", f"{intent.get('label')} (confidence {intent.get('confidence')})")
        pdf.ln(1)
        self._kv(pdf, "Word target", f"{wt.get('min')}-{wt.get('max')} (recommended {wt.get('recommended')})")
        pdf.ln(1)
        fs = br.get("featured_snippet") or {}
        self._kv(pdf, "Featured snippet", fs.get("likely_type") or "none detected")
        pdf.ln(3)

        self._h2(pdf, "Title options")
        pdf.set_font("Helvetica", "", 10)
        for i, t in enumerate(br.get("title_options") or [], 1):
            pdf.cell(0, 5.5, f"{i}. {t}")
            pdf.ln(6)
        pdf.ln(2)

        self._h2(pdf, "Outline")
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_fill_color(226, 232, 240)
        outline_cols = [76, 10, 18, 66]   # totals 170mm = printable width
        for i, h in enumerate(["Heading", "Lvl", "Words", "Angle"]):
            pdf.cell(outline_cols[i], 6, h, border=1, fill=True)
        pdf.ln(7)
        pdf.set_font("Helvetica", "", 8)
        for sec in br.get("outline") or []:
            vals = [str(sec.get("heading", ""))[:46], str(sec.get("level", "")),
                    str(sec.get("words", "")), str(sec.get("angle", ""))[:42]]
            for i, v in enumerate(vals):
                pdf.multi_cell(outline_cols[i], 4, v, border=1, max_line_height=5)
            pdf.ln(0)
        pdf.ln(4)

        self._h2(pdf, "Entities to cover")
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 5, ", ".join(br.get("entities") or []) or "(none detected)")
        pdf.ln(3)

        self._h2(pdf, "Related questions")
        pdf.set_font("Helvetica", "", 10)
        for q in br.get("related_questions") or []:
            # multi_cell(0) ends at the right margin, so reset x each pass or
            # the next iteration has zero width left and fpdf raises.
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(0, 5.5, "- " + q)
        pdf.ln(3)

        schema = br.get("schema_recommendation") or {}
        self._h2(pdf, "Schema recommendation")
        self._kv(pdf, "Primary type", schema.get("primary_type"))
        pdf.ln(1)
        self._kv(pdf, "Rationale", schema.get("rationale"))
        if schema.get("additional"):
            pdf.ln(2)
            pdf.set_font("Helvetica", "", 9)
            pdf.multi_cell(0, 5, "Additional JSON-LD blocks suggested: " +
                           ", ".join(sorted({str(b.get("@type")) for b in schema["additional"] if b})))

    def _quality_section(self, pdf: PDF, url: str):
        pdf.add_page()
        self._h1(pdf, "3. On-page Content Quality")
        html = fetch.get_text(url, timeout=20)
        if html is None:
            pdf.set_font("Helvetica", "I", 11)
            pdf.set_text_color(*_BAD)
            pdf.multi_cell(0, 6, f"Could not fetch {url} - section skipped.")
            pdf.set_text_color(30, 41, 59)
            return
        doc = extract(html, url=url)
        q = quality_mod.analyze(doc)

        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 5, f"{q.get('title') or url}")
        pdf.ln(4)
        s = q.get("overall_score")
        pdf.set_font("Helvetica", "B", 22)
        pdf.set_text_color(*_color_for(s))
        pdf.cell(0, 11, f"{s} ({q.get('overall_grade')})")
        pdf.ln(13)
        pdf.set_text_color(30, 41, 59)

        self._h2(pdf, "Score breakdown")
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(226, 232, 240)
        for i, h in enumerate(["Dimension", "Score", "Grade"]):
            pdf.cell([90, 25, 25][i], 6, h, border=1, fill=True)
        pdf.ln(7)
        pdf.set_font("Helvetica", "", 9)
        for name, val in (q.get("scores") or {}).items():
            cells = [name.replace("_", " ").title(), str(val), quality_mod.grade(val)]
            for i, c in enumerate(cells):
                pdf.cell([90, 25, 25][i], 5, c, border=1)
            pdf.ln(5.6)
        pdf.ln(4)

        rl = q.get("readability") or {}
        ps = q.get("paragraphs") or {}
        ld = q.get("lists") or {}
        sch = q.get("schema") or {}
        self._h2(pdf, "Details")
        pdf.set_font("Helvetica", "", 9)
        for label, value in (
            ("Words / sentences", f"{rl.get('word_count')} / {rl.get('sentence_count')}"),
            ("Flesch Reading Ease", f"{rl.get('flesch_reading_ease')} ({rl.get('reading_level')})"),
            ("Flesch-Kincaid grade", rl.get("flesch_kincaid_grade")),
            ("Avg words / sentence", rl.get("avg_words_per_sentence")),
            ("Paragraphs", ps.get("paragraph_count")),
            ("Median paragraph words", ps.get("median_words")),
            ("List density", f"{ld.get('items_per_1000_words')} items per 1k words"),
            ("Definition paragraphs", f"{q.get('definition_paragraph_ratio')}"),
            ("Chunking score", q.get("chunking_score")),
            ("H1 present", "yes" if (q.get("heading_structure") or {}).get("has_h1") else "no"),
            ("JSON-LD blocks", sch.get("jsonld_count")),
            ("Canonical URL", "yes" if sch.get("has_canonical") else "no"),
        ):
            pdf.set_x(pdf.l_margin)
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(*_MUTED)
            pdf.cell(62, 5, label)
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(30, 41, 59)
            pdf.multi_cell(0, 5, str(value))
        pdf.ln(3)

        self._h2(pdf, "Recommendations")
        pdf.set_font("Helvetica", "", 9)
        for i, rec in enumerate(q.get("recommendations") or [], 1):
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(0, 5, f"{i}. {rec}")
            pdf.ln(1)

    def _sources_section(self, pdf: PDF, visibility: Optional[dict], brief: Optional[dict]):
        pdf.add_page()
        self._h1(pdf, "Sources & limitations")
        pdf.set_font("Helvetica", "", 9)
        lines = [
            "opengeo fetches only public endpoints. No paid APIs, no private data.",
            "",
            "Visibility is best-effort: opengeo does not query ChatGPT, Perplexity or Gemini",
            "directly (there is no free API). It measures brand presence across public SERP",
            "and answer-box layers - Bing, DuckDuckGo organic + Instant Answers, and Google",
            "AI Overviews markers in the raw HTML. Brand presence on page one is the leading",
            "indicator of whether an answer engine can cite a brand at all.",
            "",
            "Blocked or empty sources are reported as 'unknown' with a reason, never as zero.",
        ]
        if visibility:
            lines.append(f"Engines requested for visibility: {', '.join(visibility.get('engines_requested') or [])}")
            lines.append(f"Coverage observed: {', '.join(visibility.get('coverage_summary') or [])}")
        if brief:
            src = brief.get("sources") or {}
            lines.append(f"Content brief sources: engine={src.get('engine')} "
                         f"coverage={src.get('coverage')} results_used={src.get('results_used')}")
        pdf.multi_cell(0, 5, "\n".join(lines))


def generate_report(out: str = "report.pdf", *, company: str = "opengeo",
                    logo: Optional[str] = None, visibility: Optional[dict] = None,
                    brief: Optional[dict] = None, page: Optional[str] = None) -> str:
    return Report(company=company, logo=logo, out=out).build(
        visibility=visibility, brief=brief, page=page)
