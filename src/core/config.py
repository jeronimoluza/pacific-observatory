"""Load cross-pipeline configuration: regions (with countries), settings."""

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_CONFIGS_DIR = Path(__file__).resolve().parent.parent / "configs"


def _load_yaml(path: Path) -> dict:
    """Load a YAML file, returning empty dict if missing."""
    if not path.exists():
        logger.warning("Config file not found: %s", path)
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_regions(configs_dir: Path = _CONFIGS_DIR) -> dict[str, dict]:
    """Load regions.yaml → {region_slug: {name, description, countries: {...}}}."""
    return _load_yaml(configs_dir / "regions.yaml")


def load_countries(configs_dir: Path = _CONFIGS_DIR) -> dict[str, dict]:
    """Flatten all countries from regions.yaml → {slug: {name, iso3, currency, region}}.

    Each country dict gets a 'region' key injected from its parent region.
    """
    regions = load_regions(configs_dir)
    countries = {}
    for region_slug, region_data in regions.items():
        for country_slug, country_data in region_data.get("countries", {}).items():
            countries[country_slug] = {**country_data, "region": region_slug}
    return countries


def load_settings(configs_dir: Path = _CONFIGS_DIR) -> dict[str, Any]:
    """Load settings.yaml → global paths and defaults."""
    return _load_yaml(configs_dir / "settings.yaml")


def countries_for_region(region: str, configs_dir: Path = _CONFIGS_DIR) -> list[str]:
    """Return list of country slugs belonging to a region."""
    regions = load_regions(configs_dir)
    entry = regions.get(region)
    if entry is None:
        raise ValueError(f"Unknown region: {region}. Known: {list(regions.keys())}")
    return list(entry.get("countries", {}).keys())


def discover_pipeline_configs(
    pipeline_configs_dir: Path,
    region: str | None = None,
    country: str | None = None,
) -> list[Path]:
    """Find YAML configs for a pipeline, optionally filtered by region/country.

    Walks: {pipeline_configs_dir}/{region}/{country}.yaml
    Skips directories starting with _ (e.g. _examples/).
    """
    yamls = []
    for path in sorted(pipeline_configs_dir.rglob("*.yaml")):
        # Skip _examples, _example.yaml, etc.
        if any(
            part.startswith("_")
            for part in path.relative_to(pipeline_configs_dir).parts
        ):
            continue
        if region and path.parent.name != region:
            continue
        if country and path.stem != country:
            continue
        yamls.append(path)
    return yamls
