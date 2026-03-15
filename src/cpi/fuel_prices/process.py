"""Pipeline: load → normalize → enrich → deduplicate → shape for publish.

Call order inside build_enriched_frame:
  _load_collected_observations → load per-source observations.csv files
  _apply_data_quality_rules   → drop bad products/sources, rename countries
  _normalize_products         → apply FUEL_PRODUCT_MAP (adds fuel_product_standard)
  _derive_location            → Malaysia product parse + city/subnational fallback
  _canonicalize               → series_key/series_label, AU product normalization
  _deduplicate                → single combined pass: aggregate + source/status dedup
  _monthly_rollup             → pre-cutoff monthly aggregation

Public API:
  build_enriched_frame(collect_dir) → DataFrame
  load_stored_observations(base_dir) → DataFrame
  apply_data_quality_rules(df) → DataFrame
  materialize_outputs(staged_dir, collect_dir) → dict
  frame_to_country_series(df) → dict
"""

from __future__ import annotations

import logging
import math
import re
from pathlib import Path

import pandas as pd
from pandas.tseries.offsets import MonthEnd

from .constants import (
    _AU_SOURCE_RANK,
    _STATUS_RANK,
    COLUMNS,
    FUEL_PRODUCT_MAP,
    STAGED_DATA_DIR,
)
from .utils import make_hash

logger = logging.getLogger(__name__)

# ── Canonicalization regexes ──────────────────────────────────────────────────

_WS_RE = re.compile(r"\s+")
_GENERIC_QUALIFIER_RE = re.compile(
    r"^(?P<base>.+?)\s*\((?P<qual>regular|standard|premium|super[\s_-]?premium)\)\s*$",
    re.IGNORECASE,
)
_AU_UNLEADED_RE = re.compile(
    r"^(unleaded(?:\s+petrol\s+average)?|ulp\s*91(?:\s+average)?|unleaded\s*91)$",
    re.IGNORECASE,
)
_AU_DIESEL_RE = re.compile(r"^diesel(?:\s+average)?$", re.IGNORECASE)
_AU_P95_RE = re.compile(r"^(premium\s*95|gasoline\s*\(octane-95\))$", re.IGNORECASE)
_AU_P98_RE = re.compile(r"^premium\s*98$", re.IGNORECASE)
_AU_E10_RE = re.compile(r"^e10$", re.IGNORECASE)
_AU_E20_RE = re.compile(r"^e20$", re.IGNORECASE)
_AU_E85_RE = re.compile(r"^e85$", re.IGNORECASE)
_AU_LPG_RE = re.compile(r"^lpg$", re.IGNORECASE)
_AU_PDL_RE = re.compile(r"^pdl$", re.IGNORECASE)
_MY_LOCATION_RE = re.compile(
    r"\((?P<loc>East Malaysia|Peninsular Malaysia)\)\s*$", re.IGNORECASE
)

# ── Dedup configuration ───────────────────────────────────────────────────────

_MONTHLY_ROLLUP_CUTOFF = pd.Timestamp("2026-01-01")
_DEDUP_KEY = ["country", "observation_date", "location", "fuel_product"]
_STATUS_RANK_DEFAULT = 9

# Columns used for intra-source location aggregation (averaging same-source duplicates)
_AGG_GROUP_COLS = (
    "country",
    "wb_iso3",
    "location",
    "fuel_family",
    "fuel_product",
    "series_key",
    "series_label",
    "sulfur_standard",
    "gas_type",
    "delivery_type",
    "consumer_segment",
    "currency",
    "unit",
    "tax_status",
    "source_key",
    "source_name",
    "source_url",
    "source_type",
    "effective_from",
    "effective_to",
    "observation_date",
    "publication_frequency",
    "observation_method",
    "status",
)


# ── Helper utilities ──────────────────────────────────────────────────────────


def _is_missing(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, float):
        return math.isnan(value)
    if isinstance(value, str):
        return value.strip().lower() in {"", "nan", "none"}
    return False


def _clean_text(value: object) -> str | None:
    if _is_missing(value):
        return None
    text = _WS_RE.sub(" ", str(value)).strip()
    return text or None


