"""Qatar MOCI Central Market — daily vegetable prices (domestic + imported).

The Ministry of Commerce and Industry publishes a live JSON feed behind its
"Daily Vegetable Prices" and "Imported Vegetable Prices" pages, backing the
jQuery table each page renders client-side. Both endpoints share the same
payload shape (id/name/Source/Unit/Size/PackPrice/price) and both are
wholesale central-market prices in QAR per kilogram. Rows with price <= 0
(out-of-season / not traded that day) are dropped.
"""

import logging
from datetime import date, datetime

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_ENDPOINTS = [
    "https://www.moci.gov.qa/wp-content/themes/2018_mec_v1/api/dailyPrice.php?id=12&lang=en",
    "https://www.moci.gov.qa/wp-content/themes/2018_mec_v1/api/dailyPrice.php?id=13&lang=en",
]
_COUNTRY = "Qatar"
_CURRENCY = "QAR"
_SOURCE_KEY = "qa_moci_vegetables"
_COICOP = "01.1.7"

_IDENT = ["source_key", "observation_date", "item_name", "notes"]


def fetch_qa_moci_vegetables(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    rows = []
    for url in _ENDPOINTS:
        try:
            resp = session.get(
                url, timeout=30, headers={"Referer": "https://www.moci.gov.qa/"}
            )
            resp.raise_for_status()
            payload = resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[qa_moci_vegetables] request failed for %s: %s", url, exc)
            continue
        if payload.get("status") != "sucess":
            continue
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
                "source_url": url,
                "notes": entry.get("Source"),
                "scrape_ts": get_scrape_ts(),
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

    return pd.DataFrame(rows) if rows else None
