"""Export Cross-Country Comparison tab data to Excel.

Produces scripts/fuel_prices_grouped.xlsx with one row per (country, fuel_family),
columns = dates, values = average USD price across products in that family.
Mirrors the data shown in the Cross-Country Comparison tab of the dashboard.
"""

import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from src.cpi.fuel_prices.constants import DASHBOARD_HISTORY_YEARS
from src.cpi.fuel_prices.loader import load_fuel_data
from src.cpi.fuel_prices.visualize_policy import (
    COUNTRY_PRODUCTS,
    _apply_usd_prices,
    _load_fx_rates,
)

OUTPUT_EXCEL = "scripts/fuel_prices_grouped.xlsx"

_FAMILIES = ["diesel", "gasoline", "lpg", "kerosene"]
_FAMILY_LABELS = {
    "diesel": "Diesel",
    "gasoline": "Gasoline",
    "lpg": "LPG",
    "kerosene": "Kerosene",
}

_FUEL_KEEP = {
    "observation_date",
    "price_local",
    "location",
    "source_key",
    "fuel_product",
    "series_key",
    "fuel_family",
    "currency",
    "unit",
}

# LPG density for L → kg conversion (same as dashboard)
_LPG_L_TO_KG = 0.54

# China: NDRC stores prices in CNY/ton — convert to CNY/L
_CN_L_PER_TON = {"Gasoline": 1379.0, "Diesel": 1197.6}

# Thailand: rename Bangchak product names to OR/PTTOR canonical names
_TH_PRODUCT_MAP = {"E20": "Gasohol E20", "E85": "Gasohol E85", "Hi Diesel S": "Diesel"}

# Taiwan CPC product name normalization
_TW_RENAME = {
    "92 Unleaded": "Unleaded 92",
    "95 Unleaded": "Unleaded 95",
    "98 Unleaded": "Unleaded 98",
}

# COUNTRY_PRODUCTS uses "Taiwan, China" but we display that way too
_DISPLAY_TO_CSV = {"Taiwan, China": "Taiwan"}

_ALLOWED_PAIRS = {
    (_DISPLAY_TO_CSV.get(country, country), product)
    for country, products in COUNTRY_PRODUCTS.items()
    for product in products
}


def _avg_stations(records):
    """Collapse per-station rows into one averaged row per (date, product, source)."""
    groups = defaultdict(list)
    first = {}
    for r in records:
        key = (r.get("observation_date"), r.get("fuel_product"), r.get("source_key"))
        groups[key].append(r.get("price_local"))
        if key not in first:
            first[key] = r
    out = []
    for key, prices in groups.items():
        valid = [p for p in prices if p is not None]
        if not valid:
            continue
        rec = dict(first[key])
        rec["price_local"] = round(sum(valid) / len(valid), 4)
        rec["subnational_area"] = ""
        rec["location"] = ""
        out.append(rec)
    return out


def _collapse(records):
    """Average price per (date, product, source, family, currency, unit)."""
    groups = defaultdict(list)
    first = {}
    for r in records:
        obs = str(r.get("observation_date", ""))[:10]
        price = r.get("price_local")
        if not obs or price is None:
            continue
        try:
            price_f = float(price)
        except (TypeError, ValueError):
            continue
        key = (
            obs,
            r.get("fuel_product"),
            r.get("series_key"),
            r.get("source_key"),
            r.get("fuel_family"),
            r.get("currency"),
            r.get("unit"),
        )
        groups[key].append(price_f)
        first.setdefault(key, r)
    out = []
    for key, prices in groups.items():
        rec = dict(first[key])
        rec["observation_date"] = key[0]
        rec["price_local"] = round(sum(prices) / len(prices), 4)
        rec["location"] = "National"
        out.append(rec)
    return out


