"""Liberia Ministry of Commerce and Industry (MOCI) — "Commerce Today:
Monthly Critical Commodities Bulletin" retail/wholesale price PDF.

MOCI publishes a monthly bulletin PDF covering a handful of "critical
commodities" (rice, vegetable oil, sardine/mackerel fish, flour, onion,
eggs, sausage, chicken feet, plus non-food construction materials and
fuel that are out of scope here per the food/beverage-only onboarding
pass). There is no single stable archive URL: the site's own
"publications/document-type" listing only carries 2 (old, 2024) editions,
and the most recent edition is instead linked from a "press releases"
node whose URL slug carries the volume/edition number
(".../commerce-today-monthly-critical-commodities-bulletin-volume-N-
edition-M"). This fetcher combines both discovery paths:

1. The document-type listing page (whatever historical PDFs it has).
2. The MOCI homepage, which links the CURRENT edition's press-release
   page in its "latest" section; that press-release page embeds the
   actual PDF URL.

The bulletin's own table layout is NOT stable across editions -- 3
editions probed (Sept 2024, Oct 2024, Aug 2026) used 3 different column
layouts. Rather than hand-parsing each layout, every table row extracted
by pdfplumber is scanned for a known food/beverage keyword in any cell,
and the row's LAST parseable currency-looking number is taken as the
observed price (this is consistently the "Retail Price" / range-high
column in every layout seen). This is a deliberately loose heuristic
tolerant of layout drift; rows with no parseable keyword or number are
silently skipped, not force-fit.

Bulletin date is parsed from the in-PDF headline text ("VOLUME 3 EDITION
8 ... August 15, 2026" / "September, 15 2024"), not the filename (which
does not carry a date in the older editions).

analytical_role: official_avg (retail commodity price levels, not an
index). coicop_classification: source_curated -- the item list is a
small, hand-curated, stable set of named commodities.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date

import pandas as pd
import pdfplumber
import requests

from prices.fetchers.utils import get_scrape_ts, make_hash

logger = logging.getLogger(__name__)

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_HOMEPAGE_URL = "https://moci.gov.lr"
_LISTING_URL = (
    "https://moci.gov.lr/index.php/publications/document-type/"
    "commerce-today-monthly-critical-commodities-bulletin"
)
_COUNTRY = "Liberia"
_CURRENCY = "USD"
_SOURCE_KEY = "lr_moci_commodities"
_IDENT = ["source_key", "observation_date", "item_name"]

# keyword (matched case-insensitively anywhere in the row's joined text) ->
# (canonical item_name, unit, COICOP-2018 code). Only food/beverage items
# are curated -- cement/steel/zinc/plywood/petroleum rows in the same
# bulletin are out of scope for this onboarding pass and are simply never
# matched.
_COICOP_MAP: dict[str, tuple[str, str, str]] = {
    "rice": ("Rice, 25kg bag", "25kg bag", "01.1.1"),
    "flour": ("Wheat flour, 50lb bag", "50lb bag", "01.1.1"),
    "vegetable\noil": ("Vegetable oil", "L", "01.1.6"),
    "vegetable oil": ("Vegetable oil", "L", "01.1.6"),
    "sardine": ("Sardine, tinned", "carton", "01.1.3"),
    "mackerel": ("Mackerel fish, frozen", "20kg carton", "01.1.3"),
    "chicken feet": ("Chicken feet, frozen", "10kg carton", "01.1.2"),
    "sausage": ("Sausage", "carton", "01.1.2"),
    "eggs": ("Eggs", "carton", "01.1.5"),
    "onion": ("Onion", "bag", "01.1.7"),
}

_NUM_RE = re.compile(r"[\d][\d,]*\.\d{2}")

# e.g. "August 15, 2026", "Septe mber,15 2024" (bulletin headlines have
# stray internal spaces from PDF kerning artifacts -- strip all whitespace
# before matching month names).
_MONTHS = (
    "january|february|march|april|may|june|july|august|"
    "september|october|november|december"
)
# Applied AFTER stripping every whitespace char, since the bulletin
# headline's kerning drops a stray space *inside* month names ("Septe
# mber", "Octob er", "Augus t") -- stripping first turns those back into
# clean month names, at the cost of also gluing "15" to "2024" for
# "...15 2024" -- \d{1,2} is intentionally non-greedy-safe (tries 2 first)
# so it still resolves day vs. a following 4-digit year correctly.
_DATE_RE = re.compile(r"(" + _MONTHS + r")\D*?(\d{1,2})\D*?(\d{4})", re.IGNORECASE)


def _parse_bulletin_date(text: str) -> date | None:
    head = re.sub(r"\s+", "", text[:400])
    m = _DATE_RE.search(head)
    if not m:
        return None
    month_name, day, year = m.groups()
    month_num = {
        "january": 1, "february": 2, "march": 3, "april": 4, "may": 5,
        "june": 6, "july": 7, "august": 8, "september": 9, "october": 10,
        "november": 11, "december": 12,
    }[month_name.lower()]
    try:
        return date(int(year), month_num, 1)
    except ValueError:
        return None


def _discover_pdf_urls(session: requests.Session) -> list[str]:
    urls: set[str] = set()

    resp = session.get(_LISTING_URL, timeout=30)
    if resp.status_code == 200:
        for href in re.findall(r'href="([^"]+\.pdf[^"]*)"', resp.text, re.IGNORECASE):
            urls.add(href if href.startswith("http") else "https://moci.gov.lr" + href)

    resp = session.get(_HOMEPAGE_URL, timeout=30)
    if resp.status_code == 200:
        press_links = set(
            re.findall(
                r'href="(/index\.php/media/press-releases/commerce-today[^"]*)"',
                resp.text,
                re.IGNORECASE,
            )
        )
        for link in press_links:
            try:
                page = session.get("https://moci.gov.lr" + link, timeout=30)
            except requests.RequestException:
                continue
            if page.status_code != 200:
                continue
            for href in re.findall(r'href="([^"]+\.pdf[^"]*)"', page.text, re.IGNORECASE):
                urls.add(href if href.startswith("http") else "https://moci.gov.lr" + href)

    return sorted(urls)


def _extract_rows(pdf_bytes: bytes, pdf_url: str) -> list[dict]:
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        full_text = "\n".join(p.extract_text() or "" for p in pdf.pages)
        bulletin_date = _parse_bulletin_date(full_text)
        if bulletin_date is None:
            logger.warning("[%s] Could not parse bulletin date from %s", _SOURCE_KEY, pdf_url)
            return []

        tables: list[list] = []
        for p in pdf.pages:
            tables.extend(p.extract_tables())

    rows: list[dict] = []
    seen_items: set[str] = set()
    for table in tables:
        for raw_row in table:
            cells = [c for c in raw_row if c]
            if not cells:
                continue
            joined = " ".join(cells).lower()
            match = None
            for kw, (item_name, unit, coicop) in _COICOP_MAP.items():
                if kw in joined:
                    match = (item_name, unit, coicop)
                    break
            if match is None:
                continue
            item_name, unit, coicop = match
            if item_name in seen_items:
                continue  # keep first (highest-priority keyword) match per row set
            nums = []
            for c in cells:
                nums.extend(_NUM_RE.findall(c))
            if not nums:
                continue
            try:
                price = float(nums[-1].replace(",", ""))
            except ValueError:
                continue
            if price <= 0:
                continue
            seen_items.add(item_name)
            rows.append(
                {
                    "observation_date": bulletin_date.isoformat(),
                    "period_kind": "monthly_avg",
                    "country": _COUNTRY,
                    "source_key": _SOURCE_KEY,
                    "item_name": item_name,
                    "price_local": price,
                    "currency": _CURRENCY,
                    "unit": unit,
                    "coicop_code": coicop,
                    "source_url": pdf_url,
                    "scrape_ts": get_scrape_ts(),
                    "observation_hash": None,
                }
            )
    return rows


def fetch_lr_moci_commodities(cutoff: date) -> pd.DataFrame | None:
    session = requests.Session()
    session.headers.update({"User-Agent": _UA})

    pdf_urls = _discover_pdf_urls(session)
    if not pdf_urls:
        logger.warning("[%s] No bulletin PDFs discovered", _SOURCE_KEY)
        return None

    all_rows: list[dict] = []
    for pdf_url in pdf_urls:
        try:
            resp = session.get(pdf_url, timeout=60)
        except requests.RequestException as exc:
            logger.warning("[%s] Fetch failed for %s: %s", _SOURCE_KEY, pdf_url, exc)
            continue
        if resp.status_code != 200:
            continue
        try:
            rows = _extract_rows(resp.content, pdf_url)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] Parse failed for %s: %s", _SOURCE_KEY, pdf_url, exc)
            continue
        all_rows.extend(rows)

    if not all_rows:
        return None

    kept = [r for r in all_rows if date.fromisoformat(r["observation_date"]) > cutoff]
    if not kept:
        return None

    for row in kept:
        row["observation_hash"] = make_hash(row, _IDENT)

    return pd.DataFrame(kept)
