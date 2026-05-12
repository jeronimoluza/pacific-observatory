"""Fuel build stage: country-scoped local and USD price outputs."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import click
import pandas as pd

from core.storage import save_csv

from .config import ProductSpec, build_fuel_registry
from .fx import DEFAULT_FX_CACHE, attach_fx_and_usd
from .paths import canonical_observations_path_for_entry

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = _PROJECT_ROOT / "data" / "fuel"
OUTPUTS_DIR = _PROJECT_ROOT / "outputs" / "fuel"

_CANONICAL_FAMILY_UNITS = {
    "gasoline": "L",
    "diesel": "L",
    "kerosene": "L",
    "lpg": "L",
}
_FAMILY_USD_FAMILIES = {"gasoline", "diesel", "kerosene", "lpg"}
_CADENCE_DAYS = {
    "daily": 1,
    "weekly": 7,
    "biweekly": 14,
    "monthly": 31,
    "quarterly": 92,
    "yearly": 366,
    "irregular": 1,
}
_PRODUCT_COLUMNS = [
    "observation_date",
    "region",
    "subregion",
    "country_slug",
    "country",
    "iso3",
    "currency",
    "series_key",
    "label",
    "fuel_family",
    "unit",
    "price_local",
    "source_key",
    "source_priority",
    "observed_on",
    "is_forward_filled",
]
_FAMILY_COLUMNS = [
    "observation_date",
    "region",
    "subregion",
    "country_slug",
    "country",
    "iso3",
    "currency",
    "fuel_family",
    "unit",
    "product_count",
    "price_local",
    "fx_rate",
    "fx_rate_date",
    "price_usd",
]


def _observations_path(entry: dict, base_dir: Path = DATA_DIR) -> Path:
    return canonical_observations_path_for_entry(entry, base_dir=base_dir)


def _normalize_price(price_local: float, spec: ProductSpec) -> tuple[float, str]:
    amount = spec.amount or 1.0
    unit = spec.unit
    family = spec.fuel_family

    if family in {"gasoline", "diesel", "kerosene"}:
        if unit == "liter":
            quantity = amount
        elif unit == "gallon":
            quantity = amount * 3.785411784
        else:
            raise ValueError(
                f"Unsupported liquid conversion from {unit} for {spec.series_key}"
            )
        return price_local / quantity, _CANONICAL_FAMILY_UNITS[family]

    if family == "lpg":
        if unit == "liter":
            quantity_in_liters = amount
        elif unit == "gallon":
            quantity_in_liters = amount * 3.785411784
        else:
            if unit == "kilogram" or unit == "cylinder":
                kg_amount = amount
            elif unit == "ton":
                kg_amount = amount * 1000.0
            elif unit == "pound":
                kg_amount = amount * 0.45359237
            else:
                raise ValueError(
                    f"Unsupported LPG conversion from {unit} for {spec.series_key}"
                )
            if spec.density_l_per_kg is None or spec.density_l_per_kg <= 0:
                raise ValueError(
                    f"density_l_per_kg required for LPG product '{spec.series_key}' "
                    f"(unit={unit}); update its config YAML"
                )
            quantity_in_liters = kg_amount * spec.density_l_per_kg
        return price_local / quantity_in_liters, _CANONICAL_FAMILY_UNITS[family]

    normalized = price_local / amount if spec.amount else price_local
    return normalized, unit


def _load_source_frame(entry: dict, data_dir: Path = DATA_DIR) -> pd.DataFrame:
    path = _observations_path(entry, base_dir=data_dir)
    if not path.exists():
        return pd.DataFrame()

    df = pd.read_csv(path, low_memory=False)
    if df.empty:
        return df

    raw_products = {str(v).strip() for v in df["fuel_product"].dropna().unique()}
    mapped_products = set(entry["products"].keys())
    missing = sorted(raw_products - mapped_products)
    if missing:
        raise ValueError(
            f"Unmapped raw products for {entry['source_key']}: {missing}. Update {entry['config_path']}"
        )

    df = df.copy()
    df["product_spec"] = df["fuel_product"].map(entry["products"])
    df["include_in_build"] = df["product_spec"].map(lambda spec: spec.include_in_build)
    df = df[df["include_in_build"]].copy()
    if df.empty:
        return df

    df["observation_date"] = pd.to_datetime(
        df["observation_date"], errors="coerce"
    ).dt.normalize()
    df["price_local"] = pd.to_numeric(df["price_local"], errors="coerce")
    df = df[df["observation_date"].notna() & df["price_local"].notna()].copy()
    if df.empty:
        return df

    df["series_key"] = df["product_spec"].map(lambda spec: spec.series_key)
    df["label"] = df["product_spec"].map(lambda spec: spec.label or spec.series_key)
    df["fuel_family"] = df["product_spec"].map(lambda spec: spec.fuel_family)
    normalized = df.apply(
        lambda row: _normalize_price(float(row["price_local"]), row["product_spec"]),
        axis=1,
    )
    df["price_local"] = normalized.map(lambda item: item[0])
    df["unit"] = normalized.map(lambda item: item[1])
    df["region"] = entry["region"]
    df["subregion"] = entry["subregion"]
    df["country_slug"] = entry["country_slug"]
    df["country"] = entry["country_name"]
    df["iso3"] = entry["iso3"]
    df["currency"] = entry["currency"]
    df["source_key"] = entry["source_key"]
    df["source_priority"] = entry["priority"]
    df["cadence"] = entry["cadence"]
    df["carry_forward"] = entry["carry_forward"]
    return df


def _collapse_source_rows(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    group_cols = [
        "region",
        "subregion",
        "country_slug",
        "country",
        "iso3",
        "currency",
        "source_key",
        "source_priority",
        "cadence",
        "carry_forward",
        "observation_date",
        "series_key",
        "label",
        "fuel_family",
        "unit",
    ]
    collapsed = (
        df.groupby(group_cols, dropna=False, as_index=False)["price_local"]
        .mean()
        .round(6)
    )
    collapsed["observed_on"] = collapsed["observation_date"]
    collapsed["is_forward_filled"] = False
    return collapsed


def _expand_with_carry_forward(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    today = pd.Timestamp(date.today()).normalize()
    rows: list[dict[str, object]] = []
    group_cols = ["country_slug", "source_key", "series_key"]
    for _, group in df.groupby(group_cols, dropna=False, sort=False):
        ordered = group.sort_values("observation_date").reset_index(drop=True)
        for idx, row in ordered.iterrows():
            start = pd.Timestamp(row["observation_date"]).normalize()
            end = start
            if bool(row["carry_forward"]):
                window = max(_CADENCE_DAYS[row["cadence"]] - 1, 0)
                end = start + pd.Timedelta(days=window)
                if idx + 1 < len(ordered):
                    next_date = pd.Timestamp(
                        ordered.iloc[idx + 1]["observation_date"]
                    ).normalize()
                    end = min(end, next_date - pd.Timedelta(days=1))
                end = min(end, today)
            for obs_date in pd.date_range(start, end, freq="D"):
                item = row.to_dict()
                item["observation_date"] = obs_date
                item["is_forward_filled"] = obs_date > start
                rows.append(item)
    return pd.DataFrame(rows)


def _resolve_overlaps(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=_PRODUCT_COLUMNS)

    resolved_rows: list[dict[str, object]] = []
    group_cols = [
        "region",
        "subregion",
        "country_slug",
        "country",
        "iso3",
        "currency",
        "observation_date",
        "series_key",
    ]
    for key, group in df.groupby(group_cols, dropna=False, sort=True):
        best_priority = group["source_priority"].min()
        best = group[group["source_priority"] == best_priority].copy()
        observed_dates = sorted(
            {pd.Timestamp(v).strftime("%Y-%m-%d") for v in best["observed_on"].dropna()}
        )
        resolved_rows.append(
            {
                "region": key[0],
                "subregion": key[1],
                "country_slug": key[2],
                "country": key[3],
                "iso3": key[4],
                "currency": key[5],
                "observation_date": pd.Timestamp(key[6]).strftime("%Y-%m-%d"),
                "series_key": key[7],
                "label": best["label"].iloc[0] if "label" in best.columns else key[7],
                "fuel_family": best["fuel_family"].iloc[0],
                "unit": best["unit"].iloc[0],
                "price_local": round(best["price_local"].mean(), 6),
                "source_key": ",".join(sorted(best["source_key"].astype(str).unique())),
                "source_priority": int(best_priority),
                "observed_on": ",".join(observed_dates),
                "is_forward_filled": bool(best["is_forward_filled"].all()),
            }
        )
    return pd.DataFrame(resolved_rows, columns=_PRODUCT_COLUMNS)


def _build_family_output(
    df: pd.DataFrame, fx_cache_path: Path = DEFAULT_FX_CACHE
) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=_FAMILY_COLUMNS)

    family = df[df["fuel_family"].isin(_FAMILY_USD_FAMILIES)].copy()
    if family.empty:
        return pd.DataFrame(columns=_FAMILY_COLUMNS)

    grouped = (
        family.groupby(
            [
                "observation_date",
                "region",
                "subregion",
                "country_slug",
                "country",
                "iso3",
                "currency",
                "fuel_family",
            ],
            dropna=False,
            as_index=False,
        )
        .agg(
            price_local=("price_local", "mean"), product_count=("series_key", "nunique")
        )
        .round({"price_local": 6})
    )
    grouped["unit"] = grouped["fuel_family"].map(_CANONICAL_FAMILY_UNITS)
    with_fx = attach_fx_and_usd(grouped, cache_path=fx_cache_path)
    with_fx["observation_date"] = pd.to_datetime(
        with_fx["observation_date"], errors="coerce"
    ).dt.strftime("%Y-%m-%d")
    with_fx["fx_rate_date"] = pd.to_datetime(
        with_fx["fx_rate_date"], errors="coerce"
    ).dt.strftime("%Y-%m-%d")
    return with_fx[_FAMILY_COLUMNS]


def build_country_outputs(
    entries: list[dict],
    data_dir: Path = DATA_DIR,
    outputs_dir: Path = OUTPUTS_DIR,
    fx_cache_path: Path = DEFAULT_FX_CACHE,
) -> dict[str, Path | int]:
    enabled_entries = [entry for entry in entries if entry.get("enabled", True)]
    skipped = [
        entry["source_key"] for entry in entries if not entry.get("enabled", True)
    ]
    if skipped:
        logger.info(
            "Skipping disabled sources for %s: %s",
            entries[0]["country_slug"],
            ", ".join(skipped),
        )
    if not enabled_entries:
        country_meta = entries[0]
        logger.warning(
            "All sources disabled for country %s — no outputs written. Skipped: %s",
            country_meta["country_slug"],
            ", ".join(skipped) if skipped else "(none)",
        )
        out_dir = (
            outputs_dir
            / country_meta["region"]
            / country_meta["subregion"]
            / country_meta["country_slug"]
        )
        return {
            "product_path": out_dir / "fuel_product_local_prices.csv",
            "family_path": out_dir / "fuel_family_usd_prices.csv",
            "rows": 0,
        }
    frames = [_load_source_frame(entry, data_dir=data_dir) for entry in enabled_entries]
    frames = [frame for frame in frames if not frame.empty]
    country_meta = enabled_entries[0]
    out_dir = (
        outputs_dir
        / country_meta["region"]
        / country_meta["subregion"]
        / country_meta["country_slug"]
    )
    product_path = out_dir / "fuel_product_local_prices.csv"
    family_path = out_dir / "fuel_family_usd_prices.csv"

    if not frames:
        save_csv(
            pd.DataFrame(columns=_PRODUCT_COLUMNS),
            product_path,
            columns=_PRODUCT_COLUMNS,
        )
        save_csv(
            pd.DataFrame(columns=_FAMILY_COLUMNS), family_path, columns=_FAMILY_COLUMNS
        )
        return {"product_path": product_path, "family_path": family_path, "rows": 0}

    combined = pd.concat(frames, ignore_index=True)
    collapsed = _collapse_source_rows(combined)
    expanded = _expand_with_carry_forward(collapsed)
    resolved = _resolve_overlaps(expanded)
    family = _build_family_output(resolved, fx_cache_path=fx_cache_path)

    save_csv(resolved, product_path, columns=_PRODUCT_COLUMNS)
    save_csv(family, family_path, columns=_FAMILY_COLUMNS)
    return {
        "product_path": product_path,
        "family_path": family_path,
        "rows": len(resolved),
    }


def run_build(
    *,
    region: str | None = None,
    subregion: str | None = None,
    country: str | None = None,
    data_dir: Path = DATA_DIR,
    outputs_dir: Path = OUTPUTS_DIR,
    fx_cache_path: Path = DEFAULT_FX_CACHE,
) -> list[dict[str, Path | int]]:
    registry = build_fuel_registry(region=region, subregion=subregion, country=country)
    if not registry:
        raise click.ClickException(
            "No fuel sources found. Check --region/--subregion/--country filters."
        )

    countries: dict[str, list[dict]] = {}
    for entry in registry.values():
        countries.setdefault(entry["country_slug"], []).append(entry)

    click.echo(f"Countries to build: {', '.join(sorted(countries))}")

    results = []
    for country_slug, entries in sorted(countries.items()):
        click.echo(f"Building fuel outputs for {country_slug}...")
        try:
            result = build_country_outputs(
                entries,
                data_dir=data_dir,
                outputs_dir=outputs_dir,
                fx_cache_path=fx_cache_path,
            )
            results.append(result)
        except Exception:
            logger.exception("Failed to build %s — skipping", country_slug)
    return results
