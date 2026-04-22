"""Canonical and legacy raw-data paths for the migrated fuel pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping


def canonical_source_dir(
    region: str,
    subregion: str,
    country_slug: str,
    source: str,
    *,
    base_dir: Path,
) -> Path:
    """Return the canonical directory for one fuel source."""
    return base_dir / region / subregion / country_slug / source


def canonical_observations_path(
    region: str,
    subregion: str,
    country_slug: str,
    source: str,
    *,
    base_dir: Path,
) -> Path:
    """Return the canonical observations.csv path for one fuel source."""
    return (
        canonical_source_dir(
            region,
            subregion,
            country_slug,
            source,
            base_dir=base_dir,
        )
        / "observations.csv"
    )


def canonical_observations_path_for_entry(
    entry: Mapping[str, object], *, base_dir: Path
) -> Path:
    """Return the canonical observations path for a registry or config entry."""
    return canonical_observations_path(
        str(entry["region"]),
        str(entry["subregion"]),
        str(entry["country_slug"]),
        str(entry["source"]),
        base_dir=base_dir,
    )


def legacy_observations_path(
    country_slug: str, source_key: str, *, base_dir: Path
) -> Path:
    """Return the legacy flat observations.csv path for one fuel source."""
    return base_dir / country_slug / source_key / "observations.csv"
