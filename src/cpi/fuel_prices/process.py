"""Pipeline: load → normalize → enrich → deduplicate → shape for publish.

Call order inside build_enriched_frame:
  _load_collected_observations → load per-source observations.csv files
  _apply_data_quality_rules   → drop bad products/sources, rename countries
  _normalize_products         → apply FUEL_PRODUCT_MAP (adds fuel_product_standard)
  _derive_fuel_family         → map fuel_product_standard → fuel_family
  _derive_location            → Malaysia product parse + city/subnational/address fallback
  _canonicalize               → quality_group extraction, series_key/series_label
  _deduplicate                → single combined pass: aggregate + source dedup

Public API:
  build_enriched_frame(collect_dir) → DataFrame
  load_stored_observations(base_dir) → DataFrame
  apply_data_quality_rules(df) → DataFrame
  materialize_outputs(staged_dir, collect_dir) → dict
  frame_to_country_series(df) → dict
"""

from __future__ import annotations

from datetime import date
import logging
import math
import re
from pathlib import Path

import pandas as pd

from .constants import (
    COLUMNS,
    ENRICHED_COLUMNS,
    FUEL_PRODUCT_MAP,
    STAGED_DATA_DIR,
)
from .utils import make_hash

logger = logging.getLogger(__name__)

_COUNTRY_RENAME_MAP = {
    "Viet Nam": "Vietnam",
    "South Korea": "Korea, Rep.",
    "Laos": "Lao PDR",
}

_STATE_CONTROLLED_COUNTRY_VARIANTS: dict[str, set[str]] = {
    "Cambodia": {"Cambodia"},
    "China": {"China"},
    "Fiji": {"Fiji"},
    "Indonesia": {"Indonesia"},
    "Lao PDR": {"Lao PDR", "Laos"},
    "Malaysia": {"Malaysia"},
    "Mongolia": {"Mongolia"},
    "Myanmar": {"Myanmar"},
    "Papua New Guinea": {"Papua New Guinea"},
    "Samoa": {"Samoa"},
    "Taiwan": {"Taiwan", "Taiwan, China"},
    "Vietnam": {"Vietnam", "Viet Nam"},
}
_STATE_CONTROLLED_COUNTRIES = set(_STATE_CONTROLLED_COUNTRY_VARIANTS)
_COUNTRY_TO_STATE_CONTROLLED_CANONICAL = {
    variant: canonical
    for canonical, variants in _STATE_CONTROLLED_COUNTRY_VARIANTS.items()
    for variant in variants
}

# ── Australia source preference ranks (lower = higher priority) ───────────────
_AU_SOURCE_RANK: dict[str, int] = {
    "au_fuelwatch_perth_daily": 0,
    "au_nsw_fuelcheck_history": 0,
    "au_accc_5largestcities_quarterly": 1,
    "au_aip_tgp_weekly": 2,
    "gpp_AUS_diesel_weekly": 9,
    "gpp_AUS_gasoline_weekly": 9,
}

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

_DEDUP_KEY = ["country", "observation_date", "location", "fuel_product"]

# Columns used for intra-source location aggregation (averaging same-source duplicates)
_AGG_GROUP_COLS = (
    "country",
    "location",
    "fuel_family",
    "fuel_product",
    "series_key",
    "series_label",
    "quality_group",
    "currency",
    "unit",
    "source_key",
    "observation_date",
)

# ── Fuel family derivation map ────────────────────────────────────────────────

_FAMILY_FROM_STANDARD: dict[str, str] = {
    "gasoline_regular": "gasoline",
    "gasoline_midgrade": "gasoline",
    "gasoline_premium": "gasoline",
    "gasoline_ethanol_low": "gasoline",
    "gasoline_ethanol_medium": "gasoline",
    "gasoline_ethanol_high": "gasoline",
    "gasoline_branded": "gasoline",
    "diesel_standard": "diesel",
    "diesel_premium": "diesel",
    "diesel_low_sulfur": "diesel",
    "diesel_ultra_low_sulfur": "diesel",
    "diesel_branded": "diesel",
    "diesel_biodiesel": "diesel",
    "kerosene": "kerosene",
    "lpg_household": "lpg",
    "lpg_bulk": "lpg",
    "lpg_autogas": "lpg",
    "cng": "natural_gas",
    "ngv": "natural_gas",
    "lng": "natural_gas",
    "electricity_ev": "electricity",
    "fuel_oil_mazut": "fuel_oil",
    "premix": "gasoline",
    "crude_oil": "crude_oil",
}


