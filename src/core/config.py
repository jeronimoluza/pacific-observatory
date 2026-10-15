"""Load cross-pipeline configuration: regions, countries, settings."""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

import click
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


# ── Loaders ────────────────────────────────────────────────────────


def load_regions(configs_dir: Path = _CONFIGS_DIR) -> dict[str, dict]:
    """Load regions.yaml → {region_slug: {name, subregions: {...}}}."""
    return _load_yaml(configs_dir / "regions.yaml")


def load_countries(configs_dir: Path = _CONFIGS_DIR) -> dict[str, dict]:
    """Load countries.yaml → {slug: {name, iso3, currency, languages}}."""
    return _load_yaml(configs_dir / "countries.yaml")


def load_settings(configs_dir: Path = _CONFIGS_DIR) -> dict[str, Any]:
    """Load settings.yaml → global paths and defaults."""
    return _load_yaml(configs_dir / "settings.yaml")


# ── Lookup helpers ─────────────────────────────────────────────────


@lru_cache(maxsize=1)
def _build_index(configs_dir: str = str(_CONFIGS_DIR)) -> dict:
    """Build internal lookup index from regions + countries YAML.

    Returns dict with:
      region_names:   {region_slug: name}
      subregion_names: {subregion_slug: name}
      country_to_path: {country_slug: (region, subregion)}
      subregion_to_region: {subregion_slug: region_slug}
    """
    cd = Path(configs_dir)
    regions = load_regions(cd)
    region_names = {}
    subregion_names = {}
    country_to_path = {}
    subregion_to_region = {}

    for region_slug, region_data in regions.items():
        region_names[region_slug] = region_data.get("name", region_slug)
        for sub_slug, sub_data in region_data.get("subregions", {}).items():
            subregion_names[sub_slug] = sub_data.get("name", sub_slug)
            subregion_to_region[sub_slug] = region_slug
            for country_slug in sub_data.get("countries", []):
                country_to_path[country_slug] = (region_slug, sub_slug)

    return {
        "region_names": region_names,
        "subregion_names": subregion_names,
        "country_to_path": country_to_path,
        "subregion_to_region": subregion_to_region,
    }


def known_country_slugs(configs_dir: Path = _CONFIGS_DIR) -> set[str]:
    """Country slugs declared in regions.yaml — the canonical topology.

    Discovery walks directories, so a folder left behind by a rename silently
    becomes a country of its own: ``lao`` survived alongside ``lao_pdr`` with
    the same five sources, appeared in the dashboard under its raw slug because
    ``countries.yaml`` had no entry to label it, and was counted a second time
    in the subregion and region aggregates. Checking a discovered directory
    against this set keeps the topology, not the filesystem, in charge of what
    counts as a country.
    """
    return set(_build_index(str(configs_dir))["country_to_path"])


def get_label(slug: str, configs_dir: Path = _CONFIGS_DIR) -> str:
    """Return the display name for a region, subregion, or country slug."""
    idx = _build_index(str(configs_dir))
    # Check regions
    if slug in idx["region_names"]:
        return idx["region_names"][slug]
    # Check subregions
    if slug in idx["subregion_names"]:
        return idx["subregion_names"][slug]
    # Check countries
    countries = load_countries(configs_dir)
    if slug in countries:
        return countries[slug].get("name", slug)
    return slug


def get_country_path(
    country_slug: str, configs_dir: Path = _CONFIGS_DIR
) -> tuple[str, str, str]:
    """Return (region, subregion, country) tuple for a country slug."""
    idx = _build_index(str(configs_dir))
    if country_slug not in idx["country_to_path"]:
        raise ValueError(
            f"Unknown country: {country_slug}. "
            f"Known: {sorted(idx['country_to_path'].keys())}"
        )
    region, subregion = idx["country_to_path"][country_slug]
    return (region, subregion, country_slug)


def get_country_meta(
    country_slug: str, configs_dir: Path = _CONFIGS_DIR
) -> dict[str, Any]:
    """Return country properties with region/subregion injected."""
    countries = load_countries(configs_dir)
    if country_slug not in countries:
        raise ValueError(f"Unknown country: {country_slug}")
    region, subregion, _ = get_country_path(country_slug, configs_dir)
    return {**countries[country_slug], "region": region, "subregion": subregion}


# ── Filtering helpers ──────────────────────────────────────────────


def countries_for_region(region: str, configs_dir: Path = _CONFIGS_DIR) -> list[str]:
    """Return list of country slugs belonging to a region."""
    regions = load_regions(configs_dir)
    entry = regions.get(region)
    if entry is None:
        raise ValueError(f"Unknown region: {region}. Known: {list(regions.keys())}")
    result = []
    for sub_data in entry.get("subregions", {}).values():
        result.extend(sub_data.get("countries", []))
    return sorted(result)


def countries_for_subregion(
    region: str, subregion: str, configs_dir: Path = _CONFIGS_DIR
) -> list[str]:
    """Return list of country slugs belonging to a subregion."""
    regions = load_regions(configs_dir)
    entry = regions.get(region)
    if entry is None:
        raise ValueError(f"Unknown region: {region}")
    sub_entry = entry.get("subregions", {}).get(subregion)
    if sub_entry is None:
        known = list(entry.get("subregions", {}).keys())
        raise ValueError(f"Unknown subregion: {subregion}. Known: {known}")
    return sorted(sub_entry.get("countries", []))


