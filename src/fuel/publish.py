"""Fuel publish stage: assemble data and generate policy dashboards.

Region-agnostic — discovers countries from build outputs and generates
a standalone HTML dashboard per region.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path

import click
import pandas as pd
import yaml

from core.config import load_countries

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DATA_DIR = _PROJECT_ROOT / "data" / "fuel"
_OUTPUTS_DIR = _PROJECT_ROOT / "outputs" / "fuel"
_CONFIGS_DIR = Path(__file__).resolve().parent / "configs"
_REFERENCE_CACHE = _DATA_DIR / "_reference"

_COUNTRY_NAME_MAP: dict[str, str] = {
    "Viet Nam": "Vietnam",
    "Micronesia, Fed. Sts.": "Micronesia (Federated States of)",
    "Micronesia (Fed. Sts.)": "Micronesia (Federated States of)",
    "Korea, Rep.": "Korea, Rep.",
    "Lao PDR": "Lao PDR",
    "Timor-Leste": "Timor-Leste",
}


def _load_publish_config(region: str) -> dict:
    """Load region-specific publish config from configs/_publish/{region}.yaml."""
    path = _CONFIGS_DIR / "_publish" / f"{region}.yaml"
    if not path.exists():
        return {
            "region": region,
            "region_label": region.upper(),
            "dashboard_history_years": 3,
            "regime_overrides": {},
            "scatter_focus_region": True,
            "commodity_products": [],
        }
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def discover_publish_countries(
    outputs_dir: Path = _OUTPUTS_DIR,
    region: str | None = None,
    subregion: str | None = None,
) -> list[dict]:
    """Find countries with build outputs.

    Walks ``outputs/fuel/{region}/{subregion}/{country}/`` looking for
    ``fuel_product_local_prices.csv``.
    """
    countries_meta = load_countries()
    results: list[dict] = []

    search_root = outputs_dir
    if region:
        search_root = outputs_dir / region

    for csv_path in sorted(search_root.rglob("fuel_product_local_prices.csv")):
        rel = csv_path.relative_to(outputs_dir)
        parts = rel.parts  # (region, subregion, country, filename)
        if len(parts) < 4:
            continue
        r, sr, cs = parts[0], parts[1], parts[2]
        if region and r != region:
            continue
        if subregion and sr != subregion:
            continue
        meta = countries_meta.get(cs, {})
        # When slug doesn't match countries.yaml, peek at CSV for metadata
        if not meta:
            try:
                head = pd.read_csv(csv_path, nrows=1)
                if not head.empty:
                    meta = {
                        "name": str(head["country"].iloc[0])
                        if "country" in head.columns
                        else cs,
                        "iso3": str(head["iso3"].iloc[0])
                        if "iso3" in head.columns
                        else "",
                        "currency": str(head["currency"].iloc[0])
                        if "currency" in head.columns
                        else "",
                    }
            except Exception:
                pass
        results.append(
            {
                "country_slug": cs,
                "country": meta.get("name", cs),
                "iso3": meta.get("iso3", ""),
                "currency": meta.get("currency", ""),
                "region": r,
                "subregion": sr,
                "output_dir": csv_path.parent,
            }
        )
    return results


def _load_country_fuel_data(
    countries: list[dict],
    history_years: int = 3,
) -> dict[str, list[dict]]:
    """Read fuel_product_local_prices.csv per country → {country_name: [records]}."""
    cutoff = (date.today() - timedelta(days=365 * history_years)).strftime("%Y-%m-%d")
    fuel_data: dict[str, list[dict]] = {}

    for c in countries:
        csv_path = c["output_dir"] / "fuel_product_local_prices.csv"
        if not csv_path.exists():
            continue
        df = pd.read_csv(csv_path, low_memory=False)
        if df.empty:
            continue

        df["observation_date"] = df["observation_date"].astype(str).str[:10]
        df = df[df["observation_date"] >= cutoff].copy()
        if df.empty:
            continue

        records = []
        for _, row in df.iterrows():
            series_key = row.get("series_key", "")
            label = row.get("label", "") or series_key
            rec = {
                "observation_date": row.get("observation_date", ""),
                "fuel_product": label,
                "series_key": series_key,
                "fuel_family": row.get("fuel_family", ""),
                "price_local": row.get("price_local"),
                "currency": row.get("currency", ""),
                "unit": row.get("unit", ""),
                "source_key": row.get("source_key", ""),
                "location": "National",
            }
            if pd.notna(rec["price_local"]):
                records.append(rec)

        if records:
            fuel_data[c["country"]] = records

    return fuel_data


def _load_country_usd_data(
    countries: list[dict],
    history_years: int = 3,
) -> dict[str, list[dict]]:
    """Read fuel_family_usd_prices.csv per country for Tab 4."""
    cutoff = (date.today() - timedelta(days=365 * history_years)).strftime("%Y-%m-%d")
    usd_data: dict[str, list[dict]] = {}

    for c in countries:
        csv_path = c["output_dir"] / "fuel_family_usd_prices.csv"
        if not csv_path.exists():
            continue
        df = pd.read_csv(csv_path, low_memory=False)
        if df.empty:
            continue

        df["observation_date"] = df["observation_date"].astype(str).str[:10]
        df = df[df["observation_date"] >= cutoff].copy()
        if df.empty:
            continue

        records = []
        for _, row in df.iterrows():
            price_usd = row.get("price_usd")
            if pd.isna(price_usd):
                continue
            records.append(
                {
                    "observation_date": row.get("observation_date", ""),
                    "fuel_family": row.get("fuel_family", ""),
                    "unit": row.get("unit", ""),
                    "price_usd": float(price_usd),
                }
            )

        if records:
            usd_data[c["country"]] = records

    return usd_data


def assemble_publish_data(
    region: str,
    countries: list[dict],
    data_dir: Path = _DATA_DIR,
    cache_dir: Path = _REFERENCE_CACHE,
) -> dict:
    """Assemble all data needed by gen_policy_html."""
    from .reference.commodities import load_commodity_series
    from .reference.gdp import load_gdp
    from .reference.population import load_population
    from .reference.subsidies import (
        PRODUCTS,
        REGIME_COLORS,
        TABLE_PRODUCTS,
        load_imf_subsidies,
        load_regime_data,
    )

    pub_cfg = _load_publish_config(region)
    history_years = pub_cfg.get("dashboard_history_years", 3)
    regime_overrides = pub_cfg.get("regime_overrides", {})

    logger.info("Loading commodity data ...")
    comm_series = load_commodity_series(data_dir, history_years=history_years)

    commodity_filter = pub_cfg.get("commodity_products", [])
    if commodity_filter:
        comm_series = {k: v for k, v in comm_series.items() if k in commodity_filter}

    logger.info("Loading regime data ...")
    regime_csv = cache_dir / "worldbank" / "subsidies_price_controls.csv"
    df_regime, product_regimes = load_regime_data(
        regime_csv, overrides=regime_overrides
    )

    logger.info("Loading IMF subsidies ...")
    df_imf = load_imf_subsidies(cache_dir)

    logger.info("Loading population ...")
    df_pop = load_population(cache_dir)
    if "country_name" in df_pop.columns:
        df_pop["country_name"] = df_pop["country_name"].replace(_COUNTRY_NAME_MAP)

    logger.info("Loading GDP per capita ...")
    df_gdp = load_gdp(cache_dir)
    if "country_name" in df_gdp.columns:
        df_gdp["country_name"] = df_gdp["country_name"].replace(_COUNTRY_NAME_MAP)

    # Region country list with regimes
    region_isos = sorted({c["iso3"] for c in countries if c.get("iso3")})
    region_countries: list[dict] = []
    if not df_regime.empty:
        for c in countries:
            iso3 = c.get("iso3", "")
            regime_row = df_regime[df_regime["wb_iso3"] == iso3]
            entry = {
                "country": c["country"],
                "wb_iso3": iso3,
                "base_regime": "Unknown",
                "subsidy_flag": False,
                "regime": "Unknown",
                "tooltip": "",
            }
            if not regime_row.empty:
                row = regime_row.iloc[0]
                entry["base_regime"] = row.get("base_regime", "Unknown")
                entry["subsidy_flag"] = bool(row.get("subsidy_flag", False))
                entry["regime"] = row.get("regime", "Unknown")
                entry["tooltip"] = str(row.get("tooltip", ""))
            region_countries.append(entry)
    else:
        region_countries = [
            {
                "country": c["country"],
                "wb_iso3": c.get("iso3", ""),
                "base_regime": "Unknown",
                "subsidy_flag": False,
                "regime": "Unknown",
                "tooltip": "",
            }
            for c in countries
        ]

    # IMF per-capita subsidies
    imf_pc_by_iso3: dict[str, dict[str, float | None]] = {}
    imf_raw_by_iso3: dict[str, dict[str, float | None]] = {}
    if not df_imf.empty:
        df_imf_pop = (
            df_imf.merge(df_pop[["wb_iso3", "population"]], on="wb_iso3", how="left")
            if not df_pop.empty
            else df_imf.assign(population=None)
        )
        for _, row in df_imf_pop.iterrows():
            iso3 = str(row.get("wb_iso3", "")).strip()
            pop = row.get("population")
            pop_ok = pd.notna(pop) and float(pop) > 0
            prods: dict[str, float | None] = {}
            raw_prods: dict[str, float | None] = {}
            for prod in PRODUCTS:
                val = row.get(prod)
                raw_prods[prod] = float(val) if pd.notna(val) else None
                if pd.notna(val) and pop_ok:
                    prods[prod] = float(val) * 1e9 / float(pop)
                else:
                    prods[prod] = None
            imf_pc_by_iso3[iso3] = prods
            imf_raw_by_iso3[iso3] = raw_prods

    # Scatter data
    scatter_points: list[dict] = []
    if not df_gdp.empty:
        scatter_base = df_gdp[["wb_iso3", "gdp_per_capita"]].copy()
        if "country_name" in df_gdp.columns:
            scatter_base["country_name"] = df_gdp["country_name"]
        else:
            scatter_base["country_name"] = scatter_base["wb_iso3"]

        if not df_pop.empty:
            scatter_base = scatter_base.merge(
                df_pop[["wb_iso3", "population"]], on="wb_iso3", how="left"
            )
        else:
            scatter_base["population"] = None

        if not df_regime.empty:
            scatter_base = scatter_base.merge(
                df_regime[["wb_iso3", "base_regime", "subsidy_flag", "regime"]],
                on="wb_iso3",
                how="left",
            )
            scatter_base["regime"] = scatter_base["regime"].fillna("Unknown")
            scatter_base["base_regime"] = scatter_base["base_regime"].fillna("Unknown")
            scatter_base["subsidy_flag"] = (
                scatter_base["subsidy_flag"]
                .where(scatter_base["subsidy_flag"].notna(), False)
                .astype(bool)
            )
        else:
            scatter_base["regime"] = "Unknown"
            scatter_base["base_regime"] = "Unknown"
            scatter_base["subsidy_flag"] = False

        for _, row in scatter_base.iterrows():
            iso3 = str(row.get("wb_iso3", ""))
            imf_pc = imf_pc_by_iso3.get(iso3, {p: None for p in PRODUCTS})
            imf_raw = imf_raw_by_iso3.get(iso3, {p: None for p in PRODUCTS})
            scatter_points.append(
                {
                    "country": str(row.get("country_name", "")),
                    "wb_iso3": iso3,
                    "base_regime": str(row.get("base_regime", "Unknown")),
                    "regime": str(row.get("regime", "Unknown")),
                    "gdp_per_capita": (
                        float(row["gdp_per_capita"])
                        if pd.notna(row.get("gdp_per_capita"))
                        else None
                    ),
                    "population": (
                        int(row["population"])
                        if pd.notna(row.get("population"))
                        else None
                    ),
                    "subsidies": {
                        p: (round(float(v), 4) if v is not None else None)
                        for p, v in imf_pc.items()
                    },
                    "imf_has_subsidy": {
                        p: (v is not None and v > 0) for p, v in imf_raw.items()
                    },
                }
            )

    return {
        "comm_series": comm_series,
        "region_countries": region_countries,
        "region_isos": region_isos,
        "scatter": scatter_points,
        "regime_colors": REGIME_COLORS,
        "product_regimes": product_regimes,
        "products": PRODUCTS,
        "table_products": TABLE_PRODUCTS,
        "imf_raw_by_iso3": imf_raw_by_iso3,
    }


def run_publish(
    *,
    region: str | None = None,
    subregion: str | None = None,
    data_dir: Path = _DATA_DIR,
    outputs_dir: Path = _OUTPUTS_DIR,
    cache_dir: Path = _REFERENCE_CACHE,
) -> None:
    """Generate fuel policy dashboards for one or all regions."""
    from .publish_html import gen_policy_html

    if region:
        regions_to_publish = [region]
    else:
        regions_to_publish = sorted(
            {
                p.relative_to(outputs_dir).parts[0]
                for p in outputs_dir.rglob("fuel_product_local_prices.csv")
                if len(p.relative_to(outputs_dir).parts) >= 4
                and not p.relative_to(outputs_dir).parts[0].startswith("_")
            }
        )

    if not regions_to_publish:
        raise click.ClickException("No build outputs found. Run `po fuel build` first.")

    for reg in regions_to_publish:
        countries = discover_publish_countries(
            outputs_dir, region=reg, subregion=subregion
        )
        if not countries:
            logger.warning("No countries with build outputs for region=%s", reg)
            continue

        pub_cfg = _load_publish_config(reg)
        history_years = pub_cfg.get("dashboard_history_years", 3)
        region_label = pub_cfg.get("region_label", reg.upper())

        names = ", ".join(c["country"] for c in countries)
        click.echo(f"Publishing {reg} dashboard ({len(countries)} countries: {names})")

        logger.info("Assembling data for %s ...", reg)
        data = assemble_publish_data(
            reg, countries, data_dir=data_dir, cache_dir=cache_dir
        )

        logger.info("Loading country fuel data ...")
        fuel_data = _load_country_fuel_data(countries, history_years=history_years)

        logger.info("Loading country USD data ...")
        usd_data = _load_country_usd_data(countries, history_years=history_years)

        out_path = outputs_dir / reg / "fuel_policy_dashboard.html"
        gen_policy_html(
            data=data,
            fuel_data=fuel_data,
            usd_data=usd_data,
            out=out_path,
            region_label=region_label,
        )
        logger.info("Dashboard written to %s", out_path)
