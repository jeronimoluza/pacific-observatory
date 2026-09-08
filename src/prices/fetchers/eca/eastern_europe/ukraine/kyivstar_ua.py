"""Kyivstar (Ukraine) -- retail mobile tariff plans.

Discovery lead (wave 3, bare hostname `kyivstar.ua`). Kyivstar is Ukraine's
largest mobile operator; the public `/tariffs` page is a Next.js SSR page
that embeds the full tariff catalogue as structured JSON in a
`<script id="__NEXT_DATA__" type="application/json">` block -- no separate
API call, no Playwright needed (plain `requests` clears it, no WAF).

Path to the tariff array inside the payload:
`props.pageProps.data.pageData.dynamicZone[2].tariffs` -- found by
recursively searching the deserialized JSON for objects carrying an
`externalCode` + `productPrice` shape (the array index `[2]` is a
CMS-authored page-block position and could shift on a redesign; the
recursive search is what actually locates the array, the index is just
documentation of what was observed 2026-09-06).

Each tariff's advertised price lives at
`productPrice.priceVariants[0].recurringCharge` -- `{"price": 370,
"period": {"id": "P_1M", ...}, "dailyAverage": ...}`. `regularPrice` /
`price` at the priceVariant's top level are always null; do not use them.
Currency name comes from `productPrice.currency.name.uk` ("грн" -> UAH).

Billing periods observed: `P_1M` (month, the default retail cadence),
`P_4W` (4 weeks -- the "Дитячий"/Kids plan), `P_1Y` (year -- its annual
variant). `unit` is set per-plan from this period rather than assumed
uniformly monthly, since a 4-week or annual price divided as if monthly
would silently misstate the tariff.

All plans are COICOP 08.3.2.0 (mobile telecom service subscriptions) --
single-value `_COICOP_MAP`, `coicop_classification: source_curated`.

7 plans observed live 2026-09-06: ВСЕ РАЗОМ Легкий (370 UAH/month), Крутий
(450), Топовий Контракт (750), Комфорт (220), Дитячий (270/4 weeks),
Дитячий Річний (2000/year), СуперГіг (500/month).
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timezone

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://kyivstar.ua/tariffs"
_COUNTRY = "Ukraine"
_CURRENCY = "UAH"
_SOURCE_KEY = "ua_kyivstar_tariffs"
_COICOP = "08.3.2.0"
_IDENT = ["source_key", "observation_date", "item_name"]

_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.DOTALL
)

_PERIOD_UNIT = {
    "P_1M": "month",
    "P_4W": "4 weeks",
    "P_1Y": "year",
    "P_1D": "day",
}


def _find_tariff_arrays(obj) -> list[list[dict]]:
    """Recursively find arrays of tariff-shaped dicts (externalCode + productPrice)."""
    found = []
    if isinstance(obj, dict):
        for v in obj.values():
            found.extend(_find_tariff_arrays(v))
    elif isinstance(obj, list):
        if obj and all(
            isinstance(x, dict) and "externalCode" in x and "productPrice" in x
            for x in obj
        ):
            found.append(obj)
        else:
            for v in obj:
                found.extend(_find_tariff_arrays(v))
    return found


def fetch_ua_kyivstar_tariffs(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    resp = session.get(_URL, timeout=30)
    resp.raise_for_status()

    m = _NEXT_DATA_RE.search(resp.text)
    if not m:
        logger.warning("kyivstar_ua: no __NEXT_DATA__ found on %s", _URL)
        return None
    try:
        data = json.loads(m.group(1))
    except ValueError:
        logger.warning("kyivstar_ua: unparseable __NEXT_DATA__ on %s", _URL)
        return None

    arrays = _find_tariff_arrays(data)
    if not arrays:
        logger.warning("kyivstar_ua: no tariff array found in payload")
        return None
    tariffs = max(arrays, key=len)

    obs_date = datetime.now(timezone.utc).date()
    if obs_date <= cutoff:
        logger.info("kyivstar_ua: obs_date %s <= cutoff %s — no new rows", obs_date, cutoff)
        return None

    scrape_ts = get_scrape_ts()
    rows: list[dict] = []
    for tf in tariffs:
        try:
            name = tf["name"]["uk"]
            variant = tf["productPrice"]["priceVariants"][0]
            charge = variant.get("recurringCharge") or {}
            price = charge.get("price")
            period_id = (charge.get("period") or {}).get("id")
        except (KeyError, IndexError, TypeError):
            continue
        if price is None or price <= 0:
            continue
        unit = _PERIOD_UNIT.get(period_id, "month")
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": _COICOP,
            "item_name": f"Kyivstar {name}",
            "price_local": float(price),
            "currency": _CURRENCY,
            "unit": unit,
            "source_url": _URL,
            "scrape_ts": scrape_ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    if not rows:
        logger.warning("kyivstar_ua: no tariff rows extracted from %s", _URL)
        return None
    return pd.DataFrame(rows)
