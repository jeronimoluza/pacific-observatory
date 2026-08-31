"""DGH Côte d'Ivoire — regulated maximum retail fuel/gas prices.

The Direction Generale des Hydrocarbures (DGH, Ministere des Mines, du
Petrole et de l'Energie) sets a mandatory maximum pump price each month for
Cote d'Ivoire, applied uniformly nationwide (an automatic price-adjustment
mechanism tied to international product costs). Every filling station must
display these prices; there is no retailer-level variation to scrape.

No stable government web page publishes a machine-readable feed of these
monthly decisions — energie.gouv.ci/petrole is a static informational page
with no communique archive, and the DGH's own press releases are PDFs
distributed to media rather than hosted on a fixed URL. Each month's
decision is instead confirmed via independent press coverage of the DGH
communique (koaci.com, financialafrik.com, fratmat.info, sikafinance.com —
cross-checked, all report identical figures). This mirrors the
evn_vn_tariff.py convention (Vietnam) of hardcoding an official regulator's
decision when no scrapable primary source exists.

_KNOWN_DECISIONS must be updated by hand each time the DGH revises prices
(historically monthly, sometimes held flat for several months).

COICOP split: Super sans plomb / Gasoil are vehicle fuel (07.2.2). Petrole
lampant (kerosene) is a household heating/lighting fuel (04.5.4). Gaz
butane bottles are household cooking gas (04.5.3).
"""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Cote d'Ivoire"
_CURRENCY = "XOF"
_SOURCE_KEY = "civ_dgh_fuel_tariff"
_SOURCE_URL = (
    "https://www.koaci.com/article/2026/07/31/cote-divoire/societe/"
    "cote-divoire-carburants-les-prix-a-la-pompe-augmentent-des-le-1er-aout-"
    "le-super-sp-a-905-fcfa-et-le-gasoil-a-725-fcfa_199113.html"
)
_IDENT = ["source_key", "observation_date", "item_name"]

# decision_date -> effective date of the DGH communique.
_KNOWN_DECISIONS: dict[str, list[dict]] = {
    "2026-08-01": [
        {
            "item_name": "Super sans plomb, pompe, prix maximum reglemente",
            "price_local": 905,
            "unit": "L",
            "coicop_code": "07.2.2",
        },
        {
            "item_name": "Gasoil moteur, pompe, prix maximum reglemente",
            "price_local": 725,
            "unit": "L",
            "coicop_code": "07.2.2",
        },
        {
            "item_name": "Petrole lampant, pompe, prix maximum reglemente",
            "price_local": 780,
            "unit": "L",
            "coicop_code": "04.5.4",
        },
        {
            "item_name": "Gaz butane, bouteille 6kg, prix maximum reglemente",
            "price_local": 2000,
            "unit": "bottle_6kg",
            "coicop_code": "04.5.3",
        },
        {
            "item_name": "Gaz butane, bouteille 12.5kg, prix maximum reglemente",
            "price_local": 5200,
            "unit": "bottle_12.5kg",
            "coicop_code": "04.5.3",
        },
        {
            "item_name": "Gaz butane, bouteille 28kg, prix maximum reglemente",
            "price_local": 13000,
            "unit": "bottle_28kg",
            "coicop_code": "04.5.3",
        },
    ],
}


# DGH issues a new maximum-price decision every month. _KNOWN_DECISIONS is
# hardcoded (no scrapable primary feed exists), so it goes stale silently
# unless someone is told. Warn once the newest entry is more than this many
# days behind the run date -- roughly 1.5 monthly cycles.
_STALE_AFTER_DAYS = 45


def _warn_if_stale(cutoff: date) -> None:
    latest = max(date.fromisoformat(d) for d in _KNOWN_DECISIONS)
    age = (cutoff - latest).days
    if age > _STALE_AFTER_DAYS:
        logger.warning(
            "[%s] _KNOWN_DECISIONS newest entry is %s, %d days before cutoff %s. "
            "DGH decides monthly, so at least one decision is almost certainly "
            "missing. Update _KNOWN_DECISIONS from energie.gouv.ci / press "
            "coverage before trusting this series.",
            _SOURCE_KEY,
            latest.isoformat(),
            age,
            cutoff.isoformat(),
        )


def fetch_civ_dgh_fuel_tariff(cutoff: date) -> pd.DataFrame | None:
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
                    "DGH (Direction Generale des Hydrocarbures) monthly maximum "
                    "retail price decision, effective nationwide from "
                    f"{decision_date_str}; confirmed across koaci.com, "
                    "financialafrik.com, fratmat.info, sikafinance.com."
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
