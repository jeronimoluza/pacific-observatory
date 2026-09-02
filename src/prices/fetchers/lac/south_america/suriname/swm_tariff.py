"""SWM (Surinaamsche Waterleiding Maatschappij) -- drinking-water tariffs.

swm.sr/over-water/tarieven/ renders one clean HTML `<table>` (confirmed
live 2026-09-01, `pandas.read_html` parses it directly): 9 tariff groups
(Tariefgroep 20/30A/30B/31/40/41/42/52/60) with an SRD/m3 rate each,
covering household connections (with/without pool), commercial,
public, hospital/social, and construction-crane categories.

Unlike EBS/GOw2, the page states no explicit effective-from date for
this tariff table -- period_kind is therefore "snapshot" (the date
fetched), not "effective_from", per the PriceObservation vocabulary
rule: don't fabricate an effective date the source itself doesn't state.
"""

from __future__ import annotations

import io
import logging
from datetime import date, datetime, timezone

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://swm.sr/over-water/tarieven/"
_COUNTRY = "Suriname"
_CURRENCY = "SRD"
_SOURCE_KEY = "sr_swm_tariff"
_COICOP = "04.4.1"  # Water supply

_IDENT = ["source_key", "observation_date", "item_name"]


def fetch_sr_swm_tariff(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    resp = session.get(_URL, timeout=30)
    resp.raise_for_status()

    obs_date = datetime.now(timezone.utc).date()
    if obs_date <= cutoff:
        return None

    try:
        tables = pd.read_html(io.StringIO(resp.text))
    except ValueError:
        logger.exception(
            "[%s] pandas.read_html found no tables at %s", _SOURCE_KEY, _URL
        )
        return None
    if not tables:
        logger.warning("[%s] No tables found at %s", _SOURCE_KEY, _URL)
        return None

    df = tables[0]
    expected_cols = {"Tariefgroepen", "Omschrijving", "Tarief"}
    if not expected_cols.issubset(set(df.columns.astype(str))):
        logger.warning(
            "[%s] Unexpected table columns: %s", _SOURCE_KEY, list(df.columns)
        )
        return None

    rows = []
    for _, r in df.iterrows():
        try:
            rate = float(r["Tarief"])
        except (TypeError, ValueError):
            continue
        item_name = f"{r['Tariefgroepen']} - {r['Omschrijving']}".strip()
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "item_name": item_name,
            "price_local": rate,
            "currency": _CURRENCY,
            "unit": "m3",
            "coicop_code": _COICOP,
            "source_url": _URL,
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    return pd.DataFrame(rows) if rows else None
