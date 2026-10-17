"""Per-region Excel export for the fuel pipeline.

Writes ``outputs/fuel/excels/{region}_fuel_prices.xlsx`` with two sheets:

- ``data``    — wide table: iso3, fuel_product, currency, units, price_note + one
  column per date (price_note = "Best available, not pump price" when the
  source's price_basis is not retail)
- ``sources`` — iso3, source, url (one row per (country, source) actually used)
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from .config import build_fuel_registry
from .publish_parallel import parallel_sheets, station_stats_sheet
from .regimes import basis_note

logger = logging.getLogger(__name__)

_DATA_COLS_STATIC = ["iso3", "fuel_product", "currency", "units", "price_note"]


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
            price_note=(
                df["price_basis"].map(basis_note) if "price_basis" in df else ""
            ),
        )
        frames.append(
            df[
                [
                    "iso3",
                    "fuel_product",
                    "currency",
                    "units",
                    "price_note",
                    "observation_date",
                    "price_local",
                ]
            ]
        )
    if not frames:
        return pd.DataFrame(columns=_DATA_COLS_STATIC)

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.groupby(
        _DATA_COLS_STATIC + ["observation_date"],
        as_index=False,
    )["price_local"].mean()
    wide = combined.pivot_table(
        index=_DATA_COLS_STATIC,
        columns="observation_date",
        values="price_local",
    )
    # Contiguous daily columns; cells hold only what the build wrote, carried-
    # forward days included, so the Excel and the dashboard show the same fill.
    if not wide.columns.empty:
        all_dates = pd.date_range(
            wide.columns.min(), wide.columns.max(), freq="D"
        ).strftime("%Y-%m-%d")
        wide = wide.reindex(columns=all_dates)

    wide = wide.reset_index().sort_values(["iso3", "fuel_product"])
    return wide


def _build_freshness_sheet(countries: list[dict]) -> pd.DataFrame:
    """Per series: the last date with a real observation and the last date the
    data sheet shows (carried forward within the source's cadence window)."""
    frames = []
    for c in countries:
        path = c["output_dir"] / "fuel_product_local_prices.csv"
        if not path.exists():
            continue
        df = pd.read_csv(path, low_memory=False)
        if df.empty:
            continue
        observed = df["observed_on"].astype(str).str.split(",").str[-1].str[:10]
        frames.append(
            df.assign(
                iso3=df["iso3"].fillna(c.get("iso3", "")),
                fuel_product=df["label"].fillna(df["series_key"]),
                observed=observed,
                shown=df["observation_date"].astype(str).str[:10],
                price_basis=df["price_basis"] if "price_basis" in df else "retail",
            )
            .groupby(["iso3", "fuel_product"], as_index=False)
            .agg(
                last_observed=("observed", "max"),
                last_shown=("shown", "max"),
                price_basis=(
                    "price_basis",
                    lambda s: ",".join(sorted(set(s.dropna()))),
                ),
            )
        )
        frames[-1]["price_note"] = frames[-1]["price_basis"].map(basis_note)
    if not frames:
        return pd.DataFrame(
            columns=[
                "iso3",
                "fuel_product",
                "last_observed",
                "last_shown",
                "price_basis",
                "price_note",
            ]
        )
    return pd.concat(frames, ignore_index=True).sort_values(["iso3", "fuel_product"])


def _build_sources_sheet(region: str, countries: list[dict]) -> pd.DataFrame:
    registry = build_fuel_registry(region=region)
    meta_by_key = {
        k: {
            "url": v.get("url", ""),
            "display_name": v.get("display_name") or k,
            "price_basis": v.get("price_basis", "retail"),
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
                    "price_basis": meta.get("price_basis", "retail"),
                }
            )
    if not rows:
        return pd.DataFrame(columns=["iso3", "source", "url", "price_basis"])
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
        _build_freshness_sheet(countries).to_excel(
            writer, sheet_name="freshness", index=False
        )
        for name, sheet in extra.items():
            sheet.to_excel(writer, sheet_name=name, index=False)

    logger.info(
        "Wrote %s (data: %d rows, sources: %d rows)",
        out_path,
        len(data_sheet),
        len(sources_sheet),
    )
    return out_path
