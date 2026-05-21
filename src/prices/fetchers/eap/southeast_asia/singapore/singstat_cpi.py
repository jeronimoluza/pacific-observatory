"""SingStat M213751 — Consumer Price Index (CPI), 2024 base year, monthly.

SingStat's grouping is 11 divisions (not the COICOP-2018 13). Mapping:

  1.01 Food Excl Serving Services         → COICOP 01
  1.02 Clothing & Footwear                → COICOP 03
  1.03 Housing & Utilities                → COICOP 04
  1.04 Household Durables & Services      → COICOP 05
  1.05 Health                             → COICOP 06
  1.06 Transport                          → COICOP 07
  1.07 Information & Communication        → COICOP 08
  1.08 Recreation, Sport & Culture        → COICOP 09
  1.09 Education                          → COICOP 10
  1.10 Miscellaneous Goods & Services     → COICOP 12 (folds 12 + parts of 13)
  1.11 Food & Beverage Serving Services   → COICOP 11

COICOP 02 (alcohol & tobacco) is absorbed into Misc and is not separately
reported by SingStat — left uncovered. The All-Items headline (series 1)
is NOT emitted: IndexObservation requires a coicop_code, and there is no
sanctioned sentinel for headline CPI yet. See the skill polish note about
how to surface headline CPI without breaking the contract.

Emits IndexObservation rows.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_METADATA_URL = "https://tablebuilder.singstat.gov.sg/api/table/metadata/M213751"
_TABLEDATA_URL = "https://tablebuilder.singstat.gov.sg/api/table/tabledata/M213751"
_COUNTRY = "Singapore"
_SOURCE_KEY = "sg_singstat_cpi"
_BASE_PERIOD = "2024=100"
_SOURCE_URL = "https://tablebuilder.singstat.gov.sg/table/TS/M213751"

_DIVISION_MAP = {
    "1.01": "01",
    "1.02": "03",
    "1.03": "04",
    "1.04": "05",
    "1.05": "06",
    "1.06": "07",
    "1.07": "08",
    "1.08": "09",
    "1.09": "10",
    "1.10": "12",
    "1.11": "11",
}
_IDENT = ["source_key", "observation_date", "coicop_code", "subnational_area"]
_PERIOD_RE = re.compile(r"^(\d{4})\s+([A-Za-z]{3})$")


def _parse_period(key: str) -> date | None:
    m = _PERIOD_RE.match(key.strip())
    if not m:
        return None
    try:
        return datetime.strptime(f"{m.group(1)} {m.group(2)}", "%Y %b").date()
    except ValueError:
        return None


def fetch_sg_singstat_cpi(cutoff: date) -> pd.DataFrame | None:
    session = get_session()

    rows: list[dict] = []

    for sn in _DIVISION_MAP:
        resp = session.get(_TABLEDATA_URL, params={"seriesNoORrowNo": sn}, timeout=60)
        resp.raise_for_status()
        for r in resp.json().get("Data", {}).get("row", []):
            coicop = _DIVISION_MAP.get(r["seriesNo"])
            if coicop is None:
                logger.warning(
                    "[%s] No COICOP mapping for series %s (%s) — dropping",
                    _SOURCE_KEY,
                    r["seriesNo"],
                    r.get("rowText"),
                )
                continue
            for col in r.get("columns", []):
                obs_date = _parse_period(col.get("key", ""))
                if obs_date is None or obs_date <= cutoff:
                    continue
                raw = col.get("value")
                if raw in (None, "", "na", "n.a.", "-"):
                    continue
                try:
                    idx = float(raw)
                except (TypeError, ValueError):
                    continue
                row = {
                    "observation_date": obs_date.isoformat(),
                    "period_kind": "monthly_avg",
                    "country": _COUNTRY,
                    "source_key": _SOURCE_KEY,
                    "coicop_code": coicop,
                    "index_value": idx,
                    "index_base_period": _BASE_PERIOD,
                    "source_url": _SOURCE_URL,
                    "notes": r.get("rowText", ""),
                    "scrape_ts": get_scrape_ts(),
                    "observation_hash": None,
                }
                row["observation_hash"] = make_hash(row, _IDENT)
                rows.append(row)

    return pd.DataFrame(rows) if rows else None
