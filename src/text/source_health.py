"""Probe the URLs a text collect actually requests and classify each one.

Used by `po text source-health` (text/source_health_cli.py). Deterministic: one GET per
listing URL (one retry on timeout/5xx), no article fetches.

Statuses: ok | redirect_moved | not_found | forbidden | cloudflare | dns_dead | timeout |
server_error | conn_error (refused/TLS/reset) | hijacked | empty_listing.
"""

from __future__ import annotations

import asyncio
import collections
import html as htmllib
import json
import re
import socket
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import unquote, urlsplit

import httpx

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
TIMEOUT = 20.0
DOMAIN_GAP = 2.0  # seconds between two requests to the same host
MAX_BYTES = 8_000_000

# Script each config language is written in; anything not listed is Latin.
_SCRIPT_LANGS = {
    "Cyrillic": "ru uk bg mk be kk ky tg mn",
    "Arabic": "ar arabic urdu fa farsi",
    "Hebrew": "he",
    "Thai": "th thai",
    "Lao": "lao",
    "Khmer": "km",
    "Myanmar": "my",
    "Georgian": "ka",
    "Armenian": "hy",
    "Bengali": "bn",
    "Devanagari": "hindi hi ne mr",
    "Sinhala": "si",
    "Tamil": "tamil ta",
    "Malayalam": "ml",
    "Oriya": "or",
    "Kannada": "kn",
    "Gujarati": "gu",
    "Gurmukhi": "pa",
    "Telugu": "te",
    "Thaana": "dv",
    "Ethiopic": "amharic am",
    "Han": "zh chinese_traditional chinese_simplified",
    "Hangul": "ko korean",
}
LANG_SCRIPTS = {lang: {s} for s, ls in _SCRIPT_LANGS.items() for lang in ls.split()}
LANG_SCRIPTS.update(
    {
        "sr": {"Latin", "Cyrillic"},
        "me": {"Latin", "Cyrillic"},
        "bs": {"Latin", "Cyrillic"},
        "ja": {"Han", "Kana"},
    }
)
_RANGES = [  # (start, end, script); first match wins, Latin is < 0x250
    (0x0370, 0x0400, "Greek"),
    (0x0400, 0x0530, "Cyrillic"),
    (0x0530, 0x0590, "Armenian"),
    (0x0590, 0x0600, "Hebrew"),
    (0x0600, 0x0780, "Arabic"),
    (0x0780, 0x07C0, "Thaana"),
    (0x0900, 0x0980, "Devanagari"),
    (0x0980, 0x0A00, "Bengali"),
    (0x0A00, 0x0A80, "Gurmukhi"),
    (0x0A80, 0x0B00, "Gujarati"),
    (0x0B00, 0x0B80, "Oriya"),
    (0x0B80, 0x0C00, "Tamil"),
    (0x0C00, 0x0C80, "Telugu"),
    (0x0C80, 0x0D00, "Kannada"),
    (0x0D00, 0x0D80, "Malayalam"),
    (0x0D80, 0x0E00, "Sinhala"),
    (0x0E00, 0x0E80, "Thai"),
    (0x0E80, 0x0F00, "Lao"),
    (0x1000, 0x10A0, "Myanmar"),
    (0x10A0, 0x1100, "Georgian"),
    (0x1100, 0x1200, "Hangul"),
    (0x1200, 0x1400, "Ethiopic"),
    (0x1780, 0x1800, "Khmer"),
    (0x3040, 0x3100, "Kana"),
    (0x4E00, 0xA000, "Han"),
    (0xAC00, 0xD7B0, "Hangul"),
    (0xFB50, 0xFF00, "Arabic"),
]
GAMBLING = re.compile(
    r"ufabet|sbobet|betflix|baccarat|บาคาร่า|สล็อต|คาสิโน|แทงบอล|เว็บพนัน|slot gacor|situs slot|"
    r"judi online|togel|online casino|casino online|pg slot|slot online|카지노|바카라|토토사이트",
    re.I,
)
CF_BODY = re.compile(
    r"Just a moment\.\.\.|challenge-platform|cf-chl-|Attention Required! \| Cloudflare",
    re.I,
)
WP_JSON = re.compile(r"^(https?://[^/]+)(/[^?]*)?/wp-json(/wp/v2/[^?]*)\??(.*)$")


@dataclass
class Probe:
    url: str
    role: str
    status: str = ""
    http: int | None = None
    final_url: str = ""
    detail: str = ""
    tried: list = field(default_factory=list)


