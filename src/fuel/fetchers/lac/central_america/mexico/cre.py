"""Mexico CRE daily retail gasoline and diesel fetcher.

Source: https://www.cne.gob.mx/ConsultaPrecios/GasolinasyDiesel/GasolinasyDiesel.html
XML feed: https://publicacionexterna.azurewebsites.net/publicaciones/prices

The Comisión Reguladora de Energía publishes a daily XML feed of every
service-station's reported price under Acuerdo A/041/2018. Refreshed
daily at 18:00 CST (GMT-6).

Schema (per <place>):
  <place place_id="...">
    <gas_price type="regular">22.95</gas_price>
    <gas_price type="premium">27.90</gas_price>
    <gas_price type="diesel">27.99</gas_price>
  </place>

Octane convention (AKI = (RON+MON)/2):
  regular ≥ 87 AKI (~91 RON), premium ≥ 91 AKI (~95 RON).

Strategy: aggregate ~13k station-level prices to a national daily mean
per product. The feed exposes only today's snapshot, so each successful
fetch emits one row per product dated today (UTC).
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone

import pandas as pd

from core.http import make_session

logger = logging.getLogger(__name__)

_URL = "https://publicacionexterna.azurewebsites.net/publicaciones/prices"
_COUNTRY = "Mexico"
_CURRENCY = "MXN"
_SOURCE_KEY = "mx_cre_daily"
_PRODUCTS = ("regular", "premium", "diesel")
_MIN_PRICE = 5.0  # MXN/L — anything below is clearly garbage (test/zero data)
_MAX_PRICE = 100.0  # MXN/L — soft upper bound to filter typos


def fetch_mx_cre(cutoff: date) -> pd.DataFrame | None:
    """Fetch Mexico CRE national mean retail gasoline + diesel prices (MXN/L)."""
    today = datetime.now(timezone.utc).date()
    if today <= cutoff:
        logger.info("[mx_cre] Already at cutoff %s (today=%s)", cutoff, today)
        return None

    session = make_session()
    try:
        resp = session.get(_URL, timeout=120)
        resp.raise_for_status()
    except Exception:
        logger.exception("[mx_cre] Failed to fetch CRE XML feed")
        return None

    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError:
        logger.exception("[mx_cre] Failed to parse XML")
        return None

    prices: dict[str, list[float]] = {p: [] for p in _PRODUCTS}
    for place in root.findall("place"):
        for gp in place.findall("gas_price"):
            ptype = (gp.attrib.get("type") or "").lower()
            if ptype not in prices or not gp.text:
                continue
            try:
                value = float(gp.text)
            except ValueError:
                continue
            if not (_MIN_PRICE <= value <= _MAX_PRICE):
                continue
            prices[ptype].append(value)

    rows: list[dict] = []
    for product in _PRODUCTS:
        values = prices[product]
        if not values:
            logger.warning("[mx_cre] No usable %s prices in feed", product)
            continue
        mean = sum(values) / len(values)
        rows.append(
            {
                "observation_date": today.strftime("%Y-%m-%d"),
                "country": _COUNTRY,
                "fuel_product": product,
                "price_local": round(mean, 4),
                "currency": _CURRENCY,
                "source_key": _SOURCE_KEY,
                "unit": "L",
            }
        )

    if not rows:
        return None

    out = pd.DataFrame(rows).sort_values("fuel_product").reset_index(drop=True)
    logger.info(
        "[mx_cre] %s: regular=%d premium=%d diesel=%d → %d rows",
        today,
        len(prices["regular"]),
        len(prices["premium"]),
        len(prices["diesel"]),
        len(out),
    )
    return out
