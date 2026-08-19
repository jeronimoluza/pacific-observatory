"""Lebanon Monthly Price Monitor — Ministry of Economy and Trade x WFP.

A joint MoET/WFP market-price-information project: ~75 essential food and
non-food items priced weekly across ~800 shops in Lebanon's 8 governorates,
published as a monthly PDF bulletin ("Lebanon Monthly Price Monitor") whose
Annex table carries Max/Avg/Min price plus one column per governorate
(Akkar, Baalbek-El Hermel, Beirut, Bekaa, El Nabatieh, Mount Lebanon, North,
South) for every item. This is the statutory-adjacent essential-goods price
feed the round-3 brief flagged for Lebanon; the ministry's older "Info Price
— Top Ten Supermarkets" and "Consumer Basket — Monthly" pages on the same
site are abandoned (last PDFs 2020), so this is the live one.

economy.gov.lb sits behind a Cloudflare JS challenge — plain `requests`
gets a "Just a moment..." 403. Verified live 2026-08-07 with a real
Playwright/Chromium session (which clears it) AND with curl_cffi
`impersonate="chrome120"` (also clears it, no headless browser needed at
collection time — the TLS fingerprint mismatch is what trips the challenge
for plain requests/urllib, not a JS check). This fetcher uses curl_cffi
directly for that reason.

Listing page (.../lebanon-monthly-price-monitor) links PDFs back to
July 2024; latest posted at probe time was April 2025 (~16 months stale
vs. today) — the ministry's cadence has visibly slowed but the page itself
is live and not lying about dates (unlike the CKAN staleness trap: no
metadata claims freshness the content doesn't have). Sample from the April
2025 Annex: 'Egyptian Rice' 900g, Beirut avg $1.02; 'Chicken Breast' 1000g,
North avg $9.38. Prices are in USD, not LBP — Lebanon's retail sector
re-dollarized after the 2019-22 currency crisis and the bulletin itself
prices everything in "$"; per the "site's own currency code wins over
countries.yaml" rule this fetcher emits USD, not LBP.

Table extraction uses pdfplumber's extract_tables() (the raw text layer
interleaves the vertical/rotated "Component" category label character by
character, which does not decode cleanly — the category column is dropped
rather than guessed at; item name + weight + per-governorate prices extract
cleanly and are what matters for the classifier). One row is emitted per
(item, governorate) pair, plus a 9th synthetic "National Average" row from
the Avg. Price column, mirroring the per-city breakdown pattern used by the
Pakistan PBS SPI fetcher.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date

import pandas as pd
import pdfplumber
from curl_cffi import requests as cffi_requests

from prices.fetchers.utils import get_scrape_ts, make_hash

logger = logging.getLogger(__name__)

_LISTING_URL = (
    "https://www.economy.gov.lb/en/services/center-for-pricing-policies/"
    "lebanon-monthly-price-monitor"
)
_COUNTRY = "Lebanon"
_CURRENCY = "USD"
_SOURCE_KEY = "lb_moet_price_monitor"
_IDENT = ["source_key", "observation_date", "item_name", "unit", "notes"]
_IMPERSONATE = "chrome120"

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
_MONTH_YEAR_RE = re.compile(
    r"(january|february|march|april|may|june|july|august|september|october|"
    r"november|december)\s*(\d{4})",
    re.IGNORECASE,
)
_PDF_HREF_RE = re.compile(r'href="([^"]+\.pdf)"', re.IGNORECASE)
_PRICE_RE = re.compile(r"[\d.]+")


def _num(cell) -> float | None:
    if not cell or not isinstance(cell, str):
        return None
    m = _PRICE_RE.search(cell)
    if not m:
        return None
    try:
        v = float(m.group(0))
    except ValueError:
        return None
    return v if v > 0 else None


def _list_bulletins(html: str) -> list[tuple[date, str]]:
    """Parse (bulletin_month, pdf_url) pairs from the listing page HTML."""
    out: list[tuple[date, str]] = []
    for m in re.finditer(
        r'href="([^"]+\.pdf)"[^>]*>([^<]*)</a>|<a[^>]*href="([^"]+\.pdf)"',
        html,
        re.IGNORECASE,
    ):
        href = m.group(1) or m.group(3)
        text = m.group(2) or ""
        my = _MONTH_YEAR_RE.search(text) or _MONTH_YEAR_RE.search(href)
        if not href or not my:
            continue
        month = _MONTHS[my.group(1).lower()]
        year = int(my.group(2))
        url = href if href.startswith("http") else f"https://www.economy.gov.lb{href}"
        out.append((date(year, month, 1), url))
    # de-dup by month, keep first occurrence (page lists most recent first)
    seen: set[date] = set()
    uniq: list[tuple[date, str]] = []
    for d, u in out:
        if d in seen:
            continue
        seen.add(d)
        uniq.append((d, u))
    return uniq


def _rows_from_pdf(pdf_bytes: bytes, obs_date: date, url: str) -> list[dict]:
    ts = get_scrape_ts()
    out: list[dict] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            if not tables:
                continue
            table = tables[0]
            if not table or len(table) < 2:
                continue
            header = [str(h or "").replace("\n", " ").strip() for h in table[0]]
            if "Item" not in header or "Avg" not in " ".join(header):
                continue
            col_item = header.index("Item")
            col_weight = next(
                (i for i, h in enumerate(header) if h.startswith("Weight")), None
            )
            col_avg = next(
                (i for i, h in enumerate(header) if h.startswith("Avg")), None
            )
            gov_cols = [(i, header[i]) for i in range(6, len(header)) if header[i]]
            for row in table[1:]:
                if row is None or len(row) <= col_item:
                    continue
                item = (row[col_item] or "").replace("\n", " ").strip()
                if not item:
                    continue
                unit = (
                    (row[col_weight] or "").replace("\n", " ").strip()
                    if col_weight is not None and col_weight < len(row)
                    else None
                )
                candidates = list(gov_cols)
                if col_avg is not None:
                    candidates = [(col_avg, "National Average")] + candidates
                for col, gov in candidates:
                    if col >= len(row):
                        continue
                    price = _num(row[col])
                    if price is None:
                        continue
                    r = {
                        "observation_date": obs_date.isoformat(),
                        "period_kind": "monthly_avg"
                        if gov == "National Average"
                        else "monthly",
                        "country": _COUNTRY,
                        "source_key": _SOURCE_KEY,
                        "item_name": item,
                        "price_local": round(price, 2),
                        "currency": _CURRENCY,
                        "unit": unit or None,
                        "source_url": url,
                        "notes": f"governorate={gov}",
                        "scrape_ts": ts,
                        "observation_hash": None,
                    }
                    r["observation_hash"] = make_hash(r, _IDENT)
                    out.append(r)
    return out


def fetch_lb_moet_price_monitor(cutoff: date) -> pd.DataFrame | None:
    try:
        listing = cffi_requests.get(_LISTING_URL, impersonate=_IMPERSONATE, timeout=30)
        listing.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] listing fetch failed: %s", _SOURCE_KEY, exc)
        return None
    bulletins = [(d, u) for d, u in _list_bulletins(listing.text) if d > cutoff]
    if not bulletins:
        logger.info("[%s] no new bulletins (cutoff=%s)", _SOURCE_KEY, cutoff)
        return None
    all_rows: list[dict] = []
    for obs_date, url in bulletins:
        try:
            resp = cffi_requests.get(url, impersonate=_IMPERSONATE, timeout=60)
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] pdf fetch failed for %s: %s", _SOURCE_KEY, url, exc)
            continue
        rows = _rows_from_pdf(resp.content, obs_date, url)
        logger.info("[%s] %s -> %d rows", _SOURCE_KEY, obs_date, len(rows))
        all_rows.extend(rows)
    logger.info("[%s] %d total rows (cutoff=%s)", _SOURCE_KEY, len(all_rows), cutoff)
    return pd.DataFrame(all_rows) if all_rows else None
