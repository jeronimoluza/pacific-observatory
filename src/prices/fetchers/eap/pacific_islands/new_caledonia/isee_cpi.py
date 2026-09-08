"""Institut de la Statistique et des Études Économiques (ISEE) — New Caledonia CPI.

Monthly COICOP-2018-coded detailed consumer price index, published as an XLS
download linked from ISEE's rolling '/indices' landing page (the file itself
lives at a month-dated path like
'/sites/default/files/2026-08/indiceprix-mois.xls', which changes every
month -- the fetcher re-resolves the link from the landing page each run
rather than hardcoding a URL that would go stale next month).

The 'historique indice détaillé' sheet holds one row per COICOP code (e.g.
'01', '01.1', '01.1.1', ...) with monthly index values in wide format,
base 100 = December 2021. Row index 6 carries the year, present only in the
first column of each year's 12-column block (December of the first
published year, 2010, is a lone column, hence the block boundaries are
irregular); row index 7 carries the French month abbreviation for every
column, so year is forward-filled and month is read directly per column.

Only the most recent fully-published month is emitted per run -- the
fetcher does not backfill the full history, matching the "snapshot current
value" pattern used elsewhere for slow-cadence official sources. The
division-01 row is used to find the latest populated column since not every
row necessarily lags by the same amount as the file rolls over.

Verified live 2026-09-06: 158 COICOP-coded rows for 2026-07 (division 01
through fine-grained leaves). The 'Indice général' / 'Indice hors tabac' /
'Indice hors tabac hors loyer' aggregate rows are dropped -- no sanctioned
all-items sentinel exists yet in this pipeline (same call as BPS Indonesia /
SingStat / GCC-Stat CPI fetchers).
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_INDICES_URL = "https://isee.nc/indices"
_COUNTRY = "New Caledonia"
_SOURCE_KEY = "nc_isee_cpi"
_BASE_PERIOD = "2021-12=100"
_SHEET = "historique indice détaillé"

_MONTH_MAP = {
    "janv.": 1,
    "fév.": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juil.": 7,
    "août": 8,
    "sept.": 9,
    "oct.": 10,
    "nov.": 11,
    "déc.": 12,
}

_CODE_RE = re.compile(r"^\d{2}(\.\d+)*$")

_IDENT = ["source_key", "observation_date", "coicop_code"]


def _resolve_xls_url(session) -> str | None:
    resp = session.get(_INDICES_URL, timeout=30)
    resp.raise_for_status()
    m = re.search(r'(/sites/default/files/[^"]*indiceprix-mois\.xls)', resp.text)
    if not m:
        return None
    return "https://isee.nc" + m.group(1)


def fetch_nc_isee_cpi(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    xls_url = _resolve_xls_url(session)
    if not xls_url:
        logger.warning("[%s] Could not resolve current indiceprix-mois.xls link", _SOURCE_KEY)
        return None

    resp = session.get(xls_url, timeout=60)
    resp.raise_for_status()
    df = pd.read_excel(io.BytesIO(resp.content), sheet_name=_SHEET, header=None)

    year_row = df.iloc[6].ffill()
    month_row = df.iloc[7]

    col_dates: dict[int, date] = {}
    for col in range(2, df.shape[1]):
        month_label = str(month_row[col]).strip().lower()
        month_num = _MONTH_MAP.get(month_label)
        year = year_row[col]
        if month_num is None or pd.isna(year):
            continue
        col_dates[col] = date(int(year), month_num, 1)

    if not col_dates:
        logger.warning("[%s] Could not parse any date columns", _SOURCE_KEY)
        return None

    code_col, label_col = 0, 1
    div01_row = None
    for i in range(8, df.shape[0]):
        if str(df.iat[i, code_col]).strip() == "01":
            div01_row = i
            break
    if div01_row is None:
        logger.warning("[%s] Could not locate division-01 reference row", _SOURCE_KEY)
        return None

    latest_col = max(
        (c for c in col_dates if pd.notna(df.iat[div01_row, c])),
        default=None,
    )
    if latest_col is None:
        return None
    obs_date = col_dates[latest_col]
    if obs_date <= cutoff:
        logger.info("[%s] No new data since cutoff %s", _SOURCE_KEY, cutoff)
        return None

    rows = []
    for i in range(8, df.shape[0]):
        code = str(df.iat[i, code_col]).strip()
        if not _CODE_RE.match(code):
            continue  # skips blank rows, aggregate headline rows, footnotes
        value = df.iat[i, latest_col]
        if pd.isna(value):
            continue
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "monthly_avg",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": code,
            "index_value": float(value),
            "index_base_period": _BASE_PERIOD,
            "source_url": xls_url,
            "notes": str(df.iat[i, label_col]).strip(),
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    return pd.DataFrame(rows) if rows else None
