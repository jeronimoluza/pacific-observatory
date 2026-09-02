"""Togo — regulated maximum retail fuel prices (CSFPPP).

The Comite de Suivi des Fluctuations des Prix des Produits Petroliers
(CSFPPP), under an interministerial decree (Economy, Finance, Energy
ministers), sets a mandatory maximum pump price applied uniformly
nationwide under Togo's automatic price-adjustment mechanism (decree
n°2010-146/PR of 26 November 2010). Every filling station displays the
same regulated price, so there is no retailer-level catalog to crawl --
this is a tariff/official-average-style source, not a retailer_sku
spider.

No stable Togolese government page publishes a machine-readable feed of
these decisions as a table (republicoftogo.com's own "Evolution du prix
des produits petroliers" page is a static 2023 article with no table and
no archive). Each decision is instead confirmed via the official
government portal (republiquetogolaise.tg, "Site officiel du Togo") and
cross-checked against independent press coverage (togofirst.com,
koaci.com). This mirrors the evn_vn_tariff.py / civ dgh_fuel_tariff.py
convention of hardcoding a regulator's decision when no scrapable primary
feed exists.

_KNOWN_DECISIONS must be updated by hand each time the CSFPPP revises
prices (historically irregular, sometimes held flat for many months).
"""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Togo"
_CURRENCY = "XOF"
_SOURCE_KEY = "tgo_csfppp_fuel_tariff"
_SOURCE_URL = (
    "https://www.republiquetogolaise.tg/gouvernance-economique/2705-11937-"
    "nouveaux-tarifs-pour-les-produits-petroliers-a-partir-de-ce-mercredi"
)
_IDENT = ["source_key", "observation_date", "item_name"]

# decision_date -> effective date of the interministerial decree.
_KNOWN_DECISIONS: dict[str, list[dict]] = {
    "2026-05-27": [
        {
            "item_name": "Super sans plomb, pompe, prix maximum reglemente",
            "price_local": 725,
            "unit": "L",
            "coicop_code": "07.2.2",
        },
        {
            "item_name": "Gasoil moteur, pompe, prix maximum reglemente",
            "price_local": 750,
            "unit": "L",
            "coicop_code": "07.2.2",
        },
        {
            "item_name": "Petrole lampant, pompe, prix maximum reglemente",
            "price_local": 1040,
            "unit": "L",
            "coicop_code": "04.5.4",
        },
        {
            "item_name": "Melange deux temps, pompe, prix maximum reglemente",
            "price_local": 811,
            "unit": "L",
            "coicop_code": "07.2.2",
        },
    ],
}


# CSFPPP revisions are irregular (sometimes held flat for months), so there
# is no fixed cycle to alarm on precisely -- but a decision this old is
# almost certainly stale. Warn past ~4 months.
_STALE_AFTER_DAYS = 120


def _warn_if_stale(cutoff: date) -> None:
    latest = max(date.fromisoformat(d) for d in _KNOWN_DECISIONS)
    age = (cutoff - latest).days
    if age > _STALE_AFTER_DAYS:
        logger.warning(
            "[%s] _KNOWN_DECISIONS newest entry is %s, %d days before cutoff %s. "
            "Check republiquetogolaise.tg / togofirst.com for a newer CSFPPP "
            "communique before trusting this series.",
            _SOURCE_KEY,
            latest.isoformat(),
            age,
            cutoff.isoformat(),
        )


def fetch_tgo_csfppp_fuel_tariff(cutoff: date) -> pd.DataFrame | None:
    _warn_if_stale(cutoff)
    rows: list[dict] = []
    scrape_ts = get_scrape_ts()

    for decision_date_str, items in _KNOWN_DECISIONS.items():
        obs_date = date.fromisoformat(decision_date_str)
        if obs_date <= cutoff:
            continue
        for item in items:
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "effective_from",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "coicop_code": item["coicop_code"],
                "item_name": item["item_name"],
                "price_local": float(item["price_local"]),
                "currency": _CURRENCY,
                "unit": item["unit"],
                "source_url": _SOURCE_URL,
                "notes": (
                    "CSFPPP (Comite de Suivi des Fluctuations des Prix des "
                    "Produits Petroliers) interministerial maximum retail "
                    "price decree, effective nationwide from "
                    f"{decision_date_str}; confirmed on republiquetogolaise.tg "
                    "(official government portal), cross-checked against "
                    "togofirst.com and koaci.com."
                ),
                "scrape_ts": scrape_ts,
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

    if not rows:
        logger.info(
            "[%s] all decision dates <= cutoff %s -- nothing new", _SOURCE_KEY, cutoff
        )
        return None

    return pd.DataFrame(rows)
