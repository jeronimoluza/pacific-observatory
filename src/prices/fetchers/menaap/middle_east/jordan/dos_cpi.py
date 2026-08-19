"""Jordan Department of Statistics — Monthly Consumer Price Index, via PxWeb API.

The Department of Statistics (dos.gov.jo) publishes its statistical databank on a
PxWeb instance at jorinfo.dos.gov.jo/Databank. Under folder DOS_Database/15
("Price indices") sits table CPI_T1, "Monthly Consumer Price Index (2018=100) by
Expenditure groups and Time". Re-verified live 2026-08-07: metadata resolves
2006M01 - 2026M06 (last month two behind current calendar month, normal CPI
publication lag) and a live POST query for 2026M04-2026M06 returns numeric index
values (e.g. All Items 116.13 for 2026M06). This is a genuine documented REST API
(PxWeb JSON-stat-ish query protocol), not a scrape.

Discovery path: DOS's own "Agricultural prices" databank
(Databank/Metadata/Agricultural-prices.xlsx, linked from dosweb.dos.gov.jo/data_price/)
turned out to be a survey codebook/methodology document, not a data table -- dead end,
noted here so it isn't re-investigated. The live CPI table was found instead via the
PxWeb folder listing at jorinfo.dos.gov.jo/Databank/api/v1/en/DOS_Database/.

The publisher's own ITEM_CPI codes are Jordan's national CPI classification, which
predates the COICOP 2018 13-division revision (12 divisions, e.g. division 12
"Other Goods and Services" folds personal care instead of a separate division 13).
Codes are numeric strings whose digit positions already align with COICOP dotted
notation depth (2-digit division, 1-digit group, 1-digit class), so they are
converted mechanically: "011" -> "01.1", "0111" -> "01.1.1", "0562" -> "05.6.2".
The headline "0" (All Items) has no sanctioned COICOP sentinel and is dropped.

analytical_role: cpi_benchmark -> IndexObservation, not PriceObservation.
coicop_classification: publisher_labeled.
coicop_divisions: 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12
divisions_basis: walked_categories (every ITEM_CPI code in the table's own metadata
  response was read directly, not sampled)
"""

from __future__ import annotations

import json
import logging
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Jordan"
_SOURCE_KEY = "jo_dos_cpi"
_TABLE_URL = "https://jorinfo.dos.gov.jo/Databank/api/v1/en/DOS_Database/15/CPI_T1"
_BASE_PERIOD = "2018=100"
_IDENT = ["source_key", "observation_date", "coicop_code"]


def _to_coicop(code: str) -> str | None:
    code = str(code).strip()
    if not code.isdigit() or code in ("", "0"):
        return None
    parts = [code[0:2], code[2:3], code[3:4]]
    parts = [p for p in parts if p]
    return ".".join(parts)


def _month_to_date(period: str) -> str | None:
    # "2026M06" -> "2026-06-01"
    if "M" not in period:
        return None
    y, m = period.split("M")
    try:
        return date(int(y), int(m), 1).isoformat()
    except ValueError:
        return None


def fetch_jo_dos_cpi(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    try:
        meta_resp = session.get(_TABLE_URL, timeout=30)
        meta_resp.raise_for_status()
        meta = meta_resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] metadata fetch failed: %s", _SOURCE_KEY, exc)
        return None

    variables = {v["code"]: v for v in meta.get("variables", [])}
    item_var = variables.get("ITEM_CPI")
    time_var = variables.get("TIME")
    if not item_var or not time_var:
        logger.warning(
            "[%s] unexpected metadata shape, missing ITEM_CPI/TIME", _SOURCE_KEY
        )
        return None

    item_codes = [c for c in item_var["values"] if c != "0"]
    new_times = [
        t for t in time_var["values"] if (_month_to_date(t) or "") > cutoff.isoformat()
    ]
    if not new_times:
        logger.info("[%s] no new months past cutoff=%s", _SOURCE_KEY, cutoff)
        return None

    body = {
        "query": [
            {"code": "ITEM_CPI", "selection": {"filter": "item", "values": item_codes}},
            {
                "code": "ContentsCode",
                "selection": {"filter": "item", "values": ["CPI_T1"]},
            },
            {"code": "TIME", "selection": {"filter": "item", "values": new_times}},
        ],
        "response": {"format": "json"},
    }
    try:
        resp = session.post(_TABLE_URL, json=body, timeout=60)
        resp.raise_for_status()
        # PxWeb's data-query response is UTF-8 with a BOM; resp.json() chokes on it.
        payload = json.loads(resp.content.decode("utf-8-sig"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] data query failed: %s", _SOURCE_KEY, exc)
        return None

    ts = get_scrape_ts()
    rows: list[dict] = []
    for entry in payload.get("data", []):
        item_code, period = entry["key"]
        coicop = _to_coicop(item_code)
        if coicop is None:
            continue
        obs_date = _month_to_date(period)
        if not obs_date or obs_date <= cutoff.isoformat():
            continue
        raw_val = entry.get("values", [None])[0]
        try:
            index_value = float(raw_val)
        except (TypeError, ValueError):
            continue
        row = {
            "observation_date": obs_date,
            "period_kind": "monthly_avg",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": coicop,
            "index_value": index_value,
            "index_base_period": _BASE_PERIOD,
            "source_url": _TABLE_URL,
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    logger.info("[%s] %d rows (cutoff=%s)", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows) if rows else None
