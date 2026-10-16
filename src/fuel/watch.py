"""`po fuel watch`: alerts for countries whose fuel prices live in a manual table.

One YAML per country under src/fuel/configs/_watch/. Each run, per country:

- pages: official URLs. `mode: links` hashes the set of matching <a> links (new link ->
  alert, listing it); `mode: urls` does the same for every URL in the raw body (JSON
  APIs, RSS feeds); `mode: text` hashes normalized text lines (new lines -> alert).
  0 matching links is a failure unless `allow_empty: true` (news feeds, home pages),
  and even then the page must still carry some links.
  Normalization drops scripts, styles, comments, dates, times and view counters, plus
  any `ignore` regexes, so cosmetic changes do not alert.
- news: Google News RSS queries. An item alerts once: seen by link OR by normalized
  title, its title must hold a `keywords` term and (when set) a `must` term (country,
  regulator), and be newer than `lookback_days`.
- gpp: GlobalPetrolPrices as a reference only (see watch_gpp.py).
- levels: our table; its latest row older than `stale_months` -> amarillo.

Every fetch that fails (HTTP error, parse error, matching links gone, GPP stale) counts
toward `broken_after`; at that count a rojo "vigilancia rota" goes out, and an info when
it recovers. The first run of a page or query only records a baseline. State per
country (hashes, seen items, GPP anchors, alerts already sent) lives in
<state_dir>/<country>.json, so re-running is idempotent.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import unicodedata
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote_plus, unquote, urljoin, urlsplit, urlunsplit

import requests
import yaml
from bs4 import BeautifulSoup, Comment

from fuel import watch_gpp

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = Path(__file__).resolve().parent / "configs" / "_watch"
QUARANTINE = (
    Path(__file__).resolve().parent / "configs" / "_quarantine" / "observations.yaml"
)
STATE_DIR = ROOT / "data" / "fuel" / "_watch"
GPP_DIR = ROOT / "data" / "fuel" / "_reference" / "gpp"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
SEEN_CAP = 1000

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


def load_configs(
    country: str | None = None, config_dir: Path = CONFIG_DIR
) -> list[dict]:
    out = []
    for p in sorted(config_dir.glob("*.yaml")):
        cfg = yaml.safe_load(p.read_text())
        if country in (None, cfg["country"]):
            out.append(cfg)
    return out


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
    first = "hash" not in st
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


def _quarantined() -> set[str]:
    if not QUARANTINE.exists():
        return set()
    return {e["observation_hash"] for e in yaml.safe_load(QUARANTINE.read_text()) or []}


def latest_levels(lv: dict, today: date) -> dict[str, tuple[date, float]] | None:
    """{product: (date, price)} from our table(s); None when no table file exists."""
    cols = {
        "date": "observation_date",
        "product": "fuel_product",
        "price": "price_local",
        **lv.get("columns", {}),
    }
    paths = [ROOT / p if not Path(p).is_absolute() else Path(p) for p in lv["paths"]]
    paths = [p for p in paths if p.exists()]
    if not paths:
        return None
    bad, out = _quarantined(), {}
    for p in paths:
        with open(p, newline="") as f:
            for r in csv.DictReader(f):
                if (
                    r.get("observation_hash") in bad
                    or not r.get(cols["price"])
                    or not r.get(cols["date"])
                ):
                    continue
                d = date.fromisoformat(r[cols["date"]][:10])
                if d <= today and (
                    r[cols["product"]] not in out or d >= out[r[cols["product"]]][0]
                ):
                    out[r[cols["product"]]] = (d, float(r[cols["price"]]))
    return out


def check_levels(cfg: dict, levels, today: date) -> list[tuple[str, str, str]]:
    lv = cfg.get("levels")
    if not lv:
        return []
    if levels is None:
        return [
            (
                "amarillo",
                "levels:missing",
                f"tabla propia no encontrada: {', '.join(lv['paths'])}",
            )
        ]
    if not levels:
        return [
            (
                "amarillo",
                "levels:empty",
                "tabla propia sin filas válidas (vacía o en cuarentena)",
            )
        ]
    last = max(d for d, _ in levels.values())
    months = lv.get("stale_months", 3)
    if (today - last).days > months * 30.5:
        return [
            (
                "amarillo",
                f"stale:{last}",
                f"tabla propia vencida: última fila {last} (> {months} meses)",
            )
        ]
    return []


def check_gpp(
    cfg: dict, levels, st: dict, ref_dir: Path, today: date, fails: list
) -> list[tuple[str, str, str]]:
    g, out, rows = cfg["gpp"], [], []
    for product, ours_name in g["products"].items():
        wid = f"gpp:{product}"
        url = watch_gpp.URL.format(slug=g["slug"], product=product)
        try:
            when, price = watch_gpp.parse_page(
                fetch(url),
                name=g["name"],
                currency=cfg["currency"],
                max_age_days=g.get("max_age_days", 45),
                today=today,
            )
        except Exception as e:  # noqa: BLE001 - any failure is a broken watch, not a crash
            fails.append((wid, url, f"{type(e).__name__}: {e}"))
            continue
        fails.append((wid, url, None))
        rows.append(
            {
                "gpp_date": when.isoformat(),
                "product": product,
                "price_local": price,
                "currency": cfg["currency"],
                "unit": "liter",
                "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "url": url,
                "reference_only": "true",
            }
        )
        ours = (levels or {}).get(ours_name) if ours_name else None
        out += watch_gpp.compare(
            product, when, price, ours, st.setdefault(product, {}), g
        )
    watch_gpp.append_reference(ref_dir / f"{cfg['country']}.csv", rows)
    return out


# ── orchestration ────────────────────────────────────────────────


def _load_state(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def _save_state(path: Path, st: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, indent=1, sort_keys=True, default=str))
    os.replace(tmp, path)


def _track(
    st: dict, wid: str, url: str, err: str | None, broken_after: int
) -> list[tuple[str, str, str]]:
    """Consecutive-failure counter per watched item -> broken / restored alerts."""
    fails = st.setdefault("fails", {})
    if err is None:
        was = fails.pop(wid, {}).get("n", 0)
        if was >= broken_after:
            st.setdefault("sent", {}).pop(f"broken:{wid}", None)
            return [
                (
                    "info",
                    f"restored:{wid}:{was}",
                    f"vigilancia restaurada: {wid} <{url}> responde de nuevo",
                )
            ]
        return []
    f = fails.setdefault(wid, {"n": 0})
    f["n"], f["last_error"] = f["n"] + 1, err[:200]
    if f["n"] >= broken_after:
        sent = st.setdefault("sent", {})
        for k in [k for k in sent if k.startswith(f"restored:{wid}:")]:
            del sent[k]
        return [
            (
                "rojo",
                f"broken:{wid}",
                f"vigilancia rota: {wid} <{url}> falló {f['n']} veces seguidas ({err[:160]})",
            )
        ]
    return []


def watch_country(
    cfg: dict,
    state_dir: Path = STATE_DIR,
    ref_dir: Path = GPP_DIR,
    now: datetime | None = None,
    save: bool = True,
) -> tuple[list[tuple[str, str]], dict]:
    """Run every check for one country; return (NEW alerts as (severity, message), {watch id: ok|error}).

    save=False (dry run) leaves the state file untouched, so the same alerts come back.
    """
    now = now or datetime.now(timezone.utc)
    today, country = now.date(), cfg["country"]
    path = state_dir / f"{country}.json"
    st = _load_state(path)
    broken_after = cfg.get("broken_after", 3)
    alerts, results = [], []  # results: (watch id, url, error or None)

    for page in cfg.get("pages", []):
        try:
            alerts += check_page(
                page, st.setdefault("pages", {}).setdefault(page["id"], {})
            )
            results.append((f"page:{page['id']}", page["url"], None))
        except Exception as e:  # noqa: BLE001
            results.append(
                (f"page:{page['id']}", page["url"], f"{type(e).__name__}: {e}")
            )
    for q in cfg.get("news", []):
        wid = f"news:{_sha(q['q'])}"
        try:
            alerts += check_news(
                q,
                cfg.get("keywords", []),
                st.setdefault("news", {}).setdefault(q["q"], {}),
                cfg.get("lookback_days", 10),
                now,
                cfg.get("must", []),
            )
            results.append((wid, news_url(q), None))
        except Exception as e:  # noqa: BLE001
            results.append((wid, news_url(q), f"{type(e).__name__}: {e}"))
    levels = latest_levels(cfg["levels"], today) if cfg.get("levels") else None
    alerts += check_levels(cfg, levels, today)
    if cfg.get("gpp"):
        alerts += check_gpp(
            cfg, levels, st.setdefault("gpp", {}), ref_dir, today, results
        )
    for wid, url, err in results:
        alerts += _track(st, wid, url, err, broken_after)

    sent, new = st.setdefault("sent", {}), []
    for sev, key, msg in alerts:
        if key not in sent:
            sent[key] = now.isoformat(timespec="seconds")
            new.append((sev, f"fuel-watch {country}: {msg}"))
    st["last_run"] = now.isoformat(timespec="seconds")
    st["last_results"] = {w: (e or "ok") for w, _, e in results}
    if save:
        _save_state(path, st)
    return new, st["last_results"]
