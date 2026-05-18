"""MME Namibia — Ministry of Mines and Energy Fuel Price Review.

Monthly Fuel Price Review announcements live at https://www.mme.gov.na/news/
as numbered articles whose slug encodes the month (e.g.
``/news/151/Fuel-Price-Review-Announcement-April-2026``). Each article body
prints Walvis Bay reference prices in N$/litre for three products:
Petrol, Diesel 50ppm, Diesel 10ppm.

The live listing exposes ~11 most recent items; older articles are
unreachable directly (older IDs 404 / fall back to the listing) but the
Wayback Machine indexes them through ``web.archive.org/cdx/search/cdx``.
We combine the two: live scrape for current, Wayback CDX backfill for the
older history. Effective dates are taken from explicit phrasing ("come
into effect on …", "with effect from …", "effective …") when present,
falling back to the slug's month/year (first-of-month).
"""

import logging
import re
import time
from datetime import date
from urllib.parse import urljoin

import pandas as pd
from bs4 import BeautifulSoup

from core.http import make_session

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.mme.gov.na"
_NEWS_PATH = "/news/"
_COUNTRY = "Namibia"
_CURRENCY = "NAD"
_SOURCE_KEY = "mme_na_monthly"
_CITY = "Walvis Bay"

_THROTTLE_S = 1.0
_CDX_URL = "https://web.archive.org/cdx/search/cdx"
_WAYBACK_FETCH_TMPL = "https://web.archive.org/web/{ts}id_/{url}"

_NEWS_HREF_RE = re.compile(r"/news/(\d+)/([A-Za-z0-9_\-]+)", re.IGNORECASE)

_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}
_SLUG_MONTH_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|"
    r"September|October|November|December)\b[\s_-]+(\d{4})",
    re.IGNORECASE,
)
_DATE_PHRASE_RE = re.compile(
    r"(?:come into effect on|with effect from|effective(?:\s+from)?)\s+"
    r"(\d{1,2})\s+(\w+)\s+(\d{4})",
    re.IGNORECASE,
)

# Raw token → canonical product label (matches YAML keys)
_PRODUCT_MAP = {
    "petrol": "Petrol",
    "diesel 50ppm": "Diesel 50ppm",
    "diesel 10ppm": "Diesel 10ppm",
}
_PRICE_RE = re.compile(
    r"N\$\s*N?\$?\s*([\d]+(?:\.\d+)?)\s*per\s+litre\s+for\s+"
    r"(petrol|diesel\s+50ppm|diesel\s+10ppm)",
    re.IGNORECASE,
)


def _slug_to_date(slug: str) -> date | None:
    """Derive first-of-month from a slug like 'Fuel-Price-Review-March-2026'."""
    cleaned = slug.replace("-", " ").replace("_", " ")
    m = _SLUG_MONTH_RE.search(cleaned)
    if not m:
        return None
    month = _MONTHS.get(m.group(1).lower())
    if not month:
        return None
    try:
        return date(int(m.group(2)), month, 1)
    except ValueError:
        return None


def _body_to_date(body: str) -> date | None:
    m = _DATE_PHRASE_RE.search(body)
    if not m:
        return None
    month = _MONTHS.get(m.group(2).lower())
    if not month:
        return None
    try:
        return date(int(m.group(3)), month, int(m.group(1)))
    except ValueError:
        return None


def _parse_article(html: str, slug: str) -> tuple[date | None, dict[str, float]]:
    """Return (effective_date, {product_label: price})."""
    soup = BeautifulSoup(html, "lxml")
    body = re.sub(r"\s+", " ", " ".join(soup.stripped_strings))
    obs_date = _body_to_date(body) or _slug_to_date(slug)
    prices: dict[str, float] = {}
    for match in _PRICE_RE.finditer(body):
        raw = match.group(2).lower()
        raw = re.sub(r"\s+", " ", raw).strip()
        label = _PRODUCT_MAP.get(raw)
        if not label:
            continue
        try:
            price = float(match.group(1))
        except ValueError:
            continue
        if price <= 0:
            continue
        prices.setdefault(label, price)
    return obs_date, prices


def _discover_live(session) -> list[tuple[str, str]]:
    """Return [(slug, full_url), ...] for fuel-price articles on the live site."""
    resp = session.get(urljoin(_BASE_URL, _NEWS_PATH), timeout=30)
    resp.raise_for_status()
    out: dict[str, str] = {}
    for nid, slug in _NEWS_HREF_RE.findall(resp.text):
        if not slug.lower().startswith("fuel"):
            continue
        out.setdefault(slug, urljoin(_BASE_URL, f"/news/{nid}/{slug}"))
    return sorted(out.items(), key=lambda x: x[0])


