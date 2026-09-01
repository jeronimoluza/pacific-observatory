"""Air Vanuatu -- domestic route "from" fares (one-way, per adult).

The domestic-airfare page renders a static grid of route cards
(`div.card__content-inner`), each holding an origin/destination pair and a
"FROM VUV <amount>*" one-way headline fare. There is no published
"effective from" date for these -- they are the site's current lowest-fare
snapshot, not a dated regulator tariff (contrast with the URA tariffs in
this same directory, which do carry an effective date) -- so this fetcher
uses `period_kind: snapshot` with `observation_date` = the day it ran,
per the fetcher_pattern.md guidance for tariff pages with no archive.

The trailing "*" on each fare is the site's own footnote marker (fare rules
apply); stripped before parsing. Fares are plain integers with thousands
commas (e.g. "17,600"), consistent with VUV having no minor unit.

curl_cffi with `impersonate="chrome124"` is required -- plain `requests`
against airvanuatu.com is fine too in practice, but chrome124 was what the
onboarding probe used and is kept here for consistency with the rest of the
skill's TLS guidance.
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup
from curl_cffi import requests as curl_requests

from prices.fetchers.utils import get_scrape_ts, make_hash

logger = logging.getLogger(__name__)

_URL = "https://www.airvanuatu.com/travel-info/domestic-airfare"
_COUNTRY = "Vanuatu"
_CURRENCY = "VUV"
_SOURCE_KEY = "vu_air_vanuatu_domestic"
_COICOP = "07.3.3.1"
_UNIT = "trip"
_IDENT = ["source_key", "observation_date", "item_name"]

_FARE_RE = re.compile(r"VUV\s*([\d,]+)")
_ROUTE_RE = re.compile(r"^([A-Za-z .'\-]+?)\s+to\s+([A-Za-z .'\-]+)$")


def _parse_cards(html: str) -> list[dict]:
    """Route cards come in pairs per direction: a "Round - trip" card and a
    "One-way" card, both matching the same "<origin> to <destination> FROM
    VUV <amount>*" text shape. Only the One-way card is emitted -- picking
    up both would silently double-count each route under the same
    item_name at two different price points.
    """
    soup = BeautifulSoup(html, "lxml")
    out = []
    for card in soup.select("div.card__content-inner"):
        text = card.get_text(" ", strip=True)
        if "One-way" not in text:
            continue
        route_m = _ROUTE_RE.match(text.split(" FROM")[0].strip())
        fare_m = _FARE_RE.search(text)
        if not route_m or not fare_m:
            continue
        origin, destination = route_m.group(1).strip(), route_m.group(2).strip()
        try:
            price = float(fare_m.group(1).replace(",", ""))
        except ValueError:
            continue
        out.append({"origin": origin, "destination": destination, "price": price})
    return out


def fetch_vu_air_vanuatu_domestic(cutoff: date) -> pd.DataFrame | None:
    resp = curl_requests.get(_URL, impersonate="chrome124", timeout=30)
    if resp.status_code != 200:
        logger.warning("[%s] HTTP %s from %s", _SOURCE_KEY, resp.status_code, _URL)
        return None

    parsed = _parse_cards(resp.text)
    if not parsed:
        logger.warning("[%s] No route/fare cards found at %s", _SOURCE_KEY, _URL)
        return None

    today = date.today()
    if today <= cutoff:
        return None

    rows = []
    for item in parsed:
        if item["price"] <= 0:
            continue
        row = {
            "observation_date": today.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "item_name": f"Domestic airfare, one-way – {item['origin']} to {item['destination']}",
            "price_local": item["price"],
            "currency": _CURRENCY,
            "unit": _UNIT,
            "coicop_code": _COICOP,
            "source_url": _URL,
            "notes": "Site's current lowest 'from' one-way fare, per adult; no published effective date.",
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    return pd.DataFrame(rows) if rows else None
