"""EMAE (Empresa de Água e Electricidade) — regulated water tariff, Sao Tome.

Sibling manifest to emae_electricity_tariff.yaml -- same page
(/PT/clientes/tarifarios), same fetch, the WATER table instead of the two
ELECTRICITY tables. See that module's docstring for the shared parsing approach,
the STN-vs-STD currency reasoning, and the no-printed-effective-date rationale for
period_kind=snapshot.

analytical_role: tariff -> PriceObservation.
coicop_classification: source_curated (coicop_codes: ["04.4.1"], water supply).
"""

from __future__ import annotations

import io
import logging
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://emae.st/PT/clientes/tarifarios"
_COUNTRY = "Sao Tome and Principe"
_CURRENCY = "STN"
_SOURCE_KEY = "stp_emae_water_tariff"
_COICOP = "04.4.1"
_IDENT = ["source_key", "observation_date", "item_name"]


def _parse_band_table(df: pd.DataFrame, label_prefix: str) -> list[tuple[str, float]]:
    bands = [str(b).strip() for b in df.iloc[1, 1:].tolist()]
    out = []
    for i in range(2, len(df)):
        category = df.iat[i, 0]
        if not isinstance(category, str) or not category.strip():
            continue
        for j, band in enumerate(bands, start=1):
            val = df.iat[i, j]
            if pd.isna(val):
                continue
            try:
                price = float(str(val).replace(",", "."))
            except ValueError:
                continue
            if price <= 0:
                continue
            item_name = f"{label_prefix} - {category.strip()} ({band})"
            out.append((item_name, price))
    return out


def fetch_stp_emae_water_tariff(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    resp = session.get(_URL, timeout=30)
    resp.raise_for_status()

    try:
        tables = pd.read_html(io.StringIO(resp.text))
    except ValueError as exc:
        logger.warning("[%s] no tables found at %s: %s", _SOURCE_KEY, _URL, exc)
        return None
    if len(tables) < 3:
        logger.warning("[%s] expected >=3 tables, found %d", _SOURCE_KEY, len(tables))
        return None

    items = _parse_band_table(tables[2], "Água")
    if not items:
        logger.warning("[%s] no tariff rows parsed", _SOURCE_KEY)
        return None

    obs_date = date.today()
    if obs_date <= cutoff:
        logger.info(
            "[%s] scrape date %s <= cutoff %s, skipping", _SOURCE_KEY, obs_date, cutoff
        )
        return None

    ts_scrape = get_scrape_ts()
    rows = []
    for item_name, price in items:
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "item_name": item_name,
            "price_local": price,
            "currency": _CURRENCY,
            "unit": "m3",
            "coicop_code": _COICOP,
            "source_url": _URL,
            "notes": "EMAE published tariff quoted in dobras (STN); no effective date printed on page.",
            "scrape_ts": ts_scrape,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    logger.info("[%s] %d rows (cutoff=%s)", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows)