def _discover_wayback(session) -> list[tuple[str, str, str]]:
    """Return [(timestamp, slug, original_url), ...] for Wayback-known articles."""
    params = {
        "url": "mme.gov.na/news/*",
        "output": "json",
        "collapse": "urlkey",
        "filter": "statuscode:200",
        "limit": "500",
    }
    try:
        resp = session.get(_CDX_URL, params=params, timeout=120)
    except Exception:
        logger.exception("[mme_na] CDX query failed")
        return []
    if resp.status_code != 200:
        logger.warning("[mme_na] CDX HTTP %d", resp.status_code)
        return []
    try:
        data = resp.json()
    except Exception:
        logger.warning("[mme_na] CDX response not JSON")
        return []
    if not data or len(data) < 2:
        return []
    # First row is the column header
    header, *rows = data
    ts_idx = header.index("timestamp")
    url_idx = header.index("original")
    out: list[tuple[str, str, str]] = []
    seen_slugs: set[str] = set()
    for row in rows:
        original = row[url_idx]
        m = _NEWS_HREF_RE.search(original)
        if not m:
            continue
        slug = m.group(2)
        if not slug.lower().startswith("fuel"):
            continue
        if slug in seen_slugs:
            continue
        seen_slugs.add(slug)
        out.append((row[ts_idx], slug, original))
    return out


def _fetch_article(session, url: str) -> str | None:
    try:
        resp = session.get(url, timeout=30)
    except Exception:
        logger.exception("[mme_na] fetch failed %s", url)
        return None
    if resp.status_code != 200 or "fuel" not in resp.text.lower():
        return None
    return resp.text


def fetch_mme_na(cutoff: date) -> pd.DataFrame | None:
    session = make_session()

    # Live first — these are authoritative for the most recent months
    live_articles = _discover_live(session)
    logger.info("[mme_na] live: %d fuel articles", len(live_articles))

    parsed: dict[date, dict[str, float]] = {}
    for slug, url in live_articles:
        time.sleep(_THROTTLE_S)
        html = _fetch_article(session, url)
        if html is None:
            continue
        obs_date, prices = _parse_article(html, slug)
        if obs_date is None or not prices:
            continue
        if obs_date <= cutoff:
            continue
        parsed.setdefault(obs_date, {}).update(prices)
        logger.info(
            "[mme_na] live %s → date=%s products=%d", slug[:60], obs_date, len(prices)
        )

    # Wayback backfill for older months not seen live
    wayback_articles = _discover_wayback(session)
    logger.info("[mme_na] wayback: %d candidate articles", len(wayback_articles))
    live_slugs = {slug.lower() for slug, _ in live_articles}
    parsed_dates = set(parsed.keys())
    for ts, slug, original in wayback_articles:
        if slug.lower() in live_slugs:
            continue
        snapshot_url = _WAYBACK_FETCH_TMPL.format(ts=ts, url=original)
        time.sleep(_THROTTLE_S)
        html = _fetch_article(session, snapshot_url)
        if html is None:
            continue
        obs_date, prices = _parse_article(html, slug)
        if obs_date is None or not prices:
            continue
        if obs_date <= cutoff:
            continue
        if obs_date in parsed_dates:
            continue
        parsed.setdefault(obs_date, {}).update(prices)
        parsed_dates.add(obs_date)
        logger.info(
            "[mme_na] wayback %s → date=%s products=%d",
            slug[:60],
            obs_date,
            len(prices),
        )

    if not parsed:
        logger.info("[mme_na] No data after cutoff %s", cutoff)
        return None

    rows: list[dict] = []
    for obs_date, prods in parsed.items():
        iso = obs_date.strftime("%Y-%m-%d")
        for label, price in prods.items():
            rows.append(
                {
                    "observation_date": iso,
                    "country": _COUNTRY,
                    "fuel_product": label,
                    "price_local": price,
                    "currency": _CURRENCY,
                    "unit": "L",
                    "source_key": _SOURCE_KEY,
                    "city": _CITY,
                }
            )

    df = (
        pd.DataFrame(rows)
        .drop_duplicates(subset=["observation_date", "fuel_product"])
        .sort_values(["observation_date", "fuel_product"])
        .reset_index(drop=True)
    )
    logger.info(
        "[mme_na] %d rows (%s → %s, %d months × %d products)",
        len(df),
        df["observation_date"].iloc[0],
        df["observation_date"].iloc[-1],
        df["observation_date"].nunique(),
        df["fuel_product"].nunique(),
    )
    return df


__all__ = ["fetch_mme_na"]
