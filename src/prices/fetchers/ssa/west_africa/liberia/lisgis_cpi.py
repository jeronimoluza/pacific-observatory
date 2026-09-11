"""LISGIS (Liberia Institute of Statistics and Geo-Information Services) —
Consumer Price Index, published via a Knoema-hosted "Liberia Data Portal"
(liberia.opendataforafrica.org), dataset "wmstzic" — "Consumer Price Index
(CPI) - 2019-2026" (COICOP, Chained Index, Jan 2019-Present; Base: Dec
2018=100; Weights: 2016). LISGIS's own site (lisgis.gov.lr) is a
placeholder page that names the CPI program and links out to this portal
as the current publication channel (ref field on the dataset points at
lisgis.gov.lr).

The portal's JSON data API (not documented publicly, reverse-engineered
from the front-end's XHR calls) is:

    GET /api/1.0/data/<datasetId>?area=<areaKey>&indicator=<indicatorKey>

where <areaKey>/<indicatorKey> are the *numeric* dimension-member keys
(NOT the short "id" codes like "LBR"/"I2" -- those return an empty
result set silently). Keys are discovered via:

    GET /api/1.0/meta/dataset/<datasetId>/dimension/area
    GET /api/1.0/meta/dataset/<datasetId>/dimension/indicator

Liberia has a single area member (key 1000000, id "LBR"). The indicator
dimension carries 13 members: "Total" (I1, the all-items headline -- no
sanctioned COICOP sentinel exists for this yet, see the skill's open
design question, so it is dropped) plus 12 COICOP-1999-style divisions
(I2..I13) that map 1:1 onto COICOP-2018 divisions 01-12 by content
(division 13, "Insurance and financial services" under COICOP-2018's
13-division split, is not separately published -- same gap seen on
Sierra Leone's Stats SL series in this region).

The response mixes multiple `Frequency` values (A/H/Q/M) for the same
indicator, apparently Knoema auto-aggregating (summing, not averaging --
the "A"/"H"/"Q" values are implausibly large multiples of the monthly
value). Only `Frequency == "M"` rows are genuine LISGIS-published monthly
index points; every other frequency is a derived artifact and is
discarded.

Verified live 2026-09-11: 88 monthly rows for the Food division alone,
Jan 2019 - Apr 2026, no auth required, plain `requests` with a browser
User-Agent (no curl_cffi/TLS fingerprint needed).
"""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd
import requests

from prices.fetchers.utils import get_scrape_ts, make_hash

logger = logging.getLogger(__name__)

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_BASE_URL = "https://liberia.opendataforafrica.org/api/1.0/data/wmstzic"
_COUNTRY = "Liberia"
_SOURCE_KEY = "lr_lisgis_cpi"
_INDEX_BASE_PERIOD = "December 2018=100"
_AREA_KEY = 1000000  # Liberia
_IDENT = ["source_key", "observation_date", "coicop_code"]

# Knoema indicator numeric key -> (COICOP-2018 division, label). Total
# ("I1" / key 1000000... actually key differs, see below) is intentionally
# excluded -- no sanctioned all-items COICOP sentinel.
_INDICATOR_MAP: dict[int, tuple[str, str]] = {
    1000010: ("01", "Food and non-alcoholic beverages"),
    1000020: ("02", "Alcoholic beverages, tobacco and narcotics"),
    1000030: ("03", "Clothing and footwear"),
    1000040: ("04", "Housing, water, electricity, gas and other fuels"),
    1000050: ("05", "Furnishings, household equipment and routine household maintenance"),
    1000060: ("06", "Health"),
    1000070: ("07", "Transport"),
    1000080: ("08", "Communication"),
    1000090: ("09", "Recreation and culture"),
    1000100: ("10", "Education"),
    1000110: ("11", "Restaurants and hotels"),
    1000120: ("12", "Miscellaneous goods and services"),
}


def fetch_lr_lisgis_cpi(cutoff: date) -> pd.DataFrame | None:
    session = requests.Session()
    session.headers.update({"User-Agent": _UA})

    rows: list[dict] = []
    for indicator_key, (coicop, label) in _INDICATOR_MAP.items():
        try:
            resp = session.get(
                _BASE_URL,
                params={"area": _AREA_KEY, "indicator": indicator_key},
                timeout=30,
            )
            resp.raise_for_status()
            payload = resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] fetch failed for indicator %s: %s", _SOURCE_KEY, label, exc)
            continue

        for rec in payload.get("data", []):
            if rec.get("Frequency") != "M":
                continue
            obs_date_str = rec.get("Time")
            if not obs_date_str:
                continue
            obs_date = date.fromisoformat(obs_date_str[:10])
            if obs_date <= cutoff:
                continue
            value = rec.get("Value")
            if value is None:
                continue
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "monthly_avg",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "coicop_code": coicop,
                "index_value": float(value),
                "index_base_period": _INDEX_BASE_PERIOD,
                "source_url": "https://liberia.opendataforafrica.org/wmstzic/consumer-price-index-cpi-2019-2026",
                "notes": label,
                "scrape_ts": get_scrape_ts(),
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

    if not rows:
        return None
    return pd.DataFrame(rows)