# ── Helper utilities ──────────────────────────────────────────────────────────


def _is_missing(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, float):
        return math.isnan(value)
    if isinstance(value, str):
        return value.strip().lower() in {"", "nan", "none"}
    return False


def _today() -> date:
    return date.today()


def _canonical_country_name(value: object) -> str | None:
    text = _clean_text(value)
    if text is None:
        return None
    text = _COUNTRY_RENAME_MAP.get(text, text)
    return _COUNTRY_TO_STATE_CONTROLLED_CANONICAL.get(text, text)


def _country_variants(country: str) -> set[str]:
    canonical = _canonical_country_name(country)
    if canonical is None:
        return set()
    return set(_STATE_CONTROLLED_COUNTRY_VARIANTS.get(canonical, {canonical}))


def _build_observation_hash(row: dict[str, object]) -> str:
    payload = dict(row)
    obs_date = payload.get("observation_date")
    if isinstance(obs_date, pd.Timestamp):
        payload["observation_date"] = obs_date.strftime("%Y-%m-%d")
    return make_hash(payload)


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
    return 10


# ── Load stage ────────────────────────────────────────────────────────────────

# Directory slugs whose observations.csv files are commodity/reference data, not fuel prices
_COMMODITY_SLUGS = {"global", "eap"}


def load_stored_observations(base_dir: Path) -> pd.DataFrame:
    """Load all per-source observations.csv files recursively under base_dir.

    Skips any path whose components include a directory starting with '_'
    (e.g. _archive, _diagnostic_backups).
    """
    frames: list[pd.DataFrame] = []
    for path in sorted(base_dir.rglob("observations.csv")):
        rel_parts = path.relative_to(base_dir).parts
        if any(part.startswith("_") for part in rel_parts):
            continue
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
    """Load per-source observations, excluding commodity sources."""
    all_obs = load_stored_observations(base_dir=collect_dir)
    if all_obs.empty:
        return pd.DataFrame(columns=pd.Index(COLUMNS))

    commodity_mask = all_obs["country"].isin(["Global", "EAP"]) | all_obs[
        "source_key"
    ].str.startswith("global_", na=False)
    return all_obs[~commodity_mask].copy()


def _load_from_paths(paths: list[Path], collect_dir: Path) -> pd.DataFrame:
    """Load full observations from a specific list of source paths."""
    frames: list[pd.DataFrame] = []
    for path in paths:
        try:
            obs = pd.read_csv(path, low_memory=False)
        except OSError as exc:
            logger.warning("Could not read %s: %s", path, exc)
            continue
        if obs.empty:
            continue
        obs = obs.copy()
        obs["_storage_path"] = str(path.relative_to(collect_dir))
        frames.append(obs)

    if not frames:
        return pd.DataFrame(columns=pd.Index(COLUMNS))

    combined = pd.concat(frames, ignore_index=True, sort=False)
    for col in COLUMNS:
        if col not in combined.columns:
            combined[col] = None
    return combined


def _find_dirty_countries(
    collect_dir: Path,
    enriched_mtime: float,
) -> dict[str, list[Path]]:
    """Scan source files for any modified after the enriched output was written.

    Returns a dict mapping country name → list of source paths newer than enriched.
    """
    dirty: dict[str, list[Path]] = {}

    for path in sorted(collect_dir.rglob("observations.csv")):
        rel_parts = path.relative_to(collect_dir).parts
        if any(part.startswith("_") for part in rel_parts):
            continue
        try:
            slug_dir = rel_parts[0]
        except IndexError:
            continue
        if slug_dir in _COMMODITY_SLUGS:
            continue

        if path.stat().st_mtime <= enriched_mtime:
            continue

        try:
            df = pd.read_csv(path, usecols=["country"], nrows=1, low_memory=False)
        except (OSError, ValueError) as exc:
            logger.warning("Could not scan %s: %s", path, exc)
            continue

        if df.empty:
            continue

        country = _canonical_country_name(df["country"].iloc[0])
        if country is not None:
            dirty.setdefault(country, []).append(path)

    return dirty


