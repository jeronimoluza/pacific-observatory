"""Curated ~10k consumable dataset family with canonical product identity.

Turns the `trusted` slice of ``data/prices/build/eap_fnb_observations.parquet``
into a small, clean, ready-to-share EAP food & non-alcoholic beverage dataset
family plus a Stata bundle, under ``outputs/prices/consumable_datasets/``.

Solves the ``input_hash`` over-count (URL fragmentation): the same real product
appears under many URLs that encode location/branch/city, so ``unique(input_hash)``
inflates the product count. We collapse to a ``canonical_product_id`` = hash of
(country, source, coicop_code, name_norm, standard_unit, amount_value, count,
multiplier) — location noise disappears (name + pack identical across fragments)
while parsed pack size keeps genuine variants apart.

Cleanliness: raw trusted history has ~49% same-day duplicate rows (repeated scrapes
/ per-location listings). We collapse the observation deliverable to one median row
per (product, day).

Scope: real-retail sources only (multi-country USD-basket aggregators —
livingcost/expatistan/mylifeelsewhere — excluded; the 13 countries they are the sole
source for drop out with them, all with zero analytically-usable cells anyway) and
positive unit values only.

Deliverables under ``outputs/prices/consumable_datasets/``:
  1. eap_fnb_products.parquet               — ~10k product master
  2. eap_fnb_latest_snapshot.parquet        — one row/product at its most-recent month
  3. eap_fnb_daily.parquet                  — clean daily history (1 row/product/day)
  4. eap_fnb_monthly.parquet                — per-product monthly unit-value summary
  5. eap_fnb_coicop_monthly_summary.parquet — per-(country, leaf, unit) monthly summary
  6. eap_fnb_coicop_latest_summary.parquet  — per-(country, leaf, unit) latest cross-section
  7. eap_fnb_coicop_titles.dta              — coicop_code -> COICOP 2018 leaf title
  8. eap_fnb_datasets_stata.zip             — all eap_fnb_* except _products as .dta + README
  9. README.md
"""

from __future__ import annotations

import hashlib
import re
import tempfile
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from prices.enrich import config as enrich_config

REPO_ROOT = Path(__file__).resolve().parents[3]
OBS_PARQUET = REPO_ROOT / "data/prices/build/eap_fnb_observations.parquet"
OUT_DIR = REPO_ROOT / "outputs/prices/consumable_datasets"

N_TARGET = 10_000  # target unique canonical products
MIN_DAYS = 2  # floor: every shipped product carries >=2 distinct days
CELL_FLOOR = 1  # every (country, leaf) cell keeps min(size, 1) product

# Multi-country crowd-sourced USD-basket sources — no real retail time series
# (fixed snapshot per country). Excluded; the 13 countries they are the sole
# source for drop out with them.
AGGREGATOR_SOURCES = {"livingcost", "expatistan", "mylifeelsewhere"}

KEY_COLS = [
    "country",
    "source",
    "coicop_code",
    "name_norm",
    "standard_unit",
    "amt",
    "count",
    "multiplier",
]
_ws = re.compile(r"\s+")


def _norm(s) -> str:
    return _ws.sub(" ", str(s).strip().lower())


def _log_mad(v: pd.Series) -> float:
    v = pd.to_numeric(v, errors="coerce")
    v = v[v > 0]
    if len(v) < 2:
        return np.nan
    lv = np.log(v)
    return float((lv - lv.median()).abs().median())


def _modal(s):
    m = s.mode()
    return m.iloc[0] if len(m) else None


def load_trusted() -> pd.DataFrame:
    obs = pd.read_parquet(OBS_PARQUET)
    t = obs[obs["qa_status"] == "trusted"].copy()
    t = t[~t["source"].isin(AGGREGATOR_SOURCES)].copy()
    t["name_norm"] = t["product_name"].map(_norm)
    t["amt"] = pd.to_numeric(t["amount_value"], errors="coerce").round(4)
    t["canonical_product_id"] = (
        t[KEY_COLS]
        .astype(str)
        .agg("|".join, axis=1)
        .map(lambda s: hashlib.sha256(s.encode()).hexdigest()[:16])
    )
    t["obs_day"] = pd.to_datetime(t["observation_date"], errors="coerce").dt.normalize()
    return t