def _fill(template: str, values: dict) -> str:
    out = re.sub(
        r"\{(\w+)\}", lambda m: str(values.get(m.group(1), m.group(0))), template
    )
    return out.replace("{{", "{").replace("}}", "}")


def _as_list(v) -> list:
    return [] if v is None else [v] if isinstance(v, str) else list(v)


def listing_urls(cfg: dict, today: datetime) -> list[tuple[str, str]]:
    """(role, url) pairs a collect requests first, per listing type (see scrapers/strategies)."""
    L = cfg.get("listing") or {}
    t = L.get("type")
    date_vals = {
        "year": today.year,
        "month": f"{today.month:02d}",
        "day": f"{today.day:02d}",
    }
    if t == "api":
        vals = {
            "page": L.get("page_start", 0),
            "offset": L.get("offset_start", 0),
            "size": L.get("offset_step", 100),
        }
        return [("api", _fill(u, vals)) for u in _as_list(L.get("url_template"))]
    if t == "pagination":
        out = [("start_url", u) for u in _as_list(L.get("start_url"))]
        n = L.get("start_page", 1)
        return out + [
            ("page", _fill(u, {"num": n})) for u in _as_list(L.get("url_template"))
        ]
    if t == "sitemap":
        out = [("sitemap_index", u) for u in _as_list(L.get("sitemap_index_url"))]
        sm = _as_list(L.get("sitemap_urls"))
        return out + [("sitemap", u) for u in (sm[:1] + sm[-1:] if len(sm) > 1 else sm)]
    if t == "rss":
        return [("feed", u) for u in _as_list(L.get("feed_urls"))[:3]]
    if t in ("follow_link", "cursor"):
        return [("start_url", u) for u in _as_list(L.get("start_url"))]
    if t == "archive":
        return [
            ("archive", _fill(u, date_vals)) for u in _as_list(L.get("url_template"))
        ]
    if t == "paginated_archive":
        if L.get("date_format") == "range":
            f = L.get("range_date_format", "%d.%m.%Y")
            date_vals = {"date_from": today.strftime(f), "date_to": today.strftime(f)}
        return [
            ("archive", _fill(u, {**date_vals, "num": ""}))
            for u in _as_list(L.get("start_url"))
        ]
    return []


def script_share(text: str) -> tuple[int, dict]:
    c = collections.Counter()
    for ch in text:
        if not ch.isalpha():
            continue
        o = ord(ch)
        if o < 0x250:
            c["Latin"] += 1
            continue
        c[next((s for a, b, s in _RANGES if a <= o < b), "Other")] += 1
    n = sum(c.values())
    return n, {k: v / n for k, v in c.most_common()} if n else {}


def visible_text(body: str, kind: str) -> str:
    if kind == "json":  # WP JSON escapes non-ASCII as \uXXXX
        body = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), body)
    body = re.sub(r"(?is)<(script|style|noscript)\b.*?</\1>", " ", body)
    return htmllib.unescape(re.sub(r"<[^>]+>", " ", body))


def lang_scripts(language) -> set:
    return LANG_SCRIPTS.get(str(language).strip("[]\"' ").lower(), {"Latin"})


def hijack_reason(
    text: str,
    language: str,
    country_scripts: frozenset = frozenset(),
    items: list | None = None,
) -> str:
    """Why this listing is not the configured outlet ('' if it looks fine). A script that
    some other config of the same country is written in is a wrong language tag, not a
    hijack, so it does not count. Gambling: half the listed posts (`items`), or 20 hits
    on a page without posts; real outlets run a few sponsored casino posts."""
    if items:
        g = sum(bool(GAMBLING.search(i)) for i in items)
        if g / len(items) >= 0.5:
            return f"gambling terms in {g}/{len(items)} posts"
    elif len(hits := GAMBLING.findall(text)) >= 20:
        return f"gambling terms x{len(hits)} ({', '.join(sorted({h.lower() for h in hits})[:4])})"
    n, share = script_share(text)
    if n < 300 or not share:
        return ""
    expected = lang_scripts(language)
    top = next(iter(share))
    if (
        top not in expected | country_scripts
        and top != "Latin"
        and share[top] >= 0.6
        and not any(share.get(s, 0) >= 0.15 for s in expected)
    ):
        return f"script {top} {share[top]:.0%}, expected {'/'.join(sorted(expected))}"
    return ""


