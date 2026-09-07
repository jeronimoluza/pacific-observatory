"""Singtel Singapore prepaid monthly data-plan tariffs."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://www.singtel.com/personal/products-services/mobile/prepaid-plans/data-plans"
_COUNTRY = "Singapore"
_CURRENCY = "SGD"
_SOURCE_KEY = "sg_singtel_prepaid"
_COICOP = "08.3.0"
_UNIT = "package"
_IDENT = ["source_key", "observation_date", "item_name"]

_PLAN_RE = re.compile(
    r"^\$([0-9]+(?:\.[0-9]+)?)\s+((?:5G\+\s+)?(?:Enhanced\s+)?Ultimate Plan)$"
)


def fetch_sg_singtel_prepaid(cutoff: date) -> pd.DataFrame | None:
    obs_date = datetime.now(timezone.utc).date()
    if obs_date <= cutoff:
        return None

    session = get_session()
    resp = session.get(_URL, timeout=45)
    resp.raise_for_status()
    text = BeautifulSoup(resp.text, "html.parser").get_text("\n", strip=True)

    rows: list[dict] = []
    seen: set[str] = set()
    ts = get_scrape_ts()
    for line in text.splitlines():
        m = _PLAN_RE.match(line.strip())
        if not m:
            continue
        price = float(m.group(1))
        plan_name = m.group(2)
        item_name = f"Singtel prepaid {plan_name}, ${price:g}"
        if item_name in seen:
            continue
        seen.add(item_name)
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": _COICOP,
            "item_name": item_name,
            "price_local": round(price, 2),
            "currency": _CURRENCY,
            "unit": _UNIT,
            "source_url": _URL,
            "notes": "4-week validity; official Singtel prepaid monthly data plan",
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    logger.info("[%s] %d rows", _SOURCE_KEY, len(rows))
    return pd.DataFrame(rows) if rows else None
