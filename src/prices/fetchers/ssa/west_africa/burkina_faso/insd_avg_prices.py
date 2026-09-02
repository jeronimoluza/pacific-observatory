"""Burkina Faso INSD — regional average prices of essential products, monthly.

Same monthly workbook as `insd_ihpc_cpi.py` (see `_insd_common.py`). One
sheet carries "Tableau 4 : Prix moyens de quelques produits essentiels au
niveau régional" — verified live 2026-09-01 on the May-2026 release: 32
product rows x 13 regions (Kadiogo/Centre, Guiriko/Hauts-Bassins,
Goulmou/Est, Yaadga/Nord, Liptako/Sahel, Kuilse/Centre-Nord,
Oubri/Plateau-Central, Nakambe/Centre-Est, Nazinon/Centre-Sud,
Nando/Centre-Ouest, Bankui/Boucle-du-Mouhoun, Tannounyan/Cascades,
Djoro/Sud-Ouest), e.g. "Riz brisé local ou importé" (Sac de 25 Kg) =
13,662.70 XOF in Kadiogo. The catalog spans food staples (rice, maize,
millet, sorghum, meat, fish, oils, vegetables) plus a few non-food
essentials the report bundles into the same table (firewood, charcoal,
bottled-gas refills, super/gasoil fuel) — a WIDE source, so COICOP is left
to the downstream classifier rather than mapped here.

CURRENCY TRAP: source values are already the true XOF integer amount
(no minor unit) — e.g. "13662.69618" is 13,663 XOF, not a smaller unit.
No division is applied.

analytical_role: official_avg -> PriceObservation. channel: null (this is a
national-statistics average-price table, not a retail outlet).
subnational_area carries the region name so the 13 regional quotes are kept
distinct rather than collapsed to one national figure.

Observation date is taken from the workbook's own release month (parsed from
the source filename's French month name, e.g. "...de_MAI_2026.xlsx" ->
2026-05-01) since this table has no per-row date column — the whole sheet is
a snapshot of "current month" prices only, republished each release.
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd

from prices.fetchers.ssa.west_africa.burkina_faso._insd_common import (
    FR_MONTHS,
    find_latest_note_url,
    open_workbook,
)
from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Burkina Faso"
_SOURCE_KEY = "insd_avg_prices_bfa"
_IDENT = ["source_key", "observation_date", "item_name", "unit", "subnational_area"]
_MONTH_RE = re.compile(r"_de_([A-Za-zÀ-ÿ]+)_(\d{4})", re.IGNORECASE)


def _find_products_sheet(xl: pd.ExcelFile) -> pd.DataFrame | None:
    for sheet in xl.sheet_names:
        df = xl.parse(sheet, header=None)
        if df.shape[1] < 3:
            continue
        col0 = df.iloc[:, 0].astype(str).str.strip()
        if (col0 == "PRODUITS").any():
            return df
    return None


def _release_date_from_url(note_url: str) -> date | None:
    m = _MONTH_RE.search(note_url)
    if not m:
        return None
    month_name, year = m.groups()
    month = FR_MONTHS.get(month_name.strip().lower())
    if not month:
        return None
    return date(int(year), month, 1)


def fetch_insd_avg_prices_bfa(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    note_url = find_latest_note_url(session)
    if not note_url:
        return None

    obs_date = _release_date_from_url(note_url)
    if obs_date is None:
        logger.warning(
            "[%s] could not parse release month from %s", _SOURCE_KEY, note_url
        )
        return None
    if obs_date <= cutoff:
        logger.info("[%s] no new release past cutoff=%s", _SOURCE_KEY, cutoff)
        return None

    xl = open_workbook(session, note_url)
    if xl is None:
        return None

    df = _find_products_sheet(xl)
    if df is None:
        logger.warning("[%s] products sheet not found in %s", _SOURCE_KEY, note_url)
        return None

    header_row = df.index[df.iloc[:, 0].astype(str).str.strip() == "PRODUITS"][0]
    region_cols = list(range(2, df.shape[1]))
    region_labels = [
        re.sub(r"\s+", " ", str(df.iat[header_row, c])).strip() for c in region_cols
    ]

    ts = get_scrape_ts()
    rows: list[dict] = []
    for i in range(header_row + 1, len(df)):
        product = str(df.iat[i, 0]).strip()
        if (
            not product
            or product.upper().startswith("NB")
            or product.upper().startswith("SOURCE")
        ):
            continue
        unit = str(df.iat[i, 1]).strip() if not pd.isna(df.iat[i, 1]) else None
        for c, region in zip(region_cols, region_labels):
            raw_val = df.iat[i, c]
            if pd.isna(raw_val):
                continue
            try:
                price = round(float(raw_val), 2)
            except (TypeError, ValueError):
                continue
            if price <= 0:
                continue
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "monthly_avg",
                "country": _COUNTRY,
                "subnational_area": region,
                "source_key": _SOURCE_KEY,
                "item_name": product,
                "price_local": price,
                "currency": "XOF",
                "unit": unit,
                "source_url": note_url,
                "notes": "INSD regional average price of essential products",
                "scrape_ts": ts,
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

    logger.info(
        "[%s] %d rows (cutoff=%s, obs_date=%s, source=%s)",
        _SOURCE_KEY,
        len(rows),
        cutoff,
        obs_date,
        note_url,
    )
    return pd.DataFrame(rows) if rows else None
