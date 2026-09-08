"""Mytel (Myanmar telecom) -- VAS (value-added service) data/voice/combo packages.

mytel.com.mm is an Angular SPA -- the static shell ships almost no content
(confirmed 2026-09-06: 4.8KB response, no product data at all, matching the
Myanmar discovery inventory's "near-empty body" note). The catalog lives
behind an open JSON API discovered via a Playwright network trace of the
homepage: `POST https://apis.mytel.com.mm/mytel-website/api/v1/get-vas-package`
with an empty JSON body (`{}`) and no auth headers -- plain `requests` works
once `Origin`/`Referer` are set to `https://mytel.com.mm` (curl without
those headers 405s, i.e. the reverse-proxy/CDN in front of the API
distinguishes on those headers, not on a security token). This is the
"Playwright to discover, plain HTTP to scrape" pattern.

Response shape: `{"success": true, "result": [{"vasGroupName": ...,
"vasPackage": [{...}]}]}` -- a list of category groups, each with a list of
package dicts. 26 packages across 6 groups confirmed live 2026-09-06
(Entertainment Packs, Data pack, Just For You, Combo, Voice, International).

No currency field in the payload -- Kyat is the only currency Mytel prices
in for domestic plans (confirmed against the site's own MMK-denominated
values, e.g. 999, 1999); hardcoded MMK per countries.yaml, not parsed from
anywhere in the response.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://apis.mytel.com.mm/mytel-website/api/v1/get-vas-package"
_COUNTRY = "Myanmar"
_CURRENCY = "MMK"
_SOURCE_KEY = "mm_mytel_vas_packages"
_COICOP = "08.3.2.0"
_IDENT = ["source_key", "item_name", "price_local"]

_HEADERS = {
    "Origin": "https://mytel.com.mm",
    "Referer": "https://mytel.com.mm/",
    "Content-Type": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}


def fetch_mm_mytel_vas_packages(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    resp = session.post(_URL, headers=_HEADERS, json={}, timeout=30)
    resp.raise_for_status()
    payload = resp.json()

    groups = payload.get("result") or []
    if not groups:
        logger.warning("[%s] No VAS groups found at %s", _SOURCE_KEY, _URL)
        return None

    observation_date = datetime.now(timezone.utc).date()
    if observation_date <= cutoff:
        return None

    rows = []
    for group in groups:
        group_name = group.get("vasGroupName") or "Uncategorised"
        for pkg in group.get("vasPackage") or []:
            name = pkg.get("name")
            price_raw = pkg.get("price")
            if not name or price_raw in (None, ""):
                continue
            try:
                price = float(str(price_raw).replace(",", ""))
            except ValueError:
                continue
            if price <= 0:
                continue

            validity = pkg.get("validity")
            item_name = f"{group_name} – {name}"
            if validity:
                item_name += f" ({validity} day(s))"

            row = {
                "observation_date": observation_date.isoformat(),
                "period_kind": "snapshot",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "item_name": item_name,
                "price_local": price,
                "currency": _CURRENCY,
                "unit": "plan",
                "coicop_code": _COICOP,
                "source_url": _URL,
                "notes": pkg.get("descriptionEn") or "",
                "scrape_ts": get_scrape_ts(),
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

    return pd.DataFrame(rows) if rows else None
