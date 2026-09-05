import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from datetime import datetime

from src.cpi.fuel_prices.visualize_policy import COUNTRY_PRODUCTS

DATA_PATH = "data/cpi/fuel_prices_staged/enrich/retail_series_enriched.csv"
COMMODITY_PATHS = [
    "data/cpi/fuel_prices/global/global_investing_daily/observations.csv",
    "data/cpi/fuel_prices/eap/global_investing_daily/observations.csv",
]
OUTPUT_EXCEL = "scripts/fuel_price_time_series.xlsx"

# Gasoline RBOB is stored in USD/gal — convert to USD/bbl
_GAL_TO_BBL = 42.0

START_DATE = "2025-05-01"
END_DATE = datetime.today().strftime("%Y-%m-%d")

LAST_WEEK_DAYS = 35

# China: NDRC stores prices in CNY/ton — convert to CNY/L
_CN_L_PER_TON = {"Gasoline": 1379.0, "Diesel": 1197.6}

# Thailand: Bangchak uses different names for products that OR/PTTOR later covers.
# Rename to OR/PTTOR canonical names so Bangchak history stitches seamlessly.
_TH_PRODUCT_MAP = {
    "E20": "Gasohol E20",
    "E85": "Gasohol E85",
    "Hi Diesel S": "Diesel",
}

# COUNTRY_PRODUCTS uses "Taiwan, China" but the enriched CSV stores "Taiwan"
_DISPLAY_TO_CSV = {"Taiwan, China": "Taiwan"}

_ALLOWED_PAIRS = {
    (_DISPLAY_TO_CSV.get(country, country), product)
    for country, products in COUNTRY_PRODUCTS.items()
    for product in products
}


