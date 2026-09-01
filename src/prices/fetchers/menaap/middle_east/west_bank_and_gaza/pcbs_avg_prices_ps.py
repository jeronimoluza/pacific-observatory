"""PCBS Consumer Price Index Dashboard — commodity average-price series.

The Palestinian Central Bureau of Statistics (pcbs.gov.ps) publishes its CPI
dashboard as a Plotly Dash app at /CPIDashBoard/ (English UI: /cpiDashboard/en).
Re-verified live 2026-09-01: the dashboard's "Commodities" tab carries a
`commodity_view` option literally labelled "Average price" (Arabic: المتوسط
السعري) alongside "Percent change" -- this is PCBS's own detailed average
retail-price series by item and region, not a re-derived CPI index. It is the
source the onboarding brief named as "very likely the highest-value source
available" for West Bank and Gaza.

Discovery path: the dashboard page (`/CPIDashBoard/en`) itself carries no data
in its HTML -- it's a Dash SPA shell. Dash's own introspection endpoints
(`/CPIDashBoard/_dash-layout`, `/CPIDashBoard/_dash-dependencies`) expose the
full component tree and callback graph without authentication, which is how
the `commodity_category` (74 categories) and per-category `commodity_item`
(PCBS's own COICOP-shaped item codes, e.g. "011100109" = Egyptian Rice 1kg)
option lists were found. The callback that fills `commodity_table` is a plain
POST to `/CPIDashBoard/_dash-update-component` -- no auth, no WAF, works with
plain `requests` (curl_cffi impersonation was not needed here; verified both
paths return 200). Passing `commodity_item: ["__ALL__"]` bypasses the
category/item filters entirely and returns the FULL commodity table in one
call -- confirmed against `commodity_category: ["Rice"]` (returned rows from
Category="Electricity tariffs, gas and fuel" etc, i.e. all categories, not
just Rice), so no need to walk 74 categories individually.

`regions` accepts `["Palestine"]` (national), `["West Bank"]`, `["Gaza Strip"]`,
or `["Jerusalem J1"]`. This fetcher takes the `Palestine` (national) series as
the primary product; the three subnational slices exist behind the same
endpoint for future work (swap the `regions` value in `_fetch_table`).

CURRENCY: the dashboard's own currency-conversion tab (`academic_currency`,
a separate feature for converting the series to USD) defaults to `NIS` (the
Israeli new shekel, ISO 4217 ILS) and the commodity table itself carries no
currency column -- confirming the "Average Price" values are natively
denominated in ILS, matching `karaz_ps` and `wfp_prices` for this country
(NOT the USD `countries.yaml` declares for west_bank_and_gaza -- the known
per-brief defect). A single constant currency is used here because the
source itself does not vary currency per row; this is different from a
backfill stamping row 1's currency onto every row, which is the anti-pattern
the brief warns against.

DUPLICATE QUOTES: with `regions: ["Palestine"]` and `time_window: "all"`,
~1.2% of (Period, Item Code) pairs (271 of ~14,000 combinations checked in a
2019-2026 pull) carry more than one raw "Average Price" value for the same
month -- e.g. Gaza Strip diesel in 2026-01 had 7 distinct quoted prices
ranging 5.96-8.70 ILS/L. The dashboard exposes no sub-region/collector
dimension that would explain these, so -- following the same pattern as
`wfp_prices.yaml`'s per-market collapse -- this fetcher averages same-month
duplicates into one national mean per item and records the underlying quote
count in `notes`, rather than emitting the raw (and unexplained) duplicates
as if they were independent observations.

analytical_role: official_avg (PriceObservation, not IndexObservation).
coicop_classification: classifier -- PCBS's own "Item" labels are free-text
product descriptions (many still in Arabic despite `lang_store: "en"`)
spanning most of the COICOP basket (food, fuel, tobacco, ... 74 categories),
so COICOP is left to the downstream classifier rather than mapped here.
"""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_SOURCE_KEY = "pcbs_avg_prices_ps"
_COUNTRY = "State of Palestine"
_CURRENCY = "ILS"
_DASHBOARD_URL = "https://www.pcbs.gov.ps/cpiDashboard/en"
_API_URL = "https://www.pcbs.gov.ps/CPIDashBoard/_dash-update-component"
_IDENT = ["source_key", "observation_date", "item_name", "unit", "item_code"]

