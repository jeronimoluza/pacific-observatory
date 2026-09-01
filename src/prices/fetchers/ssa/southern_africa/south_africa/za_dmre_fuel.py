"""South Africa — DMRE-regulated monthly retail/wholesale fuel prices.

The Department of Mineral Resources and Energy (DMRE) sets South Africa's
petrol pump price and diesel/paraffin wholesale price under the Petroleum
Products Act via a monthly Government Gazette notice (basic fuels price
formula), split by two pricing zones: Coastal and Inland (Gauteng/inland
depots carry a higher transport-recovery margin).

DMRE's own web presence (dmre.gov.za, energy.gov.za) is currently
unreachable for automated collection: `dmre.gov.za` times out at the TCP
level and `energy.gov.za` serves an expired-certificate 503 -- both
confirmed with `curl_cffi impersonate=chrome124` and cross-checked against
8.8.8.8/1.1.1.1 (DNS resolves fine to real gov.za IPs; the *servers* are
down/misconfigured, not a sandbox DNS lie). No stable Gazette-archive page
was found either. The Automobile Association of South Africa (AA), a
century-old motoring body, republishes the identical DMRE-gazetted monthly
schedule as its own public "fuel pricing" tool -- this mirrors the
`civ_dgh_fuel_tariff.py` convention (Cote d'Ivoire) of taking an official
regulator's decision from a reliable secondary publisher when the primary
source has no scrapable feed. The AA page's own fuel-price-calculator
widget calls a WordPress AJAX action (`getFuelPricesStart`) which is a
plain, unauthenticated JSON endpoint (no cookies/session needed) and
returns the FULL 2008-present monthly history in one call -- verified live
2026-09-01, 224 monthly records from 2008-01-02 to 2026-08-04.

Grades/products covered (all vehicle/engine fuel, single COICOP class):
- Petrol 93 octane unleaded (coastal + inland)
- Petrol 95 octane unleaded (coastal + inland)
- Petrol LRP (lead-replacement petrol) -- 95 octane on the coast, 93 octane
  inland, matching the source's own field pairing (lrp95Coast/lrp93Inland;
  no lrp93Coast/lrp95Inland fields exist in the payload)
- Diesel 500ppm (0.05% sulphur) (coastal + inland)
- Diesel 50ppm (0.005% sulphur) (coastal + inland)

All 10 series are pump/wholesale fuel prices -> COICOP 07.2.2 (fuels and
lubricants for personal transport equipment). Illuminating paraffin
(04.5.4) is NOT in this payload -- Stats SA / DMRE publish it separately
and it was not found on this endpoint, so it is not emitted here.

The endpoint also returns an `upcoming` key (the next month's
already-gazetted price, published a few days ahead of its effective date).
Deliberately NOT emitted here to keep `observation_date` always <= the
fetcher's run date; it will appear in `prices.fuelPrices` on its own once
its effective date has passed and AA rolls it into history.
"""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd
from curl_cffi import requests as curl_requests

from prices.fetchers.utils import get_scrape_ts, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "South Africa"
_CURRENCY = "ZAR"
_SOURCE_KEY = "za_dmre_fuel"
_SOURCE_URL = "https://www.aa.co.za/fuel-pricing"
_AJAX_URL = "https://aa.co.za/wp-admin/admin-ajax.php"
_IDENT = ["source_key", "observation_date", "item_name", "subnational_area"]

# payload field -> (item_name, subnational_area)
_FIELD_MAP: dict[str, tuple[str, str]] = {
    "unleaded93Coast": ("Petrol 93 octane unleaded, pump price", "Coastal"),
    "unleaded93Inland": ("Petrol 93 octane unleaded, pump price", "Inland"),
    "unleaded95Coast": ("Petrol 95 octane unleaded, pump price", "Coastal"),
    "unleaded95Inland": ("Petrol 95 octane unleaded, pump price", "Inland"),
    "lrp95Coast": ("Petrol 95 octane LRP (lead-replacement), pump price", "Coastal"),
    "lrp93Inland": ("Petrol 93 octane LRP (lead-replacement), pump price", "Inland"),
    "diesel500Coast": ("Diesel 500ppm (0.05% sulphur), wholesale price", "Coastal"),
    "diesel500Inland": ("Diesel 500ppm (0.05% sulphur), wholesale price", "Inland"),
    "diesel50Coast": ("Diesel 50ppm (0.005% sulphur), wholesale price", "Coastal"),
    "diesel50Inland": ("Diesel 50ppm (0.005% sulphur), wholesale price", "Inland"),
}


def fetch_za_dmre_fuel(cutoff: date) -> pd.DataFrame | None:
    resp = curl_requests.post(
        _AJAX_URL,
        data={"action": "getFuelPricesStart"},
        impersonate="chrome124",
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()
    if not payload or not payload[0].get("prices", {}).get("ok"):
        logger.warning("[%s] unexpected payload shape: %r", _SOURCE_KEY, payload)
        return None

    fuel_prices = payload[0]["prices"]["fuelPrices"]
    # The source occasionally carries two raw records for the same
    # updatedOn date (confirmed live 2026-09-01: 2022-04-06 has an exact
    # duplicate id=11/id=12; 2018-10-03 has a near-duplicate id=283/id=284
    # differing by a transposed digit in two diesel fields -- a data
    # correction in AA's own DB, not a real second gazette notice). Keep
    # only the highest `id` per date so a correction supersedes the value
    # it replaced instead of both landing in the output with a colliding
    # observation_hash.
    by_date: dict[str, dict] = {}
    for rec in fuel_prices:
        d = rec.get("updatedOn")
        if d is None:
            continue
        if d not in by_date or rec.get("id", 0) > by_date[d].get("id", 0):
            by_date[d] = rec

    scrape_ts = get_scrape_ts()
    rows: list[dict] = []

    for rec in by_date.values():
        try:
            obs_date = date.fromisoformat(rec["updatedOn"])
        except (KeyError, ValueError):
            continue
        if obs_date <= cutoff:
            continue
        for field, (item_name, zone) in _FIELD_MAP.items():
            raw = rec.get(field)
            if raw in (None, ""):
                continue
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "effective_from",
                "country": _COUNTRY,
                "subnational_area": zone,
                "source_key": _SOURCE_KEY,
                "coicop_code": "07.2.2",
                "item_name": item_name,
                "price_local": float(raw),
                "currency": _CURRENCY,
                "unit": "L",
                "source_url": _SOURCE_URL,
                "notes": (
                    "DMRE (Dept. of Mineral Resources and Energy) monthly "
                    "regulated fuel price, republished by the Automobile "
                    "Association of South Africa (AA) fuel-pricing tool; "
                    f"zone={zone}."
                ),
                "scrape_ts": scrape_ts,
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

    if not rows:
        logger.info(
            "[%s] all observation dates <= cutoff %s -- nothing new",
            _SOURCE_KEY,
            cutoff,
        )
        return None

    return pd.DataFrame(rows)