def _posts(body: str) -> list | None:
    """One string per post of a JSON list listing (None if it is not one)."""
    try:
        data = json.loads(body.lstrip("\ufeff"))
    except ValueError:
        return None
    if isinstance(data, list) and data and all(isinstance(x, dict) for x in data):
        return [json.dumps(x, ensure_ascii=False) for x in data]
    return None


def empty_reason(body: str, kind: str, role: str, cfg: dict) -> str:
    """'' unless the listing parsed to zero entries where the parser expects some."""
    s = body.strip()
    if role == "api":
        if s in ("[]", "{}"):
            return "API returned an empty list"
        if re.search(
            r"/wp-json/|rest_route=", cfg.get("_probe_url", "")
        ) and not s.startswith(("[", "{", "﻿")):
            return "WP REST URL did not return JSON"
        return ""
    if role in ("sitemap_index", "sitemap"):
        return "" if re.search(r"<loc>", s, re.I) else "sitemap has no <loc>"
    if role == "feed":
        return (
            ""
            if re.search(r"<(item|entry)[\s>]", s, re.I)
            else "feed has no <item>/<entry>"
        )
    thumb = (cfg.get("selectors") or {}).get("thumbnail")
    container = thumb.get("container") if isinstance(thumb, dict) else thumb
    if not container or container == "filler" or kind != "html":
        return ""
    try:
        import parsel

        n = len(parsel.Selector(body).css(container))
    except Exception:
        return ""
    return "" if n else f"0 matches for thumbnail selector {container!r}"


def _host(u: str) -> str:
    h = urlsplit(u).netloc.lower()
    return h[4:] if h.startswith("www.") else h


# A redirect to one of these is a dead outlet, not a move.
PARKED = re.compile(
    r"suspendedpage\.cgi|suspended\.page|hugedomains\.com|expireddomains\.com|sedo\.com|"
    r"afternic\.com|dan\.com/|godaddy\.com/domain|parkingcrew|bodis\.com|recaptcha\.cloud",
    re.I,
)


GAMBLING_HOST = re.compile(
    r"slot|casino|togel|judi|poker|baccarat|ufabet|\dbet|bet\d", re.I
)


def _norm_path(path: str) -> str:
    """Unquoted, no trailing slash, and page 1 (`/page/1`, `/1`) folded into the base:
    WordPress answers /category/x/page/1/ with a redirect to /category/x/."""
    return re.sub(r"/(page/)?1$", "", unquote(path).rstrip("/"))


def _moved(url: str, final: str) -> str:
    a, b = urlsplit(url), urlsplit(final)
    if _host(url) != _host(final):
        return f"host -> {b.netloc}"
    if _norm_path(a.path) != _norm_path(b.path):
        return f"path -> {b.path or '/'}"
    return ""


