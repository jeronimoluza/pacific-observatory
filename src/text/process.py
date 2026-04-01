"""Text build stage: EPU index calculation and analysis."""

from pathlib import Path

import click

from core.config import discover_pipeline_configs

CONFIGS_DIR = Path(__file__).resolve().parent / "configs"


def run_build(
    region=None, subregion=None, country=None, yes=False, cutoff=None, rebuild=False
):
    """Run EPU analysis for matching units (countries + aggregates)."""
    # Resolve country list from configs for the display summary
    countries = set()
    configs = discover_pipeline_configs(
        CONFIGS_DIR, region=region, subregion=subregion, country=country
    )
    for cfg in configs:
        parts = cfg.relative_to(CONFIGS_DIR).parts
        # Structure: {region}/{subregion}/{country}/{source}.yaml
        if len(parts) >= 4:
            countries.add(parts[2])
        elif len(parts) >= 3:
            countries.add(parts[1])
        elif len(parts) >= 2:
            countries.add(parts[0])

    if not countries:
        click.echo("No countries found matching filters.")
        return

    click.echo()
    click.echo("  Text build (EPU analysis)")
    click.echo("  " + "-" * 40)
    click.echo(f"  Countries: {', '.join(sorted(countries))}")
    if cutoff:
        click.echo(f"  Cutoff: {cutoff}")
    if rebuild:
        click.echo("  Mode: full rebuild (recalculate params)")
    click.echo()

    if not yes:
        click.confirm("  Proceed?", abort=True)

    try:
        from text.analysis.main import run_analysis

        run_analysis(
            region=region,
            subregion=subregion,
            countries=list(countries) if country else None,
            cutoff=cutoff,
            recalculate_params=rebuild,
            yes=yes,
        )
    except ImportError:
        click.echo("  Analysis module not yet migrated. Skipping.")
    except Exception as e:
        click.echo(f"  Error: {e}")
