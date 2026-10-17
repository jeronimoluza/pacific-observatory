"""Official pages and Google News for `po fuel watch` (orchestration: watch.py).

Page modes: `links` (matching <a> links), `urls` (every URL in a raw JSON/RSS/HTML
body) and `text` (normalized text lines). Normalization drops scripts, styles,
comments, dates, times, view counters and update labels, so cosmetic changes do not
alert. News items are deduped by link OR normalized title.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus, unquote, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup, Comment

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
SEEN_CAP = 1000
# Bump whenever fold()/normalize_lines()/link canonicalization changes: a page whose state
# was hashed under another version is re-baselined silently instead of alerting on every line.
NORM_VERSION = 2

_MONTHS = (
    r"jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|janv|fevr|mars|avr|mai|juin|juil|"
    r"aout|sept|janvier|fevrier|avril|juillet|septembre|octobre|novembre|decembre|january|"
    r"february|march|april|june|july|august|september|october|november|december|"
    r"janeiro|fevereiro|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro"
)
_NOISE = [
    re.compile(r"\b\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}\b"),  # 12/10/2026, 2026-10-12
    re.compile(rf"\b\d{{1,2}}(er)?\s+({_MONTHS})\.?\s+\d{{4}}\b"),  # 12 octobre 2026
    re.compile(rf"\b({_MONTHS})\.?\s+\d{{1,2}},?\s+\d{{4}}\b"),  # Oct 12, 2026
    re.compile(r"\b\d{1,2}:\d{2}(:\d{2})?\s*(am|pm|h)?\b"),  # 14:05
    re.compile(
        r"\b\d[\d\s,.]*\s*(views?|vues?|visites?|comments?|commentaires?|partages?|shares?)\b"
    ),
    re.compile(r"\b(il y a|ago|ha)\s+\d+\s+\w+\b|\b\d+\s+\w+\s+ago\b"),
    re.compile(r"©.*$"),
    re.compile(
        r"\b(mis|mise) a jour( le)?\b|\b(publie|poste)( le)?\b|\b(last )?updated( on)?\b|"
        r"\bposted( on)?\b|\b(actualizado|atualizado|publicado)( el| em)?\b"
    ),
]


_GENERIC = re.compile(
    r"download|telecharger|lire la suite|read more|here|ici|voir|pdf|more|plus"
)


def fold(s: str) -> str:
    """Lowercase, strip accents and apostrophes (’ vs '), collapse whitespace."""
    s = re.sub(r"[’'`´]", "", s)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", s).strip()


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:16]


# ── fetching ──────────────────────────────────────────────────────


def fetch(url: str, insecure: bool = False) -> str:
    r = requests.get(
        url,
        headers={"User-Agent": UA, "Accept-Language": "fr,en;q=0.8"},
        timeout=40,
        verify=not insecure,
    )
    r.raise_for_status()
    return r.text


def _region(html: str, css: str | None):
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript", "iframe", "svg"]):
        t.decompose()
    for c in soup.find_all(string=lambda x: isinstance(x, Comment)):
        c.extract()
    if css:
        found = soup.select(css)
        if not found:
            raise ValueError(f"css {css!r} matched nothing (page layout changed?)")
        return found
    return [soup.body or soup]


def normalize_lines(
    html: str, css: str | None = None, ignore: list[str] = ()
) -> list[str]:
    """Text lines with dates, times, counters and `ignore` patterns removed."""
    pats = [re.compile(p, re.I) for p in ignore]
    lines = []
    for node in _region(html, css):
        for raw in node.get_text("\n").splitlines():
            s = fold(raw)
            for p in [*_NOISE, *pats]:
                s = p.sub(" ", s)
            s = re.sub(r"\s+", " ", s).strip(" |-·•")
            if len(s) >= 3:
                lines.append(s)
    return lines


def _canon_url(href: str, base: str) -> str:
    u = urlsplit(urljoin(base, href.strip()))
    return urlunsplit(
        (u.scheme, u.netloc.lower(), u.path.rstrip("/") or "/", u.query, "")
    )


def matching_links(
    html: str, base: str, match: str, css: str | None = None
) -> dict[str, str]:
    """{canonical url: folded link text} for links whose text or url matches `match`."""
    rx = re.compile(match, re.I)
    out = {}
    for node in _region(html, css):
        for a in node.find_all("a", href=True):
            if a["href"].startswith(("#", "javascript:", "mailto:", "tel:")):
                continue
            url, text = _canon_url(a["href"], base), fold(a.get_text(" "))
            if len(text) < 4 or _GENERIC.fullmatch(text):
                text = fold(unquote(urlsplit(url).path.rsplit("/", 1)[-1]))
            if rx.search(text) or rx.search(fold(url)):
                out[url] = text[:160]
    return out


_URL_RX = re.compile(r"https?://[^\s\"'<>]+")


