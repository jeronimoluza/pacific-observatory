"""FAOSTAT (via HDX) -- Central African Republic Consumer Price Indices, monthly.

FAO republishes its bulk-download CPI series per country on the Humanitarian
Data Exchange ("<iso3>-faostat-food-prices" dataset slug; CKAN resource name
"<iso3>_faostat_consumer_price_indices.csv"). Verified live 2026-09-01:
resolves via CKAN package_show, 453 rows, 3 `Item` series -- "Consumer
Prices, Food Indices (2015 = 100)", "Consumer Prices, General Indices
(2015 = 100)", and "Food price inflation" -- monthly, 2000-01 through
2026-01 (2026 partial year).

Genuinely independent of ICASEES: the ICASEES "IHPC mensuel" master
spreadsheet linked from icasees.org's own download page was found to be
UNTRUSTWORTHY during this pass -- its `docProps/core.xml` shows
`dc:creator: openpyxl`, `lastModifiedBy: hp`, created 2026-08-12, and its own
"Notes_Methodologiques" sheet narrates a "reconciliation applied ... at the
user's request" in the first person. That is not language a national
statistics office publishes about itself, and every one of ICASEES's
individual monthly bulletin PDFs (the only place the real IHPC would live)
returns HTTP 200 with 0 bytes -- the underlying files are missing from the
CMS. FAOSTAT's CAR CPI series, by contrast, is FAO's own bulk-download
product (fenixservices.fao.org), independently re-hosted on HDX with a
stable CKAN API -- not scraped from icasees.org at all.

Only the Food Indices series is emitted (coicop_code "01" -- Food and
non-alcoholic beverages, direct passthrough per COICOP 2018 division 01).
The General/all-items Indices series is dropped (no sanctioned "all-items"
COICOP sentinel yet, matching the convention in e.g.
sar/south_asia/maldives/ecpi_male.py). "Food price inflation" is a
year-on-year percentage-change series, not an index LEVEL -- dropped for
the same reason IND14 is excluded from any future ICASEES rebuild (a rate
is not an IndexObservation row).

index_base_period = "2015" per the series' own "(2015 = 100)" naming and
the `Note` column ("base year is 2015") on every row.

Test run (cutoff=2000-01-01): 75 rows (2020-01 .. 2026-03 Food Indices;
FAOSTAT's CAR bulk file itself only carries 2020 onward for this series,
despite the sibling General Indices series reaching back to 2000), 75
distinct observation_date, 0 duplicate observation_hash. Values range
118.0-156.0 (base 2015=100). Spot-checked against the raw CSV: 2025-01
Food Indices = 155.311892 (matches a fresh re-download).

coicop_classification: publisher_labeled -- FAOSTAT's own Item taxonomy
maps directly to a COICOP division.
"""

from __future__ import annotations

import io
import logging
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Central African Republic"
_SOURCE_KEY = "faostat_cpi_caf"
_CKAN = "https://data.humdata.org/api/3/action/package_show"
_DATASET_SLUG = "caf-faostat-food-prices"
_RESOURCE_NAME_HINT = "consumer_price_indices"
_INDEX_BASE_PERIOD = "2015"
_FOOD_ITEM = "Consumer Prices, Food Indices (2015 = 100)"
_IDENT = ["source_key", "observation_date", "coicop_code"]


def _find_resource_url(session) -> str | None:
    try:
        resp = session.get(_CKAN, params={"id": _DATASET_SLUG}, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] CKAN package_show failed: %s", _SOURCE_KEY, exc)
        return None
    if not data.get("success"):
        logger.warning("[%s] CKAN package_show unsuccessful", _SOURCE_KEY)
        return None
    for res in data["result"].get("resources", []):
        name = (res.get("name") or "").lower()
        if _RESOURCE_NAME_HINT in name and name.endswith(".csv"):
            return res.get("url")
    return None


def fetch_faostat_cpi_caf(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    csv_url = _find_resource_url(session)
    if not csv_url:
        logger.warning("[%s] consumer-price-indices resource not found", _SOURCE_KEY)
        return None

    try:
        resp = session.get(csv_url, timeout=60)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] CSV download failed: %s", _SOURCE_KEY, exc)
        return None

    try:
        df = pd.read_csv(io.StringIO(resp.text))
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] CSV parse failed: %s", _SOURCE_KEY, exc)
        return None

    df = df[df["Item"] == _FOOD_ITEM]
    if df.empty:
        logger.warning("[%s] no rows for item=%s", _SOURCE_KEY, _FOOD_ITEM)
        return None

    ts = get_scrape_ts()
    rows: list[dict] = []
    for _, r in df.iterrows():
        try:
            obs_date = date.fromisoformat(str(r["StartDate"])[:10])
        except (ValueError, TypeError):
            continue
        if obs_date <= cutoff:
            continue
        try:
            index_value = round(float(r["Value"]), 4)
        except (TypeError, ValueError):
            continue
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "monthly_avg",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": "01",
            "index_value": index_value,
            "index_base_period": _INDEX_BASE_PERIOD,
            "source_url": csv_url,
            "notes": f"FAOSTAT via HDX — {_FOOD_ITEM}, flag={r.get('Flag')}",
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    logger.info("[%s] %d rows (cutoff=%s)", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows) if rows else None
