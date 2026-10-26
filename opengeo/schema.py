"""JSON-LD / structured-data validation and recommendations."""
from __future__ import annotations

import json
import re
from typing import Optional
from urllib.parse import urlparse

from opengeo.text_extraction import TextDoc

_REQ_FIELDS = ("@context", "@type")


def extract_jsonld(scripts: list[str]) -> list[dict]:
    """Parse every JSON-LD-ish script block, returning successful objects."""
    out: list[dict] = []
    for raw in scripts:
        text = (raw or "").strip()
        if not text:
            continue
        try:
            data = json.loads(text)
        except Exception:
            continue
        if isinstance(data, dict):
            out.append(data)
        elif isinstance(data, list):
            out.extend([d for d in data if isinstance(d, dict)])
    return out


def validate_jsonld(obj: dict) -> list[str]:
    """Structural checks. This is *not* a full schema.org validator - see the
    docs' limitations section."""
    errors: list[str] = []
    for f in _REQ_FIELDS:
        if f not in obj:
            errors.append(f"missing required field '{f}'")
    if "@context" in obj and "schema.org" not in str(obj["@context"]):
        errors.append("'@context' does not reference schema.org")
    stype = obj.get("@type")
    if stype is not None and not isinstance(stype, (str, list)):
        errors.append("'@type' must be a string or list of strings")
    if stype is None and "@context" in obj:
        errors.append("no '@type' declared - no graph to validate")
    # validate URL-valued fields are reachable-looking URLs
    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if isinstance(v, str) and re.match(r"^https?://", v):
                    parts = urlparse(v)
                    if not parts.netloc:
                        errors.append(f"malformed URL in '{k}': {v}")
                elif isinstance(v, (dict, list)):
                    walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)
    walk(obj)
    return errors


def meta_value(doc: TextDoc, *keys: str) -> Optional[str]:
    wanted = {k.lower() for k in keys}
    for name, val in doc.meta:
        if name.lower() in wanted and val:
            return val
    return None


def canonical_url(doc: TextDoc) -> Optional[str]:
    """Find the canonical URL. BeautifulSoup 4.15 does not surface <link> tags
    through the meta collection, so also scan the raw HTML directly."""
    for name, val in doc.meta:
        if name.lower() == "canonical" and val:
            return val
    if doc.raw:
        m = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]*href=["\']([^"\']+)',
                      doc.raw, re.I)
        if not m:
            m = re.search(r'<link[^>]+href=["\']([^"\']+)["\'][^>]*rel=["\']canonical["\']',
                          doc.raw, re.I)
        if m:
            return m.group(1)
    return None


def has_structured_data_signal(doc: TextDoc) -> bool:
    for script in doc.scripts:
        s = (script or "").strip().lower()
        if '"@context"' in s or '"@type"' in s:
            return True
    for name, _ in doc.meta:
        n = name.lower()
        if any(tok in n for tok in ("og:", "twitter:", "article:", "itemprop", "position")):
            return True
    return False


def validate_schema(doc: TextDoc) -> dict:
    blocks = extract_jsonld(doc.scripts)
    types: list[str] = []
    errors: list[str] = []
    for obj in blocks:
        t = obj.get("@type")
        if isinstance(t, list):
            types.extend(t)
        elif t:
            types.append(t)
        for e in validate_jsonld(obj):
            errors.append(e)
    return {
        "jsonld_count": len(blocks),
        "types": sorted(set(str(t) for t in types)),
        "has_jsonld": len(blocks) > 0,
        "has_canonical": canonical_url(doc) is not None,
        "canonical_url": canonical_url(doc),
        "has_meta_description": bool(doc.meta_description),
        "has_structured_data_signal": has_structured_data_signal(doc),
        "errors": errors,
        "ok": len(blocks) > 0 and not errors,
    }
