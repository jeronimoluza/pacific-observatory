"""Fuel source configuration: Pydantic models, discovery, and registry builder."""

from __future__ import annotations

import importlib
import logging
from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.config import discover_pipeline_configs, load_countries, parse_config_path

logger = logging.getLogger(__name__)

_FUEL_CONFIGS_DIR = Path(__file__).resolve().parent / "configs"


# ── Pydantic models ──────────────────────────────────────────────────────────


class ProductSpec(BaseModel):
    """Fuel product definition within a source config."""

    model_config = ConfigDict(extra="ignore")

    series_key: str
    fuel_family: str
    unit: str = "liter"
    amount: float | None = None
    include_in_build: bool = True
    grade: str | None = None
    octane_ron: int | None = None
    label: str = ""

    @field_validator("fuel_family")
    @classmethod
    def _normalize_family(cls, value: str) -> str:
        aliases = {
            "gasoline": "gasoline",
            "diesel": "diesel",
            "lpg": "lpg",
            "kerosene": "kerosene",
            "cng": "cng",
            "ngv": "cng",
            "heatingoil": "heating_oil",
            "heating_oil": "heating_oil",
            "electricityev": "electricity_ev",
            "electricity_ev": "electricity_ev",
            "fuel_oil": "fuel_oil",
            "fueloil": "fuel_oil",
            "jet_fuel": "jet_fuel",
            "jetfuel": "jet_fuel",
            "asphalt": "asphalt",
        }
        key = str(value).strip().lower().replace(" ", "_")
        key = key.replace("-", "_")
        key = key.replace("__", "_")
        if key not in aliases:
            raise ValueError(f"Unsupported fuel_family: {value}")
        return aliases[key]

    @field_validator("unit")
    @classmethod
    def _normalize_unit(cls, value: str) -> str:
        aliases = {
            "l": "liter",
            "liter": "liter",
            "liters": "liter",
            "litre": "liter",
            "litres": "liter",
            "gallon": "gallon",
            "gallons": "gallon",
            "kg": "kilogram",
            "kgs": "kilogram",
            "kilogram": "kilogram",
            "kilograms": "kilogram",
            "lb": "pound",
            "lbs": "pound",
            "pound": "pound",
            "pounds": "pound",
            "ton": "ton",
            "tons": "ton",
            "tonne": "ton",
            "tonnes": "ton",
            "cylinder": "cylinder",
            "m3": "m3",
            "kw": "kw",
            "kwh": "kwh",
            "fee": "fee",
        }
        key = str(value).strip().lower()
        if key not in aliases:
            raise ValueError(f"Unsupported unit: {value}")
        return aliases[key]

    @field_validator("amount")
    @classmethod
    def _validate_amount(cls, value: float | None) -> float | None:
        if value is not None and value <= 0:
            raise ValueError("amount must be positive")
        return value


class FuelSourceConfig(BaseModel):
    """Source-centric config loaded from a single YAML file."""

    model_config = ConfigDict(extra="ignore")

    source_key: str
    module: str
    function: str
    url: str = ""
    enabled: bool = True
    fallback_date: date = date(2020, 1, 1)
    full_refresh: bool = False
    default_unit: str = "L"
    first_row_only: bool = False
    priority: int = 100
    cadence: Literal[
        "daily",
        "weekly",
        "biweekly",
        "monthly",
        "quarterly",
        "yearly",
        "irregular",
    ]
    carry_forward: bool = False
    products: dict[str, ProductSpec]  # raw_product_name → ProductSpec

    # Resolved from path + countries.yaml (not in YAML file)
    country_slug: str = ""
    country_name: str = ""
    iso3: str = ""
    currency: str = ""
    region: str = ""
    subregion: str = ""
    source: str = ""
    config_path: str = Field(default="", exclude=True)


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
    raw.setdefault("country_name", country_props.get("name", country_slug))
    raw.setdefault("iso3", country_props.get("iso3", ""))
    raw.setdefault("currency", country_props.get("currency", ""))
    raw["region"] = region
    raw["subregion"] = subregion
    raw["source"] = path.stem
    raw["config_path"] = str(path)

    cfg = FuelSourceConfig(**raw)
    for raw_name, spec in cfg.products.items():
        if not spec.label:
            spec.label = raw_name
    return cfg


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
    try:
        mod = importlib.import_module(mod_path)
    except ModuleNotFoundError as exc:
        raise ValueError(
            f"Failed to import module '{mod_path}' for {cfg.source_key} ({cfg.config_path})"
        ) from exc
    try:
        return getattr(mod, cfg.function)
    except AttributeError as exc:
        raise ValueError(
            f"Failed to resolve function '{cfg.function}' for {cfg.source_key} ({cfg.config_path})"
        ) from exc


def _build_global_registry(
    source_key: str | None = None,
    configs_dir: Path = _FUEL_CONFIGS_DIR,
) -> dict[str, dict]:
    """Build registry for _global sources (commodities, etc.).

    These configs live under ``configs/_global/`` and don't follow the
    region/subregion/country hierarchy.
    """
    global_dir = configs_dir / "_global"
    if not global_dir.exists():
        return {}

    registry: dict[str, dict] = {}
    for yaml_path in sorted(global_dir.glob("*.yaml")):
        with open(yaml_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        if not isinstance(raw, dict):
            continue
        key = raw.get("source_key", yaml_path.stem)
        if source_key and key != source_key:
            continue

        mod_path = f"fuel.fetchers.{raw['module']}"
        try:
            mod = importlib.import_module(mod_path)
            fn = getattr(mod, raw["function"])
        except Exception:
            logger.exception("Failed to resolve _global fetcher: %s", key)
            continue

        fallback = raw.get("fallback_date", date(2021, 1, 1))
        if isinstance(fallback, str):
            fallback = date.fromisoformat(fallback)

        registry[key] = {
            "fn": fn,
            "fallback_date": fallback,
            "enabled": raw.get("enabled", True),
            "full_refresh": raw.get("full_refresh", False),
            "priority": raw.get("priority", 10),
            "cadence": raw.get("cadence", "daily"),
            "carry_forward": raw.get("carry_forward", False),
            "country_slug": "",
            "country_name": "Global",
            "iso3": "",
            "currency": "USD",
            "region": "_global",
            "subregion": "",
            "source": yaml_path.stem,
            "products": {},
            "config_path": str(yaml_path),
            "source_key": key,
            "url": raw.get("url", ""),
        }
    return registry


def build_fuel_registry(
    region: str | None = None,
    subregion: str | None = None,
    country: str | None = None,
    source_key: str | None = None,
    include_global: bool = False,
) -> dict[str, dict]:
    """Build a registry of source_key → {fn, fallback_date, enabled, ...}.

    If source_key is given, only that source is included.
    Pass ``region="global"`` to load commodity sources from ``_global/``.
    Pass ``include_global=True`` to auto-include global commodity sources
    alongside region-specific sources.
    """
    if region == "global":
        return _build_global_registry(source_key=source_key)

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
            "priority": cfg.priority,
            "cadence": cfg.cadence,
            "carry_forward": cfg.carry_forward,
            "country_slug": cfg.country_slug,
            "country_name": cfg.country_name,
            "iso3": cfg.iso3,
            "currency": cfg.currency,
            "region": cfg.region,
            "subregion": cfg.subregion,
            "source": cfg.source,
            "products": cfg.products,
            "config_path": cfg.config_path,
            "source_key": key,
            "url": cfg.url,
        }

    if include_global and not source_key:
        global_reg = _build_global_registry()
        registry.update(global_reg)

    return registry
