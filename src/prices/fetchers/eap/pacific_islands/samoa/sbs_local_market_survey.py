"""Samoa Bureau of Statistics (sbs.gov.ws) — Local Market Survey, monthly.

SBS publishes a monthly "Local Market Survey" release (sbs.gov.ws/local-market-survey/)
covering fresh produce sold at Samoa's local (fa'amarova) markets — items supermarkets
structurally don't carry (root crops, breadfruit, leafy greens). Each release is a
paired PDF + XLSX under /documents/economics/Local_Market_Survey/<year>/ (older
releases used other path/casing variants — /digi/, /images/sbs-documents/...,
/images/.../local-market-survey/<year>/ — ignored here in favour of the current
"documents/economics/Local_Market_Survey" path, which alone covers 2023-present).

Verified live 2026-08-11: the June 2026 XLSX has TWO sheets, each holding three
stacked tables (title row, blank row, header row, then item rows to the next
title):

  Sheet "Table 1 2 3":
    Table 1  Quantity Supplied (kg)
    Table 2  Weighted Average Price Per Kilogram (in Tala)   <- this fetcher
    Table 3  Value of Supplies (Tala thousands)
  Sheet "Table 4 5 6":
    Table 4  Volume Index (2014=100)
    Table 5  Price Index (2014=100)
    Table 6  Number of Sellers

Only Table 2 is pulled (item-level price, analytical_role: official_avg -> a
PriceObservation). Tables 1/3/4/5/6 are index/volume/seller-count series, out of
scope for this pass — noted here so a future session doesn't re-discover the
sheet layout from scratch.

Each release's Table 2 header row is NOT a clean cumulative series — verified by
inspecting the actual column list, not assumed from the Tuvalu/Tunisia pattern.
The June 2026 file's columns run JAN93.AV..DEC07.AV monthly, then jump straight
to three annual-snapshot columns ("2008 AVE", "2010 AVE", "2014 AVE" — 2009,
2011-2013, 2015-2024 are simply absent, not blank), then resume as a rolling
~13-month monthly window ending at the release month (JUN.25.AV..JUN.26.AV in
this file). So there is a real, undocumented ~17-year gap (2008-mid 2025) in
the source's own machine-readable release that this fetcher does not attempt to
backfill — the older per-month PDF/XLSX links on the survey page use different
path conventions (/digi/, /images/sbs-documents/..., and a
/images/.../local-market-survey/<year>/ path for 2020-2022) and inconsistent
sheet layouts across years; stitching those into one series is future work, not
done this round (see the onboarding report). What IS reliable: as long as the
rolling window holds, downloading only the single latest release each run
naturally accumulates the post-2025 monthly history over time via the
`cutoff`-gated append, without re-fetching every monthly link — the same
economy-of-effort as the Tuvalu CPI / Tunisia INS CPI fetchers, just without
their "fully cumulative" guarantee. Column headers are monthly averages named
"<MON><YY>.AV" (older, e.g. "JAN93.AV") or "<MON>.<YY>.AV" (recent, e.g.
"JUN.26.AV"); non-month summary columns ("1996 AVE", "2008 AVE",
"% chng from prev mnth", "12 over 12 months") are excluded by the
month-column regex, not by position.

Item -> COICOP-2018 leaf mapping (looked up against the repo's own
coicop_categories.xlsx, not guessed): the survey's 12 items are Samoan root-crop
and vegetable staples, matched to their nearest leaf. Two are judgment calls,
recorded here:
  - BANANA -> 01.1.7.5.7 "Plantains and cooking bananas" (not 01.1.6.1.2 fresh
    dessert banana) because it's grouped with taro/ta'amu/yam/coconut as a
    supply-quantity staple crop, not with a fruit-stand assortment.
  - TARO PALAGI -> 01.1.7.5.6 "Yautia" — Samoa's "taro palagi" is Xanthosoma
    sagittifolium (tannia), COICOP's own name for that species.
  - TA'AMU (giant taro, Alocasia) has no dedicated leaf -> 01.1.7.5.9 "Other
    tubers".
  - BREADFRUIT has no dedicated leaf in either the fruit (01.1.6) or vegetable
    (01.1.7) trees -> 01.1.6.5.9 "Other fruits ... n.e.c." (closest fresh-fruit
    catch-all).
  - CH.CABBAGE (Chinese cabbage) shares 01.1.7.1.2 "Cabbages" with HEAD
    CABBAGE — COICOP has no separate Chinese-cabbage leaf; item_name is kept
    distinct so the two rows don't collide.

Emits PriceObservation rows (analytical_role: official_avg).
coicop_classification: source_curated (12 stable items, static map below).
Currency: WST (Tala) — the sheet header states "(in Tala)" explicitly, matches
countries.yaml.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Samoa"
_CURRENCY = "WST"
_SOURCE_KEY = "ws_sbs_local_market"
_UNIT = "kg"
_IDENT = ["source_key", "observation_date", "item_name"]
_SURVEY_URL = "https://www.sbs.gov.ws/local-market-survey/"
_XLSX_HREF_RE = re.compile(
    r'href="(https://www\.sbs\.gov\.ws/documents/economics/Local_Market_Survey/(\d{4})/[^"]*\.xlsx)"',
    re.IGNORECASE,
)
_MONTH_COL_RE = re.compile(
    r"^(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\.?(\d{2})\.AV$", re.IGNORECASE
)
_MONTHS = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}

_COICOP_MAP = {
    "TARO": "01.1.7.5.5",
    "BANANA": "01.1.7.5.7",
    "TARO PALAGI": "01.1.7.5.6",
    "TA'AMU": "01.1.7.5.9",
    "COCONUT": "01.1.6.1.8",
    "BREADFRUIT": "01.1.6.5.9",
    "YAM": "01.1.7.5.4",
    "HEAD CABBAGE": "01.1.7.1.2",
    "TOMATOES": "01.1.7.2.4",
    "CH.CABBAGE": "01.1.7.1.2",
    "CUCUMBER": "01.1.7.2.2",
    "PUMPKIN": "01.1.7.2.5",
}


def _month_date(label: object) -> date | None:
    if not isinstance(label, str):
        return None
    m = _MONTH_COL_RE.match(label.strip())
    if not m:
        return None
    mon, yy = m.group(1).upper(), int(m.group(2))
    year = 1900 + yy if yy >= 90 else 2000 + yy
    return date(year, _MONTHS[mon], 1)


def _find_latest_xlsx_url(session) -> str | None:
    try:
        resp = session.get(_SURVEY_URL, timeout=30)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] survey page fetch failed: %s", _SOURCE_KEY, exc)
        return None
    matches = _XLSX_HREF_RE.findall(resp.text)
    if not matches:
        return None

    def _month_key(item: tuple[str, str]) -> tuple[int, int]:
        url, year = item
        base = url.rsplit("/", 1)[-1]
        m = re.match(r"0?(\d{1,2})[-_.]", base)
        month = int(m.group(1)) if m else 0
        return (int(year), month)

    best = max(matches, key=_month_key)
    return best[0]


def _rows_from_xlsx(xlsx_bytes: bytes, url: str, cutoff: date) -> list[dict]:
    df = pd.read_excel(io.BytesIO(xlsx_bytes), sheet_name="Table 1 2 3", header=None)
    col1 = df.iloc[:, 1].astype(str)
    table2_rows = col1[col1.str.contains("Table 2", na=False)].index
    table3_rows = col1[col1.str.contains("Table 3", na=False)].index
    if len(table2_rows) == 0 or len(table3_rows) == 0:
        logger.warning("[%s] could not locate Table 2/Table 3 markers", _SOURCE_KEY)
        return []
    title_row = table2_rows[0]
    end_row = table3_rows[0]
    header_row = title_row + 2

    header = df.iloc[header_row].tolist()
    date_cols = [
        (i, d) for i, h in enumerate(header) if (d := _month_date(h)) is not None
    ]
    if not date_cols:
        return []

    ts_scrape = get_scrape_ts()
    out: list[dict] = []
    for row_idx in range(header_row + 1, end_row):
        raw_label = df.iloc[row_idx, 1]
        if pd.isna(raw_label):
            continue
        label = str(raw_label).strip()
        coicop = _COICOP_MAP.get(label)
        if coicop is None:
            logger.warning(
                "[%s] no COICOP mapping for %r — dropping row", _SOURCE_KEY, label
            )
            continue
        for col_idx, obs_date in date_cols:
            if obs_date <= cutoff:
                continue
            val = df.iloc[row_idx, col_idx]
            try:
                price = float(val)
            except (TypeError, ValueError):
                continue
            if price <= 0:
                continue
            r = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "monthly_avg",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "item_name": label,
                "price_local": round(price, 4),
                "currency": _CURRENCY,
                "unit": _UNIT,
                "coicop_code": coicop,
                "source_url": url,
                "notes": "SBS Local Market Survey, weighted average price per kg",
                "scrape_ts": ts_scrape,
                "observation_hash": None,
            }
            r["observation_hash"] = make_hash(r, _IDENT)
            out.append(r)
    return out


def fetch_ws_sbs_local_market(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120 Safari/537.36"
        }
    )
    xlsx_url = _find_latest_xlsx_url(session)
    if not xlsx_url:
        logger.warning("[%s] no Local Market Survey xlsx link found", _SOURCE_KEY)
        return None
    try:
        resp = session.get(xlsx_url, timeout=60)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] xlsx fetch failed: %s", _SOURCE_KEY, exc)
        return None
    rows = _rows_from_xlsx(resp.content, xlsx_url, cutoff)
    logger.info("[%s] %d rows (cutoff=%s)", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows) if rows else None
