"""INS-Congo (Institut National de la Statistique, Republic of Congo /
Congo-Brazzaville) -- monthly "Bulletin INHPC" (Indice National Harmonisé
des Prix à la Consommation des ménages, the CEMAC-harmonized CPI).

INS-Congo's own price-statistics page (ins-congo.cg/stat-prix.html) is a
client-rendered widget backed by an undocumented JSON API
(ins-congo.cg/backend/api/...), reverse-engineered from the page's
`assets/js/ins-data-secteur.js`. Two gotchas found live:

- `statistiques/index.php?secteur=stat-prix` (the page's own
  "Indicateurs clés" widget) returns an empty `data: []` -- INS-Congo has
  not populated that indicator table for this sector.
- `publications/list.php?secteur=stat-prix` ALSO returns empty --
  `secteur` is the wrong query param. The publications are actually
  tagged under `sous_secteur`, not `secteur` (confirmed by fetching the
  endpoint with no filter at all and inspecting a real record's field
  names): `publications/list.php?sous_secteur=stat-prix` returns the full
  25-bulletin history.

Each bulletin ships BOTH a PDF and an Excel workbook
(`download.php?id=<id>&format=excel`) -- the Excel is used here, since it
avoids all PDF-table-layout fragility. The workbook is ~21 sheets (openpyxl
names them "Table 1".."Table N" regardless of the sheet's actual visible
tab name); sheet *numbers* are not stable across releases (a bulletin
with slightly different content shifts every later table), so sheets are
located by content-sniffing their first few rows rather than by fixed
index -- this fetcher's sibling `insc_retail_prices.py` does the same for
the 5 city retail-price tables.

The national annex table (row header containing both "FONCTION" and
"RUBRIQUE") is a 13-month-wide time series per release: 12 COICOP-2018-
style divisions (bare FONCTION numbers 1-12; the "INDICE GLOBAL" row,
FONCTION blank, is the all-items headline and is dropped -- no
sanctioned all-items COICOP sentinel) x 13 consecutive months ending on
the bulletin's own reference month. Month-column headers carry OCR-like
typos in the source workbook itself (e.g. "juiletl-\n25" for
"juillet-25") -- matched by month-name PREFIX only (first 3-4 letters),
which survives the typos, plus a 2-digit year suffix.

Only the most recent bulletin is fetched (each one already backfills 13
months; walking all 25 historical bulletins would mean parsing 25 Excel
workbooks for heavily overlapping data).

Emits IndexObservation rows (analytical_role: cpi_benchmark).
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date

import openpyxl
import pandas as pd
from curl_cffi import requests as curl_requests

from prices.fetchers.utils import get_scrape_ts, make_hash

logger = logging.getLogger(__name__)

_PUBLICATIONS_URL = "https://ins-congo.cg/backend/api/publications/list.php"
_DOWNLOAD_URL = "https://ins-congo.cg/backend/api/publications/download.php"
_COUNTRY = "Congo Republic"
_SOURCE_KEY = "cg_insc_inhpc_cpi"
_INDEX_BASE_PERIOD = "2018=100"
_IDENT = ["source_key", "observation_date", "coicop_code"]

_DIVISION_LABELS = {
    1: "Alimentation et boisson non alcoolisées",
    2: "Boissons alcoolisées, tabac et stupéfiant",
    3: "Articles d'habillement et chaussures",
    4: "Logement, eau, électricité, gaz et autres combustibles",
    5: "Meubles, articles de ménages et entretien courant du foyer",
    6: "Santé",
    7: "Transports",
    8: "Communications",
    9: "Loisirs et cultures",
    10: "Enseignements",
    11: "Restaurants et hôtels",
    12: "Biens et services divers",
}

_MONTH_PREFIX = {
    "janv": 1, "fevr": 2, "févr": 2, "mars": 3, "avr": 4, "mai": 5,
    "juin": 6, "juil": 7, "aout": 8, "août": 8, "sept": 9, "oct": 10,
    "nov": 11, "dec": 12, "déc": 12,
}
_MONTH_COL_RE = re.compile(
    r"(janv|f[ée]vr|mars|avr|mai|juin|juil|ao[uû]t|sept|oct|nov|d[ée]c)[a-zé]*-?\s*(\d{2})",
    re.IGNORECASE,
)


def _clean(v) -> str:
    return re.sub(r"\s+", "", str(v or ""))


def _parse_month_col(label) -> date | None:
    m = _MONTH_COL_RE.search(_clean(label).lower())
    if not m:
        return None
    prefix, yy = m.groups()
    prefix = prefix.replace("û", "u").replace("î", "i")
    for key, num in _MONTH_PREFIX.items():
        if prefix.startswith(key[:4]) or key.startswith(prefix[:4]):
            return date(2000 + int(yy), num, 1)
    return None


def _find_national_table(wb) -> tuple[object, int] | None:
    for name in wb.sheetnames:
        ws = wb[name]
        for r in range(1, min(ws.max_row, 10) + 1):
            values = [str(c.value or "") for c in ws[r]]
            joined = " ".join(values).upper()
            if "FONCTION" in joined and "RUBRIQUE" in joined:
                return ws, r
    return None


def _latest_bulletin(session: curl_requests.Session) -> dict | None:
    resp = session.get(
        _PUBLICATIONS_URL,
        params={"sous_secteur": "stat-prix", "per_page": 100},
        timeout=30,
        impersonate="chrome124",
    )
    resp.raise_for_status()
    pubs = resp.json().get("data", [])
    inhpc = [p for p in pubs if p.get("has_excel")]
    if not inhpc:
        return None
    inhpc.sort(key=lambda p: p.get("id", 0), reverse=True)
    return inhpc[0]


def fetch_cg_insc_inhpc_cpi(cutoff: date) -> pd.DataFrame | None:
    session = curl_requests.Session()

    pub = _latest_bulletin(session)
    if pub is None:
        logger.warning("[%s] No stat-prix bulletin with an Excel export found", _SOURCE_KEY)
        return None

    xlsx_url = "https://ins-congo.cg/" + pub["download_url_excel"].lstrip("/")
    resp = session.get(xlsx_url, timeout=60, impersonate="chrome124")
    if resp.status_code != 200:
        logger.warning("[%s] Excel fetch failed (%s): %s", _SOURCE_KEY, resp.status_code, xlsx_url)
        return None

    wb = openpyxl.load_workbook(io.BytesIO(resp.content), data_only=True)
    found = _find_national_table(wb)
    if found is None:
        logger.warning("[%s] Could not locate FONCTION/RUBRIQUE table in %s", _SOURCE_KEY, xlsx_url)
        return None
    ws, header_row = found

    header_cells = ws[header_row]
    month_cols: list[tuple[int, date]] = []
    for cell in header_cells:
        if cell.column <= 3:
            continue
        d = _parse_month_col(cell.value)
        if d is not None:
            month_cols.append((cell.column, d))
    if not month_cols:
        logger.warning("[%s] No parseable month columns in header row", _SOURCE_KEY)
        return None

    label_lookup = {
        re.sub(r"\s+", " ", label).strip().lower(): num
        for num, label in _DIVISION_LABELS.items()
    }

    rows: list[dict] = []
    for r in range(header_row + 1, ws.max_row + 1):
        fonction_val = ws.cell(r, 1).value
        rubrique_val = ws.cell(r, 2).value
        if rubrique_val is None:
            continue
        division_num = None
        try:
            division_num = int(float(fonction_val))
        except (ValueError, TypeError):
            # Division 3 ("Articles d'habillement et chaussures") ships
            # with a blank FONCTION cell in the source workbook -- fall
            # back to matching the RUBRIQUE label text directly.
            division_num = label_lookup.get(
                re.sub(r"\s+", " ", str(rubrique_val)).strip().lower()
            )
        if division_num not in _DIVISION_LABELS:
            continue
        for col, month_date in month_cols:
            if month_date <= cutoff:
                continue
            val = ws.cell(r, col).value
            if val is None:
                continue
            try:
                index_value = float(val)
            except (ValueError, TypeError):
                continue
            row = {
                "observation_date": month_date.isoformat(),
                "period_kind": "monthly_avg",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "coicop_code": f"{division_num:02d}",
                "index_value": index_value,
                "index_base_period": _INDEX_BASE_PERIOD,
                "source_url": xlsx_url,
                "notes": _DIVISION_LABELS[division_num],
                "scrape_ts": get_scrape_ts(),
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

    if not rows:
        return None
    return pd.DataFrame(rows)
