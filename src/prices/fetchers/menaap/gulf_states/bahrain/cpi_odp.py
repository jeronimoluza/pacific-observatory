"""Bahrain CPI (Division and Group, Index Numbers) — Bahrain Open Data Portal.

Published by the Information & eGovernment Authority on data.gov.bh (an
OpenDataSoft — not CKAN — instance), dataset
`01-consumer-price-index-division-and-group-index-number`. Monthly index
numbers at COICOP division (level 2), group (level 3) and, for food, class
(level 4) grain, back to January 2017. The all-items headline row
(`coicop_code == "0"`, level 0) has no sanctioned COICOP sentinel in this
pipeline yet, so it is dropped (see the skill's open design question on a
headline CPI slot).

The source's `coicop_code` values are inconsistently zero-padded ("1.1" vs
"01.1.2") — normalized here to a zero-padded 2-digit division prefix.
Division 13 (COICOP 2018 "Personal care, social protection and misc.") does
not appear as its own division in this publisher's grouping; division 12
("Miscellaneous Goods And Services") is the COICOP-1999-style catch-all,
same pattern as BPS Indonesia.
"""

import logging
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_DATASET = "01-consumer-price-index-division-and-group-index-number"
_RECORDS_URL = (
    f"https://www.data.gov.bh/api/explore/v2.1/catalog/datasets/{_DATASET}/records"
)
_PAGE_SIZE = 100
_COUNTRY = "Bahrain"
_SOURCE_KEY = "bh_cpi_odp"

_MONTH_MAP = {
    "01": 1,
    "02": 2,
    "03": 3,
    "04": 4,
    "05": 5,
    "06": 6,
    "07": 7,
    "08": 8,
    "09": 9,
    "10": 10,
    "11": 11,
    "12": 12,
}

_IDENT = ["source_key", "observation_date", "coicop_code"]


def _normalize_coicop(code: str) -> str:
    parts = code.split(".")
    parts[0] = parts[0].zfill(2)
    return ".".join(parts)


def fetch_bh_cpi_odp(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    rows = []
    offset = 0
    while True:
        try:
            resp = session.get(
                _RECORDS_URL,
                params={
                    "limit": _PAGE_SIZE,
                    "offset": offset,
                    "order_by": "year asc, month asc",
                },
                timeout=30,
            )
            resp.raise_for_status()
            payload = resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[bh_cpi_odp] request failed at offset=%s: %s", offset, exc)
            break

        results = payload.get("results", [])
        if not results:
            break

        for entry in results:
            raw_code = str(entry.get("coicop_code") or "")
            if not raw_code or raw_code == "0":
                continue  # all-items headline row — no sanctioned sentinel yet
            month_num = _MONTH_MAP.get(str(entry.get("month") or "")[:2])
            year = entry.get("year")
            if not month_num or not year:
                continue
            try:
                obs_date = date(int(year), month_num, 1)
            except (TypeError, ValueError):
                continue
            if obs_date <= cutoff:
                continue
            point = entry.get("point")
            if point is None:
                continue
            coicop = _normalize_coicop(raw_code)
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "monthly_avg",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "coicop_code": coicop,
                "index_value": float(point),
                "index_base_period": "2019=100",
                "source_url": _RECORDS_URL,
                "notes": entry.get("coicop_division_group"),
                "scrape_ts": get_scrape_ts(),
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

        offset += _PAGE_SIZE
        if offset >= payload.get("total_count", 0):
            break

    return pd.DataFrame(rows) if rows else None
