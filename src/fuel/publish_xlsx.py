"""Per-region Excel export for the fuel pipeline.

Writes ``outputs/fuel/excels/{region}_fuel_prices.xlsx`` with two sheets:

- ``data``    — wide table: iso3, fuel_product, currency, units + one column per date
- ``sources`` — iso3, source, url (one row per (country, source) actually used)
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from .config import build_fuel_registry
from .publish_parallel import parallel_sheets, station_stats_sheet

logger = logging.getLogger(__name__)

_DATA_COLS_STATIC = ["iso3", "fuel_product", "currency", "units"]


def _load_country_prices(country_dir: Path, cutoff: str) -> pd.DataFrame:
    csv_path = country_dir / "fuel_product_local_prices.csv"
    if not csv_path.exists():
        return pd.DataFrame()
    df = pd.read_csv(csv_path, low_memory=False)
    if df.empty:
        return df
    df["observation_date"] = df["observation_date"].astype(str).str[:10]
    df = df[df["observation_date"] >= cutoff]
    df = df[df["price_local"].notna()]
    return df


def _carry_forward_keys(region: str) -> set[tuple[str, str]]:
    """Return {(iso3, label)} for products whose source config sets carry_forward=true.

    Honors per-product override: spec.carry_forward if set, else source default.
    """
    registry = build_fuel_registry(region=region)
    keys: set[tuple[str, str]] = set()
    for entry in registry.values():
        iso3 = entry.get("iso3", "")
        source_default = bool(entry.get("carry_forward", False))
        for raw_name, spec in entry.get("products", {}).items():
            cf = spec.carry_forward
            effective = source_default if cf is None else bool(cf)
            if not effective:
                continue
            if not getattr(spec, "include_in_build", True):
                continue
            label = spec.label or spec.series_key or raw_name
            keys.add((iso3, label))
    return keys


def _build_data_sheet(
    region: str, countries: list[dict], history_years: int
) -> pd.DataFrame:
    cutoff = (date.today() - timedelta(days=365 * history_years)).strftime("%Y-%m-%d")
    frames: list[pd.DataFrame] = []
    for c in countries:
        df = _load_country_prices(c["output_dir"], cutoff)
        if df.empty:
            continue
        df = df.assign(
            iso3=df["iso3"].fillna(c.get("iso3", "")),
            currency=df["currency"].fillna(c.get("currency", "")),
            fuel_product=df["label"].fillna(df["series_key"]),
            units=df["currency"].astype(str) + "/" + df["unit"].astype(str),
        )
        frames.append(
            df[
                [
                    "iso3",
                    "fuel_product",
                    "currency",
                    "units",
                    "observation_date",
                    "price_local",
                ]
            ]
        )
    if not frames:
        return pd.DataFrame(columns=_DATA_COLS_STATIC)

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.groupby(
        ["iso3", "fuel_product", "currency", "units", "observation_date"],
        as_index=False,
    )["price_local"].mean()
    wide = combined.pivot_table(
        index=["iso3", "fuel_product", "currency", "units"],
        columns="observation_date",
        values="price_local",
    )
    # Reindex date columns to a contiguous daily range so ffill can bridge gaps.
    if not wide.columns.empty:
        all_dates = pd.date_range(
            wide.columns.min(), wide.columns.max(), freq="D"
        ).strftime("%Y-%m-%d")
        wide = wide.reindex(columns=all_dates)

    cf_keys = _carry_forward_keys(region)
    if cf_keys and not wide.empty:
        mask = pd.Series(
            [(iso3, fp) in cf_keys for iso3, fp, *_ in wide.index],
            index=wide.index,
        )
        if mask.any():
            wide.loc[mask] = wide.loc[mask].ffill(axis=1)

    wide = wide.reset_index().sort_values(["iso3", "fuel_product"])
    return wide


def _build_sources_sheet(region: str, countries: list[dict]) -> pd.DataFrame:
    registry = build_fuel_registry(region=region)
    meta_by_key = {
        k: {
            "url": v.get("url", ""),
            "display_name": v.get("display_name") or k,
        }
        for k, v in registry.items()
    }

    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for c in countries:
        csv_path = c["output_dir"] / "fuel_product_local_prices.csv"
        if not csv_path.exists():
            continue
        df = pd.read_csv(csv_path, usecols=["iso3", "source_key"], low_memory=False)
        if df.empty:
            continue
        iso3 = c.get("iso3", "") or (
            str(df["iso3"].dropna().iloc[0]) if not df["iso3"].dropna().empty else ""
        )
        keys: set[str] = set()
        for raw in df["source_key"].dropna().astype(str):
            for part in raw.split(","):
                part = part.strip()
                if part:
                    keys.add(part)
        for key in sorted(keys):
            ident = (iso3, key)
            if ident in seen:
                continue
            seen.add(ident)
            meta = meta_by_key.get(key, {})
            rows.append(
                {
                    "iso3": iso3,
                    "source": meta.get("display_name") or key,
                    "url": meta.get("url", ""),
                }
            )
    if not rows:
        return pd.DataFrame(columns=["iso3", "source", "url"])
    return pd.DataFrame(rows).sort_values(["iso3", "source"]).reset_index(drop=True)


def export_region_xlsx(
    region: str,
    countries: list[dict],
    out_dir: Path,
    history_years: int = 3,
) -> Path:
    """Write ``{region}_fuel_prices.xlsx`` with two sheets and return its path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{region}_fuel_prices.xlsx"

    data_sheet = _build_data_sheet(region, countries, history_years=history_years)
    sources_sheet = _build_sources_sheet(region, countries)

    extra = parallel_sheets(countries, history_years=history_years)
    stations = station_stats_sheet(countries, history_years=history_years)
    if not stations.empty:
        extra["station_stats"] = stations

    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        data_sheet.to_excel(writer, sheet_name="data", index=False)
        sources_sheet.to_excel(writer, sheet_name="sources", index=False)
        for name, sheet in extra.items():
            sheet.to_excel(writer, sheet_name=name, index=False)

    logger.info(
        "Wrote %s (data: %d rows, sources: %d rows)",
        out_path,
        len(data_sheet),
        len(sources_sheet),
    )
    return out_path
