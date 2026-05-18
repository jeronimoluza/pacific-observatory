"""Senegal ministry fuel-price communiqués.

The Ministry of Energy, Petroleum and Mines site describes CNH as the body
that calculates domestic petroleum product prices every four weeks, but no
complete official CNH price archive was found. This fetcher therefore reads
only first-party ministry pages under ``https://energie.gouv.sn`` and parses
the sparse official communiqués/articles that include explicit pump-price
levels. It does not use media reposts or third-party copies.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import date
from urllib.parse import urljoin

import pandas as pd
from bs4 import BeautifulSoup

from core.http import make_session

logger = logging.getLogger(__name__)

_BASE_URL = "https://energie.gouv.sn"
_INDEX_URLS = [
    f"{_BASE_URL}/our-blog/",
    f"{_BASE_URL}/our-blog/page/2/",
    f"{_BASE_URL}/our-blog/page/3/",
    f"{_BASE_URL}/our-blog/page/4/",
    f"{_BASE_URL}/our-blog/page/5/",
    f"{_BASE_URL}/author/mpesite/page/5/",
]
_COUNTRY = "Senegal"
_CURRENCY = "XOF"
_SOURCE_KEY = "mepm_sn_irregular"
_THROTTLE_S = 1.0

_MONTHS = {
    "janvier": 1,
    "février": 2,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "août": 8,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "décembre": 12,
    "decembre": 12,
}
_FUEL_LINK_RE = re.compile(
    r"(carburant|supercarburant|gasoil|p[ée]trole\s+lampant|gaz\s+butane|prix\s+.*pompe)",
    re.I,
)
_PRODUCT_PATTERNS = [
    ("Super", re.compile(r"\b(?:supercarburant|super\s+carburant|super)\b", re.I)),
    ("Gasoil", re.compile(r"\bgasoil\b", re.I)),
    ("Pétrole lampant", re.compile(r"\bp[ée]trole\s+lampant\b", re.I)),
    ("Gaz butane", re.compile(r"\bgaz\s+butane\b|\bbutane\b", re.I)),
]


def _parse_date(text: str) -> date | None:
    match = re.search(r"(\d{1,2})(?:er)?\s+([A-Za-zéûôîàèù]+)\s+(20\d{2})", text, re.I)
    if match:
        month = _MONTHS.get(match.group(2).lower())
        if month:
            try:
                return date(int(match.group(3)), month, int(match.group(1)))
            except ValueError:
                pass
    match = re.search(r"\b(20\d{2})-(\d{2})-(\d{2})\b", text)
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            pass
    return None


def _parse_number(raw: str | None) -> float | None:
    if raw is None:
        return None
    try:
        value = float(raw.replace(" ", "").replace(",", "."))
    except ValueError:
        return None
    return value if 1 <= value <= 5000 else None


def _fetch_html(session, url: str) -> str | None:
    try:
        resp = session.get(url, timeout=45)
    except Exception:
        logger.exception("[mepm_sn] request failed: %s", url)
        return None
    if resp.status_code != 200:
        return None
    return resp.text


def _discover_pages(session) -> dict[str, date | None]:
    pages: dict[str, date | None] = {}
    for url in _INDEX_URLS:
        html = _fetch_html(session, url)
        if not html:
            continue
        text = BeautifulSoup(html, "lxml").get_text(" ", strip=True)
        if _FUEL_LINK_RE.search(text):
            pages[url] = _parse_date(text)
        soup = BeautifulSoup(html, "lxml")
        for anchor in soup.find_all("a", href=True):
            label = " ".join(anchor.stripped_strings)
            href = urljoin(url, anchor["href"])
            if not href.startswith(_BASE_URL):
                continue
            if _FUEL_LINK_RE.search(f"{label} {href}"):
                pages[href] = _parse_date(label)
    return pages


def _extract_prices(text: str) -> dict[str, float]:
    prices: dict[str, float] = {}
    flat = re.sub(r"\s+", " ", text)
    pass_match = re.search(
        r"(supercarburant|super\s+carburant)[^.]{0,80}?passe\s+de\s+"
        r"([0-9 ]+)\s*(?:à|a)\s*([0-9 ]+)\s*F",
        flat,
        re.I,
    )
    if pass_match:
        price = _parse_number(pass_match.group(3))
        if price is not None:
            prices["Super"] = price
    for product, pattern in _PRODUCT_PATTERNS:
        if product in prices:
            continue
        match = pattern.search(flat)
        if not match:
            continue
        window = flat[match.start() : match.start() + 180]
        value_match = re.search(r"(?:à|a|prix\s+de)\s+([0-9 ]{2,5})\s*F", window, re.I)
        if not value_match:
            continue
        price = _parse_number(value_match.group(1))
        if price is not None:
            prices[product] = price
    return prices


def fetch_mepm_sn(cutoff: date) -> pd.DataFrame | None:
    session = make_session()
    rows: list[dict] = []
    for url, link_date in _discover_pages(session).items():
        time.sleep(_THROTTLE_S)
        html = _fetch_html(session, url)
        if not html:
            continue
        text = BeautifulSoup(html, "lxml").get_text("\n", strip=True)
        prices = _extract_prices(text)
        if not prices:
            continue
        obs_date = _parse_date(text) or link_date
        if obs_date is None or obs_date <= cutoff:
            continue
        for product, price in prices.items():
            rows.append(
                {
                    "observation_date": obs_date.isoformat(),
                    "country": _COUNTRY,
                    "fuel_product": product,
                    "price_local": price,
                    "currency": _CURRENCY,
                    "unit": "L",
                    "source_key": _SOURCE_KEY,
                }
            )

    if not rows:
        logger.info("[mepm_sn] no rows after cutoff %s", cutoff)
        return None
    return (
        pd.DataFrame(rows)
        .drop_duplicates(subset=["observation_date", "fuel_product"], keep="last")
        .sort_values(["observation_date", "fuel_product"])
        .reset_index(drop=True)
    )


__all__ = ["fetch_mepm_sn"]
