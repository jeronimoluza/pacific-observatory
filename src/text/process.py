"""Text build stage: EPU index calculation and analysis."""

from __future__ import annotations

from pathlib import Path

import click
import pandas as pd

from core.config import discover_pipeline_configs
from text.analysis.baseline import (
    format_baseline_window,
    normalize_bound,
    source_key_for_news_path,
)

CONFIGS_DIR = Path(__file__).resolve().parent / "configs"


def _validate_baseline_window(
    cutoff_start_date: str | None,
    cutoff_end_date: str | None,
) -> tuple[str | None, str | None]:
    """Normalize and validate the requested baseline window."""
    cutoff_start_date = normalize_bound(cutoff_start_date)
    cutoff_end_date = normalize_bound(cutoff_end_date)

    if cutoff_start_date is None and cutoff_end_date is None:
        raise click.ClickException("You need to define a baseline period.")

    try:
        start_ts = pd.Timestamp(cutoff_start_date) if cutoff_start_date else None
        end_ts = pd.Timestamp(cutoff_end_date) if cutoff_end_date else None
    except Exception as exc:
        raise click.ClickException(f"Invalid baseline date: {exc}") from exc

    if start_ts is not None and end_ts is not None and start_ts > end_ts:
        raise click.ClickException(
            "cutoff start date must be earlier than or equal to cutoff end date."
        )

    return cutoff_start_date, cutoff_end_date


def _requested_unit_names(units: list[dict]) -> tuple[list[str], list[str]]:
    """Split preview units into country and aggregate labels."""
    countries = [u["name"] for u in units if u.get("level") == "country"]
    aggregates = [u["name"] for u in units if u.get("level") != "country"]
    return countries, aggregates


def _classify_units(
    units: list[dict],
    cutoff_start_date: str | None,
    cutoff_end_date: str | None,
) -> tuple[list[str], list[str]]:
    """Return unit names whose source_counts cache is current vs stale.

    Aggregate units (level != "country") never have their own cache; their
    "freshness" is implicitly the staleness of their constituent countries,
    so we lump them in with `matching` (the per-country gate handles
    auto-build during processing).
    """
    from src.text.analysis import source_counts as sc
    from src.text.analysis.orchestrator import KEYWORDS_ROOT
    from src.text.analysis.utils import LANGUAGE_ALIASES

    matching: list[str] = []
    rebuild: list[str] = []
    for unit in units:
        if unit.get("level") != "country":
            matching.append(unit["name"])
            continue
        cache_dir = unit["cache_dir"]
        _, cached_params = sc.read_source_counts(cache_dir)
        source_keys = sorted(
            source_key_for_news_path(fp) for fp in unit.get("news_dirs", [])
        )
        languages = {
            LANGUAGE_ALIASES.get(lang, lang)
            for lang in (unit.get("source_languages") or {}).values()
        }
        keyword_hashes = sc.keyword_hash_bundle(KEYWORDS_ROOT, languages)
        stale, _ = sc.is_stale(cached_params, source_keys, keyword_hashes)
        (rebuild if stale else matching).append(unit["name"])
    return matching, rebuild


def run_build(
    region=None,
    subregion=None,
    country=None,
    cutoff_start_date=None,
    cutoff_end_date=None,
    rebuild=False,
    max_parallel_sources: int = 1,
):
    """Run EPU analysis for matching units (countries + aggregates)."""
    countries = set()
    configs = discover_pipeline_configs(
        CONFIGS_DIR, region=region, subregion=subregion, country=country
    )
    for cfg in configs:
        parts = cfg.relative_to(CONFIGS_DIR).parts
        if len(parts) >= 4:
            countries.add(parts[2])
        elif len(parts) >= 3:
            countries.add(parts[1])
        elif len(parts) >= 2:
            countries.add(parts[0])

    if not countries:
        click.echo("No countries found matching filters.")
        return

    from text.analysis.main import preview_build_units, run_analysis

    preview_units = preview_build_units(
        region=region,
        subregion=subregion,
        countries=list(countries) if country else None,
    )
    cutoff_start_date, cutoff_end_date = _validate_baseline_window(
        cutoff_start_date, cutoff_end_date
    )

    matching_units: list[str] = []
    rebuild_units: list[str] = []
    if preview_units and not rebuild:
        matching_units, rebuild_units = _classify_units(
            preview_units,
            cutoff_start_date,
            cutoff_end_date,
        )
        if matching_units and rebuild_units:
            click.echo()
            click.echo("  Units requiring full rebuild:")
            for unit_name in rebuild_units:
                click.echo(f"   - {unit_name}")

    _preview_countries, preview_aggregates = _requested_unit_names(preview_units)

    click.echo()
    click.echo("  Text build (EPU analysis)")
    click.echo("  " + "-" * 40)
    click.echo(f"  Countries: {', '.join(sorted(countries))}")
    if preview_aggregates:
        click.echo(f"  Aggregates: {', '.join(preview_aggregates)}")
    click.echo(
        "  Baseline: " + format_baseline_window(cutoff_start_date, cutoff_end_date)
    )
    if rebuild:
        click.echo("  Mode: full rebuild (all selected units)")
    elif preview_units:
        click.echo(f"  Incremental units: {len(matching_units)}")
        click.echo(f"  Full rebuild units: {len(rebuild_units)}")
    click.echo()

    try:
        run_analysis(
            region=region,
            subregion=subregion,
            countries=list(countries) if country else None,
            cutoff_start_date=cutoff_start_date,
            cutoff_end_date=cutoff_end_date,
            recalculate_params=rebuild,
            max_parallel_sources=max_parallel_sources,
        )
    except ImportError:
        click.echo("  Analysis module not yet migrated. Skipping.")
    except Exception as e:
        click.echo(f"  Error: {e}")
