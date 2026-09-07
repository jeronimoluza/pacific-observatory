"""Hotlink Malaysia prepaid plan tariffs."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone
from io import StringIO

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://www.hotlink.com.my/en/products/prepaid/compare/"
_COUNTRY = "Malaysia"
_CURRENCY = "MYR"
_SOURCE_KEY = "my_hotlink_prepaid"
_COICOP = "08.3.0"
_UNIT = "package"
_IDENT = ["source_key", "observation_date", "item_name"]

_PRICE_RE = re.compile(r"RM\s*([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)


def _feature_notes(df: pd.DataFrame, column: str) -> str:
    parts: list[str] = []
    for _, row in df.iterrows():
        label = str(row.iloc[0]).strip()
        value = str(row[column]).strip()
        if not label or label.lower() == "nan" or not value or value.lower() == "nan":
            continue
        parts.append(f"{label}: {value}")
    return "; ".join(parts)


def fetch_my_hotlink_prepaid(cutoff: date) -> pd.DataFrame | None:
    obs_date = datetime.now(timezone.utc).date()
    if obs_date <= cutoff:
        return None

    session = get_session()
    resp = session.get(_URL, timeout=45)
    resp.raise_for_status()

    tables = pd.read_html(StringIO(resp.text))
    if not tables:
        logger.warning("[%s] no plan-comparison table found", _SOURCE_KEY)
        return None
    df = tables[0]

    rows: list[dict] = []
    ts = get_scrape_ts()
    for column in df.columns[1:]:
        m = _PRICE_RE.search(str(column))
        if not m:
            continue
        price = float(m.group(1))
        notes = _feature_notes(df, column)
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": _COICOP,
            "item_name": f"Hotlink prepaid plan {column}",
            "price_local": round(price, 2),
            "currency": _CURRENCY,
            "unit": _UNIT,
            "source_url": _URL,
            "notes": notes[:500],
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    logger.info("[%s] %d rows", _SOURCE_KEY, len(rows))
    return pd.DataFrame(rows) if rows else None
