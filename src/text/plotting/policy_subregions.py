"""Group workbook country cells by the subregion topology in regions.yaml.

Tracker workbooks are analyst-typed, so a country cell may be shorthand
("PNG", "RMI", "FSM"), a World Bank long form ("Micronesia, Fed. Sts.") or a
name the topology has never listed ("Cook Islands"). A plain slug lookup
therefore leaves rows out of every subregion. Names that still fail to match
are returned to the caller so the build can say so instead of dropping them
quietly -- they remain reachable under the "All subregions" default.
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Tuple

from core.config import load_countries, load_regions


# Workbook shorthand that neither the slug nor the countries.yaml name matches.
NAME_ALIASES: Dict[str, str] = {
    "png": "papua_new_guinea",
    "fsm": "micronesia_fed_sts",
    "rmi": "marshall_islands",
    "laos": "lao_pdr",
    "korearep": "south_korea",
}

# Countries and aggregate rows the topology does not carry at all, mapped
# straight onto a subregion key.
EXTRA_MEMBERS: Dict[str, str] = {
    "cookislands": "pacific_islands",
    "allpacific": "pacific_islands",
}

ALL_LABEL = "All subregions"


def _norm(value: str) -> str:
    text = re.sub(r"\s+", " ", (value or "").strip().lower()).replace("&", "and")
    return re.sub(r"[^a-z0-9]+", "", text)


def _slug_to_subregion(region_key: str) -> Tuple[Dict[str, str], Dict[str, str]]:
    region = load_regions().get(region_key, {})
    subregion_names: Dict[str, str] = {}
    by_slug: Dict[str, str] = {}
    for sub_key, sub in (region.get("subregions") or {}).items():
        subregion_names[sub_key] = sub.get("name", sub_key)
        for slug in sub.get("countries") or []:
            by_slug[slug] = sub_key
    return by_slug, subregion_names


def build_subregion_groups(
    countries: Iterable[str], region_key: str
) -> Tuple[Dict[str, List[str]], List[str]]:
    """Return (subregion display name -> country cells, unmatched cells)."""
    by_slug, subregion_names = _slug_to_subregion(region_key)
    if not by_slug:
        return {}, []

    properties = load_countries()
    lookup: Dict[str, str] = {}
    for slug, sub_key in by_slug.items():
        lookup[_norm(slug)] = sub_key
        name = (properties.get(slug) or {}).get("name")
        if name:
            lookup[_norm(name)] = sub_key
    for alias, slug in NAME_ALIASES.items():
        if slug in by_slug:
            lookup[alias] = by_slug[slug]
    for alias, sub_key in EXTRA_MEMBERS.items():
        if sub_key in subregion_names:
            lookup[alias] = sub_key

    grouped: Dict[str, List[str]] = {}
    unmatched: List[str] = []
    for country in countries:
        sub_key = lookup.get(_norm(country))
        if sub_key is None:
            unmatched.append(country)
            continue
        grouped.setdefault(subregion_names[sub_key], []).append(country)

    ordered = {name: sorted(members) for name, members in sorted(grouped.items())}
    return ordered, sorted(set(unmatched))
