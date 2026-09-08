"""ANP (Autoridade Nacional do Petroleo) -- Timor-Leste
"Daily Fuel Price" bulletins, published as one WordPress post per date
range under https://www.anp.tl/category/daily-fuel-price/ (e.g.
"Daily Fuel Price - 16-20 July 2026", "Daily Fuel Price - 15 July 2026").

Confirmed live 2026-09-06. Each post embeds one PDF attachment
("Fuel-Prices-<range>-English.pdf") whose page 1 is a single table:

    No. Municipality Fuel Filling Stations Petrol Diesel
    1   Aileu         Fitun Foun Unipessoal, Lda  $ 1,45  $ 1,60
    ...

parsed with pdfplumber's extract_tables() -- the table extraction is
clean (unlike EWURA's free-text regex approach) because ANP's PDF has
real table borders. Many stations have no price in a given bulletin
(blank Petrol/Diesel cells -- station did not report or was closed
that period); those rows are skipped rather than emitting a zero
price. Prices are USD with a comma decimal separator ("$ 1,45" ->
1.45) -- Timor-Leste's currency is USD (see countries.yaml) despite
the comma, which is a Portuguese-locale decimal mark, not a thousands
separator (values are all sub-$2/L).

The post slug/title carries a date RANGE, not a single day
("16-20-july-2026" or a single day "15-july-2026") -- this is a
periodic bulletin whose price holds for the stated range, so
observation_date = the range's FIRST day and period_kind =
effective_from, matching the convention used by other regulator
cap/schedule fetchers (ewura_fuel_caps.py, za_dmre_fuel.py).

subnational_area = "<Municipality> - <Fuel Filling Station>" (the
per-station identity). This is deliberately in `_IDENT` alongside
source_key/observation_date/item_name: ANP publishes ~85 stations
per bulletin, so omitting the per-station identity would collapse the
whole country into one row per (date, item) and silently drop the
vast majority of rows -- the same class of defect documented in
ewura_fuel_caps.py.
"""

import logging
import re
from datetime import date
from io import BytesIO

import pandas as pd
import pdfplumber
from curl_cffi import requests as curl_requests

from prices.fetchers.utils import get_scrape_ts, make_hash

logger = logging.getLogger(__name__)

_CATEGORY_URL = "https://www.anp.tl/category/daily-fuel-price/"
_SOURCE_URL = "https://www.anp.tl/category/daily-fuel-price/"
_COUNTRY = "Timor-Leste"
_CURRENCY = "USD"
_SOURCE_KEY = "tl_anp_fuel"
_UNIT = "L"
_IDENT = ["source_key", "observation_date", "item_name", "subnational_area"]
_MAX_LISTING_PAGES = 30

_ITEM_COICOP = {
    "Petrol": "07.2.2",
    "Diesel": "07.2.2",
}

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

_POST_LINK_RE = re.compile(
    r'href="(https://www\.anp\.tl/daily-fuel-price-[a-z0-9-]+/)"', re.I
)
_SLUG_DATE_RE = re.compile(
    r"daily-fuel-price-(\d{1,2})(?:-\d{1,2})?-([a-z]+)-(\d{4})", re.I
)
_PDF_LINK_RE = re.compile(
    r'href="(https://www\.anp\.tl/wp-content/uploads/[^"]*\.pdf)"', re.I
)
_PRICE_RE = re.compile(r"\$?\s*([\d]+,\d{2})")


def _parse_slug_date(url: str) -> date | None:
    m = _SLUG_DATE_RE.search(url)
    if not m:
        return None
    day, month_name, year = m.groups()
    month = _MONTHS.get(month_name.lower())
    if month is None:
        return None
    try:
        return date(int(year), month, int(day))
    except ValueError:
        return None


def _list_posts(cutoff: date) -> list[tuple[date, str]]:
    """Walk the category listing pages, newest first, stopping once a
    page's posts are all at/before cutoff (WordPress lists newest-first)."""
    posts: dict[str, date] = {}
    for page_num in range(1, _MAX_LISTING_PAGES + 1):
        url = _CATEGORY_URL if page_num == 1 else f"{_CATEGORY_URL}page/{page_num}/"
        try:
            resp = curl_requests.get(url, impersonate="chrome124", timeout=30)
        except Exception:
            logger.warning("[%s] listing page failed: %s", _SOURCE_KEY, url, exc_info=True)
            break
        if resp.status_code == 404:
            break  # ran off the end of pagination
        if resp.status_code != 200:
            logger.warning("[%s] HTTP %s for %s", _SOURCE_KEY, resp.status_code, url)
            break

        found_new = False
        for m in _POST_LINK_RE.finditer(resp.text):
            post_url = m.group(1)
            post_date = _parse_slug_date(post_url)
            if post_date is None:
                continue
            if post_url not in posts:
                posts[post_url] = post_date
                found_new = True

        if not found_new:
            break
        if all(d <= cutoff for d in posts.values()) and len(posts) > 0:
            break

    return sorted(posts.items(), key=lambda kv: kv[1])


