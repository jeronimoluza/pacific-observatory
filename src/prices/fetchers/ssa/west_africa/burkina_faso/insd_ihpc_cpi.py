"""Burkina Faso INSD — Indice Harmonisé des Prix à la Consommation (IHPC), monthly.

INSD (Institut National de la Statistique et de la Démographie) publishes a
monthly "NOTE_IHPC_Base_2023_de_<MOIS>_<ANNEE>" workbook, linked from
https://www.insd.bf/fr/statistiques/statistiques-economiques/statistiques-des-prix
(see `_insd_common.py` for the shared discovery helper — both this fetcher and
`insd_avg_prices.py` read from the same monthly workbook).

Verified live 2026-09-01 on the May-2026 release (NOTE_IHPC_Base_2023_de_MAI_2026.xlsx,
328,916 bytes, 7 sheets `page1`..`page7`). Sheet `page6` carries "Tableau 5 :
Évolution des indices nationaux suivant les groupes de la NCOA-IHPC" — a
national index table with a 4-digit publisher code per row (e.g. "0101"
PRODUITS ALIMENTAIRES, "0405" ÉLECTRICITÉ GAZ ET AUTRES COMBUSTIBLES) and 5
monthly index columns (one year-ago month for the annual-change comparison,
plus the 4 most recent months). The 4-digit code decomposes cleanly as
COICOP division (first 2 digits) + group (last 2 digits, leading zero
stripped) -- "0101" -> "01.1" (Food), "0203" -> "02.3" (Tobacco), "0405" ->
"04.5" (Electricity, gas and other fuels), "1101" -> "11.1" (Catering
services) -- all confirmed against COICOP 2018 group definitions, so
`coicop_code` is a direct passthrough, no translation table needed.

coicop_classification: publisher_labeled. analytical_role: cpi_benchmark ->
IndexObservation, not PriceObservation. index_base_period is "2023" per the
workbook's own "Base 2023" naming (INSD rebased the IHPC to 2023=100).

Emits one row per (group, month) across all 5 date columns present each
release (not just the latest), so a run that lands between releases still
picks up whichever of those 5 months is newer than `cutoff` -- cheap partial
backfill, not a deep history claim (see `_insd_common.py` docstring for the
real gap: months where only a PDF is published are skipped until a
spreadsheet release covers them again).
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd

from prices.fetchers.ssa.west_africa.burkina_faso._insd_common import (
    find_latest_note_url,
    open_workbook,
)
from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Burkina Faso"
_SOURCE_KEY = "insd_ihpc_cpi_bfa"
_IDENT = ["source_key", "observation_date", "coicop_code"]
_CODE_RE = re.compile(r"^\d{4}$")


def _find_group_sheet(xl: pd.ExcelFile) -> pd.DataFrame | None:
    for sheet in xl.sheet_names:
        df = xl.parse(sheet, header=None)
        if df.shape[1] < 9:
            continue
        if (df.iloc[:, 2].astype(str).str.strip() == "Libellé").any():
            return df
    return None


def _coicop_from_code(code: str) -> str:
    division = code[:2]
    group = str(int(code[2:]))
    return f"{division}.{group}"


def fetch_insd_ihpc_cpi_bfa(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    note_url = find_latest_note_url(session)
    if not note_url:
        return None

    xl = open_workbook(session, note_url)
    if xl is None:
        return None

    df = _find_group_sheet(xl)
    if df is None:
        logger.warning("[%s] group-index sheet not found in %s", _SOURCE_KEY, note_url)
        return None

    header_row = df.index[df.iloc[:, 2].astype(str).str.strip() == "Libellé"][0]
    date_cols = list(range(4, 9))
    date_labels: list[date] = []
    for c in date_cols:
        try:
            date_labels.append(pd.Timestamp(df.iat[header_row, c]).date())
        except (ValueError, TypeError):
            date_labels.append(None)

    ts = get_scrape_ts()
    rows: list[dict] = []
    for i in range(header_row + 1, len(df)):
        code = str(df.iat[i, 1]).strip()
        if not _CODE_RE.match(code):
            continue
        label = str(df.iat[i, 2]).strip()
        coicop_code = _coicop_from_code(code)
        for c, obs_date in zip(date_cols, date_labels):
            if obs_date is None or obs_date <= cutoff:
                continue
            raw_val = df.iat[i, c]
            if pd.isna(raw_val):
                continue
            try:
                index_value = round(float(raw_val), 4)
            except (TypeError, ValueError):
                continue
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "monthly_avg",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "coicop_code": coicop_code,
                "index_value": index_value,
                "index_base_period": "2023",
                "source_url": note_url,
                "notes": f"NCOA-IHPC group {code} — {label}",
                "scrape_ts": ts,
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

    logger.info(
        "[%s] %d rows (cutoff=%s, source=%s)", _SOURCE_KEY, len(rows), cutoff, note_url
    )
    return pd.DataFrame(rows) if rows else None
