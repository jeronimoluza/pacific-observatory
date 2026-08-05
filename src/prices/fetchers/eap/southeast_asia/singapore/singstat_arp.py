"""SingStat M213761 — Average Retail Prices of Selected Consumer Items.

Public TableBuilder JSON endpoint, monthly. Items are stable-ish but the
2024-based basket switch in January 2024 reshuffled some entries — leave
COICOP tagging to the downstream embedding->head classifier (`coicop_classification: classifier`).

Each commodity row has a header like ``Premium Thai Rice (Per 5 Kilogram)``;
the unit-of-account is the bracketed suffix.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_METADATA_URL = "https://tablebuilder.singstat.gov.sg/api/table/metadata/M213761"
_TABLEDATA_URL = "https://tablebuilder.singstat.gov.sg/api/table/tabledata/M213761"
_COUNTRY = "Singapore"
_CURRENCY = "SGD"
_SOURCE_KEY = "sg_singstat_arp"

_IDENT = ["source_key", "observation_date", "item_name"]

_UNIT_RE = re.compile(r"\(Per\s+([^)]+)\)\s*$", re.IGNORECASE)
_PERIOD_RE = re.compile(r"^(\d{4})\s+([A-Za-z]{3})$")


def _parse_period(key: str) -> date | None:
    m = _PERIOD_RE.match(key.strip())
    if not m:
        return None
    try:
        return datetime.strptime(f"{m.group(1)} {m.group(2)}", "%Y %b").date()
    except ValueError:
        return None


def _split_item_and_unit(row_text: str) -> tuple[str, str]:
    """Pull the bracketed '(Per X)' unit off the item name."""
    m = _UNIT_RE.search(row_text)
    if not m:
        return row_text.strip(), "each"
    unit = m.group(1).strip()
    name = _UNIT_RE.sub("", row_text).strip()
    return name, unit


def fetch_sg_singstat_arp(cutoff: date) -> pd.DataFrame | None:
    session = get_session()

    meta = session.get(_METADATA_URL, timeout=30)
    meta.raise_for_status()
    series_list = meta.json()["Data"]["records"].get("row", [])
    series_nos = [r["seriesNo"] for r in series_list]
    logger.info("[%s] %d series in metadata", _SOURCE_KEY, len(series_nos))

    rows: list[dict] = []
    for sn in series_nos:
        resp = session.get(_TABLEDATA_URL, params={"seriesNoORrowNo": sn}, timeout=60)
        resp.raise_for_status()
        payload = resp.json().get("Data", {})
        for r in payload.get("row", []):
            item_name, unit = _split_item_and_unit(r.get("rowText", ""))
            for col in r.get("columns", []):
                obs_date = _parse_period(col.get("key", ""))
                if obs_date is None or obs_date <= cutoff:
                    continue
                raw = col.get("value")
                if raw in (None, "", "na", "n.a.", "-"):
                    continue
                try:
                    price = float(raw)
                except (TypeError, ValueError):
                    continue
                row = {
                    "observation_date": obs_date.isoformat(),
                    "period_kind": "monthly_avg",
                    "country": _COUNTRY,
                    "source_key": _SOURCE_KEY,
                    "item_name": item_name,
                    "price_local": price,
                    "currency": _CURRENCY,
                    "unit": unit,
                    "source_url": (
                        "https://tablebuilder.singstat.gov.sg/table/TS/M213761"
                    ),
                    "scrape_ts": get_scrape_ts(),
                    "observation_hash": None,
                }
                row["observation_hash"] = make_hash(row, _IDENT)
                rows.append(row)

    return pd.DataFrame(rows) if rows else None