def matching_urls(body: str, match: str) -> dict[str, str]:
    """{canonical url: file name} for every URL in a raw body (JSON, RSS, HTML) matching `match`."""
    rx, out = re.compile(match, re.I), {}
    try:  # JSON: undo \u00e0 and \/ escapes so URLs read as published
        body = json.dumps(json.loads(body), ensure_ascii=False)
    except ValueError:
        pass
    for raw in _URL_RX.findall(body):
        url = _canon_url(raw.rstrip(".,;)]}"), raw)
        if rx.search(fold(unquote(url))):
            out[url] = fold(unquote("/".join(urlsplit(url).path.rsplit("/", 2)[-2:])))[
                :160
            ]
    return out


# ── checks: each returns alerts as (severity, key, message) ──────────


def check_page(page: dict, st: dict) -> list[tuple[str, str, str]]:
    html = fetch(page["url"], page.get("insecure", False))
    first = "hash" not in st or st.get("norm") != NORM_VERSION
    st["norm"] = NORM_VERSION
    mode = page.get("mode", "links")
    if mode in ("links", "urls"):
        links = (
            matching_links(html, page["url"], page.get("match", "."), page.get("css"))
            if mode == "links"
            else matching_urls(html, page.get("match", "."))
        )
        if not links:
            # A news feed or home page often holds nothing about fuel: fine with allow_empty,
            # as long as the page still has links at all (else it is broken or blocked).
            anything = (
                matching_links(html, page["url"], ".")
                if mode == "links"
                else matching_urls(html, ".")
            )
            if not page.get("allow_empty") or not anything:
                raise ValueError(
                    f"0 links match {page.get('match')!r} ({len(anything)} links in all; layout changed?)"
                )
        new = sorted(set(links) - set(st.get("items", [])))
        st["items"] = sorted(links)[-SEEN_CAP:]
        st["hash"] = _sha("\n".join(sorted(links)))
        if first or not new:
            return []
        shown = "; ".join(f"{links[u][:70]} <{u}>" for u in new[:3])
        more = f" (+{len(new) - 3} más)" if len(new) > 3 else ""
        return [
            (
                "amarillo",
                f"page:{page['id']}:{_sha(''.join(new))}",
                f"{len(new)} enlace(s) nuevo(s) en {page['url']}: {shown}{more}",
            )
        ]
    lines = normalize_lines(html, page.get("css"), page.get("ignore", []))
    if not lines:
        raise ValueError("no text after normalization")
    h = _sha("\n".join(lines))
    old = set(st.get("items", []))
    st["items"] = sorted({_sha(x) for x in lines})
    changed, st["hash"] = st.get("hash") != h, h
    added = [x for x in lines if _sha(x) not in old]
    if first or not changed or not added:
        return []
    return [
        (
            "amarillo",
            f"page:{page['id']}:{h}",
            f"contenido cambió en {page['url']}: "
            + " / ".join(x[:90] for x in added[:3]),
        )
    ]


def news_url(q: dict) -> str:
    hl, gl = q.get("hl", "fr"), q.get("gl", "US")
    lang = hl.split("-")[0]
    return (
        f"https://news.google.com/rss/search?q={quote_plus(q['q'])}+when:{q.get('when_days', 30)}d"
        f"&hl={hl}&gl={gl}&ceid={gl}:{lang}"
    )


def _title_key(title: str) -> str:
    title = re.sub(r"\s+-\s+[^-]{2,60}$", "", title)  # Google appends " - Source"
    return _sha(re.sub(r"[^a-z0-9]+", " ", fold(title)).strip())


def check_news(
    q: dict,
    keywords: list[str],
    st: dict,
    lookback_days: int,
    now: datetime,
    must: list[str] = (),
) -> list[tuple[str, str, str]]:
    root = ET.fromstring(fetch(news_url(q)).encode())
    first = "links" not in st
    links, titles = set(st.get("links", [])), set(st.get("titles", []))

    def terms(xs, end=""):
        return (
            re.compile(r"\b(" + "|".join(re.escape(fold(x)) for x in xs) + ")" + end)
            if xs
            else None
        )

    # keywords: leading boundary only ("fuel price" matches "fuel prices");
    # must: whole word ("niger" must not match "nigeria").
    kws, musts = terms(keywords), terms(must, r"\b")
    fresh = []
    for it in root.iter("item"):
        title, link = it.findtext("title") or "", it.findtext("link") or ""
        tk = _title_key(title)
        seen = link in links or tk in titles
        links.add(link)
        titles.add(tk)
        ft = fold(title)
        relevant = bool(kws and kws.search(ft)) and (
            musts is None or bool(musts.search(ft))
        )
        if seen or first or not relevant:
            continue
        try:
            pub = parsedate_to_datetime(it.findtext("pubDate") or "")
        except (TypeError, ValueError):
            pub = now
        if pub >= now - timedelta(days=lookback_days):
            fresh.append((title, link))
    st["links"], st["titles"] = sorted(links)[-SEEN_CAP:], sorted(titles)[-SEEN_CAP:]
    if not fresh:
        return []
    shown = "; ".join(f"{t[:100]} <{u}>" for t, u in fresh[:3])
    more = f" (+{len(fresh) - 3} más)" if len(fresh) > 3 else ""
    return [
        (
            "amarillo",
            f"news:{_sha(''.join(u for _, u in fresh))}",
            f"{len(fresh)} noticia(s) nueva(s) [{q['q']}]: {shown}{more}",
        )
    ]
