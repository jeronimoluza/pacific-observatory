"""National Bank of Ukraine (bank.gov.ua) official UAH exchange rates.

Daily official rates for a curated set of reference currencies, used as the
FX denominator for real-exchange-rate / PPP work. Uses NBU's date-range
endpoint (one request per currency for the whole backfill window).

analytical_role: aggregate_proxy.
NOTE ON COICOP: an FX rate is a denominator series, not a consumption price —
it has no COICOP code. ``coicop_code`` is intentionally left null here. This is
a deliberate exception to the "drop null coicop" rule, which targets
consumption-priced sources; FX is a reference series with no basket position.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_RANGE_URL = "https://bank.gov.ua/NBU_Exchange/exchange_site"
_COUNTRY = "Ukraine"
_CURRENCY = "UAH"  # price_local is denominated in UAH
_SOURCE_KEY = "ua_nbu_fx"

# Reference currencies most relevant to UA trade / RER analysis.
_CURRENCIES = ("USD", "EUR", "GBP", "PLN", "CNY")

_IDENT = ["source_key", "observation_date", "item_name"]


def _fetch_currency(session, cc: str, start: date, end: date) -> list[dict]:
    params = {
        "start": start.strftime("%Y%m%d"),
        "end": end.strftime("%Y%m%d"),
        "valcode": cc,
        "sort": "exchangedate",
        "order": "asc",
        "json": "",
    }
    resp = session.get(_RANGE_URL, params=params, timeout=30)
    resp.raise_for_status()
    payload = resp.json()

    rows: list[dict] = []
    for entry in payload:
        # exchangedate is DD.MM.YYYY
        d, mo, y = entry["exchangedate"].split(".")
        obs_date = f"{y}-{mo}-{d}"
        units = entry.get("units") or 1
        rate = float(entry["rate"]) / float(units)  # UAH per 1 unit of cc
        if not 0 < rate < 100000:
            logger.warning("NBU FX: rate %.4f out of bounds (%s %s)", rate, cc, obs_date)
            continue
        row = {
            "observation_date": obs_date,
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": None,  # FX reference series — see module docstring
            "item_name": f"UAH per {cc}",
            "price_local": round(rate, 6),
            "currency": _CURRENCY,
            "unit": f"1 {cc}",
            "source_url": f"{_RANGE_URL}?valcode={cc}&json",
            "notes": entry.get("enname"),
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)
    return rows


def fetch_ua_nbu_fx(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    start = cutoff + timedelta(days=1)
    end = date.today()
    if start > end:
        return None

    rows: list[dict] = []
    for cc in _CURRENCIES:
        try:
            rows.extend(_fetch_currency(session, cc, start, end))
        except Exception:  # noqa: BLE001 — one bad currency shouldn't kill the run
            logger.exception("NBU FX: failed to fetch %s", cc)
    return pd.DataFrame(rows) if rows else None
