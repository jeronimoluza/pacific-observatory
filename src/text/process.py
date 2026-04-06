"""Text build stage: EPU index calculation and analysis."""

from __future__ import annotations

import json
from pathlib import Path

import click
import pandas as pd

from core.config import discover_pipeline_configs
from text.analysis.baseline import (
    cache_matches_baseline,
    cached_baseline_window,
    format_baseline_window,
    has_modern_baseline_window,
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


def _prompt_baseline_window() -> tuple[str | None, str | None]:
    """Prompt the operator for a baseline window."""
    click.echo("  Enter baseline window for standardization.")
    cutoff_start_date = click.prompt(
        "  Cutoff start date (YYYY-MM-DD, blank for open start)",
        default="",
        show_default=False,
    )
    cutoff_end_date = click.prompt(
        "  Cutoff end date (YYYY-MM-DD, blank for today)",
        default="",
        show_default=False,
    )
    return _validate_baseline_window(cutoff_start_date, cutoff_end_date)


def _requested_unit_names(units: list[dict]) -> tuple[list[str], list[str]]:
    """Split preview units into country and aggregate labels."""
    countries = [u["name"] for u in units if u.get("level") == "country"]
    aggregates = [u["name"] for u in units if u.get("level") != "country"]
    return countries, aggregates


def _inspect_cached_windows(units: list[dict]) -> set[tuple[str | None, str | None]]:
    """Return the unique modern cached baseline windows among the selected units."""
    windows = set()
    for unit in units:
        params_path = unit["cache_dir"] / "params.json"
        cache_path = unit["cache_dir"] / "epu_stats_cache.csv"
        if not (params_path.exists() and cache_path.exists()):
            continue
        try:
            params = json.loads(params_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if has_modern_baseline_window(params):
            windows.add(cached_baseline_window(params))
    return windows


def _classify_units(
    units: list[dict],
    cutoff_start_date: str | None,
    cutoff_end_date: str | None,
) -> tuple[list[str], list[str]]:
    """Return unit names whose caches match or require full rebuild."""
    matching = []
    rebuild = []
    for unit in units:
        params_path = unit["cache_dir"] / "params.json"
        cache_path = unit["cache_dir"] / "epu_stats_cache.csv"
        if not (params_path.exists() and cache_path.exists()):
            rebuild.append(unit["name"])
            continue
        try:
            params = json.loads(params_path.read_text(encoding="utf-8"))
        except Exception:
            rebuild.append(unit["name"])
            continue
        current_sources = {
            source_key_for_news_path(fp) for fp in unit.get("news_dirs", [])
        }
        if cache_matches_baseline(
            params,
            current_sources,
            cutoff_start_date,
            cutoff_end_date,
        ):
            matching.append(unit["name"])
        else:
            rebuild.append(unit["name"])
    return matching, rebuild


def _resolve_baseline_window(
    units: list[dict],
    yes: bool,
    cutoff_start_date: str | None,
    cutoff_end_date: str | None,
) -> tuple[str | None, str | None]:
    """Resolve the requested invocation-wide baseline window."""
    if cutoff_start_date is not None or cutoff_end_date is not None:
        return _validate_baseline_window(cutoff_start_date, cutoff_end_date)

    if yes:
        raise click.ClickException(
            "Non-interactive builds require --cutoff-start-date and/or --cutoff-end-date."
        )

    cached_windows = _inspect_cached_windows(units)
    if len(cached_windows) == 1:
        cached_start, cached_end = next(iter(cached_windows))
        click.echo(
            "  Cached baseline window: "
            + format_baseline_window(cached_start, cached_end)
        )
        if click.confirm("  Reuse this baseline?", default=True):
            return cached_start, cached_end
    elif len(cached_windows) > 1:
        click.echo("  Multiple cached baseline windows detected. Enter a new one.")
        for start, end in sorted(cached_windows):
            click.echo("   - " + format_baseline_window(start, end))

    return _prompt_baseline_window()


def run_build(
    region=None,
    subregion=None,
    country=None,
    yes=False,
    cutoff_start_date=None,
    cutoff_end_date=None,
    rebuild=False,
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
    cutoff_start_date, cutoff_end_date = _resolve_baseline_window(
        preview_units,
        yes=yes,
        cutoff_start_date=cutoff_start_date,
        cutoff_end_date=cutoff_end_date,
    )

    matching_units: list[str] = []
    rebuild_units: list[str] = []
    if preview_units and not rebuild:
        matching_units, rebuild_units = _classify_units(
            preview_units,
            cutoff_start_date,
            cutoff_end_date,
        )
        if matching_units and rebuild_units and not yes:
            click.echo()
            click.echo("  Units requiring full rebuild:")
            for unit_name in rebuild_units:
                click.echo(f"   - {unit_name}")
            click.confirm(
                "  Continue with incremental builds for matching units and full rebuilds for the units above?",
                default=True,
                abort=True,
            )

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

    if not yes:
        click.confirm("  Proceed?", abort=True)

    try:
        run_analysis(
            region=region,
            subregion=subregion,
            countries=list(countries) if country else None,
            cutoff_start_date=cutoff_start_date,
            cutoff_end_date=cutoff_end_date,
            recalculate_params=rebuild,
            yes=yes,
        )
    except ImportError:
        click.echo("  Analysis module not yet migrated. Skipping.")
    except Exception as e:
        click.echo(f"  Error: {e}")
