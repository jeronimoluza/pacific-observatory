"""TheFuelPrice.com MENAAP fetcher — 12 countries via factory pattern.

Scraping strategy (2-phase):
  Phase 1: Fetch /F{cc}/en → extract date links (/F{cc}/en/MM-DD-YYYY)
  Phase 2: For each date > cutoff → fetch page → parse HTML price table
"""

import logging
import re
import time
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from core.http import make_session

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.thefuelprice.com"

# Regex for date links: /F{cc}/en/MM-DD-YYYY
_DATE_LINK_RE = re.compile(r"/F([a-z]{2})/en/(\d{2})-(\d{2})-(\d{4})$")

# Product names to exclude (commercial/wholesale)
_EXCLUDE_PATTERNS = {"jet fuel", "bunker", "fuel oil", "asphalt"}

# Per-country metadata: country_code → {name, iso3, currency, default_unit}
_COUNTRIES: dict[str, dict] = {
    "jo": {
        "name": "Jordan",
        "iso3": "JOR",
        "currency": "JOD",
        "source_key": "tfp_jo_monthly",
        "unit": "L",
    },
    "lb": {
        "name": "Lebanon",
        "iso3": "LBN",
        "currency": "LBP",
        "source_key": "tfp_lb_monthly",
        "unit": "gallon",
    },
    "sy": {
        "name": "Syrian Arab Republic",
        "iso3": "SYR",
        "currency": "SYP",
        "source_key": "tfp_sy_monthly",
        "unit": "L",
    },
    "iq": {
        "name": "Iraq",
        "iso3": "IRQ",
        "currency": "IQD",
        "source_key": "tfp_iq_monthly",
        "unit": "L",
    },
    "ps": {
        "name": "West Bank and Gaza",
        "iso3": "PSE",
        "currency": "ILS",
        "source_key": "tfp_ps_monthly",
        "unit": "L",
    },
    "ye": {
        "name": "Yemen, Rep.",
        "iso3": "YEM",
        "currency": "YER",
        "source_key": "tfp_ye_monthly",
        "unit": "L",
        "first_row_only": True,
    },
    "sa": {
        "name": "Saudi Arabia",
        "iso3": "SAU",
        "currency": "SAR",
        "source_key": "tfp_sa_monthly",
        "unit": "L",
    },
    "eg": {
        "name": "Egypt, Arab Rep.",
        "iso3": "EGY",
        "currency": "EGP",
        "source_key": "tfp_eg_monthly",
        "unit": "L",
    },
    "dz": {
        "name": "Algeria",
        "iso3": "DZA",
        "currency": "DZD",
        "source_key": "tfp_dz_monthly",
        "unit": "L",
    },
    "ly": {
        "name": "Libya",
        "iso3": "LBY",
        "currency": "LYD",
        "source_key": "tfp_ly_monthly",
        "unit": "L",
    },
    "ma": {
        "name": "Morocco",
        "iso3": "MAR",
        "currency": "MAD",
        "source_key": "tfp_ma_monthly",
        "unit": "L",
    },
    "tn": {
        "name": "Tunisia",
        "iso3": "TUN",
        "currency": "TND",
        "source_key": "tfp_tn_monthly",
        "unit": "L",
    },
    "kw": {
        "name": "Kuwait",
        "iso3": "KWT",
        "currency": "KWD",
        "source_key": "tfp_kw_monthly",
        "unit": "L",
    },
    "bh": {
        "name": "Bahrain",
        "iso3": "BHR",
        "currency": "BHD",
        "source_key": "tfp_bh_monthly",
        "unit": "L",
    },
    "qa": {
        "name": "Qatar",
        "iso3": "QAT",
        "currency": "QAR",
        "source_key": "tfp_qa_monthly",
        "unit": "L",
    },
}


def _is_excluded(product_name: str) -> bool:
    """Return True if the product is commercial/wholesale (not retail)."""
    lower = product_name.lower()
    return any(pat in lower for pat in _EXCLUDE_PATTERNS)


def _resolve_unit(product_name: str, default_unit: str) -> str:
    """Determine unit from product name — LPG is per cylinder."""
    if "l.p.g" in product_name.lower() or "lpg" in product_name.lower():
        return "cylinder"
    return default_unit


def _parse_price(text: str) -> float | None:
    """Parse a price string like '0.910' or '1,359,000' to float."""
    cleaned = text.strip().replace(",", "")
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


# ── Phase 1: Date link discovery ─────────────────────────────────────────────