class Prober:
    def __init__(self, concurrency: int = 8):
        self.sem = asyncio.Semaphore(concurrency)
        self.locks: dict[str, asyncio.Lock] = collections.defaultdict(asyncio.Lock)
        self.last: dict[str, float] = {}
        self.dns: dict[str, bool] = {}

    async def _resolves(self, host: str) -> bool:
        if host not in self.dns:
            loop = asyncio.get_running_loop()
            try:
                await loop.getaddrinfo(host, 443)
                self.dns[host] = True
            except socket.gaierror as e:
                # Only "no such name" is dead; temporary resolver failures are not.
                self.dns[host] = e.errno not in (
                    socket.EAI_NONAME,
                    getattr(socket, "EAI_NODATA", -999),
                )
        return self.dns[host]

    async def _get(self, client, url, headers, method="GET", data=None):
        host = urlsplit(url).netloc.lower()
        async with self.locks[host]:
            wait = self.last.get(host, 0) + DOMAIN_GAP - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            async with self.sem:
                try:
                    async with client.stream(
                        method, url, headers=headers, data=data
                    ) as r:
                        buf = b""
                        async for chunk in r.aiter_bytes():
                            buf += chunk
                            if len(buf) >= MAX_BYTES:
                                break
                        return r, buf
                finally:
                    self.last[host] = time.monotonic()

    async def probe(self, client, url: str, role: str, cfg: dict) -> Probe:
        p = Probe(url=url, role=role)
        host = urlsplit(url).hostname or ""
        if not await self._resolves(host):
            p.status, p.detail = "dns_dead", f"no DNS record for {host}"
            return p
        headers = {
            "User-Agent": UA,
            "Accept-Language": "en-US,en;q=0.9",
            **{k: str(v) for k, v in (cfg.get("headers") or {}).items()},
        }
        L = cfg.get("listing") or {}
        method = str(L.get("request_method", "GET")).upper() if role == "api" else "GET"
        data = (
            {
                k: _fill(
                    str(v),
                    {
                        "page": L.get("page_start", 0),
                        "offset": L.get("offset_start", 0),
                    },
                )
                for k, v in (L.get("form_data") or {}).items()
            }
            if method == "POST"
            else None
        )
        for attempt in (1, 2):
            try:
                r, body = await self._get(client, url, headers, method, data)
            except httpx.TimeoutException:
                p.status, p.detail = "timeout", f"no answer in {TIMEOUT:.0f}s"
            except httpx.ConnectError as e:
                p.status, p.detail = "conn_error", (str(e) or type(e).__name__)[:160]
                return p
            except (httpx.HTTPError, OSError) as e:
                p.status, p.detail = "conn_error", f"{type(e).__name__}: {e}"[:160]
                return p
            else:
                self._classify(p, r, body, cfg)
            p.tried.append(datetime.now(timezone.utc).strftime("%H:%M:%SZ"))
            if p.status not in ("timeout", "server_error") or attempt == 2:
                return p
            await asyncio.sleep(5)
        return p

    def _classify(self, p: Probe, r: httpx.Response, raw: bytes, cfg: dict) -> None:
        p.http, p.final_url = r.status_code, str(r.url)
        body = raw.decode(r.encoding or "utf-8", "replace") if raw else ""
        cf = (
            "cloudflare" in r.headers.get("server", "").lower() or "cf-ray" in r.headers
        )
        code = r.status_code
        if CF_BODY.search(body[:20000]) and (cf or code in (403, 503, 429)):
            p.status, p.detail = "cloudflare", f"challenge page (HTTP {code})"
        elif code in (404, 410):
            p.status, p.detail = (
                "not_found",
                f"HTTP {code}"
                + (f" after redirect to {p.final_url}" if p.final_url != p.url else ""),
            )
        elif code in (401, 403, 451):
            p.status, p.detail = (
                "forbidden",
                f"HTTP {code}" + (" (cloudflare)" if cf else ""),
            )
        elif code == 429:
            p.status, p.detail = "forbidden", "HTTP 429 rate limited"
        elif code >= 500:
            p.status = (
                "cloudflare"
                if cf and code in (503, 520, 521, 522, 523, 525, 526)
                else "server_error"
            )
            p.detail = f"HTTP {code}"
        elif code >= 400:
            p.status, p.detail = "server_error", f"HTTP {code}"
        else:
            ctype = r.headers.get("content-type", "").lower()
            kind = (
                "json"
                if "json" in ctype or body.lstrip()[:1] in ("[", "{")
                else "xml"
                if "xml" in ctype
                else "html"
            )
            text = visible_text(body, kind) if kind != "xml" else body
            hj = (
                hijack_reason(
                    text,
                    cfg.get("language", "en"),
                    cfg.get("_country_scripts", frozenset()),
                    _posts(body) if kind == "json" else None,
                )
                if kind != "xml"
                else (hijack_reason(body, "en") if GAMBLING.search(body) else "")
            )
            mv = _moved(p.url, p.final_url)
            empty = empty_reason(body, kind, p.role, {**cfg, "_probe_url": p.url})
            if _host(p.url) != _host(p.final_url) and GAMBLING_HOST.search(
                _host(p.final_url)
            ):
                p.status, p.detail = (
                    "hijacked",
                    f"redirects to gambling site {_host(p.final_url)}",
                )
            elif PARKED.search(p.final_url):
                p.status, p.detail = (
                    "hijacked",
                    f"redirects to a parked/suspended page {p.final_url[:80]}",
                )
            elif hj:
                p.status, p.detail = "hijacked", hj
            elif mv:
                p.status, p.detail = "redirect_moved", mv
            elif empty:
                p.status, p.detail = "empty_listing", empty
            else:
                p.status = "ok"


def rest_route_variant(url: str) -> str:
    """https://x/wp-json/wp/v2/posts?a=b -> https://x/?rest_route=/wp/v2/posts&a=b ('' if not WP)."""
    m = WP_JSON.match(url)
    if not m:
        return ""
    base, sub, route, q = m.groups()
    return f"{base}{sub or ''}/?rest_route={route}" + (f"&{q}" if q else "")
