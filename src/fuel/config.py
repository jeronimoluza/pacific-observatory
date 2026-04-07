"""Fuel source configuration: Pydantic models, discovery, and registry builder."""

from __future__ import annotations

import importlib
import logging
from datetime import date
from pathlib import Path
import yaml
from pydantic import BaseModel

from core.config import discover_pipeline_configs, load_countries, parse_config_path

logger = logging.getLogger(__name__)

_FUEL_CONFIGS_DIR = Path(__file__).resolve().parent / "configs"


# ── Pydantic models ──────────────────────────────────────────────────────────


class ProductSpec(BaseModel):
    """Fuel product definition within a source config."""

    family: str  # gasoline, diesel, lpg, kerosene, cng, heating_oil
    grade: str
    series_key: str
    octane_ron: int | None = None
    unit: str = "L"


class FuelSourceConfig(BaseModel):
    """Source-centric config loaded from a single YAML file."""

    source_key: str
    module: str
    function: str
    url: str = ""
    enabled: bool = True
    fallback_date: date = date(2020, 1, 1)
    full_refresh: bool = False
    default_unit: str = "L"
    first_row_only: bool = False
    products: dict[str, ProductSpec]  # raw_product_name → ProductSpec

    # Resolved from path + countries.yaml (not in YAML file)
    country_slug: str = ""
    country_name: str = ""
    iso3: str = ""
    currency: str = ""
    region: str = ""
    subregion: str = ""


# ── Loading ──────────────────────────────────────────────────────────────────


def load_source_config(
    path: Path,
    countries: dict[str, dict],
    base_dir: Path = _FUEL_CONFIGS_DIR,
) -> FuelSourceConfig:
    """Load and validate a single fuel source YAML, resolving country props."""
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    if not isinstance(raw, dict):
        raise ValueError(f"Config file {path} is not a YAML mapping")

    # Resolve country from path
    region, subregion, country_slug = parse_config_path(path, base_dir)
    country_props = countries.get(country_slug, {})

    raw["country_slug"] = country_slug
    raw["country_name"] = country_props.get("name", country_slug)
    raw["iso3"] = country_props.get("iso3", "")
    raw["currency"] = country_props.get("currency", "")
    raw["region"] = region
    raw["subregion"] = subregion

    return FuelSourceConfig(**raw)


def discover_fuel_configs(
    region: str | None = None,
    subregion: str | None = None,
    country: str | None = None,
    configs_dir: Path = _FUEL_CONFIGS_DIR,
) -> list[Path]:
    """Find fuel source YAML configs, optionally filtered."""
    return discover_pipeline_configs(configs_dir, region, subregion, country)


def load_all_source_configs(
    region: str | None = None,
    subregion: str | None = None,
    country: str | None = None,
    configs_dir: Path = _FUEL_CONFIGS_DIR,
) -> dict[str, FuelSourceConfig]:
    """Load all fuel source configs, keyed by source_key."""
    countries = load_countries()
    paths = discover_fuel_configs(region, subregion, country, configs_dir)
    configs: dict[str, FuelSourceConfig] = {}
    for p in paths:
        try:
            cfg = load_source_config(p, countries, configs_dir)
            configs[cfg.source_key] = cfg
        except Exception:
            logger.exception("Failed to load fuel config: %s", p)
    return configs


# ── Registry ─────────────────────────────────────────────────────────────────


def resolve_fetcher(cfg: FuelSourceConfig) -> callable:
    """Resolve a source config's module/function to a Python callable."""
    mod_path = f"fuel.fetchers.{cfg.module}"
    mod = importlib.import_module(mod_path)
    return getattr(mod, cfg.function)


def build_fuel_registry(
    region: str | None = None,
    subregion: str | None = None,
    country: str | None = None,
    source_key: str | None = None,
) -> dict[str, dict]:
    """Build a registry of source_key → {fn, fallback_date, enabled, ...}.

    If source_key is given, only that source is included.
    """
    configs = load_all_source_configs(region, subregion, country)

    if source_key:
        if source_key not in configs:
            available = ", ".join(sorted(configs))
            raise ValueError(
                f"Unknown source key: {source_key}. Available: {available}"
            )
        configs = {source_key: configs[source_key]}

    registry: dict[str, dict] = {}
    for key, cfg in configs.items():
        fn = resolve_fetcher(cfg)
        registry[key] = {
            "fn": fn,
            "fallback_date": cfg.fallback_date,
            "enabled": cfg.enabled,
            "full_refresh": cfg.full_refresh,
            "country_slug": cfg.country_slug,
            "country_name": cfg.country_name,
            "source_key": key,
            "url": cfg.url,
        }
    return registry