def daily_series(t: pd.DataFrame) -> pd.DataFrame:
    """One clean row per (canonical product, day): median over same-day dupes."""
    g = t.groupby(["canonical_product_id", "obs_day"])
    daily = g.agg(
        country=("country", "first"),
        source=("source", "first"),
        coicop_code=("coicop_code", "first"),
        product_name=("product_name", _modal),
        pricing_basis=("pricing_basis", _modal),
        standard_unit=("standard_unit", "first"),
        amount_value=("amount_value", "first"),
        count=("count", "first"),
        multiplier=("multiplier", "first"),
        currency=("currency", _modal),
        price_local=("price_local", "median"),
        unit_value_local=("unit_value_local", "median"),
        unit_value_usd=("unit_value_usd", "median"),
        confidence=("confidence", "median"),
        n_raw=("unit_value_local", "size"),
        n_urls=("product_url", "nunique"),
    ).reset_index()
    uv = pd.to_numeric(daily["unit_value_local"], errors="coerce")
    return daily[uv > 0].reset_index(drop=True)


def product_master(daily: pd.DataFrame) -> pd.DataFrame:
    """One row per canonical product, aggregated over its clean daily series."""
    daily = daily.copy()
    daily["ym"] = daily["obs_day"].dt.to_period("M").astype(str)
    g = daily.groupby("canonical_product_id")
    master = g.agg(
        country=("country", "first"),
        source=("source", "first"),
        coicop_code=("coicop_code", "first"),
        product_name=("product_name", "first"),
        pricing_basis=("pricing_basis", "first"),
        standard_unit=("standard_unit", "first"),
        amount_value=("amount_value", "first"),
        count=("count", "first"),
        multiplier=("multiplier", "first"),
        currency=("currency", "first"),
        n_days=("obs_day", "nunique"),
        n_months=("ym", "nunique"),
        n_raw=("n_raw", "sum"),
        n_urls=("n_urls", "max"),
        first_date=("obs_day", "min"),
        last_date=("obs_day", "max"),
        median_unit_value_local=("unit_value_local", "median"),
        median_unit_value_usd=("unit_value_usd", "median"),
        confidence_median=("confidence", "median"),
    )
    master["uv_log_mad"] = g["unit_value_local"].apply(_log_mad)
    return master.reset_index()


