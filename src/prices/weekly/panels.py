"""`--countries`: comma-separated slugs, or a panel name from src/configs/panels/."""

from __future__ import annotations

from collections import Counter

import click
import yaml

from core.config import _CONFIGS_DIR, get_country_path, load_countries
from prices.config import discover_prices_configs

PANELS_DIR = _CONFIGS_DIR / "panels"


def resolve_countries(value: str | None) -> list[str] | None:
    if not value:
        return None
    panel = PANELS_DIR / f"{value}.yaml"
    if panel.exists():
        regions = yaml.safe_load(panel.read_text())["countries"]
        pairs = [(r, c) for r, cs in regions.items() for c in cs]
    else:
        pairs = [(None, c.strip()) for c in value.split(",") if c.strip()]
    known = load_countries()
    errors = []
    for region, c in pairs:
        if c not in known:
            errors.append(f"{c}: not in countries.yaml")
        elif region and get_country_path(c)[0] != region:
            errors.append(
                f"{c}: listed under {region}, regions.yaml has {get_country_path(c)[0]}"
            )
    dups = [c for c, n in Counter(c for _, c in pairs).items() if n > 1]
    if dups:
        errors.append(f"listed twice: {', '.join(dups)}")
    if errors:
        raise click.BadParameter("; ".join(errors), param_hint="--countries")
    return [c for _, c in pairs]


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
