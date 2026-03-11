"""CSV loading, merging, deduplication, and fetch-state cache management."""

import json
from datetime import date
from pathlib import Path

import pandas as pd

from .constants import (
    FETCH_STATE_JSON,
    PRIMARY_CSV,
    SECONDARY_CSV,
    SECONDARY_ONLY_COUNTRIES,
)
from .utils import make_hash


# ── Fetch state (per-source cutoff cache) ─────────────────────────────────────


def read_fetch_state(path: Path = FETCH_STATE_JSON) -> dict[str, date]:
    """Load .fetch_state.json; return dict of source_key -> last observation_date."""
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return {k: date.fromisoformat(v) for k, v in raw.items()}
    except Exception:
        return {}


def write_fetch_state(state: dict[str, date], path: Path = FETCH_STATE_JSON) -> None:
    """Persist updated fetch state to .fetch_state.json."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({k: v.isoformat() for k, v in state.items()}, indent=2),
        encoding="utf-8",
    )


def get_cutoff(state: dict[str, date], source_key: str, fallback: date) -> date:
    """Return the stored cutoff for source_key, or fallback if not present."""
    return state.get(source_key, fallback)


# ── Row merging / deduplication ───────────────────────────────────────────────


def merge_new_rows(df_existing: pd.DataFrame, df_new: pd.DataFrame) -> pd.DataFrame:
    """Append new rows, deduplicating by observation_hash."""
    if df_new is None or df_new.empty:
        return df_existing

    if "observation_hash" not in df_new.columns:
        df_new = df_new.copy()
        df_new["observation_hash"] = df_new.apply(make_hash, axis=1)

    existing_hashes = set(df_existing["observation_hash"].dropna())
    df_unique = df_new[~df_new["observation_hash"].isin(existing_hashes)].copy()
    dupes = len(df_new) - len(df_unique)

    if df_unique.empty:
        print(f"  All {len(df_new)} fetched rows are duplicates — no changes")
        return df_existing

    print(f"  Appending {len(df_unique)} new rows ({dupes} duplicates dropped)")

    for col in df_existing.columns:
        if col not in df_unique.columns:
            df_unique[col] = None
    df_unique = df_unique[df_existing.columns]

    combined = pd.concat([df_existing, df_unique], ignore_index=True)
    return combined.sort_values(
        ["country", "source_key", "observation_date"]
    ).reset_index(drop=True)


# ── Data loading (for visualization) ─────────────────────────────────────────


def df_to_json(df: pd.DataFrame) -> list:
    data = []
    for _, row in df.iterrows():
        r = {}
        for col in df.columns:
            v = row[col]
            if pd.isna(v):
                r[col] = None
            elif isinstance(v, pd.Timestamp):
                r[col] = v.strftime("%Y-%m-%d")
            elif isinstance(v, (int, float)):
                r[col] = float(v)
            else:
                r[col] = str(v)
        data.append(r)
    return data


def load_fuel_data(
    csv_path: Path = PRIMARY_CSV,
    secondary_path: Path | None = SECONDARY_CSV,
) -> dict:
    """Load and merge primary + secondary CSVs into a per-country dict for visualization."""
    df = pd.read_csv(csv_path, low_memory=False)
    if secondary_path is not None and secondary_path.exists():
        df2 = pd.read_csv(secondary_path, low_memory=False)
        df = df[~df["country"].isin(SECONDARY_ONLY_COUNTRIES)]
        df = pd.concat([df, df2], ignore_index=True)
        if "observation_hash" in df.columns:
            df = df.drop_duplicates(subset="observation_hash")
    df["observation_date"] = pd.to_datetime(df["observation_date"])

    # Philippines: drop RON 97 (premium gasoline not tracked in the dashboard)
    ph_ron97_mask = (df["country"] == "Philippines") & (df["fuel_product"] == "RON 97")
    if ph_ron97_mask.any():
        df = df[~ph_ron97_mask].copy()

    # Drop redundant GPP rows for Malaysia and Cambodia: country-specific sources
    # (my_mof_weekly_petroleum, kh_ptt_monthly_prices) provide better coverage and
    # canonical product names. GPP rows are only ~1 week of data, conflict with
    # official source prices, and create spurious end-of-series spikes.
    gpp_drop_mask = (
        (
            (df["country"] == "Malaysia")
            & df["source_key"].str.startswith("gpp_MYS_", na=False)
        )
        | (
            (df["country"] == "Cambodia")
            & df["source_key"].str.startswith("gpp_KHM_", na=False)
        )
        | (
            (df["country"] == "Lao PDR")
            & df["source_key"].str.startswith("gpp_LAO_", na=False)
        )
    )
    if gpp_drop_mask.any():
        df = df[~gpp_drop_mask].copy()

    # Singapore: drop town_gas tariffs from fuel price visualizations
    sg_town_gas_mask = (df["country"] == "Singapore") & (
        df["fuel_family"] == "town_gas"
    )
    if sg_town_gas_mask.any():
        df = df[~sg_town_gas_mask].copy()

    # Normalise Cambodia fuel_product names across sources so all diesel rows
    # share one chip and all gasoline rows share one chip in the visualiser.
    _KH_PRODUCT_REMAP = {
        # source_key -> {old_product -> (new_product, new_quality_group)}
        "kh_ptt_monthly_prices": {
            "Super": ("Gasoline", "premium"),
            "Regular": ("Gasoline", "regular"),
        },
        "kh_moc_fuel_notices": {
            "Regular Gasoline": ("Gasoline", "regular"),
            "Diesel": ("Diesel", "regular"),
        },
    }
    # GPP Cambodia sources: rename to canonical names regardless of exact source_key suffix
    _KH_GPP_PROD_REMAP = {
        "Diesel (regular)": ("Diesel", "regular"),
        "Gasoline (Octane-95)": ("Gasoline", "regular"),
    }
    for src_key, prod_map in _KH_PRODUCT_REMAP.items():
        for old_prod, (new_prod, new_qg) in prod_map.items():
            mask = (df["source_key"] == src_key) & (df["fuel_product"] == old_prod)
            if mask.any():
                df.loc[mask, "fuel_product"] = new_prod
                df.loc[mask, "quality_group"] = new_qg

    kh_gpp_mask = (df["country"] == "Cambodia") & (
        df["source_key"].str.startswith("gpp_KHM_", na=False)
    )
    for old_prod, (new_prod, new_qg) in _KH_GPP_PROD_REMAP.items():
        mask = kh_gpp_mask & (df["fuel_product"] == old_prod)
        if mask.any():
            df.loc[mask, "fuel_product"] = new_prod
            df.loc[mask, "quality_group"] = new_qg

    # Malaysia: geography encoded in product name
    def fix_malaysia(row):
        prod = str(row["fuel_product"])
        if " (East Malaysia)" in prod:
            return pd.Series(
                [prod.replace(" (East Malaysia)", "").strip(), "East Malaysia"]
            )
        if " (Peninsular Malaysia)" in prod:
            return pd.Series(
                [
                    prod.replace(" (Peninsular Malaysia)", "").strip(),
                    "Peninsular Malaysia",
                ]
            )
        return pd.Series([prod, None])

    malaysia_mask = df["country"] == "Malaysia"
    df.loc[malaysia_mask, ["fuel_product", "_my_loc"]] = (
        df[malaysia_mask].apply(fix_malaysia, axis=1).values
    )

    def make_location(row):
        my_loc = row.get("_my_loc")
        if pd.notna(my_loc) and str(my_loc).strip():
            return str(my_loc).strip()
        city = row["city"]
        sub = row["subnational_area"]
        if pd.notna(city) and str(city).strip():
            return str(city).strip()
        if pd.notna(sub) and str(sub).strip():
            if str(sub).strip().lower().startswith("national"):
                return "National"
            return str(sub).strip()
        return "National"

    df["location"] = df.apply(make_location, axis=1)
    df["country"] = df["country"].replace({"Viet Nam": "Vietnam"})

    _STATUS_PRIORITY = {"Final": 0, "official": 1, "Published": 2, "Provisional": 3}
    df["_status_rank"] = df["status"].map(_STATUS_PRIORITY).fillna(99)
    _dedup_key = [
        "country",
        "observation_date",
        "fuel_family",
        "fuel_product",
        "quality_group",
        "location",
    ]
    df = df.sort_values("_status_rank").drop_duplicates(subset=_dedup_key, keep="first")
    df = df.drop(columns="_status_rank")

    keep = [
        "country",
        "observation_date",
        "price_local",
        "currency",
        "unit",
        "fuel_family",
        "fuel_product",
        "quality_group",
        "location",
    ]
    df = df[keep].copy()
    df = df.sort_values("observation_date")

    result = {}
    for country, grp in df.groupby("country"):
        result[country] = df_to_json(grp)
    return result
