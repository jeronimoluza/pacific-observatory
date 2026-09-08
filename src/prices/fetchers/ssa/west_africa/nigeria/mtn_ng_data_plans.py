"""MTN Nigeria — prepaid data-bundle tariffs.

Scrapes the SSR HTML data-plans listing page at mtn.ng. Each bundle is
rendered as a `_card-deal prepaid-deal` div containing a sub-heading
(validity period, e.g. "Daily Plans"), a title (data allowance, e.g.
"75MB"), and a price block (`_card-deal__price-amount`, e.g. "75"). No JS
execution required -- the tariff table is present in the raw server
response.

GOTCHA: the card also carries a `data-price=200` attribute on the wrapping
div that is constant across every card on the page (a stale/default JS
filter attribute, not the display price) -- do not use it. The real price
is the text inside `_card-deal__price-amount`.

COICOP 08.3.2.0 (mobile communication services).

Source URL: https://www.mtn.ng/data/data-plans/
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://www.mtn.ng/data/data-plans/"
_COUNTRY = "Nigeria"
_CURRENCY = "NGN"
_SOURCE_KEY = "mtn_ng_data_plans"
_COICOP_CODE = "08.3.2.0"
_IDENT = ["source_key", "observation_date", "item_name"]

_CARD_RE = re.compile(r'(?=<div\s+class="?_card-deal prepaid-deal)')
_TITLE_RE = re.compile(r'_card-deal__title">([^<]+)<')
_SUBHEAD_RE = re.compile(r'_card-deal__sub-heading">\s*([^<]+)<')
_PRICE_RE = re.compile(r"_card-deal__price-amount>\s*([\d,\.]+)")
_HREF_RE = re.compile(r"href=([^\s>]+)")


def _extract_bundles(html: str, obs_date: date, source_url: str) -> list[dict]:
    rows: list[dict] = []
    cards = _CARD_RE.split(html)[1:]
    for card in cards:
        title_m = _TITLE_RE.search(card)
        price_m = _PRICE_RE.search(card)
        if not title_m or not price_m:
            continue
        data_amount = title_m.group(1).strip()
        price_local = float(price_m.group(1).replace(",", ""))
        sub_m = _SUBHEAD_RE.search(card)
        validity = sub_m.group(1).strip() if sub_m else "unknown"
        href_m = _HREF_RE.search(card)
        href = href_m.group(1) if href_m else source_url
        row_url = href if href.startswith("http") else source_url

        item_name = f"MTN Nigeria prepaid data bundle, {data_amount}, {validity}"
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": _COICOP_CODE,
            "item_name": item_name,
            "price_local": price_local,
            "currency": _CURRENCY,
            "unit": "bundle",
            "source_url": row_url,
            "notes": f"validity={validity}",
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)
    return rows


def fetch_mtn_ng_data_plans(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    obs_date = date.today()
    if obs_date <= cutoff:
        return None

    resp = session.get(_URL, timeout=30)
    if resp.status_code != 200:
        logger.warning("[%s] HTTP %d for %s", _SOURCE_KEY, resp.status_code, _URL)
        return None

    rows = _extract_bundles(resp.text, obs_date, _URL)
    if not rows:
        logger.warning("[%s] No bundles parsed from %s", _SOURCE_KEY, _URL)
        return None

    df = pd.DataFrame(rows)
    dup_count = int(df["observation_hash"].duplicated().sum())
    if dup_count:
        logger.warning(
            "[%s] %d duplicate observation_hash rows before de-dup",
            _SOURCE_KEY,
            dup_count,
        )
        df = df.drop_duplicates(subset="observation_hash")
    return df
