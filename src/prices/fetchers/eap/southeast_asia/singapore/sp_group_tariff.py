"""SP Group — Historical Electricity Tariff (Singapore), quarterly.

Downloads the public ``Historical Electricity Tariff.xlsx`` from SP Group's
Magnolia-served DAM and emits one PriceObservation per quarter for the
Low-Tension Domestic All-Units rate (the household tariff, COICOP 04.5.1).

Source rates are in ¢/kWh excl. GST; emitted as SGD/kWh to keep
cross-country PPP comparability and let downstream tax-adjust if needed.
The ``Without GST`` sheet is canonical for the PPP layer — the GST sheet
just inflates the same numbers by 9% from 1 Jan 2024.
"""

from __future__ import annotations

import io
import logging
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_XLSX_URL = (
    "https://www.spgroup.com.sg/dam/jcr:81c964c2-5d20-4281-81b8-14ce00ba03ef/"
    "Historical%20Electricity%20Tariff.xlsx"
)
_SHEET = "SPWebsite (without GST)"
_DATE_ROW = 2
_DOMESTIC_HEADER = "LOW TENSION SUPPLIES, DOMESTIC"
_COUNTRY = "Singapore"
_CURRENCY = "SGD"
_SOURCE_KEY = "sg_sp_group_tariff"
_SOURCE_URL = "https://www.spgroup.com.sg/our-services/utilities/tariff-information"
_ITEM_NAME = "Electricity tariff, low-tension domestic"
_UNIT = "kWh"
_IDENT = ["source_key", "observation_date", "item_name"]


def _find_domestic_value_row(df: pd.DataFrame) -> int:
    labels = df.iloc[:, 1].fillna("").astype(str).str.strip()
    for i, lbl in enumerate(labels):
        if lbl.upper().startswith(_DOMESTIC_HEADER):
            return i + 1
    raise LookupError(f"row anchor not found: {_DOMESTIC_HEADER!r}")


def fetch_sg_sp_group_tariff(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    resp = session.get(_XLSX_URL, timeout=60)
    resp.raise_for_status()
    df = pd.read_excel(io.BytesIO(resp.content), sheet_name=_SHEET, header=None)

    value_row_idx = _find_domestic_value_row(df)
    dates = df.iloc[_DATE_ROW]
    rates = df.iloc[value_row_idx]

    rows: list[dict] = []
    for col in range(2, df.shape[1]):
        raw_date = dates.iloc[col]
        if pd.isna(raw_date):
            continue
        obs_date = pd.Timestamp(raw_date).date()
        if obs_date <= cutoff:
            continue
        raw_rate = rates.iloc[col]
        if pd.isna(raw_rate):
            continue
        try:
            cents_per_kwh = float(raw_rate)
        except (TypeError, ValueError):
            continue
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "quarterly_start",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": "04.5.1",
            "item_name": _ITEM_NAME,
            "price_local": round(cents_per_kwh / 100.0, 6),
            "currency": _CURRENCY,
            "unit": _UNIT,
            "source_url": _SOURCE_URL,
            "notes": "excl. GST; rate published in ¢/kWh, converted to SGD/kWh",
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    return pd.DataFrame(rows) if rows else None
