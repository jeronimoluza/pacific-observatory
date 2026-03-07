"""New Zealand MBIE weekly fuel price fetcher (full refresh)."""

import io
from datetime import date, timedelta

import pandas as pd

from ..utils import get_session, make_hash, make_template

_TMPL_NZ = make_template(
    country="New Zealand",
    wb_iso3="NZL",
    source_key="nz_mbie_weekly_fuel",
    source_name="New Zealand MBIE Weekly Fuel Price Monitoring",
    source_url="https://www.mbie.govt.nz/assets/Data-Files/Energy/Weekly-fuel-price-monitoring/weekly-table.csv",
    currency="NZD",
    unit="L",
    subnational_area="National",
    publication_frequency="weekly",
    observation_method="survey",
)

_NZ_PRODUCT_MAP = {
    "Regular Petrol": ("Regular Petrol", "gasoline", "regular", None),
    "Premium Petrol 95R": ("Premium Petrol 95R", "gasoline", "premium", 95),
    "Diesel": ("Diesel", "diesel", "regular", None),
}

_NZ_PROVISIONAL_CUTOFF = date(2025, 12, 31)

_CSV_URL = "https://www.mbie.govt.nz/assets/Data-Files/Energy/Weekly-fuel-price-monitoring/weekly-table.csv"


def fetch_nz_mbie_weekly(cutoff: date) -> pd.DataFrame:
    """Full-refresh fetch of NZ MBIE weekly adjusted retail prices."""
    print("  [nz_mbie] Fetching NZ MBIE weekly fuel data (full refresh)...")
    print(f"  [nz_mbie] Cutoff: {cutoff}")

    session = get_session()
    try:
        session.get("https://www.mbie.govt.nz/", timeout=20)
    except Exception:
        pass

    try:
        resp = session.get(_CSV_URL, timeout=60)
        resp.raise_for_status()
        if b"Incapsula" in resp.content[:500] or b"<html" in resp.content[:10]:
            print("  [nz_mbie] Blocked by Incapsula / not a CSV response")
            return pd.DataFrame()
    except Exception as e:
        print(f"  [nz_mbie] Download error: {e}")
        return pd.DataFrame()

    try:
        raw = pd.read_csv(
            io.BytesIO(resp.content), encoding="utf-8", encoding_errors="replace"
        )
    except Exception as e:
        print(f"  [nz_mbie] CSV parse error: {e}")
        return pd.DataFrame()

    required = {"Date", "Fuel", "Variable", "Value", "Status"}
    if not required.issubset(set(raw.columns)):
        print(f"  [nz_mbie] Unexpected columns: {raw.columns.tolist()}")
        return pd.DataFrame()

    retail = raw[raw["Variable"] == "Adjusted retail price"].copy()
    retail = retail[retail["Fuel"].isin(_NZ_PRODUCT_MAP)].copy()
    retail["_date"] = pd.to_datetime(retail["Date"], errors="coerce")
    retail = retail.dropna(subset=["_date"])

    status_mask = (retail["Status"] == "Final") | (
        (retail["Status"] == "Provisional")
        & (retail["_date"].dt.date > _NZ_PROVISIONAL_CUTOFF)
    )
    retail = retail[status_mask].copy()

    all_rows = []
    for _, row in retail.iterrows():
        obs_date = row["_date"].date()
        if obs_date <= cutoff:
            continue

        fuel = str(row["Fuel"]).strip()
        prod_name, family, qg, ron = _NZ_PRODUCT_MAP[fuel]
        try:
            price_cpl = float(row["Value"])
            if not (50 <= price_cpl <= 500):
                continue
            price = round(price_cpl / 100, 4)
        except (ValueError, TypeError):
            continue

        r = _TMPL_NZ.copy()
        r.update(
            {
                "fuel_family": family,
                "fuel_product": prod_name,
                "quality_group": qg,
                "octane_ron": ron,
                "price_local": price,
                "status": str(row["Status"]),
                "effective_from": str(obs_date),
                "effective_to": str(obs_date + timedelta(days=6)),
                "observation_date": str(obs_date),
                "source_url": _CSV_URL,
                "notes": "Adjusted retail price (NZD c/L ÷ 100)",
            }
        )
        r["observation_hash"] = make_hash(r)
        all_rows.append(r)

    if all_rows:
        print(f"  [nz_mbie] {len(all_rows)} new rows")
    else:
        print("  [nz_mbie] No new rows")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
