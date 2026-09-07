"""Sabah Water Department domestic tariff table."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from io import StringIO

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://water.sabah.gov.my/index.php/content/water-tariff"
_COUNTRY = "Malaysia"
_CURRENCY = "MYR"
_SOURCE_KEY = "my_sabah_water_tariff"
_COICOP = "04.4.1"
_IDENT = ["source_key", "observation_date", "item_name"]


def _clean(value: object) -> str:
    return " ".join(str(value).replace("\xa0", " ").split())


def fetch_my_sabah_water_tariff(cutoff: date) -> pd.DataFrame | None:
    obs_date = datetime.now(timezone.utc).date()
    if obs_date <= cutoff:
        return None

    session = get_session()
    resp = session.get(_URL, timeout=45)
    resp.raise_for_status()

    tables = pd.read_html(StringIO(resp.text))
    if not tables:
        logger.warning("[%s] no water tariff table found", _SOURCE_KEY)
        return None
    df = tables[0]

    rows: list[dict] = []
    ts = get_scrape_ts()
    for _, src_row in df.iterrows():
        customer_class = _clean(src_row.get("DOMESTIC /COMMERCIAL RATE", ""))
        if not customer_class.lower().startswith("domestic"):
            continue
        block = _clean(src_row.get("BLOCK (M³)", ""))
        raw_price = src_row.get("TARIFF ( RM )")
        try:
            price = float(raw_price)
        except (TypeError, ValueError):
            continue

        is_minimum = "minimum" in block.lower()
        unit = "month" if is_minimum else "m3"
        item_name = f"Sabah water tariff, {customer_class}, {block}"
        note_kind = "monthly minimum charge" if is_minimum else "rate per cubic metre"
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "subnational_area": "Sabah",
            "source_key": _SOURCE_KEY,
            "coicop_code": _COICOP,
            "item_name": item_name[:500],
            "price_local": round(price, 4),
            "currency": _CURRENCY,
            "unit": unit,
            "source_url": _URL,
            "notes": f"{note_kind}; domestic/customer-class tariff table"[:500],
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    logger.info("[%s] %d rows", _SOURCE_KEY, len(rows))
    return pd.DataFrame(rows) if rows else None
