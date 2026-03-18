"""Hong Kong Consumer Council fuel price fetchers.

Two sources sharing a common CSV download helper:
  1. Petrol (regular unleaded gasoline) — daily by company.
  2. Diesel — daily by company.
"""

from __future__ import annotations

# ruff: noqa: E402
SOURCE_META = [
    {
        "fetcher_fn": "fetch_hk_consumer_council_petrol",
        "country": "Hong Kong",
        "source_name": "Hong Kong Consumer Council — Petrol Prices",
        "url": "https://oil-price.consumer.org.hk/en/chart/download-csv",
        "description": (
            "Daily retail petrol (regular unleaded gasoline) prices by company "
            "from the Hong Kong Consumer Council oil price portal. "
            "Covers Sinopec, PetroChina, Caltex, Esso, and Shell."
        ),
        "extraction_method": ["CSV download"],
        "products": ["Regular Gasoline"],
        "source_keys": ["hk_consumer_council_petrol_daily"],
        "publishes_on": "Daily",
        "notes": (
            "GET CSV with repeated company[i] params (list of tuples). "
            "subnational_area = company name for hash uniqueness. "
            "Price range: 10–35 HKD/L."
        ),
    },
    {
        "fetcher_fn": "fetch_hk_consumer_council_diesel",
        "country": "Hong Kong",
        "source_name": "Hong Kong Consumer Council — Diesel Prices",
        "url": "https://oil-price.consumer.org.hk/en/diesel/chart/download-csv",
        "description": (
            "Daily retail diesel prices by company from the Hong Kong Consumer "
            "Council oil price portal. Covers Sinopec, PetroChina, Caltex, Esso, and Shell."
        ),
        "extraction_method": ["CSV download"],
        "products": ["Diesel"],
        "source_keys": ["hk_consumer_council_diesel_daily"],
        "publishes_on": "Daily",
        "notes": (
            "GET CSV with repeated company[i] params (list of tuples). "
            "subnational_area = company name for hash uniqueness. "
            "Price range: 8–30 HKD/L."
        ),
    },
]

import io
from datetime import date, timedelta

import pandas as pd
import requests

from ..utils import get_session, make_hash, make_template

_PETROL_URL = "https://oil-price.consumer.org.hk/en/chart/download-csv"
_DIESEL_URL = "https://oil-price.consumer.org.hk/en/diesel/chart/download-csv"

_TMPL_HK_PETROL = make_template(
    country="Hong Kong",
    wb_iso3="HKG",
    source_key="hk_consumer_council_petrol_daily",
    source_name="Hong Kong Consumer Council — Petrol Prices",
    source_url=_PETROL_URL,
    source_type="official",
    currency="HKD",
    unit="L",
    publication_frequency="daily",
    observation_method="reported",
    tax_status="tax_inclusive",
)

_TMPL_HK_DIESEL = make_template(
    country="Hong Kong",
    wb_iso3="HKG",
    source_key="hk_consumer_council_diesel_daily",
    source_name="Hong Kong Consumer Council — Diesel Prices",
    source_url=_DIESEL_URL,
    source_type="official",
    currency="HKD",
    unit="L",
    publication_frequency="daily",
    observation_method="reported",
    tax_status="tax_inclusive",
)

# Ordered company names matching the CSV columns (after Date).
_COMPANIES = ["Sinopec", "PetroChina", "Caltex", "Esso", "Shell"]

# company[i] IDs as used by the Consumer Council portal.
_COMPANY_PARAMS = [
    ("company[0]", ":company:11:"),  # Sinopec
    ("company[1]", ":company:12:"),  # PetroChina
    ("company[2]", ":company:14:"),  # Caltex
    ("company[3]", ":company:9765:"),  # Esso
    ("company[4]", ":company:13:"),  # Shell
]

_EXPECTED_COLUMNS = {"Date", "Sinopec", "PetroChina", "Caltex", "Esso", "Shell"}