def _find_stale_state_controlled_countries(
    df: pd.DataFrame,
    as_of: date | None = None,
) -> set[str]:
    if df.empty or "country" not in df.columns or "observation_date" not in df.columns:
        return set()

    check_date = pd.Timestamp(as_of or _today()).normalize()
    work = df.copy()
    work["_canonical_country"] = work["country"].map(_canonical_country_name)
    work = work[work["_canonical_country"].isin(_STATE_CONTROLLED_COUNTRIES)].copy()
    if work.empty:
        return set()

    work["observation_date"] = pd.to_datetime(work["observation_date"], errors="coerce")
    work = work[work["observation_date"].notna()].copy()
    if work.empty:
        return set()

    group_cols = [
        c
        for c in ["_canonical_country", "location", "fuel_product", "series_key"]
        if c in work.columns
    ]
    if len(group_cols) < 4:
        return set()

    last_dates = work.groupby(group_cols, dropna=False)["observation_date"].max()
    stale = last_dates[last_dates.dt.normalize() < check_date]
    if stale.empty:
        return set()

    return set(stale.reset_index()["_canonical_country"].astype(str))


# ── Data quality rules ────────────────────────────────────────────────────────


def _drop_untracked_products(df: pd.DataFrame) -> pd.DataFrame:
    mask = (df["country"] == "Philippines") & (df["fuel_product"] == "RON 97")
    if mask.any():
        df = df[~mask].copy()
    # Singapore CityEnergy town gas tariffs are utility billing, not motor fuel prices
    mask = df["source_key"] == "sg_cityenergy_town_gas"
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
    return df.assign(country=df["country"].replace(_COUNTRY_RENAME_MAP))


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

_NZ_PRODUCT_NORM: dict[str, str] = {
    "Unleaded 91": "Regular Petrol",
    "Unleaded 95": "Premium Petrol 95R",
}

