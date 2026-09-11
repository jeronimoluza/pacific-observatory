"""Mongolia NSO monthly selected prices of goods and services.

The National Statistics Office PxWeb table DT_NSO_0600_019V1 publishes monthly
prices for selected goods and services across Ulaanbaatar and aimags. The open
API returns JSON-stat2; as with the weekly NSO table, the server certificate
chain is incomplete from this environment, so requests disable verification for
data.1212.mn only.

`_COICOP_MAP` stamps a per-ITEM COICOP-2018 leaf on the emitted row. The
manifest deliberately stays `coicop_classification: classifier`: that is what
keeps this CSV in the classifier corpus at all -- `concatenate`'s
`_classifier_csv_map` ingests a fetcher's price_observations.csv ONLY for
`classifier` sources -- while the per-row code rides through as
`declared_coicop_codes` and short-circuits the head in `classify`
(`state=narrow_source`, confidence 1.0). Switching the manifest to
`source_curated` would drop this file from the corpus entirely.

Why a hand map here at all: 41 of this table's 43 item labels have no vector in
the embedding store, so the head never scores them (`state=unembedded` -- a
backlog item, not a model refusal) and 100% of this source's rows were absent
from the build. The declared-code branch runs BEFORE the unembedded branch, so
the map rescues those rows without waiting on an embed run.

Non-food rows (fuel, cement, soap, matches, firewood, haircuts, canteen meals)
are listed in `_NON_COICOP_ITEMS` and deliberately left with a null
`coicop_code` rather than dropped: under `classifier` a null is legitimate, the
downstream head already rejects them correctly, and dropping them would destroy
observations other consumers use. An item in NEITHER collection is a label the
map has not seen -- it is logged and also left null, never guessed at.
"""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd
import urllib3

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_API_URL = (
    "https://data.1212.mn/api/v1/en/NSO/Economy,%20environment/"
    "Consumer%20Price%20Index/DT_NSO_0600_019V1.px"
)
_SOURCE_URL = (
    "https://data.1212.mn/pxweb/en/NSO/"
    "NSO__Economy%2C%20environment__Consumer%20Price%20Index/"
    "DT_NSO_0600_019V1.px/"
)
_COUNTRY = "Mongolia"
_CURRENCY = "MNT"
_SOURCE_KEY = "mn_nso_monthly_selected_prices"
_UNIT = "togrogs"
_IDENT = ["source_key", "observation_date", "subnational_area", "item_name"]

# NSO item label -> COICOP-2018 leaf (src/data/prices/enrich/gold/
# coicop_leaves.txt). Labels are the PxWeb table's own English valueTexts.
# NSO item label (the PxWeb table's own English valueText) -> COICOP-2018
# leaf from src/data/prices/enrich/gold/coicop_leaves.txt.
_COICOP_MAP = {
    "Apples, yellow, kg, imported": "01.1.6.3.1",
    "Beef, with bones, kg": "01.1.2.2.1",
    "Beef, without bones, kg": "01.1.2.2.1",
    "Beer, 0.5 litre, bottled": "02.1.3.0",
    "Bread, sliced, pieces": "01.1.1.3.1",
    "Cabbage, kg, imported": "01.1.7.1.2",
    "Carrots, kg, imported": "01.1.7.4.1",
    "Chicken, thigh, kg, imported": "01.1.2.2.4",
    "Cigarettes, domestic": "02.3.0.1",
    "Cigarettes, imported": "02.3.0.1",
    "Dried grapes, kg, imported": "01.1.6.7.1",
    "Egg, pieces, дотоодын": "01.1.4.8.1",
    "Flour, first grade, packaged, kg, domestic": "01.1.1.2.1",
    "Flour, second grade, packaged, kg, domestic": "01.1.1.2.1",
    "Garlic, 1 bulb, imported": "01.1.7.4.2",
    "Goat meat, with bones, kg": "01.1.2.2.3",
    "Horse meat, with bones, kg": "01.1.2.2.6",
    "Milk, cows, plain, litre": "01.1.4.1.1",
    "Milk, packed, carton box ,1 litre, domestic": "01.1.4.1.1",
    "Millet, plain, kg, imported": "01.1.1.1.5",
    "Mutton, with bones, kg": "01.1.2.2.3",
    "Onion, kg, imported": "01.1.7.4.3",
    "Orange, kg, imported": "01.1.6.2.3",
    "Potato, domestic, kg": "01.1.7.5.1",
    "Rice, kg": "01.1.1.1.2",
    "Sugar, plain, kg, imported": "01.1.8.1.1",
    "Sweet pepper, kg, imported": "01.1.7.2.1",
    "Tomatoes, kg, imported": "01.1.7.2.4",
    "Vegetable oil, 1 litre, imported": "01.1.5.1.9",
    "Vodka, 0.75 litre": "02.1.1.0",
    "Yogurt, plain, 1 litre": "01.1.4.6.0",
}

# Non-food goods and services the same NSO table publishes alongside the food
# basket -- COICOP divisions 04/05/07/11/12. No division-01/02 leaf applies,
# so these stay uncoded rather than being force-fit or dropped.
_NON_COICOP_ITEMS = frozenset(
    {
        "Canteen food",
        "Cement, 1 bag",
        "Diesel fuel, 1 litre",
        "Dishwashing Liquid, 500 ml",
        "Fuelwood, one sack",
        "Gasoline, AI-92, 1 litre",
        "Laundry soap",
        "Matches, 10 box, ОХУ",
        "Mens haircuts",
        "Soap",
        "Washing powder, 800 g",
        "Womens haircuts, simple cuts",
    }
)