def _fetch_and_parse_csv(
    session: requests.Session,
    base_url: str,
    fuel_type: str,
    tmpl: dict,
    from_date: date,
    to_date: date,
    cutoff: date,
    price_min: float,
    price_max: float,
    fuel_product: str,
    fuel_family: str,
    quality_group: str,
) -> list[dict]:
    """Fetch the Consumer Council CSV and parse into observation rows.

    Uses a list of tuples for params to support repeated company[i] keys.
    subnational_area is set to company name for make_hash uniqueness.
    """
    params: list[tuple[str, str]] = [
        ("from", from_date.isoformat()),
        ("to", to_date.isoformat()),
        ("auto_fuel_type", fuel_type),
        *_COMPANY_PARAMS,
    ]

    tag = f"[hk_{fuel_type[:6]}]"

    try:
        resp = session.get(base_url, params=params, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"  {tag} CSV fetch failed: {e}")
        return []

    try:
        df = pd.read_csv(io.StringIO(resp.text))
    except Exception as e:
        print(f"  {tag} CSV parse error: {e}")
        return []

    missing = _EXPECTED_COLUMNS - set(df.columns)
    if missing:
        print(f"  {tag} Missing expected columns: {missing}. Got: {list(df.columns)}")
        return []

    df["_date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["_date"])
    df["_date"] = df["_date"].dt.date

    all_rows: list[dict] = []

    for _, csv_row in df.iterrows():
        obs_date: date = csv_row["_date"]
        if obs_date <= cutoff:
            continue

        for company in _COMPANIES:
            raw_val = csv_row.get(company)
            try:
                price = float(raw_val)
            except (TypeError, ValueError):
                continue
            if pd.isna(price) or not (price_min <= price <= price_max):
                continue

            row = tmpl.copy()
            row.update(
                {
                    "fuel_family": fuel_family,
                    "fuel_product": fuel_product,
                    "quality_group": quality_group,
                    "octane_ron": None,
                    "price_local": price,
                    "subnational_area": company,
                    "effective_from": str(obs_date),
                    "effective_to": str(obs_date),
                    "observation_date": str(obs_date),
                    "source_url": base_url,
                    "notes": f"Company: {company}",
                }
            )
            row["observation_hash"] = make_hash(row)
            all_rows.append(row)

    return all_rows


def fetch_hk_consumer_council_petrol(cutoff: date) -> pd.DataFrame:
    """Fetch Hong Kong Consumer Council daily petrol prices (regular unleaded)."""
    print("  [hk_petrol] Fetching HK Consumer Council petrol prices...")
    print(f"  [hk_petrol] Cutoff: {cutoff}")

    session = get_session()
    from_date = cutoff + timedelta(days=1)
    to_date = date.today()

    rows = _fetch_and_parse_csv(
        session=session,
        base_url=_PETROL_URL,
        fuel_type="regular-unleaded-gasoline",
        tmpl=_TMPL_HK_PETROL,
        from_date=from_date,
        to_date=to_date,
        cutoff=cutoff,
        price_min=10.0,
        price_max=35.0,
        fuel_product="Regular Gasoline",
        fuel_family="gasoline",
        quality_group="regular",
    )

    print(f"  [hk_petrol] {len(rows)} rows fetched (cutoff {cutoff})")
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def fetch_hk_consumer_council_diesel(cutoff: date) -> pd.DataFrame:
    """Fetch Hong Kong Consumer Council daily diesel prices."""
    print("  [hk_diesel] Fetching HK Consumer Council diesel prices...")
    print(f"  [hk_diesel] Cutoff: {cutoff}")

    session = get_session()
    from_date = cutoff + timedelta(days=1)
    to_date = date.today()

    rows = _fetch_and_parse_csv(
        session=session,
        base_url=_DIESEL_URL,
        fuel_type="diesel",
        tmpl=_TMPL_HK_DIESEL,
        from_date=from_date,
        to_date=to_date,
        cutoff=cutoff,
        price_min=8.0,
        price_max=30.0,
        fuel_product="Diesel",
        fuel_family="diesel",
        quality_group="regular",
    )

    print(f"  [hk_diesel] {len(rows)} rows fetched (cutoff {cutoff})")
    return pd.DataFrame(rows) if rows else pd.DataFrame()