def _preprocess(fuel_data):
    """Apply same country-specific transforms as gen_policy_html."""
    # Hong Kong: only PetroChina stations, average by day
    hk = _avg_stations(
        [
            r
            for r in fuel_data.get("Hong Kong", [])
            if not r.get("source_key", "").startswith("gpp_")
            and r.get("subnational_area") in {"PetroChina"}
        ]
    )
    # Mongolia: only NSO aimag weekly source
    mn = [
        r
        for r in fuel_data.get("Mongolia", [])
        if r.get("source_key") == "mn_nso_aimag_weekly_fuel"
    ]
    # Vietnam: only vn_petrolimex_retail National rows
    vn = [
        r
        for r in fuel_data.get("Vietnam", [])
        if r.get("source_key") == "vn_petrolimex_retail"
        and r.get("location") == "National"
    ]
    # China: CNY/ton → CNY/L
    cn = []
    for r in fuel_data.get("China", []):
        if r.get("unit") == "ton" and r.get("fuel_product") in _CN_L_PER_TON:
            rec = dict(r)
            rec["price_local"] = round(
                r["price_local"] / _CN_L_PER_TON[r["fuel_product"]], 4
            )
            rec["unit"] = "L"
            cn.append(rec)
        else:
            cn.append(r)
    # Thailand: exclude NGV and EPPO P04 (ex-refinery, not retail), rename Bangchak products
    _TH_SKIP_SOURCES = {"th_eppo_ngv_bangkok_2025", "th_eppo_p04_monthly"}
    th = []
    for r in fuel_data.get("Thailand", []):
        if r.get("source_key") in _TH_SKIP_SOURCES:
            continue
        fp = r.get("fuel_product")
        if fp in _TH_PRODUCT_MAP:
            rec = dict(r)
            rec["fuel_product"] = _TH_PRODUCT_MAP[fp]
            th.append(rec)
        else:
            th.append(r)

    preprocessed = {
        ("Taiwan, China" if k == "Taiwan" else k): v for k, v in fuel_data.items()
    }
    preprocessed.update(
        {"Hong Kong": hk, "Mongolia": mn, "Vietnam": vn, "China": cn, "Thailand": th}
    )
    return preprocessed


def main():
    print("Loading fuel data...")
    fuel_data = load_fuel_data()

    print("Preprocessing...")
    preprocessed = _preprocess(fuel_data)

    # Slim to needed columns & collapse to national averages
    fuel_data_slim = {
        country: _collapse([{k: r[k] for k in _FUEL_KEEP if k in r} for r in records])
        for country, records in preprocessed.items()
    }

    # Rename Taiwan CPC product names
    for r in fuel_data_slim.get("Taiwan, China", []):
        fp = r.get("fuel_product")
        if fp in _TW_RENAME:
            r["fuel_product"] = _TW_RENAME[fp]

    # Apply USD conversion
    print("Applying FX rates...")
    fx_rates = _load_fx_rates()
    _apply_usd_prices(fuel_data_slim, fx_rates)

    # Trim to dashboard history window
    cutoff = (date.today() - timedelta(days=365 * DASHBOARD_HISTORY_YEARS)).strftime(
        "%Y-%m-%d"
    )

    # Build flat rows for target families, filtered by COUNTRY_PRODUCTS + unit
    rows = []
    for country, records in fuel_data_slim.items():
        allowed = COUNTRY_PRODUCTS.get(country)
        for r in records:
            obs = str(r.get("observation_date", ""))[:10]
            if obs < cutoff:
                continue
            family = r.get("fuel_family")
            if family not in _FAMILIES:
                continue
            unit = r.get("unit")
            if unit != "L" and not (family == "lpg" and unit == "kg"):
                continue
            if allowed and r.get("fuel_product") not in allowed:
                continue
            price_usd = r.get("price_usd")
            if price_usd is None:
                continue
            # LPG in L → convert to USD/kg
            if family == "lpg" and unit == "L":
                price_usd = price_usd / _LPG_L_TO_KG
            rows.append(
                {
                    "country": country,
                    "fuel_family": family,
                    "fuel_product": r.get("fuel_product"),
                    "observation_date": obs,
                    "price_usd": price_usd,
                }
            )

    df = pd.DataFrame(rows)
    print(f"  {len(df)} filtered records across {df['country'].nunique()} countries")

    # Average across products per (country, family, date) — matching getCompareSeries()
    agg = (
        df.groupby(["country", "fuel_family", "observation_date"])["price_usd"]
        .mean()
        .reset_index()
    )

    # Pivot to wide format
    wide = agg.pivot_table(
        index=["country", "fuel_family"],
        columns="observation_date",
        values="price_usd",
        aggfunc="mean",
    )
    wide.columns.name = None
    wide = wide[sorted(wide.columns)]
    wide = wide.ffill(axis=1)
    wide = wide.reset_index()

    # Human-readable family labels
    wide["fuel_family"] = wide["fuel_family"].map(_FAMILY_LABELS)
    wide = wide.sort_values(["country", "fuel_family"]).reset_index(drop=True)

    with pd.ExcelWriter(OUTPUT_EXCEL, engine="openpyxl") as writer:
        wide.to_excel(writer, index=False)

    print(f"Saved {len(wide)} rows to {OUTPUT_EXCEL}")


if __name__ == "__main__":
    main()
