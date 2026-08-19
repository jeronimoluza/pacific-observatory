"""Qatar MOCI Central Market — imported fruit prices.

Same backend as `moci_vegetables.py`/`moci_fish.py`, id=16. Unlike the other
two category endpoints (both live/fresh at onboarding time), this one was
last updated 2024-09-05 at probe time — the ministry appears to have stopped
refreshing this specific page. Kept as a source because the historical rows
are real, but expect the fetcher to return the same fixed set of rows on
every run until the ministry resumes publishing.
"""

import logging
from datetime import date, datetime

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://www.moci.gov.qa/wp-content/themes/2018_mec_v1/api/dailyPrice.php?id=16&lang=en"
_COUNTRY = "Qatar"
_CURRENCY = "QAR"
_SOURCE_KEY = "qa_moci_fruits"
_COICOP = "01.1.6"

_IDENT = ["source_key", "observation_date", "item_name", "notes"]


def fetch_qa_moci_fruits(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    try:
        resp = session.get(
            _URL, timeout=30, headers={"Referer": "https://www.moci.gov.qa/"}
        )
        resp.raise_for_status()
        payload = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[qa_moci_fruits] request failed: %s", exc)
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
            "notes": entry.get("Source"),
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    return pd.DataFrame(rows) if rows else None
