"""EMAE (Empresa de Água e Electricidade) — regulated electricity tariff, Sao Tome.

EMAE is Sao Tome and Principe's state water/electricity utility. Its "Tarifários"
page (/PT/clientes/tarifarios) is static server-rendered HTML with clean two-row-header
tables the source itself groups by customer category: a post-paid schedule (price per
kWh, banded by monthly consumption) and a pre-paid schedule (price per kWh, banded by
meter phase). Verified live 2026-09-01: `pandas.read_html` parses both tables cleanly
(no rowspan/colspan trickery like the Vanuatu URA sibling fetcher had to work around).

Sibling manifest to emae_water_tariff.yaml -- same page, same fetch, the ELECTRICITY
tables instead of the WATER one.

No effective/publication date is printed anywhere on the page, so this is a live
snapshot rather than a dated regulatory order (period_kind: snapshot, observation_date
= scrape date), unlike Gabon's SEEG PDF or Vanuatu's URA table which both print one.

Currency: rates are in "dobras" per the page, undated as STN vs STD -- but the
magnitude (1.67-9.87 per kWh) is two to three orders of magnitude too small to be
pre-2018 STD (which would print in the thousands for a comparable tariff), and STN
1.67-9.87/kWh against the ~24.5 STN/EUR peg is a plausible EUR-cents-per-kWh range for
a small-grid island utility. Recorded as STN accordingly.

analytical_role: tariff -> PriceObservation.
coicop_classification: source_curated (coicop_codes: ["04.5.1"], electricity retail).
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
_SOURCE_KEY = "stp_emae_electricity_tariff"
_COICOP = "04.5.1"
_IDENT = ["source_key", "observation_date", "item_name"]


def _parse_band_table(
    df: pd.DataFrame, label_prefix: str, unit_suffix: str
) -> list[tuple[str, str, float]]:
    """A 2-header-row EMAE table: row0=group label, row1=band labels, row2+=data."""
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
            item_name = f"{label_prefix} - {category.strip()} ({band}{unit_suffix})"
            out.append((item_name, price))
    return out


def fetch_stp_emae_electricity_tariff(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    resp = session.get(_URL, timeout=30)
    resp.raise_for_status()

    try:
        tables = pd.read_html(io.StringIO(resp.text))
    except ValueError as exc:
        logger.warning("[%s] no tables found at %s: %s", _SOURCE_KEY, _URL, exc)
        return None
    if len(tables) < 2:
        logger.warning("[%s] expected >=2 tables, found %d", _SOURCE_KEY, len(tables))
        return None

    items: list[tuple[str, float]] = []
    items += _parse_band_table(tables[0], "Electricidade pós-pago", "")
    items += _parse_band_table(tables[1], "Electricidade pré-pago", "")

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
            "unit": "kWh",
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