def _clean_label(value: str) -> str:
    return " ".join(str(value).split())


def _parse_month(label: str) -> date | None:
    try:
        ts = pd.to_datetime(f"{label}-01")
    except (TypeError, ValueError):
        return None
    return ts.date()


def _metadata(session) -> dict:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    resp = session.get(_API_URL, timeout=30, verify=False)
    resp.raise_for_status()
    return resp.json()


def _post(
    session,
    region_values: list[str],
    item_values: list[str],
    month_values: list[str],
) -> dict:
    query = {
        "query": [
            {
                "code": "Бүс",
                "selection": {"filter": "item", "values": region_values},
            },
            {
                "code": "Бараа, үйлчилгээ",
                "selection": {"filter": "item", "values": item_values},
            },
            {
                "code": "Сар",
                "selection": {"filter": "item", "values": month_values},
            },
        ],
        "response": {"format": "JSON-stat2"},
    }
    resp = session.post(_API_URL, json=query, timeout=90, verify=False)
    resp.raise_for_status()
    return resp.json()


def _dimension(meta: dict, code: str) -> dict:
    for variable in meta.get("variables", []):
        if variable.get("code") == code:
            return variable
    raise KeyError(f"NSO PxWeb dimension not found: {code}")


def fetch_mn_nso_monthly_selected_prices(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    meta = _metadata(session)

    regions = _dimension(meta, "Бүс")
    items = _dimension(meta, "Бараа, үйлчилгээ")
    months = _dimension(meta, "Сар")

    region_values = [str(v) for v in regions.get("values", []) if str(v).strip()]
    region_labels = {
        str(v): _clean_label(label)
        for v, label in zip(regions.get("values", []), regions.get("valueTexts", []))
    }
    item_values = [str(v) for v in items.get("values", []) if str(v).strip()]
    item_labels = {
        str(v): _clean_label(label)
        for v, label in zip(items.get("values", []), items.get("valueTexts", []))
    }

    selected_month_values: list[str] = []
    month_labels: dict[str, str] = {}
    for value, label in zip(months.get("values", []), months.get("valueTexts", [])):
        obs_date = _parse_month(str(label))
        if obs_date is None or obs_date <= cutoff:
            continue
        key = str(value)
        selected_month_values.append(key)
        month_labels[key] = obs_date.isoformat()

    if not region_values or not item_values or not selected_month_values:
        logger.info("[%s] no new cells after cutoff %s", _SOURCE_KEY, cutoff)
        return None

    payload = _post(session, region_values, item_values, selected_month_values)
    values = payload.get("value") or []
    size = payload.get("size") or [
        len(region_values),
        len(item_values),
        len(selected_month_values),
    ]
    if len(size) != 3:
        logger.warning("[%s] unexpected JSON-stat size: %s", _SOURCE_KEY, size)
        return None

    region_count, item_count, month_count = (int(size[0]), int(size[1]), int(size[2]))
    ts = get_scrape_ts()
    rows: list[dict] = []
    unmapped: set[str] = set()
    for region_idx in range(region_count):
        region_code = region_values[region_idx]
        subnational_area = region_labels.get(region_code)
        if not subnational_area:
            continue
        for item_idx in range(item_count):
            item_code = item_values[item_idx]
            item_name = item_labels.get(item_code)
            if not item_name:
                continue
            for month_idx in range(month_count):
                value_idx = (
                    region_idx * item_count * month_count
                    + item_idx * month_count
                    + month_idx
                )
                if value_idx >= len(values):
                    continue
                raw_price = values[value_idx]
                if raw_price is None:
                    continue
                try:
                    price = float(raw_price)
                except (TypeError, ValueError):
                    continue
                if price <= 0:
                    continue
                obs_date = month_labels.get(selected_month_values[month_idx])
                if not obs_date:
                    continue
                coicop = _COICOP_MAP.get(item_name)
                if coicop is None and item_name not in _NON_COICOP_ITEMS:
                    unmapped.add(item_name)
                row = {
                    "observation_date": obs_date,
                    "period_kind": "monthly",
                    "country": _COUNTRY,
                    "subnational_area": subnational_area,
                    "source_key": _SOURCE_KEY,
                    "coicop_code": coicop,
                    "item_name": item_name,
                    "price_local": price,
                    "currency": _CURRENCY,
                    "unit": _UNIT,
                    "source_url": _SOURCE_URL,
                    "notes": "NSO selected goods and services monthly price table",
                    "scrape_ts": ts,
                    "observation_hash": None,
                }
                row["observation_hash"] = make_hash(row, _IDENT)
                rows.append(row)

    if unmapped:
        logger.warning(
            "[%s] %d item label(s) in neither _COICOP_MAP nor _NON_COICOP_ITEMS, "
            "left uncoded for the classifier: %s",
            _SOURCE_KEY,
            len(unmapped),
            sorted(unmapped),
        )
    logger.info("[%s] parsed %d rows after cutoff %s", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows) if rows else None