_COMMODITY_TABLE_OUTPUT = (
    "..commodity_chart_index.figure...commodities_series_table.children"
    "...commodity_table.data...commodity_table.columns.."
)


def _input(id_: str, prop: str, value):
    return {"id": id_, "property": prop, "value": value}


def _fetch_table(session) -> list[dict] | None:
    payload = {
        "output": _COMMODITY_TABLE_OUTPUT,
        "outputs": [
            {"id": "commodity_chart_index", "property": "figure"},
            {"id": "commodities_series_table", "property": "children"},
            {"id": "commodity_table", "property": "data"},
            {"id": "commodity_table", "property": "columns"},
        ],
        "inputs": [
            _input("time_window", "value", "all"),
            _input("frequency", "value", "monthly"),
            _input("regions", "value", ["Palestine"]),
            _input("date_range_month", "value", [None, None]),
            _input("date_range_year", "value", [None, None]),
            _input("commodity_category", "value", []),
            _input("commodity_item", "value", ["__ALL__"]),
            _input("commodity_search_items", "value", []),
            _input("commodity_view", "value", ["index"]),
            _input("lang_store", "data", "en"),
        ],
        "changedPropIds": ["commodity_item.value"],
        "state": [],
    }
    headers = {
        "Content-Type": "application/json",
        "Referer": _DASHBOARD_URL,
        "X-Requested-With": "XMLHttpRequest",
    }
    try:
        resp = session.post(_API_URL, json=payload, headers=headers, timeout=120)
        resp.raise_for_status()
        data = resp.json()["response"]["commodity_table"]["data"]
    except Exception:  # noqa: BLE001
        logger.warning("[%s] dash-update-component call failed", _SOURCE_KEY)
        return None
    return data


def _period_to_date(period: str) -> str | None:
    # "2026-01" -> "2026-01-01"
    try:
        y, m = period.split("-")
        return date(int(y), int(m), 1).isoformat()
    except (ValueError, AttributeError):
        return None


def fetch_pcbs_avg_prices_ps(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    raw = _fetch_table(session)
    if not raw:
        logger.info("[%s] no data returned", _SOURCE_KEY)
        return None

    df = pd.DataFrame(raw)
    df = df.rename(
        columns={
            "Period": "period",
            "Category": "category",
            "Item Code": "item_code",
            "Item": "item",
            "Unit": "unit",
            "Average Price": "price",
        }
    )
    df["observation_date"] = df["period"].apply(_period_to_date)
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df = df[df["observation_date"].notna() & df["price"].notna() & (df["price"] > 0)]
    df = df[df["observation_date"] > cutoff.isoformat()]
    df = df[df["item"].astype(str).str.strip() != ""]
    if df.empty:
        logger.info("[%s] no new rows past cutoff=%s", _SOURCE_KEY, cutoff)
        return None

    ts = get_scrape_ts()
    keys = ["observation_date", "item_code", "item", "unit", "category"]
    rows: list[dict] = []
    for (obs_date, item_code, item, unit, category), g in df.groupby(
        keys, dropna=False
    ):
        n = len(g)
        price = round(float(g["price"].mean()), 4)
        row = {
            "observation_date": obs_date,
            "period_kind": "monthly",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "item_name": str(item).strip(),
            "price_local": price,
            "currency": _CURRENCY,
            "unit": str(unit).strip() or None,
            "source_url": _DASHBOARD_URL,
            "notes": (
                f"Category: {category}; PCBS item code {item_code}; "
                f"national avg of {n} quote(s) for the month"
                + (" (multiple quotes, averaged)" if n > 1 else "")
            ),
            "scrape_ts": ts,
            "item_code": item_code,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        row.pop("item_code")
        rows.append(row)

    logger.info("[%s] %d monthly rows (cutoff=%s)", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows) if rows else None