def _as_float(value: object) -> float | None:
    if _is_missing(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _strip_internal(df: pd.DataFrame) -> pd.DataFrame:
    drop = [c for c in df.columns if c.startswith("_")]
    return df.drop(columns=drop, errors="ignore")


def _compute_source_rank(row: pd.Series) -> int:
    """Return publish-time source preference rank (lower = better)."""
    country = str(row.get("country") or "")
    source_key = str(row.get("source_key") or "")
    if country == "Australia":
        return _AU_SOURCE_RANK.get(source_key, 50)
    if source_key.startswith("gpp_"):
        return 90
    source_type = str(row.get("source_type") or "").lower()
    if source_type == "official":
        return 10
    if source_type == "industry":
        return 20
    return 50


# ── Load stage ────────────────────────────────────────────────────────────────


def load_stored_observations(base_dir: Path) -> pd.DataFrame:
    """Load all per-source observations.csv files recursively under base_dir."""
    frames: list[pd.DataFrame] = []
    for path in sorted(base_dir.rglob("observations.csv")):
        try:
            obs = pd.read_csv(path, low_memory=False)
        except OSError as exc:
            logger.warning("Could not read %s: %s", path, exc)
            continue
        if obs.empty:
            continue
        obs = obs.copy()
        obs["_storage_path"] = str(path.relative_to(base_dir))
        frames.append(obs)

    if not frames:
        return pd.DataFrame(columns=pd.Index(COLUMNS))

    combined = pd.concat(frames, ignore_index=True, sort=False)
    for col in COLUMNS:
        if col not in combined.columns:
            combined[col] = None
    return combined


def _load_collected_observations(collect_dir: Path) -> pd.DataFrame:
    """Load per-source observations, split into fuel and commodity frames."""
    all_obs = load_stored_observations(base_dir=collect_dir)
    if all_obs.empty:
        return pd.DataFrame(columns=pd.Index(COLUMNS))

    commodity_mask = all_obs["country"].isin(["Global", "EAP"]) | all_obs[
        "source_key"
    ].str.startswith("global_", na=False)
    return all_obs[~commodity_mask].copy()


# ── Data quality rules ────────────────────────────────────────────────────────


def _drop_untracked_products(df: pd.DataFrame) -> pd.DataFrame:
    mask = (df["country"] == "Philippines") & (df["fuel_product"] == "RON 97")
    if mask.any():
        df = df[~mask].copy()
    mask = (df["country"] == "Singapore") & (df["fuel_family"] == "town_gas")
    if mask.any():
        df = df[~mask].copy()
    return df


def _drop_low_priority_sources(df: pd.DataFrame) -> pd.DataFrame:
    gpp_drop = (
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
    if gpp_drop.any():
        df = df[~gpp_drop].copy()
    return df


def _rename_countries(df: pd.DataFrame) -> pd.DataFrame:
    return df.assign(
        country=df["country"].replace(
            {
                "Viet Nam": "Vietnam",
                "South Korea": "Korea, Rep.",
                "Laos": "Lao PDR",
            }
        )
    )


# Country-specific product name normalization (legacy → canonical)
_VN_PRODUCT_NORM: dict[str, str] = {
    "RON95-III": "RON 95-III",
    "E5RON92": "E5 RON 92-II",
    "Diesel 0.05S": "Diesel 0.05S-II",
    "Mazut 180CST 3.5S": "Mazut N02B (3.5S)",
}

_PH_PRODUCT_NORM: dict[str, str] = {
    "RON95": "RON 95",
    "DIESEL PLUS": "Diesel Plus",
}


def _normalize_country_products(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize legacy product names to canonical names for Vietnam and Philippines."""
    if df.empty or "fuel_product" not in df.columns:
        return df
    df = df.copy()

    vn_mask = df["country"].isin(["Vietnam", "Viet Nam"])
    if vn_mask.any():
        df.loc[vn_mask, "fuel_product"] = df.loc[vn_mask, "fuel_product"].replace(
            _VN_PRODUCT_NORM
        )

    ph_mask = df["country"] == "Philippines"
    if ph_mask.any():
        df.loc[ph_mask, "fuel_product"] = df.loc[ph_mask, "fuel_product"].replace(
            _PH_PRODUCT_NORM
        )

    return df


def _dedup_overlapping_effective_dates(df: pd.DataFrame) -> pd.DataFrame:
    """For NZ MBIE, keep only the row with the latest effective_from per (fuel_product, observation_date).

    The MBIE CSV contains overlapping Final/Provisional rows for the same
    observation_date.  The newer effective_from represents the current survey.
    """
    if df.empty or "effective_from" not in df.columns:
        return df
    nz_mbie_mask = df["source_key"] == "nz_mbie_weekly_fuel"
    if not nz_mbie_mask.any():
        return df
    nz = df[nz_mbie_mask].copy()
    rest = df[~nz_mbie_mask]
    nz = nz.sort_values("effective_from", ascending=False)
    nz = nz.drop_duplicates(subset=["fuel_product", "observation_date"], keep="first")
    return pd.concat([rest, nz], ignore_index=True)


def _drop_superseded_forward_fills(df: pd.DataFrame) -> pd.DataFrame:
    """Drop forward_filled rows when a real source covers the same series.

    For each (country, fuel_product), if forward_filled rows from one source
    overlap with real observations from another source, drop the forward_filled
    rows from the overlap period onward.  This prevents stale forward_fills
    from interleaving with fresh weekly data (e.g. Vietnam Mazut).
    """
    if df.empty or "status" not in df.columns:
        return df
    ff_mask = df["status"] == "forward_filled"
    if not ff_mask.any():
        return df
    real = df[~ff_mask]
    ff = df[ff_mask]
    drop_idx: list[int] = []
    for (country, product), ff_group in ff.groupby(["country", "fuel_product"]):
        real_group = real[
            (real["country"] == country) & (real["fuel_product"] == product)
        ]
        if real_group.empty:
            continue
        real_min = real_group["observation_date"].min()
        superseded = ff_group[ff_group["observation_date"] >= real_min]
        drop_idx.extend(superseded.index.tolist())
    if drop_idx:
        df = df.drop(index=drop_idx).copy()
    return df


def _apply_data_quality_rules(df: pd.DataFrame) -> pd.DataFrame:
    """Drop untracked products/sources and apply canonical country names."""
    if df.empty:
        return df
    df = _drop_untracked_products(df)
    df = _drop_low_priority_sources(df)
    df = _drop_superseded_forward_fills(df)
    df = _dedup_overlapping_effective_dates(df)
    df = _normalize_country_products(df)
    df = _rename_countries(df)
    return df


def _normalize_products(df: pd.DataFrame) -> pd.DataFrame:
    """Apply FUEL_PRODUCT_MAP to create fuel_product_standard column.

    Raises ValueError if any fuel_product is not in the map.
    """
    if df.empty or "fuel_product" not in df.columns:
        return df

    df = df.copy()
    unique_products = df["fuel_product"].dropna().unique()

    missing = [
        str(p).strip()
        for p in unique_products
        if str(p).strip() not in FUEL_PRODUCT_MAP
    ]
    if missing:
        raise ValueError(
            f"Unmapped fuel_product values found: {sorted(missing)}. "
            f"Add them to FUEL_PRODUCT_MAP in constants.py"
        )

    df["fuel_product_standard"] = df["fuel_product"].apply(
        lambda x: FUEL_PRODUCT_MAP.get(str(x).strip(), None) if pd.notna(x) else None
    )
    return df


# ── Location derivation ───────────────────────────────────────────────────────


def _parse_malaysia_location(product: str) -> tuple[str, str | None]:
    m = _MY_LOCATION_RE.search(str(product))
    if m:
        loc = m.group("loc")
        clean = _MY_LOCATION_RE.sub("", product).strip()
        return clean, loc
    return product, None


def _resolve_location(row: pd.Series) -> str:
    my_loc = row.get("_my_loc")
    if pd.notna(my_loc) and str(my_loc).strip():
        return str(my_loc).strip()

    city = row.get("city")
    subnational = row.get("subnational_area")

    if pd.notna(city) and str(city).strip():
        return str(city).strip()

    if pd.notna(subnational) and str(subnational).strip():
        s = str(subnational).strip()
        if s.lower().startswith("national"):
            return "National"
        return s

    return "National"


def _derive_location(df: pd.DataFrame) -> pd.DataFrame:
    """Add canonical location column; parse Malaysia location from product name."""
    df = df.copy()

    malaysia_mask = df["country"] == "Malaysia"
    if malaysia_mask.any():
        parsed = df.loc[malaysia_mask, "fuel_product"].apply(_parse_malaysia_location)
        df.loc[malaysia_mask, "fuel_product"] = parsed.apply(lambda t: t[0])
        df.loc[malaysia_mask, "_my_loc"] = parsed.apply(lambda t: t[1])
    else:
        df["_my_loc"] = None

    df["location"] = df.apply(_resolve_location, axis=1)
    df = df.drop(columns=["_my_loc"], errors="ignore")
    return df


# ── Canonicalization ──────────────────────────────────────────────────────────


def _normalize_location_text(value: object) -> str | None:
    text = _clean_text(value)
    if text is None:
        return None
    if text.lower().startswith("national"):
        return "National"
    if text.isupper() and any(ch.isalpha() for ch in text):
        return text.title()
    return text


def _normalize_generic_product_and_quality(
    row: pd.Series,
) -> tuple[str | None, str | None]:
    product = _clean_text(row.get("fuel_product"))
    quality = _clean_text(row.get("quality_group"))
    if quality is not None:
        quality = quality.lower().replace("super premium", "super_premium")

    if product is None:
        return product, quality

    match = _GENERIC_QUALIFIER_RE.match(product)
    if match:
        product = _clean_text(match.group("base"))
        parsed_quality = match.group("qual").lower().replace("-", " ").replace("_", " ")
        parsed_quality = parsed_quality.replace("super premium", "super_premium")
        if quality is None:
            quality = parsed_quality

    if quality == "standard" and str(row.get("fuel_family") or "").lower() == "diesel":
        quality = "regular"

    return product, quality


def _canonicalize_australia_row(row: pd.Series) -> pd.Series:
    if str(row.get("country") or "") != "Australia":
        return row

    product = _clean_text(row.get("fuel_product")) or ""
    family = str(row.get("fuel_family") or "").lower()

    if _AU_PDL_RE.match(product):
        row["fuel_family"] = "diesel"
        row["fuel_product"] = "Premium Diesel"
        row["quality_group"] = "premium"
        return row

    if family == "diesel":
        if _AU_DIESEL_RE.match(product) or product.lower() == "diesel":
            row["fuel_product"] = "Diesel"
            row["quality_group"] = "regular"
            return row

    if family == "gasoline":
        if _AU_UNLEADED_RE.match(product):
            row["fuel_product"] = "Unleaded 91"
            row["quality_group"] = "regular"
            if _is_missing(row.get("octane_ron")):
                row["octane_ron"] = 91
            if _is_missing(row.get("ethanol_pct")):
                row["ethanol_pct"] = 0
            return row
        if _AU_P95_RE.match(product):
            row["fuel_product"] = "Premium 95"
            row["quality_group"] = "premium"
            row["octane_ron"] = 95
            return row
        if _AU_P98_RE.match(product):
            row["fuel_product"] = "Premium 98"
            row["quality_group"] = "premium"
            row["octane_ron"] = 98
            return row
        if _AU_E10_RE.match(product):
            row["fuel_product"] = "E10"
            row["quality_group"] = "regular"
            if _is_missing(row.get("octane_ron")):
                row["octane_ron"] = 91
            if _is_missing(row.get("ethanol_pct")):
                row["ethanol_pct"] = 10
            return row
        if _AU_E20_RE.match(product):
            row["fuel_product"] = "E20"
            if _is_missing(row.get("ethanol_pct")):
                row["ethanol_pct"] = 20
            return row
        if _AU_E85_RE.match(product):
            row["fuel_product"] = "E85"
            if _is_missing(row.get("ethanol_pct")):
                row["ethanol_pct"] = 85
            return row

    if family == "lpg" and _AU_LPG_RE.match(product):
        row["fuel_product"] = "LPG"
        row["quality_group"] = None

    return row


def _series_fields(row: pd.Series) -> tuple[str, str]:
    family = str(row.get("fuel_family") or "").strip().lower()
    quality = str(row.get("quality_group") or "").strip().lower()
    product = str(row.get("fuel_product") or "").strip()
    ethanol = _as_float(row.get("ethanol_pct"))
    octane = _as_float(row.get("octane_ron"))

    if family == "diesel":
        if quality == "premium" or product == "Premium Diesel":
            return "diesel|||premium", "Diesel - Premium"
        return "diesel|||regular", "Diesel - Regular"

    if family == "gasoline":
        if ethanol is not None and ethanol >= 10:
            return "gasoline|||ethanol", "Gasoline - Ethanol Blend"
        if quality == "premium" or (octane is not None and octane >= 95):
            return "gasoline|||premium", "Gasoline - Premium"
        return "gasoline|||regular", "Gasoline - Regular"

    if family == "lpg":
        return "lpg", "LPG"
    if family == "kerosene":
        return "kerosene", "Kerosene"
    if family == "natural_gas":
        return "natural_gas", "Natural Gas"

    label = _clean_text(product) or family.replace("_", " ").title() or "Unknown"
    key = family or label.lower().replace(" ", "_")
    return key, label


def _canonicalize(df: pd.DataFrame) -> pd.DataFrame:
    """Canonicalize product/location fields and derive series_key/series_label."""
    if df.empty:
        return df

    df = df.copy()

    if "location" in df.columns:
        df["location"] = df["location"].apply(_normalize_location_text)
    if "city" in df.columns:
        df["city"] = df["city"].apply(_normalize_location_text)
    if "subnational_area" in df.columns:
        df["subnational_area"] = df["subnational_area"].apply(_clean_text)

    normalized = [
        _normalize_generic_product_and_quality(row) for _, row in df.iterrows()
    ]
    df["fuel_product"] = [item[0] for item in normalized]
    df["quality_group"] = [item[1] for item in normalized]

    canonical_rows = [
        _canonicalize_australia_row(row).to_dict() for _, row in df.iterrows()
    ]
    df = pd.DataFrame(canonical_rows, columns=df.columns)

    series_fields = [_series_fields(row) for _, row in df.iterrows()]
    df["series_key"] = [item[0] for item in series_fields]
    df["series_label"] = [item[1] for item in series_fields]
    return df


# ── Single-pass deduplication ─────────────────────────────────────────────────


def _deduplicate(df: pd.DataFrame) -> pd.DataFrame:
    """Single combined dedup pass.

    Step 1: Sort by (source_rank, status_rank) so groupby "first" picks best row.
    Step 2: Average price within same (source, location, date, series) — handles
            intra-source location normalization (e.g. INGLEBURN vs Ingleburn).
    Step 3: Sort again and drop_duplicates on DEDUP_KEY — picks best source
            per (country, date, location, series_key) slot.
    """
    if df.empty:
        return df

    df = df.copy()
    df["_source_rank"] = df.apply(_compute_source_rank, axis=1)
    df["_status_rank"] = (
        df["status"]
        .str.lower()
        .map(_STATUS_RANK)
        .fillna(_STATUS_RANK_DEFAULT)
        .astype(int)
        if "status" in df.columns
        else 0
    )

    # Step 1: sort so groupby "first" captures the best-ranked row
    df = df.sort_values(["_source_rank", "_status_rank", "observation_date"])

    # Step 2: average prices within same (source, location, date, series)
    agg_cols = [c for c in _AGG_GROUP_COLS if c in df.columns]
    if agg_cols and "price_local" in df.columns:
        pass_cols = [
            c
            for c in df.columns
            if c not in set(agg_cols) | {"price_local", "observation_hash"}
        ]
        agg_map: dict[str, str] = {c: "first" for c in pass_cols}
        agg_map["price_local"] = "mean"
        df = df.groupby(agg_cols, dropna=False, as_index=False).agg(agg_map)
        df["price_local"] = df["price_local"].round(4)

    # Step 3: pick best source for each (country, date, location, series_key)
    dedup_key = [c for c in _DEDUP_KEY if c in df.columns]
    if len(dedup_key) >= 3:
        df = df.sort_values(["_source_rank", "_status_rank"])
        df = df.drop_duplicates(subset=dedup_key, keep="first")

    # Rehash after dedup
    if "observation_hash" in df.columns:
        df["observation_hash"] = df.apply(lambda row: make_hash(row.to_dict()), axis=1)

    return _strip_internal(df).reset_index(drop=True)


# ── Monthly rollup ────────────────────────────────────────────────────────────


def _first_non_null(values: pd.Series):
    for v in values:
        if pd.notna(v):
            return v
    return None


def _monthly_rollup(
    df: pd.DataFrame,
    cutoff: pd.Timestamp = _MONTHLY_ROLLUP_CUTOFF,
) -> pd.DataFrame:
    """Roll up pre-cutoff observations to monthly grain."""
    if df.empty or "observation_date" not in df.columns:
        return df

    df = df.copy()
    df["observation_date"] = pd.to_datetime(df["observation_date"], errors="coerce")
    older = df[df["observation_date"] < cutoff].copy()
    newer = df[df["observation_date"] >= cutoff].copy()

    if older.empty:
        return df

    older["_month_start"] = (
        older["observation_date"].dt.to_period("M").dt.to_timestamp()
    )

    dedup_key = [
        c for c in _DEDUP_KEY if c in older.columns and c != "observation_date"
    ]
    group_cols = dedup_key + ["_month_start"]

    def _agg(group: pd.DataFrame) -> pd.Series:
        row: dict[str, object | None] = {}
        for col in group.columns:
            if col in {
                "observation_date",
                "effective_from",
                "effective_to",
                "_month_start",
            }:
                continue
            if col == "price_local":
                row[col] = (
                    float(group[col].mean()) if group[col].notna().any() else None
                )
            else:
                row[col] = _first_non_null(group[col])

        month_start = group["_month_start"].iloc[0]
        month_end = (month_start + MonthEnd(1)).normalize()
        row["observation_date"] = month_start
        row["effective_from"] = month_start
        row["effective_to"] = month_end
        return pd.Series(row)

    rolled = older.groupby(group_cols, dropna=False).apply(_agg).reset_index(drop=True)
    return pd.concat([rolled, newer], ignore_index=True)


# ── Public pipeline functions ─────────────────────────────────────────────────


def apply_data_quality_rules(df: pd.DataFrame) -> pd.DataFrame:
    """Apply data quality rules: product drops, low-priority source drops, country renames."""
    df = _apply_data_quality_rules(df)
    return _strip_internal(df).sort_values("observation_date").reset_index(drop=True)


def build_enriched_frame(
    collect_dir: Path | None = None,
) -> pd.DataFrame:
    """Full pipeline: load → normalize → enrich → deduplicate.

    Loads collected per-source observations, applies all data quality rules,
    derives location, canonicalizes products, deduplicates, and returns a
    publish-ready DataFrame.
    """
    from .constants import DATA_DIR

    if collect_dir is None:
        collect_dir = DATA_DIR

    df = _load_collected_observations(collect_dir)
    if df.empty:
        return pd.DataFrame(columns=pd.Index(COLUMNS))

    df["observation_date"] = pd.to_datetime(df["observation_date"], errors="coerce")
    df = _strip_internal(df)
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = None

    # Normalize
    df = _apply_data_quality_rules(df)
    df = _normalize_products(df)

    # Enrich
    df = _derive_location(df)
    df = _canonicalize(df)

    # Single dedup pass
    df = _deduplicate(df)

    # Monthly rollup for historical data
    df = _monthly_rollup(df)

    sort_cols = [
        c
        for c in ["country", "observation_date", "fuel_product", "location"]
        if c in df.columns
    ]
    if sort_cols:
        df = df.sort_values(sort_cols).reset_index(drop=True)

    logger.info(
        "build_enriched_frame: %d rows, %d countries, %d source_keys",
        len(df),
        df["country"].nunique() if "country" in df.columns else 0,
        df["source_key"].nunique() if "source_key" in df.columns else 0,
    )
    return df


def materialize_outputs(
    staged_dir: Path = STAGED_DATA_DIR,
    collect_dir: Path | None = None,
) -> dict:
    """Run full pipeline and write enriched CSV to staged_dir/enrich/."""
    df = build_enriched_frame(collect_dir=collect_dir)

    out_path = staged_dir / "enrich" / "retail_series_enriched.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    logger.info("Saved %d rows -> %s", len(df), out_path)

    return {"enriched_path": out_path, "enriched_rows": len(df)}


# ── Publish-time serialization ────────────────────────────────────────────────


def frame_to_country_series(
    df: pd.DataFrame,
) -> dict[str, list[dict[str, object | None]]]:
    """Group enriched fuel rows into publish-ready per-country payloads."""

    def _to_records(group: pd.DataFrame) -> list[dict[str, object | None]]:
        records: list[dict[str, object | None]] = []
        for _, row in group.iterrows():
            record: dict[str, object | None] = {}
            for col in group.columns:
                val = row[col]
                if pd.isna(val):
                    record[col] = None
                elif isinstance(val, pd.Timestamp):
                    record[col] = val.strftime("%Y-%m-%d")
                elif isinstance(val, (int, float)):
                    record[col] = float(val)
                else:
                    record[col] = str(val)
            records.append(record)
        return records

    return {
        str(country): _to_records(group) for country, group in df.groupby("country")
    }
