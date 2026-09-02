"""VNSO Port Vila Market Survey -- quarterly weighted average retail prices.

VNSO publishes a quarterly "Market Survey" of fresh produce sold at Port
Vila's central market. The landing page links a "Download Tables" .xlsx per
quarter; this fetcher always reads the CURRENT (latest) workbook linked at
the top of the page rather than walking the full archive of past quarters.

The workbook's "Tab 1-2" sheet stacks two tables in one column block:
Table 1 (Quantity Supplied, kg) then Table 2 ("Weighted Average Price Per
Kilograms (in Vatu)"). Table 2 is used directly -- it is already VNSO's own
per-kg retail price, not something this fetcher has to derive from
value/quantity. Prices are whole Vatu, consistent with VUV having no minor
unit (unlike the URA tariff RATES, which the regulator itself publishes to
2dp).

Table 2 mixes category subtotal rows (ALL-CAPS: "STAPLE PRODUCE", "FRUITS",
"VEGETABLE PRODUCE") with individual item rows (Title Case) -- subtotal rows
are skipped via an is-upper heuristic so they don't get force-mapped through
_COICOP_MAP as if they were a real commodity.

`coicop_classification: source_curated` -- the item list is small (~23
commodities) and stable across the quarterly cadence, matching the
onboarding skill's "narrow, stable list -> source_curated" recommendation
(cf. SingStat ARP in fetcher_pattern.md). A couple of the 23 mappings are
judgment calls, flagged inline: "Island Cabbage" is a Pacific leafy-green
(not true cabbage) mapped to the generic leafy-vegetable leaf; "Dried
coconut" / "Green coconut" are both mapped to the single COICOP fresh-
coconut leaf (no separate leaf exists for nut maturity).

vnso.gov.vu shares the same TLS quirk as vnso_cpi.py -- `verify=False`.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date

import pandas as pd
import urllib3
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_LANDING_URL = (
    "https://vnso.gov.vu/index.php/en/statistics/economic-statistics/" "market-survey"
)
_COUNTRY = "Vanuatu"
_CURRENCY = "VUV"
_SOURCE_KEY = "vu_vnso_market_survey"
_SHEET = "Tab 1-2"
_UNIT = "kg"
_IDENT = ["source_key", "observation_date", "item_name"]

# "MAR.25.AV" / "JUN.25.AV" / "SEP.25.AV" / "DEC.25..AV" (note the source's
# own double-dot typo on the December column) / "MAR.26.AV" -- quarter label
# is the calendar month the quarter ENDS in.
_QUARTER_COL_RE = re.compile(r"^(MAR|JUN|SEP|DEC)\.(\d{2})\.+AV$", re.IGNORECASE)
_QUARTER_START_MONTH = {"MAR": 1, "JUN": 4, "SEP": 7, "DEC": 10}

# Root crops, fruit, and vegetables sold at Port Vila central market ->
# COICOP-2018 leaves (src/data/prices/enrich/gold/coicop_leaves.txt).
_COICOP_MAP = {
    "Fiji Taro": "01.1.7.5.5",
    "Island Taro": "01.1.7.5.5",
    "Manioc": "01.1.7.5.3",
    "Sweet Potato (Kumala)": "01.1.7.5.2",
    "Yam": "01.1.7.5.4",
    "Banana - green": "01.1.7.5.7",  # cooking banana, not dessert fruit
    "Dried coconut": "01.1.6.1.8",  # mature nut -- same leaf as green coconut
    "Banana, Ripe": "01.1.6.1.2",
    "Pawpaw": "01.1.6.1.6",
    "Water Melon": "01.1.6.5.4",
    "Green coconut": "01.1.6.1.8",
    "Bowl Cabbage (white)": "01.1.7.1.2",
    "Bowl Cabbage (purple)": "01.1.7.1.2",
    "Carrot": "01.1.7.4.1",
    "Chinese Cabbage": "01.1.7.1.2",
    "Cucumber": "01.1.7.2.2",
    "Pumpkin": "01.1.7.2.5",
    "Island Cabbage": "01.1.7.1.9",  # Pacific leafy green, not true cabbage
    "Lettuce": "01.1.7.1.4",
    "Tomato": "01.1.7.2.4",
}


def _find_download_url(html: str) -> str | None:
    soup = BeautifulSoup(html, "lxml")
    for a in soup.find_all("a"):
        text = a.get_text(strip=True).lower()
        href = a.get("href", "")
        if "download tables" in text and href.lower().endswith(".xlsx"):
            return href
    return None


def _read_table2(xlsx_bytes: bytes) -> pd.DataFrame:
    df = pd.read_excel(io.BytesIO(xlsx_bytes), sheet_name=_SHEET, header=None)
    start = None
    for i, val in enumerate(df[0]):
        if isinstance(val, str) and val.strip().startswith("Table 2"):
            start = i
            break
    if start is None:
        raise LookupError("'Table 2' header not found in sheet")

    header = df.iloc[start + 1]
    body = df.iloc[start + 2 :]
    body = body.copy()
    body.columns = header
    return body


def fetch_vu_vnso_market_survey(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    landing = session.get(_LANDING_URL, timeout=30, verify=False)
    landing.raise_for_status()

    download_url = _find_download_url(landing.text)
    if not download_url:
        logger.warning(
            "[%s] Could not find 'Download Tables' xlsx link on %s",
            _SOURCE_KEY,
            _LANDING_URL,
        )
        return None
    if download_url.startswith("/"):
        download_url = "https://vnso.gov.vu" + download_url

    xlsx_resp = session.get(download_url, timeout=60, verify=False)
    xlsx_resp.raise_for_status()

    table2 = _read_table2(xlsx_resp.content)

    quarter_cols: list[tuple[str, date]] = []
    for col in table2.columns:
        if not isinstance(col, str):
            continue
        m = _QUARTER_COL_RE.match(col.strip())
        if not m:
            continue
        month_abbr, yy = m.group(1).upper(), int(m.group(2))
        year = 2000 + yy
        obs_date = date(year, _QUARTER_START_MONTH[month_abbr], 1)
        quarter_cols.append((col, obs_date))

    if not quarter_cols:
        logger.warning("[%s] No quarterly columns recognized in Table 2", _SOURCE_KEY)
        return None

    rows = []
    produce_col = table2.columns[0]
    for _, r in table2.iterrows():
        item = r[produce_col]
        if not isinstance(item, str):
            continue
        item = item.strip()
        if not item or item.isupper():
            continue  # category subtotal row (STAPLE PRODUCE / FRUITS / ...)

        coicop = _COICOP_MAP.get(item)
        if not coicop:
            logger.warning(
                "[%s] No COICOP mapping for produce item %r -- dropping row",
                _SOURCE_KEY,
                item,
            )
            continue

        for col, obs_date in quarter_cols:
            if obs_date <= cutoff:
                continue
            raw = r[col]
            try:
                price_local = float(raw)
            except (TypeError, ValueError):
                continue
            if price_local <= 0:
                continue  # 0 = no sales recorded that quarter, not a real price

            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "quarterly_avg",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "item_name": item,
                "price_local": price_local,
                "currency": _CURRENCY,
                "unit": _UNIT,
                "coicop_code": coicop,
                "source_url": _LANDING_URL,
                "notes": "Port Vila central market, VNSO weighted average retail price",
                "scrape_ts": get_scrape_ts(),
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

    return pd.DataFrame(rows) if rows else None