def _parse_price(cell: str | None) -> float | None:
    if not cell:
        return None
    m = _PRICE_RE.search(cell)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return None


def _parse_fuel_table(pdf_bytes: bytes) -> list[tuple[str, str, float | None, float | None]]:
    """Returns (municipality, station, petrol_price, diesel_price) rows."""
    rows: list[tuple[str, str, float | None, float | None]] = []
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for r in table:
                    if not r or len(r) < 5:
                        continue
                    no, municipality, station = r[0], r[1], r[2]
                    if not no or not str(no).strip().isdigit():
                        continue
                    if not municipality or not station:
                        continue
                    petrol = _parse_price(r[3])
                    diesel = _parse_price(r[4])
                    if petrol is None and diesel is None:
                        continue
                    rows.append((municipality.strip(), station.strip(), petrol, diesel))
    return rows


def fetch_tl_anp_fuel(cutoff: date) -> pd.DataFrame | None:
    scrape_ts = get_scrape_ts()
    try:
        posts = _list_posts(cutoff)
    except Exception:
        logger.exception("[%s] failed to list category page", _SOURCE_KEY)
        return None

    all_rows: list[dict] = []
    for post_url, post_date in posts:
        if post_date <= cutoff:
            continue

        try:
            resp = curl_requests.get(post_url, impersonate="chrome124", timeout=30)
        except Exception:
            logger.warning("[%s] request failed for %s", _SOURCE_KEY, post_url, exc_info=True)
            continue
        if resp.status_code != 200:
            logger.warning("[%s] HTTP %s for %s", _SOURCE_KEY, resp.status_code, post_url)
            continue

        pdf_links = _PDF_LINK_RE.findall(resp.text)
        if not pdf_links:
            logger.warning("[%s] no PDF attachment found on %s", _SOURCE_KEY, post_url)
            continue
        # Prefer the English-language version when more than one is attached.
        pdf_url = next((u for u in pdf_links if "english" in u.lower()), pdf_links[0])

        try:
            pdf_resp = curl_requests.get(pdf_url, impersonate="chrome124", timeout=30)
        except Exception:
            logger.warning("[%s] PDF request failed for %s", _SOURCE_KEY, pdf_url, exc_info=True)
            continue
        if pdf_resp.status_code != 200:
            logger.warning("[%s] HTTP %s for PDF %s", _SOURCE_KEY, pdf_resp.status_code, pdf_url)
            continue

        try:
            station_rows = _parse_fuel_table(pdf_resp.content)
        except Exception:
            logger.warning("[%s] unreadable PDF at %s", _SOURCE_KEY, pdf_url, exc_info=True)
            continue

        if not station_rows:
            logger.warning("[%s] no table rows parsed from %s", _SOURCE_KEY, pdf_url)
            continue

        for municipality, station, petrol, diesel in station_rows:
            for item_name, price in (("Petrol", petrol), ("Diesel", diesel)):
                if price is None or price <= 0:
                    continue
                row = {
                    "observation_date": post_date.isoformat(),
                    "period_kind": "effective_from",
                    "country": _COUNTRY,
                    "subnational_area": f"{municipality} - {station}",
                    "source_key": _SOURCE_KEY,
                    "coicop_code": _ITEM_COICOP[item_name],
                    "item_name": item_name,
                    "price_local": price,
                    "currency": _CURRENCY,
                    "unit": _UNIT,
                    "source_url": pdf_url,
                    "notes": "ANP Daily Fuel Price bulletin, per filling station.",
                    "scrape_ts": scrape_ts,
                    "observation_hash": None,
                }
                row["observation_hash"] = make_hash(row, _IDENT)
                all_rows.append(row)

    if not all_rows:
        return None
    df = pd.DataFrame(all_rows)
    # ANP occasionally re-publishes an overlapping date-range bulletin (e.g.
    # "15-17 April" and "15-20 April" both starting 15 Apr with identical
    # per-station prices), and a handful of Dili stations share an identical
    # printed name for distinct branches within one bulletin's own table
    # ("Realistik Fuel Unipessoal, Lda, Sucursal" x3) -- both collapse to the
    # same observation_hash. Keep one row per hash rather than emit exact
    # duplicates.
    df = df.drop_duplicates(subset=["observation_hash"], keep="first")
    return df
