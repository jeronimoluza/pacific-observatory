"""Guyana Ministry of Agriculture -- daily "Prevailing Retail Prices" bulletin.

This is the market-level fresh-produce/meat bulletin the wave-7 brief asked
about by name (Bourda and Stabroek markets): a per-market survey of retail
prices for ~65 non-traditional agricultural commodities (vegetables, root
crops, spices, beans/cereals, fruits, oil crops, meat and eggs), published as
one PDF per release and embedded in a WordPress post via the
"embed-any-document" plugin.

Discovery: the "Daily Market Prices" category listing paginates in the
browser, but the same posts are enumerable in one shot through the WP REST
API (`_LISTING_API`, `search=daily-market-prices`), which also gives a
reliable `link` per post without scraping category pages. 112 posts exist,
spanning 2024-11-29 to 2025-06-26 -- confirmed via `X-WP-TotalPages` and an
ascending-order probe; nothing newer has been published as of 2026-09-01, so
this reads as a DISCONTINUED bulletin rather than a live daily feed. It is
still onboarded because the archive is real, dense, market-level data (up to
11 markets x ~65 items over ~7 months) with no other source at this
granularity.

Each post's `content.rendered` embeds the PDF via a Google Docs viewer
iframe; the same URL is also present as a plain `<a href>` fallback link
("Reload document" / direct-view button), which is what's parsed here
(no iframe-following needed).

Table layout is NOT stable across releases -- two structural gotchas found by
diffing an early (Nov 2024) and late (Jun 2025) release side by side:
  1. Some releases have a leading blank column before the item name; others
     don't. Column offsets are therefore located by searching for the
     "Price Unit" header cell each time, never hardcoded.
  2. The market list itself rotates release-to-release (Bath Settlement and
     Mahaicony appear in 2024, replaced by Mckenzie/Rosehall/New Amsterdam by
     mid-2025) -- market names are read from each release's own header row,
     not from a fixed list.
Missing cells are inconsistently rendered as empty string OR the literal
"N/A"/"NA" depending on release; both are treated as missing.

Only the per-market cells are emitted (`subnational_area` = market name,
e.g. "Bourda", "Stabroek"). The bulletin's own Minimum/Maximum/Average
Market Price columns are derived from the per-market cells and are dropped
to avoid emitting redundant, non-independent rows.

`coicop_classification: classifier` -- items are plain commodity names
(BORA, CABBAGE, BEEF, EGGS (LOCAL WHITE), ...) spanning many distinct
COICOP-01 subclasses (meat, fish is absent, fruit, veg, cereals, eggs), so
this is NOT a narrow single-class source; `coicop_codes` is left unset and
the downstream classifier assigns a leaf per item.

Known quirk, verified 2026-09-01: 2 bulletin dates (2025-01-02, 2025-01-07)
each have TWO published posts. Both are kept (not deduped by this fetcher)
since 37 of the 803 resulting identity collisions carry genuinely different
corrected prices, not exact re-publishes -- silently dropping one risks
dropping the correction rather than the stale draft. `observation_hash`
does not include price, so a downstream stage that dedups on hash alone
will keep only one of the two; this is flagged here rather than resolved,
since neither post is reliably identifiable as "the correction" from its
metadata alone.
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd
import pdfplumber
import requests

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_LISTING_API = "https://agriculture.gov.gy/wp-json/wp/v2/posts"
_COUNTRY = "Guyana"
_SOURCE_KEY = "gy_moa_market_prices"
_CURRENCY = "GYD"
_IDENT = ["source_key", "observation_date", "subnational_area", "item_name", "unit"]

_MON3 = {
    m.lower(): i + 1
    for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())
}
_DATE_RE = re.compile(r"(\d{1,2})-([A-Za-z]{3})-(\d{2})\b")
_MISSING = {"", "N/A", "NA"}


def _list_posts(session: requests.Session) -> list[str]:
    urls: list[str] = []
    page = 1
    while True:
        resp = session.get(
            _LISTING_API,
            params={"search": "daily-market-prices", "per_page": 100, "page": page},
            timeout=30,
        )
        if resp.status_code == 400:  # page beyond X-WP-TotalPages
            break
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        urls.extend(post["link"] for post in batch)
        total_pages = int(resp.headers.get("X-WP-TotalPages", page))
        if page >= total_pages:
            break
        page += 1
    return urls


def _find_pdf_url(session: requests.Session, post_url: str) -> str | None:
    resp = session.get(post_url, timeout=30)
    resp.raise_for_status()
    # A naive first-".pdf"-href match grabs the site nav menu's unrelated
    # "Guyana Agri Investment Prospectus" PDF link, which appears earlier in
    # every page's HTML than the article body. Scope the search to
    # entry-content instead. Two different embed mechanisms are used across
    # the archive (confirmed on 105 vs 7 of 112 posts): most releases use the
    # "embed-any-document" plugin's iframe + fallback link; a minority use
    # the native WordPress "File" block (`wp-block-file`). Both put the real
    # bulletin PDF as the first .pdf link inside entry-content, so anchoring
    # there (rather than on either plugin's specific markup) covers both.
    content_idx = resp.text.find('class="entry-content"')
    if content_idx == -1:
        return None
    m = re.search(r'href="([^"]+\.pdf)"', resp.text[content_idx:])
    return m.group(1) if m else None


def _find_release_date(table: list[list]) -> date | None:
    for row in table[:2]:
        for cell in row:
            if not cell:
                continue
            m = _DATE_RE.search(str(cell))
            if m:
                year = 2000 + int(m.group(3))
                month = _MON3.get(m.group(2).lower())
                if month:
                    return date(year, month, int(m.group(1)))
    return None


def _parse_pdf(content: bytes) -> tuple[date | None, list[tuple[str, str, str, float]]]:
    import io

    with pdfplumber.open(io.BytesIO(content)) as pdf:
        tables = pdf.pages[0].extract_tables()
    if not tables:
        return None, []
    table = tables[0]

    obs_date = _find_release_date(table)

    header_idx = unit_col = None
    for i, row in enumerate(table):
        for c, cell in enumerate(row):
            if cell and "price unit" in str(cell).replace("\n", " ").lower():
                header_idx, unit_col = i, c
                break
        if header_idx is not None:
            break
    if header_idx is None:
        return obs_date, []

    item_col = unit_col - 1
    header_row = table[header_idx]

    min_col = None
    for c in range(unit_col + 1, len(header_row)):
        cell = header_row[c]
        if cell and "minimum" in str(cell).replace("\n", " ").lower():
            min_col = c
            break
    if min_col is None:
        return obs_date, []

    market_cols = list(range(unit_col + 1, min_col))
    market_names = []
    for c in market_cols:
        txt = re.sub(r"\s+", " ", str(header_row[c] or "").replace("\n", " ")).strip()
        txt = re.sub(r"\s*Market$", "", txt, flags=re.IGNORECASE).strip()
        txt = re.sub(r"-\s+", "-", txt)
        market_names.append(txt)

    out = []
    for row in table[header_idx + 1 :]:
        unit_raw = row[unit_col]
        if not unit_raw or "$/" not in str(unit_raw):
            continue  # category-header row or footer row, not an item row
        item_name = str(row[item_col] or "").strip()
        # Casing of the unit suffix is inconsistent release-to-release
        # ("pint" vs "Pint", "Parcel" vs "parcel") -- normalize to lowercase.
        unit = re.sub(r"^G\$/", "", str(unit_raw).strip(), flags=re.IGNORECASE).lower()
        for c, market in zip(market_cols, market_names):
            val_raw = row[c]
            if val_raw is None or str(val_raw).strip().upper() in _MISSING:
                continue
            val_str = re.sub(r"[^0-9.\-]", "", str(val_raw))
            if not val_str:
                continue
            try:
                val = float(val_str)
            except ValueError:
                continue
            out.append((item_name, unit, market, val))
    return obs_date, out


def fetch_gy_moa_market_prices(cutoff: date) -> pd.DataFrame | None:
    session = get_session()

    try:
        post_urls = _list_posts(session)
    except Exception:
        logger.exception(
            "[%s] Failed to list releases via %s", _SOURCE_KEY, _LISTING_API
        )
        return None

    if not post_urls:
        logger.warning("[%s] No daily-market-prices posts found", _SOURCE_KEY)
        return None

    rows = []
    for post_url in post_urls:
        try:
            pdf_url = _find_pdf_url(session, post_url)
        except Exception:
            logger.exception("[%s] Failed to load post %s", _SOURCE_KEY, post_url)
            continue
        if not pdf_url:
            logger.warning("[%s] No PDF link found on %s", _SOURCE_KEY, post_url)
            continue
        try:
            resp = session.get(pdf_url, timeout=60)
            resp.raise_for_status()
            obs_date, parsed = _parse_pdf(resp.content)
        except Exception:
            logger.exception("[%s] Failed to parse %s", _SOURCE_KEY, pdf_url)
            continue
        if obs_date is None:
            logger.warning(
                "[%s] Could not find a release date in %s", _SOURCE_KEY, pdf_url
            )
            continue
        if obs_date <= cutoff:
            continue
        if not parsed:
            logger.warning("[%s] No item rows parsed from %s", _SOURCE_KEY, pdf_url)
            continue
        for item_name, unit, market, price_local in parsed:
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "snapshot",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "item_name": item_name,
                "price_local": price_local,
                "currency": _CURRENCY,
                "unit": unit,
                "subnational_area": market,
                "source_url": pdf_url,
                "scrape_ts": get_scrape_ts(),
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

    return pd.DataFrame(rows) if rows else None
