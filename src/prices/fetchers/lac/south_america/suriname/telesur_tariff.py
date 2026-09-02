"""Telesur (Suriname) -- prepaid mobile-internet bundle tariffs.

NOT a duplicate of the existing `telesur_sr` spider. `telesur_sr` is a
Scrapy spider hitting Telesur's WooCommerce Store API on
www.telesur.sr/wp-json/wc/store/v1/products -- it scrapes Telesur's
DEVICE/ELECTRONICS SHOP (phones, chargers, cases, routers), channel:
electronics, analytical_role: retailer_sku. This module is a plain HTML
scrape of a completely different page (www.telesur.sr/prepaid/, the
telecom-tariff/plan page, not the shop), a different analytical_role
(tariff, not retailer_sku), and a different observation shape (fixed
bundle plans, not SKU catalog rows). The two sources do not share any
product_id namespace -- the shop's items are physical goods with
Store-API SKUs; this fetcher's items are prepaid data-bundle names
regexed straight out of page copy.

The "Mobiel internet" section of /prepaid/ lists a small, stable set of
prepaid mobile-data bundles as `<strong>DURATION</strong><br/>SRD
PRICE</p> ... <h3>DATA AMOUNT</h3>` card fragments (confirmed live
2026-09-01: 6 bundles, 150MB/12u through 1200GB/30d-5G). No effective
date is stated on the page, so period_kind is "snapshot".
"""

from __future__ import annotations

import html
import logging
import re
from datetime import date, datetime, timezone

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://www.telesur.sr/prepaid/"
_COUNTRY = "Suriname"
_CURRENCY = "SRD"
_SOURCE_KEY = "sr_telesur_tariff"
_COICOP = "08.3"  # Telephone and telefax services

_IDENT = ["source_key", "observation_date", "item_name"]

_SECTION_MARKER = ">Mobiel internet<"
_BUNDLE_RE = re.compile(
    r"<strong>([^<]+)</strong><br\s*/?>\s*SRD\s*([0-9.,]+)\s*</p>.*?<h3>([^<]+)</h3>",
    re.DOTALL,
)


def fetch_sr_telesur_tariff(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    resp = session.get(_URL, timeout=30)
    resp.raise_for_status()

    obs_date = datetime.now(timezone.utc).date()
    if obs_date <= cutoff:
        return None

    start = resp.text.find(_SECTION_MARKER)
    if start < 0:
        logger.warning(
            "[%s] 'Mobiel internet' section not found at %s", _SOURCE_KEY, _URL
        )
        return None
    section = resp.text[start : start + 30000]
    next_section = section.find("<h2", 10)
    if next_section > 0:
        section = section[:next_section]

    matches = _BUNDLE_RE.findall(section)
    if not matches:
        logger.warning("[%s] No bundle cards matched at %s", _SOURCE_KEY, _URL)
        return None

    rows = []
    for duration, price_str, data_amount in matches:
        duration = html.unescape(duration).strip()
        data_amount = html.unescape(data_amount).strip()
        try:
            price = float(price_str.replace(",", "."))
        except ValueError:
            continue
        item_name = f"Mobiel Internet {duration} ({data_amount})"
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "item_name": item_name,
            "price_local": price,
            "currency": _CURRENCY,
            "unit": "bundle",
            "coicop_code": _COICOP,
            "source_url": _URL,
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    return pd.DataFrame(rows) if rows else None
