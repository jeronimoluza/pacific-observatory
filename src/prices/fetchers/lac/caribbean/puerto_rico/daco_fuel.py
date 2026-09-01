"""DACO (Departamento de Asuntos del Consumidor, Puerto Rico) — monthly
average consumer gasoline and diesel prices.

DACO publishes a single, continuously-updated XLSX ("Precios-Promedios-de-
Gasolina-y-Diesel.xlsx") linked from the agency homepage (daco.pr.gov),
hosted on a docs.pr.gov SharePoint-style document store. No auth, no
anti-bot — a plain `requests.get` with a browser UA returns the file
directly (verified live 2026-09-01). The file carries one sheet
("Precios Mensuales") with a one-row banner, then a header row (`Fecha`,
`Promedio`, `Regular`, `Super`, `Diesel`), then one row per month from
2000-01 back-to-front (newest first) through 2026-07, followed by a few
free-text footnote rows (Hurricane-Maria disclaimer, survey-timing notes)
that are dropped by requiring a parseable `Fecha`.

Values are in **cents per US gallon** (e.g. Regular 387.10 = $3.8710/gal;
sense-checked against a Jan-2000 Diesel value of 122.0 = $1.22/gal, which
is right for that era) — divided by 100 before emitting `price_local`.
`Promedio` (a same-row blend of Regular+Super) is skipped as a derived
duplicate of the two components already emitted.

analytical_role: official_avg -> PriceObservation rows.
coicop_classification: source_curated (Regular/Super/Diesel -> 07.2.2,
fuels for personal transport; narrow, single COICOP class).
"""

from __future__ import annotations

import io
import logging
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Puerto Rico"
_CURRENCY = "USD"
_SOURCE_KEY = "pr_daco_fuel"
_UNIT = "gallon"
_XLSX_URL = (
    "https://docs.pr.gov/files/DACO/Gasolina/"
    "Precios%20Promedio%20Mensual%20al%20Consumidor/"
    "Precios-Promedios-de-Gasolina-y-Diesel.xlsx"
)

_ITEM_COLUMNS = {
    "Regular": "07.2.2",
    "Super": "07.2.2",
    "Diesel": "07.2.2",
}

_IDENT = ["source_key", "observation_date", "item_name"]


def fetch_pr_daco_fuel(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    try:
        resp = session.get(_XLSX_URL, timeout=30)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] download failed: %s", _SOURCE_KEY, exc)
        return None

    df = pd.read_excel(io.BytesIO(resp.content), header=1)
    df.columns = [str(c).strip() for c in df.columns]
    df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
    df = df.dropna(subset=["Fecha"])

    ts = get_scrape_ts()
    rows: list[dict] = []
    for _, r in df.iterrows():
        obs_date = r["Fecha"].date()
        if obs_date <= cutoff:
            continue
        for col, coicop in _ITEM_COLUMNS.items():
            price = r.get(col)
            if pd.isna(price):
                continue
            rec = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "monthly_avg",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "item_name": col,
                "price_local": round(float(price) / 100, 4),
                "currency": _CURRENCY,
                "unit": _UNIT,
                "coicop_code": coicop,
                "source_url": _XLSX_URL,
                "scrape_ts": ts,
                "observation_hash": None,
            }
            rec["observation_hash"] = make_hash(rec, _IDENT)
            rows.append(rec)

    logger.info(
        "[%s] %d rows (cutoff=%s, latest month=%s)",
        _SOURCE_KEY,
        len(rows),
        cutoff,
        df["Fecha"].max().date() if not df.empty else None,
    )
    return pd.DataFrame(rows) if rows else None
