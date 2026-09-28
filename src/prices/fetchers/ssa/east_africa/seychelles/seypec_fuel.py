"""SEYPEC (Seychelles Petroleum Company) -- retail fuel prices.

Static Drupal page at https://www.seypec.com/fuel-prices publishes the
current pump price for four products as a single "Fuel Prices" snapshot
(no archive of prior prices on the page): GASOLINE (SCR/L), GASOIL
(diesel, SCR/L), KEROSENE (sold in a 5L pack, SCR/5L), LPG (SCR/KG).
Verified live 2026-09-28: "GASOLINE SCR24.68/L GASOIL SCR25.19/L
KEROSENE SCR150.00/5L LPG SCR17.50/KG", with a "Last modified
DD/MM/YYYY" stamp used as observation_date. Kerosene's 5L pack price is
normalised to a per-litre figure for comparability with the other two
per-L fuels.

COICOP: GASOLINE and GASOIL are vehicle fuels (07.2.2). KEROSENE is a
domestic liquid heating/lighting fuel (04.5.3). LPG is bottled gas
(04.5.2). No historical series is published; this is a single
current-price snapshot per run, period_kind="effective_from" dated by
the page's own "Last modified" stamp.

Currency: SCR (matches countries.yaml).
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://www.seypec.com/fuel-prices"
_COUNTRY = "Seychelles"
_CURRENCY = "SCR"
_SOURCE_KEY = "seypec_fuel_sc"
_IDENT = ["source_key", "observation_date", "item_name"]

# label -> (item_name, coicop_code, unit, pack_size_to_normalise_by)
_PRODUCTS = {
    "GASOLINE": ("Gasoline (petrol), pump price", "07.2.2", "L", 1.0),
    "GASOIL": ("Gasoil (diesel), pump price", "07.2.2", "L", 1.0),
    "KEROSENE": ("Kerosene, retail price", "04.5.3", "L", 5.0),
    "LPG": ("LPG (bottled gas), retail price", "04.5.2", "KG", 1.0),
}

_PRICE_RE = re.compile(
    r'views-label-field-(gasoline|gasoil|kerosene|lpg)">[A-Z]+</span>'
    r'<span class="field-content">SCR([\d,]+\.\d+)/(?:(\d+))?([A-Za-z]+)</span>',
    re.IGNORECASE,
)
_MODIFIED_RE = re.compile(
    r'field--label">Last modified</div>\s*<div class="field--item">'
    r"(\d{1,2})/(\d{1,2})/(\d{4})",
    re.IGNORECASE,
)


def _parse_effective_date(text: str) -> date | None:
    m = _MODIFIED_RE.search(text)
    if not m:
        return None
    day, month, year = (int(g) for g in m.groups())
    try:
        return date(year, month, day)
    except ValueError:
        return None


def fetch_seypec_fuel_sc(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    resp = session.get(_URL, timeout=30)
    if resp.status_code != 200:
        logger.warning("[%s] HTTP %s for %s", _SOURCE_KEY, resp.status_code, _URL)
        return None

    text = resp.text
    effective_date = _parse_effective_date(text) or date.today()
    if effective_date <= cutoff:
        logger.info(
            "[%s] effective_date=%s <= cutoff=%s, skipping",
            _SOURCE_KEY,
            effective_date,
            cutoff,
        )
        return None

    scrape_ts = get_scrape_ts()
    rows: list[dict] = []
    for m in _PRICE_RE.finditer(text):
        label = m.group(1).upper()
        raw_value = float(m.group(2).replace(",", ""))
        info = _PRODUCTS.get(label)
        if info is None:
            continue
        item_name, coicop_code, unit, pack_size = info
        price_local = round(raw_value / pack_size, 4)
        row = {
            "observation_date": effective_date.isoformat(),
            "period_kind": "effective_from",
            "country": _COUNTRY,
            "subnational_area": None,
            "source_key": _SOURCE_KEY,
            "coicop_code": coicop_code,
            "item_name": item_name,
            "price_local": price_local,
            "currency": _CURRENCY,
            "unit": unit,
            "source_url": _URL,
            "notes": (
                f"raw={raw_value} {m.group(4)}"
                + (f" per {int(m.group(3))}{m.group(4)} pack, normalised to /L" if m.group(3) else "")
            ),
            "scrape_ts": scrape_ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    if not rows:
        logger.warning("[%s] No fuel price rows parsed from %s", _SOURCE_KEY, _URL)
        return None

    logger.info(
        "[%s] %d fuel price rows (effective %s)", _SOURCE_KEY, len(rows), effective_date
    )
    return pd.DataFrame(rows)
