"""Namibia Statistics Agency (NSA) -- zonal average retail prices, food items.

The same monthly "Namibia CPI <Month> <Year> Excel Tables" workbook used by
nsa_cpi.py also carries a "Zonal average prices for selected food items"
table (~17 items, 3 zones: Zone 1/2/3) -- a genuine official average-RETAIL-
price series (NAD), not a re-derived index. Verified live 2026-09-11 against
the August 2026 release.

SHEET LOOKUP BY CONTENT, NOT NAME: the sheet holding this table is named
"Table 14" in recent (2026) releases, but that name is NOT stable across
eras -- in the March-2023 release, the sheet literally named "Table 14"
holds an unrelated Transport inflation-rate table (NSA added new tables to
the workbook over time without renumbering). This fetcher locates the sheet
by scanning for the header text "Zonal average prices" and returns None
(logged) rather than mis-parsing a renamed sheet if not found. The zonal
food-price table appears to be a relatively recent addition -- it was not
present under this name as of March 2023; `fallback_date` is set
conservatively rather than assumed further back.

SCOPE: two of the ~18 published rows (Petrol, Diesel) are fuel, not food --
out of scope for this onboarding pass (COICOP 01/02 only) and hard-excluded
by item name below, regardless of what the classifier would have done with
them.

DATA-QUALITY GUARD -- cross-zone plausibility check: spot-checking three
non-adjacent releases (Jan-2026 clean, May-2026 corrupted, Aug-2026 clean)
found that in the May-2026 file, the Zone-1/Zone-3 values for two adjacent
item rows ("Tinned pilchards in tomatoes", "Biltong") were swapped between
each other (e.g. Biltong Zone 1 read ~505 NAD, in line with pilchards'
normal magnitude, while pilchards Zone 1 read ~36 NAD, in line with
biltong's) -- a transcription-style defect in NSA's own workbook, not a
parsing artifact (Zone 2 was internally consistent in the same rows). There
is no way to distinguish this from a genuine 13x zonal price gap after the
fact, so any item-month whose three zone values span a max/min ratio above
`_MAX_ZONE_RATIO` is dropped whole (all 3 zones) with a logged warning
rather than risk shipping a corrupted price. This guard cannot catch a
same-magnitude swap (e.g. two similarly-priced items swapped) -- it only
catches the kind of gross magnitude mismatch actually observed.

UNIT LABEL DRIFT: independent of the value-swap defect above, the "UoM"
column has been observed to differ between releases for the same item
even when the underlying values are self-consistent (e.g. "Pure Sunflower
Oil" is labelled "per kg" in Aug-2026 and "750ml" in May-2026; "Rooibos tea
bags" "750ml" vs "100g"). `unit` is emitted as published, per-row, without
attempting to reconcile across releases -- treat it as an approximate,
publisher-supplied label, not independently verified.

coicop_classification: classifier -- the surviving 15 items still span
several COICOP-2018 4-digit classes (cereals, meat, fish, oils, fruit,
veg, non-alcoholic beverages, wine, spirits), too wide for a single
narrow code and not worth a hand-built _COICOP_MAP when the classifier
already handles exactly this shape of free-text grocery item name.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date

import pandas as pd
import openpyxl

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Namibia"
_SOURCE_KEY = "na_nsa_zonal_food_prices"
_CURRENCY = "NAD"
_BASE_URL = "https://nsa.org.na"
_SITEMAP_URL = f"{_BASE_URL}/dlp_document-sitemap.xml"
_IDENT = ["source_key", "observation_date", "item_name", "subnational_area"]

_ZONE_LABELS = {2: "Zone 1", 3: "Zone 2", 4: "Zone 3"}
_EXCLUDED_ITEMS = {"petrol", "diesel"}
_MAX_ZONE_RATIO = 4.0  # max(zone values) / min(zone values) plausibility cap

_DOC_SLUG_RE = re.compile(
    r"<loc>(https://nsa\.org\.na/document/[^<]*cpi[^<]*excel-tables[^<]*)</loc>",
    re.IGNORECASE,
)
_XLSX_HREF_RE = re.compile(r'href="([^"]+\.xlsx)"', re.IGNORECASE)

_MONTH_NUM = {
    m.lower(): i
    for i, m in enumerate(
        [
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        ],
        start=1,
    )
}
_MONTH_ALT = "|".join(_MONTH_NUM.keys())
_SLUG_YEAR_MONTH_RE = re.compile(
    rf"cpi-(\d{{4}})-excel-tables-({_MONTH_ALT})", re.IGNORECASE
)
_SLUG_MONTH_YEAR_RE = re.compile(
    rf"cpi-({_MONTH_ALT})-(\d{{4}})-excel-tables", re.IGNORECASE
)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", str(s)).strip().upper()


def _parse_slug_period(url: str) -> tuple[int, int] | None:
    m = _SLUG_YEAR_MONTH_RE.search(url)
    if m:
        year, month_name = int(m.group(1)), m.group(2).lower()
        return year, _MONTH_NUM[month_name]
    m = _SLUG_MONTH_YEAR_RE.search(url)
    if m:
        month_name, year = m.group(1).lower(), int(m.group(2))
        return year, _MONTH_NUM[month_name]
    return None


def _find_latest_release(session) -> tuple[str, int, int] | None:
    resp = session.get(_SITEMAP_URL, timeout=30)
    resp.raise_for_status()
    candidates = _DOC_SLUG_RE.findall(resp.text)

    best: tuple[int, int, str] | None = None
    for url in candidates:
        period = _parse_slug_period(url)
        if period is None:
            continue
        year, month = period
        if best is None or (year, month) > (best[0], best[1]):
            best = (year, month, url)
    if best is None:
        return None
    year, month, url = best
    return url, year, month


def _find_xlsx_url(doc_page_url: str, session) -> str | None:
    resp = session.get(doc_page_url, timeout=30)
    resp.raise_for_status()
    matches = _XLSX_HREF_RE.findall(resp.text)
    return matches[0] if matches else None


def _find_zonal_sheet(wb) -> str | None:
    for name in wb.sheetnames:
        ws = wb[name]
        for row in ws.iter_rows(min_row=1, max_row=3, values_only=True):
            for cell in row:
                if cell and "ZONAL AVERAGE PRICES" in _norm(cell):
                    return name
    return None


def _parse_zonal_sheet(
    xlsx_bytes: bytes,
) -> tuple[date | None, list[dict]]:
    wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes), data_only=True, read_only=True)
    sheet_name = _find_zonal_sheet(wb)
    if sheet_name is None:
        logger.warning(
            "[%s] No sheet matching 'Zonal average prices' found (sheets=%s)",
            _SOURCE_KEY,
            wb.sheetnames,
        )
        return None, []
    ws = wb[sheet_name]
    rows = list(ws.iter_rows(values_only=True))

    # Row 1 (0-indexed) carries the release month in column 0.
    obs_date = None
    if len(rows) > 1 and rows[1] and hasattr(rows[1][0], "year"):
        d = rows[1][0]
        obs_date = date(d.year, d.month, 1)

    parsed_rows: list[dict] = []
    for row in rows:
        if not row or not row[0]:
            continue
        item_name = str(row[0]).strip()
        if not item_name or item_name.lower().startswith(("item", "table")):
            continue
        if item_name.lower() in _EXCLUDED_ITEMS:
            continue
        unit = str(row[1]).strip() if len(row) > 1 and row[1] else None
        zone_vals: dict[str, float] = {}
        for col_idx, zone_label in _ZONE_LABELS.items():
            if col_idx >= len(row) or row[col_idx] is None:
                continue
            try:
                zone_vals[zone_label] = float(row[col_idx])
            except (TypeError, ValueError):
                continue
        if not zone_vals:
            continue
        parsed_rows.append({"item_name": item_name, "unit": unit, "zones": zone_vals})

    return obs_date, parsed_rows


def _passes_plausibility(zone_vals: dict[str, float]) -> bool:
    vals = [v for v in zone_vals.values() if v > 0]
    if len(vals) < 2:
        return True
    ratio = max(vals) / min(vals)
    return ratio <= _MAX_ZONE_RATIO


def fetch_na_nsa_zonal_food_prices(cutoff: date) -> pd.DataFrame | None:
    session = get_session()

    found = _find_latest_release(session)
    if found is None:
        logger.warning("[%s] No CPI excel-tables document found in sitemap", _SOURCE_KEY)
        return None
    doc_url, year, month = found

    xlsx_url = _find_xlsx_url(doc_url, session)
    if xlsx_url is None:
        logger.warning("[%s] No .xlsx link found on %s", _SOURCE_KEY, doc_url)
        return None

    xlsx_resp = session.get(xlsx_url, timeout=60)
    xlsx_resp.raise_for_status()

    obs_date, items = _parse_zonal_sheet(xlsx_resp.content)
    if obs_date is None or not items:
        logger.warning("[%s] Parsed zero rows from %s", _SOURCE_KEY, xlsx_url)
        return None
    if obs_date <= cutoff:
        return None

    ts = get_scrape_ts()
    out_rows = []
    for item in items:
        if not _passes_plausibility(item["zones"]):
            logger.warning(
                "[%s] Dropping '%s' (%s): implausible cross-zone ratio %s",
                _SOURCE_KEY,
                item["item_name"],
                obs_date,
                item["zones"],
            )
            continue
        for zone_label, price in item["zones"].items():
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "monthly_avg",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "item_name": item["item_name"],
                "price_local": price,
                "currency": _CURRENCY,
                "unit": item["unit"],
                "subnational_area": zone_label,
                "source_url": xlsx_url,
                "notes": f"NSA CPI Excel Tables, document={doc_url}",
                "scrape_ts": ts,
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            out_rows.append(row)

    return pd.DataFrame(out_rows) if out_rows else None
