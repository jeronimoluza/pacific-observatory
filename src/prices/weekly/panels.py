"""`--countries`: comma-separated slugs, or a panel name from src/configs/panels/."""

from __future__ import annotations

from collections import Counter

import click
import yaml

from core.config import _CONFIGS_DIR, get_country_path, load_countries, load_regions
from prices.config import discover_prices_configs

PANELS_DIR = _CONFIGS_DIR / "panels"


def region_units(region: str, subregion: str | None = None) -> list[str]:
    """Countries of a region (or subregion) in regions.yaml, plus the text config folders outside
    regions.yaml under it (`pacific`), which the text build keeps as units of its aggregates."""
    subs = load_regions()[region]["subregions"]
    out = [c for s, v in subs.items() if subregion in (None, s) for c in v["countries"]]
    configs = _CONFIGS_DIR.parent / "text" / "configs" / region
    extra = sorted(p.name for p in configs.glob(f"{subregion or '*'}/*") if p.is_dir() and any(p.glob("*.yaml")))
    return out + [c for c in extra if c not in out]


def _panel_pairs(name: str, errors: list[str]) -> list[tuple[str | None, str]]:
    """`countries: {region: [slugs]}`, `regions: [region]` (every unit of it) and
    `include: [panel]`; a country reached twice through include/regions counts once."""
    spec = yaml.safe_load((PANELS_DIR / f"{name}.yaml").read_text())
    own = [(r, c) for r, cs in (spec.get("countries") or {}).items() for c in cs]
    dups = [c for c, n in Counter(c for _, c in own).items() if n > 1]
    if dups:
        errors.append(f"{name}: listed twice: {', '.join(dups)}")
    pairs = [p for inc in spec.get("include") or [] for p in _panel_pairs(inc, errors)]
    pairs += [(None, c) for r in spec.get("regions") or [] for c in region_units(r)]
    return pairs + own


def resolve_countries(value: str | None) -> list[str] | None:
    if not value:
        return None
    errors = []
    if (PANELS_DIR / f"{value}.yaml").exists():
        pairs = _panel_pairs(value, errors)
    else:
        pairs = [(None, c.strip()) for c in value.split(",") if c.strip()]
        dups = [c for c, n in Counter(c for _, c in pairs).items() if n > 1]
        if dups:
            errors.append(f"listed twice: {', '.join(dups)}")
    known = load_countries()
    for region, c in pairs:
        if c not in known:
            errors.append(f"{c}: not in countries.yaml")
        elif region and get_country_path(c)[0] != region:
            errors.append(
                f"{c}: listed under {region}, regions.yaml has {get_country_path(c)[0]}"
            )
    if errors:
        raise click.BadParameter("; ".join(errors), param_hint="--countries")
    return list(dict.fromkeys(c for _, c in pairs))


def sources_by_country(countries: list[str]) -> dict[str, tuple[int, int]]:
    """country -> (manifests, active manifests) under src/prices/configs."""
    out = {c: [0, 0] for c in countries}
    for path in discover_prices_configs():
        country = path.parent.name
        if country in out:
            active = (yaml.safe_load(path.read_text()) or {}).get("active", True)
            out[country][0] += 1
            out[country][1] += bool(active)
    return {c: (n, a) for c, (n, a) in out.items()}