_AU_PRODUCT_NORM: dict[str, str] = {
    "Unleaded 91": "Unleaded",
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

    nz_mask = df["country"] == "New Zealand"
    if nz_mask.any():
        df.loc[nz_mask, "fuel_product"] = df.loc[nz_mask, "fuel_product"].replace(
            _NZ_PRODUCT_NORM
        )

    au_mask = df["country"] == "Australia"
    if au_mask.any():
        df.loc[au_mask, "fuel_product"] = df.loc[au_mask, "fuel_product"].replace(
            _AU_PRODUCT_NORM
        )

    return df


def _apply_data_quality_rules(df: pd.DataFrame) -> pd.DataFrame:
    """Drop untracked products/sources and apply canonical country names."""
    if df.empty:
        return df
    df = _drop_untracked_products(df)
    df = _drop_low_priority_sources(df)
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


def _derive_fuel_family(df: pd.DataFrame) -> pd.DataFrame:
    """Derive fuel_family from fuel_product_standard."""
    if df.empty or "fuel_product_standard" not in df.columns:
        return df
    df = df.copy()
    df["fuel_family"] = df["fuel_product_standard"].map(_FAMILY_FROM_STANDARD)
    return df


# ── Location derivation ───────────────────────────────────────────────────────


def _parse_malaysia_location(product: str) -> tuple[str, str | None]:
    m = _MY_LOCATION_RE.search(str(product))
    if m:
        loc = m.group("loc")
        clean = _MY_LOCATION_RE.sub("", product).strip()
        return clean, loc
    return product, None


def _derive_location(df: pd.DataFrame) -> pd.DataFrame:
    """Add canonical location column; parse Malaysia location from product name.

    Location priority: _my_loc (Malaysia) > address > city > subnational_area > "National"
    """
    df = df.copy()

    malaysia_mask = df["country"] == "Malaysia"
    if malaysia_mask.any():
        parsed = df.loc[malaysia_mask, "fuel_product"].apply(_parse_malaysia_location)
        df.loc[malaysia_mask, "fuel_product"] = parsed.apply(lambda t: t[0])
        df.loc[malaysia_mask, "_my_loc"] = parsed.apply(lambda t: t[1])
    else:
        df["_my_loc"] = None

    def _resolve(row: pd.Series) -> str:
        my_loc = row.get("_my_loc")
        if pd.notna(my_loc) and str(my_loc).strip():
            return str(my_loc).strip()
        for field in ("address", "city", "subnational_area"):
            val = row.get(field)
            if pd.notna(val) and str(val).strip():
                s = str(val).strip()
                if s.lower().startswith("national"):
                    return "National"
                return s
        return "National"

    df["location"] = df.apply(_resolve, axis=1)
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


def _series_fields(
    family: str, standard: str, quality: str, product: str
) -> tuple[str, str]:
    """Derive (series_key, series_label) from fuel_family, fuel_product_standard, quality_group."""
    family = family.strip().lower()
    standard = standard.strip().lower()
    quality = quality.strip().lower()

    if family == "diesel":
        if quality == "premium" or standard in ("diesel_premium", "diesel_branded"):
            return "diesel|||premium", "Diesel - Premium"
        return "diesel|||regular", "Diesel - Regular"

    if family == "gasoline":
        if standard in (
            "gasoline_ethanol_low",
            "gasoline_ethanol_medium",
            "gasoline_ethanol_high",
        ):
            return "gasoline|||ethanol", "Gasoline - Ethanol Blend"
        if quality == "premium" or standard in (
            "gasoline_premium",
            "gasoline_midgrade",
        ):
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
    """Canonicalize product/location fields and derive quality_group, series_key, series_label.

    Fully vectorized — no iterrows().
    """
    if df.empty:
        return df

    df = df.copy()

    # Normalize location text fields
    if "location" in df.columns:
        df["location"] = df["location"].apply(_normalize_location_text)
    if "city" in df.columns:
        df["city"] = df["city"].apply(_normalize_location_text)
    if "subnational_area" in df.columns:
        df["subnational_area"] = df["subnational_area"].apply(_clean_text)

    # Initialize quality_group (derived, not stored in raw schema)
    df["quality_group"] = None

    # Pass 1: extract quality qualifier from product name suffix e.g. "Diesel (regular)"
    product_str = df["fuel_product"].fillna("").astype(str)
    match = product_str.str.extract(_GENERIC_QUALIFIER_RE, expand=True)
    has_match = match["base"].notna()
    if has_match.any():
        df.loc[has_match, "fuel_product"] = match.loc[has_match, "base"].str.strip()
        extracted_qual = (
            match.loc[has_match, "qual"]
            .str.lower()
            .str.replace("super premium", "super_premium", regex=False)
            .str.replace("super-premium", "super_premium", regex=False)
        )
        df.loc[has_match, "quality_group"] = extracted_qual

    # Fix diesel "standard" → "regular"
    diesel_standard = df.get("fuel_family", pd.Series(dtype=str)).eq("diesel") & (
        df["quality_group"] == "standard"
    )
    if diesel_standard.any():
        df.loc[diesel_standard, "quality_group"] = "regular"

    # Pass 2: Australia-specific product canonicalization (vectorized)
    au_mask = df["country"] == "Australia"
    if au_mask.any():
        product = df["fuel_product"].fillna("").astype(str)
        family = (
            df.get("fuel_family", pd.Series("", index=df.index))
            .fillna("")
            .astype(str)
            .str.lower()
        )

        pdl = au_mask & product.str.match(_AU_PDL_RE, na=False)
        df.loc[pdl, "fuel_product"] = "Premium Diesel"
        df.loc[pdl, "quality_group"] = "premium"

        au_diesel = au_mask & (family == "diesel")
        diesel_match = au_diesel & (
            product.str.match(_AU_DIESEL_RE, na=False)
            | product.str.lower().eq("diesel")
        )
        df.loc[diesel_match, "fuel_product"] = "Diesel"
        df.loc[diesel_match, "quality_group"] = "regular"

        au_gas = au_mask & (family == "gasoline")

        ulp = au_gas & product.str.match(_AU_UNLEADED_RE, na=False)
        df.loc[ulp, "fuel_product"] = "Unleaded"
        df.loc[ulp, "quality_group"] = "regular"

        p95 = au_gas & product.str.match(_AU_P95_RE, na=False)
        df.loc[p95, "fuel_product"] = "Premium 95"
        df.loc[p95, "quality_group"] = "premium"

        p98 = au_gas & product.str.match(_AU_P98_RE, na=False)
        df.loc[p98, "fuel_product"] = "Premium 98"
        df.loc[p98, "quality_group"] = "premium"

        e10 = au_gas & product.str.match(_AU_E10_RE, na=False)
        df.loc[e10, "fuel_product"] = "E10"
        df.loc[e10, "quality_group"] = "regular"

        e20 = au_gas & product.str.match(_AU_E20_RE, na=False)
        df.loc[e20, "fuel_product"] = "E20"

        e85 = au_gas & product.str.match(_AU_E85_RE, na=False)
        df.loc[e85, "fuel_product"] = "E85"

        lpg_au = au_mask & (family == "lpg") & product.str.match(_AU_LPG_RE, na=False)
        df.loc[lpg_au, "fuel_product"] = "LPG"
        df.loc[lpg_au, "quality_group"] = None

    # Pass 3: derive series_key and series_label (vectorized via zip)
    family_col = (
        df.get("fuel_family", pd.Series("", index=df.index)).fillna("").astype(str)
    )
    standard_col = (
        df.get("fuel_product_standard", pd.Series("", index=df.index))
        .fillna("")
        .astype(str)
    )
    quality_col = df["quality_group"].fillna("").astype(str)
    product_col = df["fuel_product"].fillna("").astype(str)

    series = [
        _series_fields(f, s, q, p)
        for f, s, q, p in zip(family_col, standard_col, quality_col, product_col)
    ]
    df["series_key"] = [item[0] for item in series]
    df["series_label"] = [item[1] for item in series]

    return df


# ── Single-pass deduplication ─────────────────────────────────────────────────


def _deduplicate(df: pd.DataFrame) -> pd.DataFrame:
    """Single combined dedup pass.

    Step 1: Sort by source_rank so groupby "first" picks best row.
    Step 2: Average price within same (source, location, date, series) — handles
            intra-source location normalization (e.g. INGLEBURN vs Ingleburn).
    Step 3: Sort again and drop_duplicates on DEDUP_KEY — picks best source
            per (country, date, location, series_key) slot.
    """
    if df.empty:
        return df

    df = df.copy()
    df["_source_rank"] = df.apply(_compute_source_rank, axis=1)

    # Step 1: sort so groupby "first" captures the best-ranked row
    df = df.sort_values(["_source_rank", "observation_date"])

    # Step 2: average prices within same (source, location, date, series)
    agg_cols = [c for c in _AGG_GROUP_COLS if c in df.columns]
    if agg_cols and "price_local" in df.columns:
        pass_cols = [c for c in df.columns if c not in set(agg_cols) | {"price_local"}]
        agg_map: dict[str, str] = {c: "first" for c in pass_cols}
        agg_map["price_local"] = "mean"
        df = df.groupby(agg_cols, dropna=False, as_index=False).agg(agg_map)
        df["price_local"] = df["price_local"].round(4)

    # Step 3: pick best source for each (country, date, location, series_key)
    dedup_key = [c for c in _DEDUP_KEY if c in df.columns]
    if len(dedup_key) >= 3:
        df = df.sort_values(["_source_rank"])
        df = df.drop_duplicates(subset=dedup_key, keep="first")

    return _strip_internal(df).reset_index(drop=True)


def _forward_fill_state_controlled_series(
    df: pd.DataFrame,
    as_of: date | None = None,
) -> pd.DataFrame:
    if df.empty:
        return df

    check_date = pd.Timestamp(as_of or _today()).normalize()
    work = df.copy()
    work["_canonical_country"] = work["country"].map(_canonical_country_name)

    eligible = work[work["_canonical_country"].isin(_STATE_CONTROLLED_COUNTRIES)].copy()
    ineligible = work[
        ~work["_canonical_country"].isin(_STATE_CONTROLLED_COUNTRIES)
    ].copy()
    if eligible.empty:
        return _strip_internal(df).reset_index(drop=True)

    eligible["observation_date"] = pd.to_datetime(
        eligible["observation_date"], errors="coerce"
    )
    eligible = eligible[eligible["observation_date"].notna()].copy()
    if eligible.empty:
        return _strip_internal(ineligible).reset_index(drop=True)

    group_cols = [
        c
        for c in [
            "_canonical_country",
            "country",
            "location",
            "fuel_product",
            "series_key",
        ]
        if c in eligible.columns
    ]
    expanded_rows: list[dict[str, object]] = []

    for _, group in eligible.groupby(group_cols, dropna=False, sort=False):
        ordered = (
            group.sort_values(
                ["observation_date", "_source_rank"]
                if "_source_rank" in group.columns
                else ["observation_date"]
            )
            .drop_duplicates(subset=["observation_date"], keep="last")
            .reset_index(drop=True)
        )
        if ordered.empty:
            continue

        for idx, row in ordered.iterrows():
            start = pd.Timestamp(row["observation_date"]).normalize()
            next_start = None
            if idx + 1 < len(ordered):
                next_start = pd.Timestamp(
                    ordered.iloc[idx + 1]["observation_date"]
                ).normalize()

            end = (
                check_date
                if next_start is None
                else min(check_date, next_start - pd.Timedelta(days=1))
            )
            if end < start:
                continue

            base = row.to_dict()
            for obs_date in pd.date_range(start, end, freq="D"):
                item = dict(base)
                item["observation_date"] = obs_date
                item["observation_hash"] = _build_observation_hash(item)
                expanded_rows.append(item)

    expanded = pd.DataFrame(expanded_rows)
    combined = pd.concat([ineligible, expanded], ignore_index=True, sort=False)
    return _strip_internal(combined).reset_index(drop=True)


# ── Public pipeline functions ─────────────────────────────────────────────────


def _run_pipeline_stages(df: pd.DataFrame) -> pd.DataFrame:
    """Run all enrichment stages on a raw DataFrame (with _storage_path present).

    Returns a fully enriched, sorted DataFrame.
    """
    df["observation_date"] = pd.to_datetime(df["observation_date"], errors="coerce")
    df = _strip_internal(df)
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = None

    df = _apply_data_quality_rules(df)
    df = _normalize_products(df)
    df = _derive_fuel_family(df)
    df = _derive_location(df)
    df = _canonicalize(df)
    df = _deduplicate(df)
    df = _forward_fill_state_controlled_series(df)

    sort_cols = [
        c
        for c in ["country", "observation_date", "fuel_product", "location"]
        if c in df.columns
    ]
    if sort_cols:
        df = df.sort_values(sort_cols).reset_index(drop=True)
    return df


def apply_data_quality_rules(df: pd.DataFrame) -> pd.DataFrame:
    """Apply data quality rules: product drops, low-priority source drops, country renames."""
    df = _apply_data_quality_rules(df)
    return _strip_internal(df).sort_values("observation_date").reset_index(drop=True)


def build_enriched_frame(
    collect_dir: Path | None = None,
    incremental: bool = True,
) -> pd.DataFrame:
    """Full pipeline: load → normalize → enrich → deduplicate.

    Incremental mode (default):
      1. Read observation_hash column from enriched.csv → enriched_hashes set
      2. Scan all source files for hashes not in enriched_hashes → dirty countries
      3. If no dirty countries: return cached enriched frame instantly
      4. Load ALL source files for dirty countries (needed for correct cross-source dedup)
      5. Re-enrich dirty countries; splice with clean rows from enriched cache

    Pass incremental=False (or --full via CLI) to force a clean rebuild from all sources.
    """
    from .constants import DATA_DIR
    from .storage import country_slug as _country_slug

    if collect_dir is None:
        collect_dir = DATA_DIR

    enriched_path = STAGED_DATA_DIR / "enrich" / "retail_series_enriched.csv"

    if incremental and collect_dir == DATA_DIR and enriched_path.exists():
        enriched_mtime = enriched_path.stat().st_mtime
        df_existing = pd.read_csv(enriched_path, low_memory=False)
        df_existing["observation_date"] = pd.to_datetime(
            df_existing["observation_date"], errors="coerce"
        )

        # Scan source files for any modified after enriched output was written
        dirty = _find_dirty_countries(collect_dir, enriched_mtime)
        stale_countries = _find_stale_state_controlled_countries(df_existing)
        for country in stale_countries:
            dirty.setdefault(country, [])

        if not dirty:
            logger.info(
                "Incremental build: no new sources, returning cached (%d rows)",
                len(df_existing),
            )
            return df_existing

        dirty_countries = set(dirty.keys())
        logger.info(
            "Incremental build: re-enriching %d countries: %s",
            len(dirty_countries),
            sorted(dirty_countries),
        )

        # Load ALL source files for dirty countries
        dirty_paths: list[Path] = []
        for country in dirty_countries:
            for variant in _country_variants(country):
                slug = _country_slug(variant)
                dirty_paths.extend(
                    sorted((collect_dir / slug).glob("*/observations.csv"))
                )

        dirty_paths = sorted(set(dirty_paths))

        df_to_enrich = _load_from_paths(dirty_paths, collect_dir)
        if not df_to_enrich.empty:
            df_to_enrich = df_to_enrich[
                ~df_to_enrich["source_key"].str.startswith("global_", na=False)
            ].copy()

        if df_to_enrich.empty:
            logger.info(
                "Incremental build: no data loaded for dirty countries, returning cached"
            )
            return df_existing

        # Enrich dirty slice, splice with clean rows
        df_clean = df_existing[~df_existing["country"].isin(dirty_countries)].copy()
        df_new = _run_pipeline_stages(df_to_enrich)

        sort_cols = [
            c
            for c in ["country", "observation_date", "fuel_product", "location"]
            if c in df_new.columns
        ]
        result = pd.concat([df_clean, df_new], ignore_index=True)
        if sort_cols:
            result = result.sort_values(sort_cols).reset_index(drop=True)

        logger.info(
            "build_enriched_frame (incremental): %d rows, %d countries, %d source_keys",
            len(result),
            result["country"].nunique() if "country" in result.columns else 0,
            result["source_key"].nunique() if "source_key" in result.columns else 0,
        )
        return result

    # Full build
    df_raw = _load_collected_observations(collect_dir)
    if df_raw.empty:
        return pd.DataFrame(columns=pd.Index(ENRICHED_COLUMNS))

    df = _run_pipeline_stages(df_raw)

    logger.info(
        "build_enriched_frame (full): %d rows, %d countries, %d source_keys",
        len(df),
        df["country"].nunique() if "country" in df.columns else 0,
        df["source_key"].nunique() if "source_key" in df.columns else 0,
    )
    return df


def materialize_outputs(
    staged_dir: Path = STAGED_DATA_DIR,
    collect_dir: Path | None = None,
    incremental: bool = True,
) -> dict:
    """Run pipeline and write enriched CSV to staged_dir/enrich/.

    Pass incremental=False to force a full rebuild regardless of existing output.
    Skips writing if incremental=True and no source files are newer than the output.
    """
    from .constants import DATA_DIR

    if collect_dir is None:
        collect_dir = DATA_DIR

    out_path = staged_dir / "enrich" / "retail_series_enriched.csv"

    # Skip build + write entirely if output is up to date
    if incremental and out_path.exists():
        enriched_mtime = out_path.stat().st_mtime
        dirty = _find_dirty_countries(collect_dir, enriched_mtime)
        df_existing = pd.read_csv(out_path, low_memory=False)
        df_existing["observation_date"] = pd.to_datetime(
            df_existing["observation_date"], errors="coerce"
        )
        stale_countries = _find_stale_state_controlled_countries(df_existing)
        for country in stale_countries:
            dirty.setdefault(country, [])
        if not dirty:
            row_count = sum(1 for _ in out_path.open()) - 1  # fast line count
            logger.info("Build skipped — output is up to date (%d rows)", row_count)
            return {"enriched_path": out_path, "enriched_rows": row_count}

    df = build_enriched_frame(collect_dir=collect_dir, incremental=incremental)

    # Ensure output contains exactly ENRICHED_COLUMNS in canonical order
    for col in ENRICHED_COLUMNS:
        if col not in df.columns:
            df[col] = None
    df = df[ENRICHED_COLUMNS]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    logger.info("Saved %d rows -> %s", len(df), out_path)

    return {"enriched_path": out_path, "enriched_rows": len(df)}


# ── Publish-time serialization ────────────────────────────────────────────────


def _clean_val(v: object) -> object:
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, (int, float)):
        return float(v)
    return str(v) if not isinstance(v, str) else v


def frame_to_country_series(
    df: pd.DataFrame,
) -> dict[str, list[dict[str, object | None]]]:
    """Group enriched fuel rows into publish-ready per-country payloads."""
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].dt.strftime("%Y-%m-%d")

    return {
        str(country): [
            {k: _clean_val(v) for k, v in rec.items()}
            for rec in group.to_dict("records")
        ]
        for country, group in out.groupby("country")
    }