def main():
    print(f"Loading data from {DATA_PATH}...")
    df = pd.read_csv(DATA_PATH, low_memory=False)
    df["observation_date"] = pd.to_datetime(df["observation_date"])
    df["price_local"] = pd.to_numeric(
        df["price_local"].astype(str).str.replace(",", ".", regex=False),
        errors="coerce",
    )

    end_dt = pd.to_datetime(END_DATE)

    # No start date filter here — we need pre-May data to back-fill May 1st
    df = df[
        pd.Series(list(zip(df["country"], df["fuel_product"])), index=df.index).isin(
            _ALLOWED_PAIRS
        )
        & (df["observation_date"] <= end_dt)
        & df["price_local"].notna()
    ].copy()

    # China: convert CNY/ton -> CNY/L
    for product, l_per_ton in _CN_L_PER_TON.items():
        mask = (
            (df["country"] == "China")
            & (df["fuel_product"] == product)
            & (df["unit"] == "ton")
        )
        df.loc[mask, "price_local"] = df.loc[mask, "price_local"] / l_per_ton
        df.loc[mask, "unit"] = "L"

    # Thailand: drop EPPO P04 (ex-refinery, not retail) and rename Bangchak products
    df = df[
        ~((df["country"] == "Thailand") & (df["source_key"] == "th_eppo_p04_monthly"))
    ].copy()
    th_mask = df["country"] == "Thailand"
    df.loc[th_mask, "fuel_product"] = df.loc[th_mask, "fuel_product"].replace(
        _TH_PRODUCT_MAP
    )

    # Only keep pairs with data in the last week
    max_dates = (
        df.groupby(["country", "fuel_product"])["observation_date"].max().reset_index()
    )
    max_dates.columns = ["country", "fuel_product", "date_end"]
    cutoff = pd.Timestamp.today() - pd.Timedelta(days=LAST_WEEK_DAYS)
    has_recent = max_dates[max_dates["date_end"] >= cutoff][["country", "fuel_product"]]

    # Extract currency and unit per series (most common value)
    meta = (
        df.groupby(["country", "fuel_product"])
        .agg(
            currency=(
                "currency",
                lambda x: x.mode().iloc[0] if not x.mode().empty else "",
            ),
            unit=("unit", lambda x: x.mode().iloc[0] if not x.mode().empty else ""),
        )
        .reset_index()
    )

    # Average price per (country, fuel_product, date)
    ts = (
        df.groupby(["country", "fuel_product", "observation_date"])["price_local"]
        .mean()
        .reset_index()
    )
    ts = ts.merge(has_recent, on=["country", "fuel_product"])
    ts["observation_date"] = ts["observation_date"].dt.strftime("%Y-%m-%d")

    ts_wide = ts.pivot_table(
        index=["country", "fuel_product"],
        columns="observation_date",
        values="price_local",
        aggfunc="mean",
    )
    ts_wide.columns.name = None

    # Ensure START_DATE column exists (NaN rows will be filled by ffill)
    if START_DATE not in ts_wide.columns:
        ts_wide[START_DATE] = float("nan")

    # Sort chronologically, forward-fill gaps, then drop pre-START_DATE columns
    ts_wide = ts_wide[sorted(ts_wide.columns)]
    ts_wide = ts_wide.ffill(axis=1)
    ts_wide = ts_wide.loc[:, ts_wide.columns >= START_DATE]

    ts_wide = ts_wide.reset_index().sort_values(["country", "fuel_product"])

    # Attach currency and unit
    ts_wide = ts_wide.merge(meta, on=["country", "fuel_product"], how="left")

    # Column order: country, fuel_product, unit, currency, then dates
    date_cols = [
        c
        for c in ts_wide.columns
        if c not in ["country", "fuel_product", "unit", "currency"]
    ]
    ts_wide = ts_wide[["country", "fuel_product", "unit", "currency"] + date_cols]

    # ── Commodities sheet ──────────────────────────────────────────────────────
    comm = pd.concat(
        [pd.read_csv(p, low_memory=False) for p in COMMODITY_PATHS],
        ignore_index=True,
    )
    comm["observation_date"] = pd.to_datetime(comm["observation_date"])
    comm["price_local"] = pd.to_numeric(comm["price_local"], errors="coerce")

    # Gasoline RBOB: USD/gal → USD/bbl
    rbob_mask = comm["unit"] == "gal"
    comm.loc[rbob_mask, "price_local"] = (
        comm.loc[rbob_mask, "price_local"] * _GAL_TO_BBL
    )
    comm.loc[rbob_mask, "unit"] = "bbl"

    comm = comm[
        (comm["observation_date"] >= pd.to_datetime(START_DATE))
        & (comm["observation_date"] <= end_dt)
        & comm["price_local"].notna()
    ].copy()

    comm_meta = (
        comm.groupby("fuel_product")
        .agg(
            currency=(
                "currency",
                lambda x: x.mode().iloc[0] if not x.mode().empty else "",
            ),
            unit=("unit", lambda x: x.mode().iloc[0] if not x.mode().empty else ""),
        )
        .reset_index()
    )

    comm_ts = (
        comm.groupby(["fuel_product", "observation_date"])["price_local"]
        .mean()
        .reset_index()
    )
    comm_ts["observation_date"] = comm_ts["observation_date"].dt.strftime("%Y-%m-%d")

    comm_wide = comm_ts.pivot_table(
        index="fuel_product",
        columns="observation_date",
        values="price_local",
        aggfunc="mean",
    )
    comm_wide.columns.name = None
    comm_wide = comm_wide[sorted(comm_wide.columns)]
    comm_wide = comm_wide.reset_index().sort_values("fuel_product")
    comm_wide = comm_wide.merge(comm_meta, on="fuel_product", how="left")

    comm_date_cols = [
        c for c in comm_wide.columns if c not in ["fuel_product", "unit", "currency"]
    ]
    comm_wide = comm_wide[["fuel_product", "unit", "currency"] + comm_date_cols]

    with pd.ExcelWriter(OUTPUT_EXCEL, engine="openpyxl") as writer:
        ts_wide.to_excel(writer, sheet_name="Time Series", index=False)
        comm_wide.to_excel(writer, sheet_name="Commodities", index=False)

    print(
        f"Saved {len(ts_wide)} series + {len(comm_wide)} commodity series to {OUTPUT_EXCEL}"
    )


if __name__ == "__main__":
    main()
