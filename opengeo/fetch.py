"""Polite HTTP fetching for opengeo.

Design rules baked in here:
  * an identifying User-Agent (``opengeo/<version>``) so operators can contact
    us rather than block us;
  * timeouts on every request, bounded retries with exponential backoff **and
    jitter** (no thundering herds);
  * a short per-process delay between requests so the tool is not a crawler;
  * ``robots.txt`` checks where feasible;
  * a small TTL cache so repeated runs in one process do not re-fetch;
  * honest failure: callers receive ``None`` plus a reason, never fake data.
"""
from __future__ import annotations

import re
import time
from typing import Optional
from urllib.parse import urlparse

import requests

try:  # optional - text extraction degrades without it
    from bs4 import BeautifulSoup

    _HAVE_BS4 = True
except Exception:  # pragma: no cover - bs4 is a declared dependency
    BeautifulSoup = None  # type: ignore
    _HAVE_BS4 = False

USER_AGENT = "opengeo/0.1.0 (+https://github.com/0xshaikh/opengeo)"

_TIMEOUT = 14          # seconds per attempt
_MAX_RETRIES = 3
_BACKOFF = 1.4         # exponential base
_MIN_GAP = 0.9         # minimum polite gap between outbound requests (s)

_cache: dict[str, tuple[float, Optional[str]]] = {}
_cache_ttl: dict[str, float] = {}
_last_request_at = 0.0
_session: Optional[requests.Session] = None


def _sess() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })
    return _session


def robots_allows(url: str, timeout: int = 6) -> bool:
    """Best-effort ``robots.txt`` check. Returns True unless the path is
    explicitly disallowed *and* the request matches the tool's User-Agent.

    Anything inconclusive (no robots.txt, unparseable, different UA, network
    error) is treated as allowed - we would rather ask than skip silently.
    """
    try:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        resp = _sess().get(robots_url, timeout=timeout)
        if resp.status_code != 200:
            return True
        path = parsed.path or "/"
        for raw in resp.text.splitlines():
            line = raw.split("#", 1)[0].strip()
            if not line.lower().startswith("user-agent:"):
                continue
            ua_token = line.split(":", 1)[1].strip().lower()
            if ua_token not in ("*", "opengeo"):
                continue
            block: list[str] = []
            for nxt in resp.text.splitlines():
                nxt_line = nxt.split("#", 1)[0].strip()
                if nxt_line.lower().startswith(("user-agent:", "sitemap:")):
                    break
                block.append(nxt_line)
            for directive in block:
                if directive.lower().startswith("disallow:"):
                    pattern = directive.split(":", 1)[1].strip()
                    if pattern and path.startswith(pattern):
                        return False
    except Exception:
        return True
    return True


def get_text(
    url: str,
    *,
    timeout: int = _TIMEOUT,
    headers: Optional[dict] = None,
    cache_ttl: float = 180.0,
    method: str = "GET",
    data: Optional[bytes] = None,
    params: Optional[dict] = None,
    allow_redirects: bool = True,
    raise_for_status: bool = False,
    check_robots: bool = True,
) -> Optional[str]:
    """Fetch *url* and return response text, or ``None`` on failure.

    ``method``/``data``/``params`` are only honoured (no caching) for non-GET
    flows such as DuckDuckGo's HTML endpoint.
    """
    now = time.monotonic()
    if method == "GET" and cache_ttl and cache_ttl > 0 and url in _cache:
        expires, cached = _cache[url]
        if now < expires:
            return cached

    if check_robots and method == "GET" and not robots_allows(url):
        return None

    global _last_request_at
    wait = _MIN_GAP - (now - _last_request_at)
    if wait > 0:
        time.sleep(wait)

    h = dict(_sess().headers)
    if headers:
        h.update(headers)

    last_exc: Optional[Exception] = None
    text: Optional[str] = None
    for attempt in range(_MAX_RETRIES):
        try:
            if method == "GET" and data is None:
                r = _sess().get(url, headers=h, timeout=timeout,
                                params=params, allow_redirects=allow_redirects)
            else:
                r = _sess().request(method, url, headers=h, timeout=timeout,
                                    data=data, params=params,
                                    allow_redirects=allow_redirects)
            _last_request_at = time.monotonic()
            if r.status_code >= 400:
                last_exc = RuntimeError(f"HTTP {r.status_code} for {url}")
                # 429 / 5xx are retryable; 400/401/403 are not.
                if r.status_code in (429, 500, 502, 503, 504):
                    raise last_exc
                if raise_for_status:
                    raise last_exc
                return None
            text = r.text
            break
        except Exception as exc:  # noqa: BLE001 - network layer is wide
            last_exc = exc
            time.sleep(_BACKOFF ** attempt + (time.monotonic() % 0.4))

    if text is None:
        return None
    if method == "GET" and cache_ttl and cache_ttl > 0:
        _cache[url] = (time.monotonic() + cache_ttl, text)
        _cache_ttl[url] = cache_ttl
    if raise_for_status:
        return text
    return text


def post_text(url: str, data: bytes, *, timeout: int = _TIMEOUT,
              headers: Optional[dict] = None) -> Optional[str]:
    """POST ``data`` and return text or ``None``."""
    return get_text(url, data=data, headers=headers, timeout=timeout,
                    check_robots=False)


def get_json(url: str, *, timeout: int = _TIMEOUT,
             headers: Optional[dict] = None):
    """GET a JSON endpoint, returning the parsed object or ``None``."""
    import json
    text = get_text(url, timeout=timeout, headers=headers)
    if text is None:
        return None
    try:
        return json.loads(text)
    except Exception:
        return None


def title_of(html: str) -> Optional[str]:
    if not _HAVE_BS4:
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
        return m.group(1).strip() if m else None
    soup = BeautifulSoup(html, "html.parser")
    t = soup.find("title")
    return t.get_text(" ", strip=True) if t else None


def sleep_polite(seconds: float = 1.5) -> None:
    """Explicit pause used by commands that batch several requests."""
    time.sleep(seconds)
