"""Owners of text partitions, from the manifest's top-level ``owners:``.

prod and panel write disjoint sources: the panel owns every region or country slug listed
in prod's ``exclude`` file (what prod's timer skips), prod owns the rest. Each owner names
its roots (staging, state, pending, logs, cache, outputs, dashboards, merged_mac). A root
written ``mac:~/...`` lives on the Mac: it is read there, or on any other machine from
``PO_GRAPH_MAC_MIRROR`` (a copy of the Mac's $HOME), else it is not visible.
"""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path


def root(spec: dict, name: str) -> Path | None:
    """An owner's root on this machine, or None when it is not visible here."""
    value = spec.get(name)
    if not value:
        return None
    if not value.startswith("mac:"):
        return Path(os.path.expanduser(value))
    value = value[len("mac:"):]
    if sys.platform == "darwin":
        return Path(os.path.expanduser(value))
    mirror = os.environ.get("PO_GRAPH_MAC_MIRROR")
    if mirror and value.startswith("~/"):
        return Path(mirror) / value[2:]
    return None


@lru_cache(maxsize=None)
def _exclude(path: str) -> frozenset[str]:
    p = Path(os.path.expanduser(path))
    if not p.exists():
        return frozenset()
    return frozenset(line.split("#")[0].strip() for line in p.read_text().splitlines()
                     if line.split("#")[0].strip())


def panel_set(owners: dict) -> frozenset[str]:
    """Regions and country slugs the panel owns (prod's exclude list)."""
    path = (owners.get("prod") or {}).get("exclude")
    return _exclude(path) if path else frozenset()


def owner_of(owners: dict, region: str, country: str | None) -> str:
    s = panel_set(owners)
    return "panel" if region in s or (country and country in s) else "prod"


def country_of_key(key: str | None, tag: str | None = None) -> str | None:
    """Country of a ``<sub>/<country>/<source>`` key, else of a ``<country>__<source>`` tag."""
    if key and key.count("/") == 2:
        return key.split("/")[1]
    if tag and "__" in tag:
        return tag.split("__", 1)[0]
    return None