def latest_snapshot(selected: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    """One row per selected product, collapsed over the dataset's LAST calendar month."""
    sel_ids = set(selected["canonical_product_id"])
    d = daily[daily["canonical_product_id"].isin(sel_ids)].copy()
    last_period = daily["obs_day"].dt.to_period("M").max()
    d = d[d["obs_day"].dt.to_period("M") == last_period]
    g = d.groupby("canonical_product_id")
    snap = g.agg(
        country=("country", "first"),
        source=("source", "first"),
        coicop_code=("coicop_code", "first"),
        product_name=("product_name", _modal),
        pricing_basis=("pricing_basis", _modal),
        standard_unit=("standard_unit", "first"),
        amount_value=("amount_value", "first"),
        count=("count", "first"),
        multiplier=("multiplier", "first"),
        currency=("currency", _modal),
        price_local=("price_local", "median"),
        unit_value_local=("unit_value_local", "median"),
        unit_value_usd=("unit_value_usd", "median"),
        confidence=("confidence", "median"),
    ).reset_index()
    meta = selected[
        ["canonical_product_id", "median_unit_value_local", "median_unit_value_usd"]
    ]
    return snap.merge(meta, on="canonical_product_id", how="left")


def allocate(master: pd.DataFrame, n_target: int) -> pd.DataFrame:
    """Coverage-balanced water-filling over (country, coicop_code) cells.

    Each cell first gets min(size, CELL_FLOOR) products so every category carries
    real depth and no cell/leaf is dropped, then the remaining budget is water-filled
    proportional to cell size among cells with headroom — holding exactly n_target.
    Within a cell, take the best-supported, tightest, most-confident products first.
    """
    uv = pd.to_numeric(master["median_unit_value_local"], errors="coerce")
    elig = master[(master["n_days"] >= MIN_DAYS) & (uv > 0)].copy()
    cells = elig.groupby(["country", "coicop_code"]).size().rename("size").reset_index()
    size = cells["size"].to_numpy()

    alloc = np.minimum(size, CELL_FLOOR).astype(int)
    remaining = n_target - int(alloc.sum())
    while remaining > 0:
        head = size - alloc
        if not (head > 0).any():
            break
        w = size * (head > 0)
        give = np.minimum(np.floor(w / w.sum() * remaining).astype(int), head)
        if give.sum() == 0:  # remainder < #cells with headroom: 1-by-1, largest first
            for i in np.argsort(-size):
                if remaining == 0:
                    break
                if head[i] > 0:
                    alloc[i] += 1
                    remaining -= 1
            break
        alloc += give
        remaining -= int(give.sum())

    cells["alloc"] = alloc
    quota = cells.set_index(["country", "coicop_code"])["alloc"].to_dict()
    elig = elig.sort_values(
        ["n_days", "confidence_median", "uv_log_mad"],
        ascending=[False, False, True],
    )
    picks = []
    for (c, leaf), sub in elig.groupby(["country", "coicop_code"], sort=False):
        k = quota.get((c, leaf), 0)
        if k:
            picks.append(sub.head(k))
    return pd.concat(picks, ignore_index=True)


def coicop_titles(codes) -> pd.DataFrame:
    """Map each COICOP leaf present in the datasets to its 2018 title."""
    tax = pd.read_excel(enrich_config.COICOP_XLSX, sheet_name="COICOP_2018")
    tax = tax[["code", "title"]].dropna(subset=["code"]).drop_duplicates("code")
    keep = tax[tax["code"].isin(set(codes))].sort_values("code").reset_index(drop=True)
    return keep


def write_stata_bundle(
    out_dir: Path, tables: dict[str, pd.DataFrame], titles: pd.DataFrame, readme: str
) -> Path:
    """Zip every table (except the product master) as .dta v118 + titles + README.

    version=118 preserves Unicode CJK/Thai product names; datetime cols map to Stata
    `td`. The zip lands as eap_fnb_datasets_stata.zip.
    """
    zip_path = out_dir / "eap_fnb_datasets_stata.zip"
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        members: list[Path] = []
        for name, df in tables.items():
            if name == "eap_fnb_products":  # excluded from the Stata bundle
                continue
            dta = tmp / f"{name}.dta"
            convert = {}
            for col in df.columns:
                if pd.api.types.is_datetime64_any_dtype(df[col]):
                    convert[col] = "td"
            df.to_stata(
                dta, write_index=False, version=118, convert_dates=convert or None
            )
            members.append(dta)
        titles_dta = out_dir / "eap_fnb_coicop_titles.dta"
        titles.to_stata(titles_dta, write_index=False, version=118)
        members.append(titles_dta)
        readme_path = tmp / "README.md"
        readme_path.write_text(readme)
        members.append(readme_path)
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for m in members:
                zf.write(m, m.name)
    return zip_path


def render_readme(stats: dict) -> str:
    """README with live coverage numbers over the stable schema documentation."""
    return f"""# EAP food & non-alcoholic beverage price datasets

Unit-value price data for **food and non-alcoholic beverages** (COICOP division 01)
across **{stats["n_countries"]} Asia-Pacific countries**, built from the `trusted` slice of the retail
price pipeline (real retailers only; multi-country USD-basket aggregators excluded).
Prices are normalized to a **unit value** — price per standard unit (kg, litre, or
single item) — so products of different pack sizes are comparable, and reported in
both local currency and USD (date-keyed FX). Reliability of each unit value is
carried by `uv_log_mad` (median absolute deviation of `log(unit_value)`; 0 = stable
price, higher = noisier).

**Coverage:** {stats["n_products"]:,} unique products · {stats["n_leaves"]} COICOP leaves · {stats["n_countries"]} countries ·
{stats["date_min"]} → {stats["date_max"]}.

## Files

| file | grain | rows |
|---|---|---|
| `eap_fnb_products.parquet` | one row per product (whole-history median) | {stats["n_products"]:,} |
| `eap_fnb_latest_snapshot.parquet` | one row per product (last-month cross-section) | {stats["n_snapshot"]:,} |
| `eap_fnb_daily.parquet` | one row per product-day | {stats["n_daily"]:,} |
| `eap_fnb_monthly.parquet` | one row per product-month | {stats["n_monthly"]:,} |
| `eap_fnb_coicop_monthly_summary.parquet` | one row per country · leaf · unit · month | {stats["n_coicop_monthly"]:,} |
| `eap_fnb_coicop_latest_summary.parquet` | one row per country · leaf · unit (last-month cross-section) | {stats["n_coicop_latest"]:,} |

`eap_fnb_coicop_titles.dta` (Stata bundle only) maps each `coicop_code` to its
COICOP 2018 leaf title.

Schemas for the analysis tables follow.

### `eap_fnb_latest_snapshot.parquet` — last-month price per product

One row per product, priced as the **median over the dataset's most-recent calendar
month** ({stats["date_max"][:7]}) — a current cross-section. Products with no observation in that
last month are absent, so this is smaller than the product master. No date column:
each row summarizes a month of prices, not a single day.

| column | type | description |
|---|---|---|
| `canonical_product_id` | str | product identifier / join key |
| `country` | str | country slug |
| `source` | str | retailer slug |
| `coicop_code` | str | COICOP leaf (e.g. `01.1.4.8.1`) |
| `product_name` | str | scraped product name |
| `pricing_basis` | str | `mass` / `volume` / `count` |
| `standard_unit` | str | `kg` / `lt` / `unit` |
| `amount_value` | float | net size in the standard unit (null on some count-basis rows) |
| `count` | int | items per listing |
| `multiplier` | int | multipack factor |
| `currency` | str | local currency (ISO) |
| `price_local` | float | median listed price over the last month, local currency |
| `unit_value_local` | float | median unit value over the last month, local currency |
| `unit_value_usd` | float | same, USD |
| `confidence` | float | COICOP classifier confidence |
| `median_unit_value_local` | float | whole-history median unit value, local currency |
| `median_unit_value_usd` | float | same, USD |

### `eap_fnb_daily.parquet` — daily price series

| column | type | description |
|---|---|---|
| `canonical_product_id` | str | product identifier / join key |
| `observation_date` | date | the day |
| `country` | str | country slug |
| `source` | str | retailer slug |
| `coicop_code` | str | COICOP leaf (e.g. `01.1.4.8.1`) |
| `product_name` | str | scraped product name |
| `pricing_basis` | str | `mass` / `volume` / `count` |
| `standard_unit` | str | `kg` / `lt` / `unit` |
| `amount_value` | float | net size in the standard unit (null on some count-basis rows) |
| `count` | int | items per listing |
| `multiplier` | int | multipack factor |
| `currency` | str | local currency (ISO) |
| `price_local` | float | median listed price that day, local currency |
| `unit_value_local` | float | median unit value that day, local currency |
| `unit_value_usd` | float | same, USD |
| `confidence` | float | COICOP classifier confidence |

### `eap_fnb_monthly.parquet` — per-product monthly summary

| column | type | description |
|---|---|---|
| `canonical_product_id` | str | product identifier / join key |
| `period` | str | calendar month, `YYYY-MM` |
| `country` | str | country slug |
| `coicop_code` | str | COICOP leaf |
| `standard_unit` | str | `kg` / `lt` / `unit` |
| `n_days` | int | distinct observation days in the month |
| `n_raw` | int | raw scrape rows behind the month |
| `n_urls` | int | distinct source URLs in the month |
| `median_unit_value_local` | float | median unit value that month, local currency |
| `median_unit_value_usd` | float | same, USD |
| `uv_log_mad` | float | within-month log-price stability (null when <2 days) |

### `eap_fnb_coicop_monthly_summary.parquet` — per-category monthly summary

Aggregates all products in a (country, COICOP leaf, unit) cell into one monthly
figure — a compact panel for category-level cross-country comparison.

| column | type | description |
|---|---|---|
| `country` | str | country slug |
| `period` | str | calendar month, `YYYY-MM` |
| `coicop_code` | str | COICOP leaf |
| `standard_unit` | str | `kg` / `lt` / `unit` |
| `n_products` | int | distinct products in the cell that month |
| `n_days` | int | distinct observation days in the cell that month |
| `median_unit_value_local` | float | median unit value across the cell, local currency |
| `median_unit_value_usd` | float | same, USD |
| `uv_log_mad` | float | within-cell log-price stability (null when <2 observations) |

### `eap_fnb_coicop_latest_summary.parquet` — per-category last-month cross-section

One figure per (country, COICOP leaf, unit), aggregating each product's last-month
median price (dataset month {stats["date_max"][:7]}). Unlike the monthly summary this is a single
collapsed cross-section, so every product observed in the last month counts —
giving multi-product category depth. The table for a current-price category
comparison across countries. No date column.

| column | type | description |
|---|---|---|
| `country` | str | country slug |
| `coicop_code` | str | COICOP leaf |
| `standard_unit` | str | `kg` / `lt` / `unit` |
| `n_products` | int | distinct products in the cell |
| `median_unit_value_local` | float | median last-month unit value across the cell, local currency |
| `median_unit_value_usd` | float | same, USD |
| `uv_log_mad` | float | across-product log-price dispersion in the cell (null when <2 products) |
"""


def run() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    t = load_trusted()
    daily = daily_series(t)
    print(f"raw trusted obs: {len(t):,}  ->  clean daily rows: {len(daily):,}")
    master = product_master(daily)
    selected = allocate(master, N_TARGET)
    print(
        f"selected: {len(selected):,} products across "
        f"{selected.country.nunique()} countries / {selected.coicop_code.nunique()} leaves"
    )

    sel_ids = set(selected["canonical_product_id"])
    obs_out = daily[daily["canonical_product_id"].isin(sel_ids)].copy()
    obs_out = obs_out.rename(columns={"obs_day": "observation_date"}).reset_index(
        drop=True
    )
    obs_out["period"] = obs_out["observation_date"].dt.to_period("M").astype(str)

    grp = obs_out.groupby(["canonical_product_id", "period"])
    monthly = grp.agg(
        country=("country", "first"),
        coicop_code=("coicop_code", "first"),
        standard_unit=("standard_unit", "first"),
        n_days=("unit_value_local", "size"),
        n_raw=("n_raw", "sum"),
        n_urls=("n_urls", "max"),
        median_unit_value_local=("unit_value_local", "median"),
        median_unit_value_usd=("unit_value_usd", "median"),
    ).reset_index()
    monthly["uv_log_mad"] = grp["unit_value_local"].apply(_log_mad).values

    cgrp = obs_out.groupby(["country", "period", "coicop_code", "standard_unit"])
    coicop = cgrp.agg(
        n_products=("canonical_product_id", "nunique"),
        n_days=("observation_date", "nunique"),
        median_unit_value_local=("unit_value_local", "median"),
        median_unit_value_usd=("unit_value_usd", "median"),
    ).reset_index()
    coicop["uv_log_mad"] = cgrp["unit_value_local"].apply(_log_mad).values

    snap = latest_snapshot(selected, daily)
    lgrp = snap.groupby(["country", "coicop_code", "standard_unit"])
    coicop_latest = lgrp.agg(
        n_products=("canonical_product_id", "nunique"),
        median_unit_value_local=("unit_value_local", "median"),
        median_unit_value_usd=("unit_value_usd", "median"),
    ).reset_index()
    coicop_latest["uv_log_mad"] = lgrp["unit_value_local"].apply(_log_mad).values

    daily_out = obs_out.drop(columns=["period", "n_raw", "n_urls"])
    tables = {
        "eap_fnb_products": selected,
        "eap_fnb_latest_snapshot": snap,
        "eap_fnb_daily": daily_out,
        "eap_fnb_monthly": monthly,
        "eap_fnb_coicop_monthly_summary": coicop,
        "eap_fnb_coicop_latest_summary": coicop_latest,
    }
    for name, df in tables.items():
        df.to_parquet(OUT_DIR / f"{name}.parquet", index=False)

    stats = {
        "n_products": len(selected),
        "n_snapshot": len(snap),
        "n_daily": len(daily_out),
        "n_monthly": len(monthly),
        "n_coicop_monthly": len(coicop),
        "n_coicop_latest": len(coicop_latest),
        "n_countries": int(selected.country.nunique()),
        "n_leaves": int(selected.coicop_code.nunique()),
        "date_min": str(daily_out.observation_date.min().date()),
        "date_max": str(daily_out.observation_date.max().date()),
    }
    titles = coicop_titles(selected.coicop_code.unique())
    readme = render_readme(stats)
    (OUT_DIR / "README.md").write_text(readme)
    zip_path = write_stata_bundle(OUT_DIR, tables, titles, readme)

    print(f"\nWROTE to {OUT_DIR}:")
    for name, df in tables.items():
        print(f"  {name + '.parquet':42s} {len(df):>9,} rows")
    print(f"  {'eap_fnb_coicop_titles.dta':42s} {len(titles):>9,} leaves")
    print(f"  {zip_path.name:42s} (Stata bundle)")
    print(
        f"\ncoverage: {stats['n_products']:,} products · {stats['n_leaves']} leaves · "
        f"{stats['n_countries']} countries · {stats['date_min']} → {stats['date_max']}"
    )


if __name__ == "__main__":
    run()
