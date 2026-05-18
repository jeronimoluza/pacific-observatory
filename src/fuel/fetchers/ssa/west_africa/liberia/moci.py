"""Liberia MoCI petroleum products monthly price circulars.

The Ministry of Commerce & Industry publishes press-release circulars for
petroleum price ceilings. The fetcher discovers circular articles from
press-release indexes, sitemap entries and date-slug probes, parses the
retail USD/gallon prices, converts them to USD/litre, and emits rows for
gasoline/PMS, AGO diesel, and any HFO or jet-fuel rows found.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import date, timedelta
from urllib.parse import urljoin

import pandas as pd
from bs4 import BeautifulSoup

from core.http import make_session

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.moci.gov.lr"
_INDEX_URLS = [
    f"{_BASE_URL}/media/press-releases",
    f"{_BASE_URL}/media-center/press-releases",
    f"{_BASE_URL}/media/news-press-release",
]
_SITEMAPS = [f"{_BASE_URL}/sitemap.xml", f"{_BASE_URL}/sitemap_index.xml"]
_COUNTRY = "Liberia"
_CURRENCY = "USD"
_SOURCE_KEY = "moci_lr_monthly"
_THROTTLE_S = 0.2
_GALLON_TO_LITRE = 3.785411784

_TITLE_RE = re.compile(
    r"petroleum\s+products\s+monthly\s+price\s+circular\s+([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})",
    re.IGNORECASE,
)
_SLUG_RE = re.compile(
    r"petroleum-products-monthly-price-circular-([a-z]+)-(\d{1,2})-(\d{4})",
    re.IGNORECASE,
)
_EFFECTIVE_RE = re.compile(
    r"Effective\s+([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})",
    re.IGNORECASE,
)
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
_PRODUCT_ALIASES = {
    "Gasoline (PMS)": r"(?:Gasoline\s*(?:\(\s*PMS\s*\))?|PMS)",
    "Fuel Oil (AGO)": r"(?:(?:Fuel\s+Oil|Diesel)\s*(?:\(\s*AGO\s*\))?|AGO)",
    "HFO": r"(?:HFO|Heavy\s+Fuel\s+Oil)",
    "Jet Fuel": r"Jet\s+Fuel",
}


def _date_from_parts(month_name: str, day: str, year: str) -> date | None:
    month = _MONTHS.get(month_name.lower())
    if month is None:
        return None
    try:
        return date(int(year), month, int(day))
    except ValueError:
        return None


def _date_from_text(text: str) -> date | None:
    match = _EFFECTIVE_RE.search(text) or _TITLE_RE.search(text)
    if match:
        return _date_from_parts(match.group(1), match.group(2), match.group(3))
    match = _SLUG_RE.search(text)
    if match:
        return _date_from_parts(match.group(1), match.group(2), match.group(3))
    return None


def _clean_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style"]):
        tag.decompose()
    lines = [
        re.sub(r"\s+", " ", line).strip() for line in soup.get_text("\n").splitlines()
    ]
    return "\n".join(line for line in lines if line)


def _discover_from_index(session, cutoff: date) -> dict[str, date | None]:
    out: dict[str, date | None] = {}
    for root in _INDEX_URLS:
        for page in range(0, 20):
            url = root if page == 0 else f"{root}?page={page}"
            try:
                resp = session.get(url, timeout=45)
            except Exception:
                logger.exception("[moci_lr] index fetch failed: %s", url)
                break
            if resp.status_code != 200:
                if page == 0:
                    continue
                break
            soup = BeautifulSoup(resp.text, "lxml")
            page_new = 0
            for link in soup.find_all("a", href=True):
                title = re.sub(r"\s+", " ", link.get_text(" ")).strip()
                href = link["href"]
                if not (_TITLE_RE.search(title) or _SLUG_RE.search(href)):
                    continue
                article_url = urljoin(_BASE_URL, href)
                obs_date = _date_from_text(title) or _date_from_text(article_url)
                if obs_date and obs_date <= cutoff:
                    continue
                if article_url not in out:
                    out[article_url] = obs_date
                    page_new += 1
            logger.info(
                "[moci_lr] index=%s page=%d new=%d total=%d",
                root,
                page,
                page_new,
                len(out),
            )
            if page_new == 0 and page > 8:
                break
            time.sleep(_THROTTLE_S)
    return out


def _discover_from_sitemap(session, cutoff: date) -> dict[str, date | None]:
    out: dict[str, date | None] = {}
    queue = list(_SITEMAPS)
    seen: set[str] = set()
    while queue:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        try:
            resp = session.get(url, timeout=45)
        except Exception:
            continue
        if resp.status_code != 200:
            continue
        locs = re.findall(r"<loc>\s*([^<]+)\s*</loc>", resp.text, flags=re.IGNORECASE)
        for loc in locs:
            if loc.endswith(".xml") and len(seen) < 30:
                queue.append(loc)
                continue
            if not _SLUG_RE.search(loc):
                continue
            obs_date = _date_from_text(loc)
            if obs_date and obs_date <= cutoff:
                continue
            out[loc] = obs_date
    return out


def _site_reachable(session) -> bool:
    try:
        resp = session.get(_BASE_URL, timeout=15)
    except Exception:
        return False
    return resp.status_code < 500


def _direct_probe_urls(cutoff: date) -> dict[str, date | None]:
    out: dict[str, date | None] = {}
    today = date.today()
    current = date(cutoff.year, cutoff.month, 1)
    while current <= today:
        month_name = list(_MONTHS.keys())[current.month - 1]
        month_end = date(
            current.year + int(current.month == 12),
            1 if current.month == 12 else current.month + 1,
            1,
        ) - timedelta(days=1)
        for day in range(1, month_end.day + 1):
            obs_date = date(current.year, current.month, day)
            if obs_date <= cutoff or obs_date > today:
                continue
            url = f"{_BASE_URL}/media/press-releases/petroleum-products-monthly-price-circular-{month_name}-{day}-{current.year}"
            out[url] = obs_date
        current = month_end + timedelta(days=1)
    return out


def _discover_articles(session, cutoff: date) -> list[tuple[str, date | None]]:
    out = _discover_from_index(session, cutoff)
    out.update(
        {
            k: v
            for k, v in _discover_from_sitemap(session, cutoff).items()
            if k not in out
        }
    )
    if not out and _site_reachable(session):
        out.update(_direct_probe_urls(cutoff))
    return sorted(out.items(), key=lambda item: item[1] or date.min)


def _parse_price(value: str) -> float | None:
    try:
        price = float(value.replace(",", ""))
    except ValueError:
        return None
    return price if price > 0 else None


def _parse_prices(text: str) -> dict[str, float]:
    prices: dict[str, float] = {}
    flat = re.sub(r"\s+", " ", text)
    for label, product_re in _PRODUCT_ALIASES.items():
        section_re = re.compile(
            rf"{product_re}.{{0,350}}?(?={ '|'.join(_PRODUCT_ALIASES.values()) }|$)",
            re.IGNORECASE,
        )
        for section_match in section_re.finditer(flat):
            section = section_match.group(0)
            retail = re.search(
                r"Retail\s+Pump\s+Price\s*:?\s*US\$\s*(\d+(?:\.\d{2})?)",
                section,
                re.IGNORECASE,
            )
            direct = re.search(
                r"US\$\s*(\d+(?:\.\d{2})?)\s*(?:/|per)?\s*gallon",
                section,
                re.IGNORECASE,
            )
            match = retail or direct
            if not match:
                continue
            price = _parse_price(match.group(1))
            if price is None:
                continue
            prices.setdefault(label, round(price / _GALLON_TO_LITRE, 6))
            break
    return prices


def fetch_moci_lr(cutoff: date) -> pd.DataFrame | None:
    session = make_session()
    rows: list[dict] = []
    seen_dates: set[date] = set()
    for article_url, discovered_date in _discover_articles(session, cutoff):
        if discovered_date and discovered_date <= cutoff:
            continue
        try:
            resp = session.get(article_url, timeout=45)
        except Exception:
            logger.exception("[moci_lr] article fetch failed: %s", article_url)
            continue
        if resp.status_code != 200:
            continue
        text = _clean_text(resp.text)
        obs_date = (
            _date_from_text(text) or discovered_date or _date_from_text(article_url)
        )
        if obs_date is None or obs_date <= cutoff or obs_date in seen_dates:
            continue
        prices = _parse_prices(text)
        if not prices:
            logger.warning("[moci_lr] no prices parsed: %s", article_url)
            continue
        seen_dates.add(obs_date)
        for product, price in prices.items():
            rows.append(
                {
                    "observation_date": obs_date.isoformat(),
                    "country": _COUNTRY,
                    "fuel_product": product,
                    "price_local": price,
                    "currency": _CURRENCY,
                    "source_key": _SOURCE_KEY,
                    "unit": "L",
                }
            )
        logger.info("[moci_lr] %s → %d products", obs_date, len(prices))
        time.sleep(_THROTTLE_S)

    if not rows:
        logger.info("[moci_lr] no rows after cutoff %s", cutoff)
        return None
    df = (
        pd.DataFrame(rows)
        .drop_duplicates(subset=["observation_date", "fuel_product"])
        .sort_values(["observation_date", "fuel_product"])
        .reset_index(drop=True)
    )
    logger.info(
        "[moci_lr] %d rows (%s → %s)",
        len(df),
        df["observation_date"].iloc[0],
        df["observation_date"].iloc[-1],
    )
    return df


__all__ = ["fetch_moci_lr"]
