"""Qatar MOCI Central Market — daily fish prices.

Same backend as `moci_vegetables.py` (a jQuery ajax call to a per-category
`dailyPrice.php` endpoint on the ministry's WordPress theme), id=17. Rows are
wholesale central-market prices in QAR per kilogram; price <= 0 rows
(not landed / not traded that day) are dropped.
"""

import logging
from datetime import date, datetime

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://www.moci.gov.qa/wp-content/themes/2018_mec_v1/api/dailyPrice.php?id=17&lang=en"
_COUNTRY = "Qatar"
_CURRENCY = "QAR"
_SOURCE_KEY = "qa_moci_fish"
_COICOP = "01.1.3"

_IDENT = ["source_key", "observation_date", "item_name"]


def fetch_qa_moci_fish(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    try:
        resp = session.get(
            _URL, timeout=30, headers={"Referer": "https://www.moci.gov.qa/"}
        )
        resp.raise_for_status()
        payload = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[qa_moci_fish] request failed: %s", exc)
        return None

    if payload.get("status") != "sucess":
        return None

    rows = []
    for entry in payload.get("table", []):
        try:
            price = float(entry.get("price") or 0)
        except (TypeError, ValueError):
            continue
        if price <= 0:
            continue
        try:
            obs_date = datetime.strptime(entry["date"], "%d/%m/%Y").date()
        except (KeyError, ValueError):
            continue
        if obs_date <= cutoff:
            continue
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "item_name": entry.get("name"),
            "price_local": price,
            "currency": _CURRENCY,
            "unit": "kg",
            "coicop_code": _COICOP,
            "source_url": _URL,
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    return pd.DataFrame(rows) if rows else None
