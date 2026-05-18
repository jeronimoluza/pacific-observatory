"""Sierra Leone NPRA weekly homepage fuel prices.

The National Petroleum Regulatory Agency publishes current fuel prices on
``https://pra.gov.sl/`` in the homepage ``#weeklyPrice`` area. Historical
coverage comes from Wayback Machine homepage snapshots, using the snapshot
date as the observation date. The live page does not expose a reliable
last-updated stamp, so live observations use the fetch date.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import date, datetime

import pandas as pd
from bs4 import BeautifulSoup

from core.http import make_session

logger = logging.getLogger(__name__)

_LIVE_URL = "https://pra.gov.sl/"
_CDX_URL = (
    "https://web.archive.org/cdx/search/cdx?"
    "url=pra.gov.sl&matchType=domain&output=json&"
    "fl=timestamp,statuscode&filter=statuscode:200&limit=500"
)
_WAYBACK_FMT = "https://web.archive.org/web/{ts}id_/https://pra.gov.sl/"
_COUNTRY = "Sierra Leone"
_CURRENCY = "SLE"
_SOURCE_KEY = "npra_sl_weekly"
_THROTTLE_S = 1.0

_PRICE_RE = re.compile(
    r"(Petrol|Diesel|Kerosene|Fuel\s*Oil)"  # product
    r"\s*[-–—:]*\s*"  # optional ASCII/en/em-dash or colon
    r"N[Ll][Ee]\s*"  # currency anchor (NLe, case-insensitive)
    r"([0-9]{1,4}(?:[.,][0-9]{1,3})?)",  # number, comma or dot decimal
    re.IGNORECASE,
)
_UPDATED_RE = re.compile(
    r"(?:last\s+updated|updated)\s*[:\-]?\s*([0-3]?\d)\s+([A-Za-z]+)\s+(20\d{2})",
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


def _clean_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True))


def _element_text(element) -> str:
    return re.sub(r"\s+", " ", element.get_text(" ", strip=True))


def _candidate_texts(html: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    candidates: list[str] = []
    weekly_price = soup.select_one("#weeklyPrice")
    if weekly_price is not None:
        candidates.append(_element_text(weekly_price))
    for element in soup.find_all(True):
        attrs = " ".join(
            str(value)
            for key in ("id", "class")
            for value in (
                element.get(key, [])
                if isinstance(element.get(key, []), list)
                else [element.get(key, "")]
            )
        )
        if re.search(r"weekly|price", attrs, re.IGNORECASE):
            text = _element_text(element)
            if text:
                candidates.append(text)
    full_text = _clean_text(html)
    match = _PRICE_RE.search(full_text)
    if match:
        end_match = re.search(
            r"The National Petroleum Regulatory Authority|Who We Are|Weekly Stocks Display",
            full_text[match.start() :],
            re.IGNORECASE,
        )
        end = match.start() + end_match.start() if end_match else len(full_text)
        candidates.append(full_text[match.start() : end])
    candidates.append(full_text)
    return list(dict.fromkeys(candidates))


def _parse_updated_date(text: str) -> date | None:
    match = _UPDATED_RE.search(text)
    if not match:
        return None
    month = _MONTHS.get(match.group(2).lower())
    if not month:
        return None
    try:
        return date(int(match.group(3)), month, int(match.group(1)))
    except ValueError:
        return None


def _parse_products(html: str) -> list[tuple[str, float]]:
    for text in _candidate_texts(html):
        products: dict[str, float] = {}
        for match in _PRICE_RE.finditer(text):
            product = re.sub(r"\s+", " ", match.group(1)).strip().title()
            if product == "Fuel Oil":
                product = "Fuel Oil"
            products[product] = float(match.group(2))
        if products:
            return [(product, price) for product, price in products.items()]
    return []


def _parse_live_date(html: str) -> date:
    for text in _candidate_texts(html):
        parsed = _parse_updated_date(text)
        if parsed:
            return parsed
    return date.today()


def _snapshot_date(timestamp: str) -> date | None:
    try:
        return datetime.strptime(timestamp[:8], "%Y%m%d").date()
    except ValueError:
        return None


def _list_snapshots(session, fallback: date) -> list[str]:
    from_ts = fallback.strftime("%Y%m%d")
    to_ts = date.today().strftime("%Y%m%d")
    url = f"{_CDX_URL}&from={from_ts}&to={to_ts}"
    try:
        resp = session.get(url, timeout=60)
    except Exception:
        logger.exception("[npra_sl] CDX request failed")
        return []
    if resp.status_code != 200:
        logger.warning("[npra_sl] CDX HTTP %d", resp.status_code)
        return []
    try:
        data = resp.json()
    except Exception:
        logger.exception("[npra_sl] CDX JSON decode failed")
        return []
    return [row[0] for row in data[1:] if row and row[0]]


def _fetch_html(session, url: str) -> str | None:
    try:
        resp = session.get(url, timeout=60)
    except Exception:
        logger.exception("[npra_sl] GET failed: %s", url)
        return None
    if resp.status_code != 200:
        logger.warning("[npra_sl] HTTP %d for %s", resp.status_code, url)
        return None
    return resp.text


def _row_for(obs_date: date, product: str, price: float) -> dict:
    return {
        "observation_date": obs_date.isoformat(),
        "country": _COUNTRY,
        "fuel_product": product,
        "price_local": price,
        "currency": _CURRENCY,
        "unit": "L",
        "source_key": _SOURCE_KEY,
    }


def fetch_npra_sl(cutoff: date) -> pd.DataFrame | None:
    session = make_session()
    rows: list[dict] = []

    html = _fetch_html(session, _LIVE_URL)
    if html:
        obs_date = _parse_live_date(html)
        products = _parse_products(html)
        if obs_date > cutoff:
            for product, price in products:
                rows.append(_row_for(obs_date, product, price))
            logger.info("[npra_sl] live %s -> %d products", obs_date, len(products))

    for ts in _list_snapshots(session, cutoff):
        obs_date = _snapshot_date(ts)
        if obs_date is None or obs_date <= cutoff:
            continue
        time.sleep(_THROTTLE_S)
        html = _fetch_html(session, _WAYBACK_FMT.format(ts=ts))
        if not html:
            continue
        products = _parse_products(html)
        if not products:
            logger.warning("[npra_sl] no prices parsed from snapshot %s", ts)
            continue
        for product, price in products:
            rows.append(_row_for(obs_date, product, price))
        logger.info("[npra_sl] wayback %s -> %d products", ts, len(products))

    if not rows:
        logger.info("[npra_sl] no rows after cutoff %s", cutoff)
        return None
    df = (
        pd.DataFrame(rows)
        .drop_duplicates(subset=["observation_date", "fuel_product"], keep="last")
        .sort_values(["observation_date", "fuel_product"])
        .reset_index(drop=True)
    )
    logger.info(
        "[npra_sl] %d rows (%s -> %s, %d dates x %d products)",
        len(df),
        df["observation_date"].iloc[0],
        df["observation_date"].iloc[-1],
        df["observation_date"].nunique(),
        df["fuel_product"].nunique(),
    )
    return df


__all__ = ["fetch_npra_sl"]
