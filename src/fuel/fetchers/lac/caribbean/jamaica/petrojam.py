"""Jamaica Petrojam weekly ex-refinery fuel price fetcher.

Source: Petrojam Limited (state petroleum refiner).
Listing: https://www.petrojam.com/price/

The /price/ archive page renders a Toolset view paginated by
?wpv_view_count=<token>&wpv_paged=<N>. Each page lists ~20 weekly
observations with columns:

  Date | Gasolene 87 | Gasolene 90 | Auto Diesel | Kerosene |
       | Propane | Butane | HFO | Asphalt | ULSD

Prices are weekly ex-refinery JMD/litre. Petrojam is the sole national
refiner, so retail pump prices track these closely — we treat the
series as state-managed (carry_forward=true). Coverage goes back to
February 2004 (~1,180 weekly observations across 59 pages).

Notes
- The server WAF rejects bare Mozilla UA strings; we send a full
  Safari UA + Accept headers.
- The wpv_view_count token rotates between page loads but every fresh
  request gets a valid one; we read whichever token page 1 returned
  and reuse it across pagination calls.
- Early years (2004-2007) have many empty cells (only Gasolene 90,
  Auto Diesel, Kerosene populated); we emit a row only when the cell
  has a numeric value.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from core.http import make_session

logger = logging.getLogger(__name__)

_LISTING_URL = "https://www.petrojam.com/price/"
_PAGED_URL = "https://www.petrojam.com/price/?wpv_view_count={token}&wpv_paged={page}"
_REQUEST_DELAY_S = 1.0

_COUNTRY = "Jamaica"
_CURRENCY = "JMD"
_SOURCE_KEY = "jm_petrojam_weekly"

# Headers a vanilla curl with a truncated UA can't get past Petrojam's WAF;
# the full Safari UA + Accept-Language gets through.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

_TOKEN_RE = re.compile(r"wpv_view_count=([^&\"']+)")
_PAGED_RE = re.compile(r"wpv_paged=(\d+)")
_DATE_RE = re.compile(r"^([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})$")

_MONTH_NAMES = {
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

# Maps the column index (after the Date column) to a product name. Order
# follows the HTML table header.
_COLUMN_PRODUCTS = [
    "Gasolene 87",
    "Gasolene 90",
    "Auto Diesel",
    "Kerosene",
    "Propane",
    "Butane",
    "HFO",
    "Asphalt",
    "ULSD",
]


def _parse_date(label: str) -> date | None:
    label = label.strip()
    m = _DATE_RE.match(label)
    if not m:
        return None
    month = _MONTH_NAMES.get(m.group(1).lower())
    if month is None:
        return None
    try:
        return date(int(m.group(3)), month, int(m.group(2)))
    except ValueError:
        return None


def _extract_token_and_max_page(html: str) -> tuple[str | None, int]:
    """Read the wpv_view_count token + highest wpv_paged value from page 1."""
    tokens = sorted(set(_TOKEN_RE.findall(html)))
    # Prefer the token that actually appears alongside wpv_paged links.
    token = next(
        (
            t
            for t in tokens
            if f"wpv_view_count={t}&" in html or f"wpv_view_count={t}&#038;" in html
        ),
        None,
    )
    pages = [int(m.group(1)) for m in _PAGED_RE.finditer(html)]
    return token, max(pages) if pages else 1


def _parse_price_table(html: str) -> list[tuple[date, str, float]]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if table is None:
        return []
    rows = table.find_all("tr")
    out: list[tuple[date, str, float]] = []
    for tr in rows[1:]:  # skip header
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) < 2:
            continue
        obs_date = _parse_date(cells[0])
        if obs_date is None:
            continue
        for i, raw in enumerate(cells[1:]):
            if i >= len(_COLUMN_PRODUCTS):
                break
            value = raw.strip()
            if not value:
                continue
            try:
                price = float(value.replace(",", ""))
            except ValueError:
                continue
            if price <= 0:
                continue
            out.append((obs_date, _COLUMN_PRODUCTS[i], price))
    return out


def fetch_jm_petrojam(cutoff: date) -> pd.DataFrame | None:
    """Fetch Jamaica Petrojam weekly ex-refinery prices (JMD/litre)."""
    session = make_session(**_HEADERS)
    try:
        resp = session.get(_LISTING_URL, timeout=45)
        resp.raise_for_status()
    except Exception:
        logger.exception("[jm_petrojam] Failed to fetch listing page")
        return None

    token, max_page = _extract_token_and_max_page(resp.text)
    if token is None:
        logger.warning("[jm_petrojam] No wpv_view_count token found on listing page")
        return None
    logger.info("[jm_petrojam] token=%s max_page=%d", token, max_page)

    seen: set[tuple[str, str]] = set()
    rows: list[dict] = []

    # Page 1 was already fetched.
    pages_html = [(1, resp.text)]
    for page_n in range(2, max_page + 1):
        url = _PAGED_URL.format(token=token, page=page_n)
        try:
            r = session.get(url, timeout=45)
            r.raise_for_status()
        except Exception:
            logger.warning("[jm_petrojam] Page %d fetch failed", page_n)
            time.sleep(_REQUEST_DELAY_S)
            continue
        pages_html.append((page_n, r.text))
        time.sleep(_REQUEST_DELAY_S)

    early_stop = False
    for page_n, html in pages_html:
        triples = _parse_price_table(html)
        added = 0
        for obs_date, product, price in triples:
            if obs_date <= cutoff:
                early_stop = True
                continue
            key = (obs_date.strftime("%Y-%m-%d"), product)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "observation_date": obs_date.strftime("%Y-%m-%d"),
                    "country": _COUNTRY,
                    "fuel_product": product,
                    "price_local": round(price, 4),
                    "currency": _CURRENCY,
                    "source_key": _SOURCE_KEY,
                    "unit": "L",
                }
            )
            added += 1
        logger.info("[jm_petrojam] page %d → %d new rows", page_n, added)
        # If a page's rows are all at-or-before cutoff and we added nothing,
        # remaining pages will be even older — bail out.
        if early_stop and added == 0:
            logger.info("[jm_petrojam] All rows on page %d ≤ cutoff; stopping", page_n)
            break

    if not rows:
        logger.info("[jm_petrojam] No new rows after cutoff %s", cutoff)
        return None

    out = (
        pd.DataFrame(rows)
        .sort_values(["observation_date", "fuel_product"])
        .reset_index(drop=True)
    )
    logger.info("[jm_petrojam] Returning %d rows (cutoff: %s)", len(out), cutoff)
    return out
