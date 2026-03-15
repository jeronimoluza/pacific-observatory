"""New Zealand MBIE weekly fuel price fetcher (full refresh)."""

# ruff: noqa: E402
SOURCE_META = [
    {
        "fetcher_fn": "fetch_nz_mbie_weekly",
        "country": "New Zealand",
        "source_name": "MBIE Weekly Fuel Price Monitoring",
        "url": "https://www.mbie.govt.nz/assets/Data-Files/Energy/Weekly-fuel-price-monitoring/weekly-table.csv",
        "description": "Official government (MBIE). Weekly fuel price monitoring as a public CSV direct download. Clean structured data; no auth required.",
        "extraction_method": ["CSV download"],
        "products": ["Gasoline (Regular Petrol)", "Gasoline (Premium 95R)", "Diesel"],
        "source_keys": ["nz_mbie_weekly_fuel"],
        "publishes_on": "Tuesday",
        "notes": "Filters to Variable == 'Adjusted retail price'. Price in NZ c/L divided by 100. Range: 50–500 c/L.",
    },
    {
        "fetcher_fn": "fetch_nz_gaspy_stats_daily",
        "country": "New Zealand",
        "source_name": "Gaspy NZ Average Fuel Prices",
        "url": "https://www.gaspy.nz/stats.html",
        "description": "Gaspy crowdsourced daily NZ average fuel prices from the Gaspy stats page (Firebase-backed).",
        "extraction_method": ["Firebase JSON"],
        "products": ["Unleaded 91", "Unleaded 95", "Unleaded 98", "Diesel"],
        "source_keys": ["nz_gaspy_stats_daily"],
        "publishes_on": "Daily",
        "notes": "Reads datamine.Averages from gaspy-datamine-stats.firebaseio.com; prices are NZD cents/L divided by 100.",
    },
]

import io
from datetime import date, datetime, timedelta

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

_GASPY_STATS_URL = "https://gaspy-datamine-stats.firebaseio.com/.json"

_TMPL_NZ_GASPY = make_template(
    country="New Zealand",
    wb_iso3="NZL",
    source_key="nz_gaspy_stats_daily",
    source_name="Gaspy NZ Average Fuel Prices",
    source_url="https://www.gaspy.nz/stats.html",
    currency="NZD",
    unit="L",
    subnational_area="National",
    publication_frequency="daily",
    observation_method="compiled",
    source_type="compiled_web",
)

_GASPY_AVERAGE_MAP = {
    "91": ("Unleaded 91", "gasoline", "regular", 91),
    "95": ("Unleaded 95", "gasoline", "premium", 95),
    "98": ("Unleaded 98", "gasoline", "premium", 98),
    "Diesel": ("Diesel", "diesel", "regular", None),
}


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
        # Deduplicate overlapping Final/Provisional rows for the same
        # (fuel_product, observation_date).  Keep the row with the latest
        # effective_from — the newer survey supersedes the stale finalized value.
        result_df = pd.DataFrame(all_rows)
        result_df = result_df.sort_values("effective_from", ascending=False)
        result_df = result_df.drop_duplicates(
            subset=["fuel_product", "observation_date"], keep="first"
        )
        all_rows = result_df.to_dict("records")
        print(f"  [nz_mbie] {len(all_rows)} new rows")
    else:
        print("  [nz_mbie] No new rows")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()


def _parse_gaspy_updated(updated: str | None) -> date | None:
    if not updated:
        return None
    text = str(updated).strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%d %b %Y @ %I:%M%p").date()
    except Exception:
        return None


def fetch_nz_gaspy_stats_daily(cutoff: date) -> pd.DataFrame:
    """Fetch Gaspy NZ average fuel prices (daily snapshot)."""
    print("  [nz_gaspy] Fetching Gaspy NZ average prices...")
    print(f"  [nz_gaspy] Cutoff: {cutoff}")

    session = get_session()
    try:
        resp = session.get(_GASPY_STATS_URL, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
    except Exception as e:
        print(f"  [nz_gaspy] Fetch error: {e}")
        return pd.DataFrame()

    datamine = payload.get("datamine", {}) if isinstance(payload, dict) else {}
    averages = datamine.get("Averages", {}) if isinstance(datamine, dict) else {}
    updated = datamine.get("Updated") if isinstance(datamine, dict) else None

    obs_date = _parse_gaspy_updated(updated) or date.today()
    if obs_date <= cutoff:
        print("  [nz_gaspy] No new rows after cutoff")
        return pd.DataFrame()

    all_rows: list[dict] = []
    note_suffix = f"; updated={updated}" if updated else ""
    for key, (prod_name, family, qg, ron) in _GASPY_AVERAGE_MAP.items():
        item = averages.get(key) if isinstance(averages, dict) else None
        if not isinstance(item, dict):
            continue
        avg_cpl = item.get("Average")
        try:
            avg_cpl = float(avg_cpl)
        except (TypeError, ValueError):
            continue
        if not (50 <= avg_cpl <= 500):
            continue

        price = round(avg_cpl / 100.0, 4)
        row = _TMPL_NZ_GASPY.copy()
        row.update(
            {
                "fuel_family": family,
                "fuel_product": prod_name,
                "quality_group": qg,
                "octane_ron": ron,
                "price_local": price,
                "effective_from": str(obs_date),
                "effective_to": str(obs_date),
                "observation_date": str(obs_date),
                "notes": f"Gaspy average prices{note_suffix}",
            }
        )
        row["observation_hash"] = make_hash(row)
        all_rows.append(row)

    if not all_rows:
        print("  [nz_gaspy] No rows extracted")
        return pd.DataFrame()

    print(f"  [nz_gaspy] {len(all_rows)} rows fetched")
    return pd.DataFrame(all_rows)