def resolve_subregion_region(subregion: str, configs_dir: Path = _CONFIGS_DIR) -> str:
    """Given a subregion slug, return its parent region slug."""
    idx = _build_index(str(configs_dir))
    if subregion not in idx["subregion_to_region"]:
        raise ValueError(
            f"Unknown subregion: {subregion}. "
            f"Known: {sorted(idx['subregion_to_region'].keys())}"
        )
    return idx["subregion_to_region"][subregion]


# ── Config discovery ───────────────────────────────────────────────


def discover_pipeline_configs(
    pipeline_configs_dir: Path,
    region: str | None = None,
    subregion: str | None = None,
    country: str | None = None,
) -> list[Path]:
    """Find YAML configs for a pipeline, optionally filtered.

    Walks: {pipeline_configs_dir}/{region}/{subregion}/{country}/{source}.yaml
    Skips directories starting with _ (e.g. _examples/, _aggregate/).
    """
    if not pipeline_configs_dir.exists():
        return []
    yamls = []
    for path in sorted(pipeline_configs_dir.rglob("*.yaml")):
        rel_parts = path.relative_to(pipeline_configs_dir).parts
        # Skip _examples, _aggregate, etc.
        if any(part.startswith("_") for part in rel_parts):
            continue
        # Filter by region (first path component)
        if region and (len(rel_parts) < 1 or rel_parts[0] != region):
            continue
        # Filter by subregion (second path component)
        if subregion and (len(rel_parts) < 2 or rel_parts[1] != subregion):
            continue
        # Filter by country (match any non-terminal part)
        if country and not any(p == country for p in rel_parts[:-1]):
            continue
        yamls.append(path)
    return yamls


def parse_config_path(config_path: Path, base_dir: Path) -> tuple[str, str, str]:
    """Return (region, subregion, country) from a pipeline config file path."""
    parts = config_path.relative_to(base_dir).parts
    region = parts[0] if len(parts) >= 4 else "unknown"
    subregion = parts[1] if len(parts) >= 4 else "unknown"
    country = parts[2] if len(parts) >= 4 else parts[1] if len(parts) >= 3 else parts[0]
    return region, subregion, country


# ── Slug validation ───────────────────────────────────────────────


def make_slug_validator(kind: str, extra_valid: set[str] | None = None):
    """Return a Click option callback that validates region/subregion/country slugs."""
    _hints = {
        "region": "Run 'po list-regions' to see available regions, subregions, and countries.",
        "subregion": "Run 'po list-regions' to see available subregions and their parent regions.",
        "country": "Run 'po list-regions' to see available countries and where they belong.",
    }
    _index_key = {
        "region": "region_names",
        "subregion": "subregion_names",
        "country": "country_to_path",
    }

    def callback(ctx, param, value):
        if value is None:
            return value
        if extra_valid and value in extra_valid:
            return value
        idx = _build_index()
        if value not in idx[_index_key[kind]]:
            raise click.BadParameter(f"unknown {kind} '{value}'. {_hints[kind]}")
        return value

    return callback


# ── Region topology display ───────────────────────────────────────


def _wrap_country_list(countries: list[str], max_width: int, indent: int) -> str:
    """Join countries with ' · ', wrapping lines at max_width."""
    if not countries:
        return ""
    lines = []
    current_line = countries[0]
    for c in countries[1:]:
        candidate = current_line + " · " + c
        if len(candidate) > max_width:
            lines.append(current_line)
            current_line = c
        else:
            current_line = candidate
    lines.append(current_line)
    return ("\n" + " " * indent).join(lines)


def format_regions_table(configs_dir: Path = _CONFIGS_DIR) -> str:
    """Format the region -> subregion -> country topology as a printable table."""
    regions = load_regions(configs_dir)
    lines = []
    total_regions = 0
    total_subregions = 0
    total_countries = 0

    rw, sw = 12, 22
    col_start = 2 + rw + sw
    lines.append(f"  {'Region':<{rw}}{'Subregion':<{sw}}Countries")
    lines.append("  " + "─" * 80)

    for region_slug, region_data in regions.items():
        total_regions += 1
        first_region = True
        for sub_slug, sub_data in region_data.get("subregions", {}).items():
            total_subregions += 1
            countries = sub_data.get("countries", [])
            total_countries += len(countries)

            region_col = region_slug if first_region else ""
            first_region = False
            country_str = _wrap_country_list(countries, 60, col_start)
            lines.append(f"  {region_col:<{rw}}{sub_slug:<{sw}}{country_str}")

    lines.append("  " + "─" * 80)
    lines.append(
        f"  {total_regions} regions · {total_subregions} subregions · "
        f"{total_countries} countries"
    )
    lines.append("")
    lines.append(
        "  Usage:  --region eap   --subregion eastern_europe   --country ukraine"
    )
    return "\n".join(lines)