def _discover_date_links(session, cc: str, cutoff: date) -> list[date]:
    """Fetch the country page and extract all date links newer than cutoff."""
    url = f"{_BASE_URL}/F{cc}/en"
    resp = session.get(url)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")
    dates: list[date] = []

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        match = _DATE_LINK_RE.search(href)
        if not match:
            continue
        cc_found = match.group(1)
        if cc_found != cc:
            continue
        month, day, year = int(match.group(2)), int(match.group(3)), int(match.group(4))
        try:
            d = date(year, month, day)
        except ValueError:
            continue
        if d > cutoff:
            dates.append(d)

    dates.sort()
    logger.info("[%s] Found %d date links after cutoff %s", cc, len(dates), cutoff)
    return dates


# ── Phase 2: Per-date page scraping ──────────────────────────────────────────


def _scrape_date_page(session, cc: str, obs_date: date, meta: dict) -> list[dict]:
    """Fetch a single date page and extract the price table rows."""
    url = f"{_BASE_URL}/F{cc}/en/{obs_date.strftime('%m-%d-%Y')}"
    resp = session.get(url)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")
    rows_out: list[dict] = []
    seen_products: set[str] = set()
    first_row_only = meta.get("first_row_only", False)
    default_unit = meta["unit"]

    for table in soup.find_all("table"):
        tds = table.find_all("td")
        if len(tds) < 2:
            continue

        # Look for rows with product name + price pattern
        # Tables on thefuelprice.com have product name in one cell, price in next
        i = 0
        while i < len(tds) - 1:
            cell_text = tds[i].get_text(strip=True)
            price_text = tds[i + 1].get_text(strip=True)

            price = _parse_price(price_text)
            if price is None or not cell_text or price <= 0:
                i += 1
                continue

            product_name = cell_text
            if _is_excluded(product_name):
                i += 2
                continue

            # Yemen dedup: skip if we've already seen this product name
            if first_row_only and product_name in seen_products:
                i += 2
                continue
            seen_products.add(product_name)

            unit = _resolve_unit(product_name, default_unit)

            rows_out.append(
                {
                    "observation_date": obs_date.strftime("%Y-%m-%d"),
                    "country": meta["name"],
                    "fuel_product": product_name,
                    "price_local": price,
                    "currency": meta["currency"],
                    "source_key": meta["source_key"],
                    "unit": unit,
                }
            )
            i += 2

    return rows_out


# ── Main scraper ─────────────────────────────────────────────────────────────


def _scrape_tfp(cc: str, meta: dict, cutoff: date) -> pd.DataFrame | None:
    """Scrape thefuelprice.com for a single country."""
    session = make_session()

    # Phase 1: discover date links
    new_dates = _discover_date_links(session, cc, cutoff)
    if not new_dates:
        logger.info("[%s] No new dates since %s", cc, cutoff)
        return None

    # Phase 2: scrape each date page
    all_rows: list[dict] = []
    for i, obs_date in enumerate(new_dates):
        if i > 0:
            time.sleep(1)  # polite throttle
        try:
            rows = _scrape_date_page(session, cc, obs_date, meta)
            all_rows.extend(rows)
            logger.info("[%s] %s: %d products", cc, obs_date, len(rows))
        except Exception:
            logger.exception("[%s] Failed to scrape %s", cc, obs_date)
            continue

    if not all_rows:
        return None

    return pd.DataFrame(all_rows)


# ── Factory ──────────────────────────────────────────────────────────────────


def _make_fetcher(cc: str):
    """Create a fetch_tfp_{cc}(cutoff) function for a given country code."""
    meta = _COUNTRIES[cc]

    def _fetch(cutoff: date) -> pd.DataFrame | None:
        return _scrape_tfp(cc, meta, cutoff)

    _fetch.__name__ = f"fetch_tfp_{cc}"
    _fetch.__doc__ = f"Fetch fuel prices for {meta['name']} from thefuelprice.com."
    return _fetch


fetch_tfp_jo = _make_fetcher("jo")
fetch_tfp_lb = _make_fetcher("lb")
fetch_tfp_sy = _make_fetcher("sy")
fetch_tfp_iq = _make_fetcher("iq")
fetch_tfp_ps = _make_fetcher("ps")
fetch_tfp_ye = _make_fetcher("ye")
fetch_tfp_sa = _make_fetcher("sa")
fetch_tfp_eg = _make_fetcher("eg")
fetch_tfp_dz = _make_fetcher("dz")
fetch_tfp_ly = _make_fetcher("ly")
fetch_tfp_ma = _make_fetcher("ma")
fetch_tfp_tn = _make_fetcher("tn")
fetch_tfp_kw = _make_fetcher("kw")
fetch_tfp_bh = _make_fetcher("bh")
fetch_tfp_qa = _make_fetcher("qa")
