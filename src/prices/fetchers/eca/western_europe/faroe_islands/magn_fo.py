"""Magn (Faroe Islands) -- P/F Magn's own published retail fuel price schedule.

Magn is one of the two dominant fuel retailers in the Faroe Islands (the other
being Effo). https://magn.fo/oljuprisir ("oil prices") publishes a dated
history of the company's per-litre pump price at its own stations
("Pr. litur a Magn-stodum") going back to 2024-07-26, one block per price
change (~100 blocks observed 2026-09-28, roughly weekly cadence). Each block
gives several product rows (road fuel, boat fuel, bulk heating oil); this
fetcher takes only the two unambiguous road-fuel rows sold at the company's
own filling stations -- "Bensin 95 E10" (regular unleaded) and "Diesel" --
both COICOP 07.2.2 (fuels and lubricants for personal transport). Boat fuel
("Batadiesel"/"Batadiesel Pluss") and bulk-delivered heating oil
("Gassolja", sold per 1000 litres under a separate table) are deliberately
excluded: mixing them in under 07.2.2 would misclassify marine/heating fuel
as a road-transport price.

No anti-bot layer observed (plain `requests` returns 200, no impersonation
needed). Page text renders month names in English ("26 September 2026")
even though the surrounding page chrome is Faroese, so date parsing uses
`%d %B %Y` directly -- no month-name translation table required.

analytical_role: tariff, coicop_classification: source_curated -- the
fetcher assigns the COICOP code itself; the site is a single-retailer price
schedule, not a per-SKU catalogue, so it does not go through the classifier.
"""

from __future__ import annotations

import logging
from datetime import date, datetime

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Faroe Islands"
_SOURCE_KEY = "magn_fo"
_URL = "https://magn.fo/oljuprisir"
_CURRENCY = "DKK"
_COICOP_CODE = "07.2.2"
_IDENT = ["source_key", "observation_date", "item_name"]

# Only these two rows are road fuel sold at Magn's own stations. Everything
# else in a block (boat fuel, bulk heating oil) is out of scope for this code.
_ITEMS = {"Bensin 95 E10", "Diesel"}


def _parse_block(block) -> tuple[date | None, list[dict]]:
    day = block.select_one(".date-day")
    month = block.select_one(".date-month")
    year = block.select_one(".date-year")
    if not (day and month and year):
        return None, []
    try:
        obs_date = datetime.strptime(
            f"{day.get_text(strip=True)} {month.get_text(strip=True)} {year.get_text(strip=True)}",
            "%d %B %Y",
        ).date()
    except ValueError:
        logger.warning("[%s] unparsable date block, skipping", _SOURCE_KEY)
        return None, []

    out = []
    for row in block.select(".pricing_row"):
        feats = row.select(".pricing_feature div")
        nums = row.select(".pricing_number")
        if not feats or not nums:
            continue
        item_name = feats[0].get_text(strip=True)
        if item_name not in _ITEMS:
            continue
        try:
            price = float(nums[0].get_text(strip=True))
        except ValueError:
            continue
        if price <= 0:
            continue
        out.append({"item_name": item_name, "price_local": price})
    return obs_date, out


def fetch_magn_fo(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    try:
        resp = session.get(_URL, timeout=30)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] page fetch failed: %s", _SOURCE_KEY, exc)
        return None

    soup = BeautifulSoup(resp.text, "lxml")
    blocks = soup.select(".pricing_component")
    if not blocks:
        logger.warning("[%s] no pricing_component blocks found", _SOURCE_KEY)
        return None

    ts = get_scrape_ts()
    rows: list[dict] = []
    for block in blocks:
        obs_date, items = _parse_block(block)
        if obs_date is None or obs_date <= cutoff:
            continue
        for item in items:
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "effective_from",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "coicop_code": _COICOP_CODE,
                "item_name": item["item_name"],
                "price_local": item["price_local"],
                "currency": _CURRENCY,
                "unit": "L",
                "effective_from": obs_date.isoformat(),
                "source_url": _URL,
                "scrape_ts": ts,
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

    if not rows:
        logger.info("[%s] no new rows past cutoff=%s", _SOURCE_KEY, cutoff)
        return None

    logger.info("[%s] %d rows (cutoff=%s)", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows)
