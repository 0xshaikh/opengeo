"""HTML -> structured text. Pure parsing; no network, no invented content."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional, Tuple
from urllib.parse import urljoin, urlparse

try:
    from bs4 import BeautifulSoup

    _HAVE_BS4 = True
except Exception:  # pragma: no cover
    BeautifulSoup = None  # type: ignore
    _HAVE_BS4 = False


LINK_TAGS = ("script", "style", "noscript", "svg", "iframe", "template", "nav", "footer", "header")
# Only these are true site chrome that should never count towards content
# metrics. <script> and <header> are excluded: scripts carry JSON-LD, and
# <header> is a legitimate sectioning element that often holds an article title.
CHROME_TAGS = ("svg", "iframe", "template", "nav", "footer")


def normalize_url(href: str, base: str) -> str:
    """Make *href* absolute relative to *base*, then drop fragment/query."""
    if not href:
        return href
    if href.startswith("data:") or href.startswith("javascript:") or href.startswith("#"):
        return href
    joined = urljoin(base, href)
    parts = urlparse(joined)
    if not parts.scheme and not parts.netloc and not href.startswith("/"):
        return href  # opaque/relative, leave as-is
    return f"{parts.scheme}://{parts.netloc}{parts.path}".lower()


@dataclass
class TextDoc:
    url: str
    title: Optional[str] = None
    meta_description: Optional[str] = None
    headings: list[Tuple[int, str]] = field(default_factory=list)
    paragraphs: list[str] = field(default_factory=list)
    list_items: list[str] = field(default_factory=list)
    links: list[Tuple[str, str]] = field(default_factory=list)   # (anchor text, href)
    scripts: list[str] = field(default_factory=list)              # script contents
    meta: list[Tuple[str, str]] = field(default_factory=list)     # (name/property, content)
    raw: str = ""

    @property
    def words(self) -> list[str]:
        text = " ".join([self.title or "", self.meta_description or ""] +
                        [h for _, h in self.headings] + self.paragraphs + self.list_items)
        return text.split()

    @property
    def text(self) -> str:
        return " ".join(self.words)


def extract(html: str, url: str = "") -> TextDoc:
    if not _HAVE_BS4:
        return TextDoc(url=url)
    soup = BeautifulSoup(html, "html.parser")

    # Capture structured data before pruning: scripts hold JSON-LD, and meta
    # tags hold the description and canonical.
    scripts = [s.string or "" for s in soup.find_all("script") if s.string]
    meta: list[Tuple[str, str]] = []
    for m in soup.find_all("meta"):
        key = m.get("name") or m.get("property") or m.get("http-equiv") or ""
        val = m.get("content") or ""
        if key:
            meta.append((key, val))

    # Remove site chrome before measuring: navigation menus, footers, inline
    # vectors and embeds are full of <li> items that would otherwise inflate
    # list density and dilute the readability score of the actual article body.
    for tag_name in CHROME_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    title = None
    title_tag = soup.find("title")
    if title_tag is not None:
        title = title_tag.get_text(" ", strip=True) or None
    meta_description = None
    desc_tag = soup.find("meta", attrs={"name": "description"})
    if desc_tag is None:
        desc_tag = soup.find("meta", attrs={"property": "og:description"})
    if desc_tag is not None:
        meta_description = (desc_tag.get("content") or "").strip() or None

    headings: list[Tuple[int, str]] = []
    for tag in soup.find_all(lambda t: t.name and t.name.startswith("h") and len(t.name) == 2):
        level = int(tag.name[1])
        text = tag.get_text(" ", strip=True)
        if text:
            headings.append((level, text))

    paragraphs: list[str] = []
    for p in soup.find_all("p"):
        text = p.get_text(" ", strip=True)
        if len(text.split()) >= 2:
            paragraphs.append(text)

    list_items: list[str] = []
    for li in soup.find_all("li"):
        text = li.get_text(" ", strip=True)
        if len(text.split()) >= 1:
            list_items.append(text)

    links: list[Tuple[str, str]] = []
    for a in soup.find_all("a", href=True):
        text = a.get_text(" ", strip=True)
        href = normalize_url(a["href"], url or "")
        if href.startswith(("https:", "http:")):
            links.append((text, href))

    return TextDoc(url=url, title=title, meta_description=meta_description,
                   headings=headings, paragraphs=paragraphs, list_items=list_items,
                   links=links, scripts=scripts, meta=meta, raw=html)


def iter_plain_text(doc: TextDoc) -> Iterable[str]:
    for chunk in [doc.title or "", doc.meta_description or ""] + \
                 [h for _, h in doc.headings] + doc.paragraphs + doc.list_items:
        if chunk:
            yield chunk
