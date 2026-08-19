"""Click command for the prices Wayback backfill (library lives in backfill.py)."""

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path

import click

from prices.backfill import load_url_universe, run_source_backfill
from prices.config import PriceSourceConfig, discover_prices_configs

_PRICES_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _PRICES_DIR.parent.parent


def _load_manifests(
    region: str | None,
    subregion: str | None,
    country: str | None,
    source: str | None,
) -> list[PriceSourceConfig]:
    paths = discover_prices_configs(region=region, subregion=subregion, country=country)
    if source is not None:
        paths = [p for p in paths if p.stem == source]
    return [PriceSourceConfig.load(p) for p in paths]


def _source_dir_for(manifest: PriceSourceConfig) -> Path:
    return (
        _PROJECT_ROOT
        / "data"
        / "prices"
        / manifest.region
        / manifest.subregion
        / manifest.country
        / manifest.source
    )


def _parse_iso_date(value: str | None) -> date | None:
    if value is None:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


@click.command()
@click.option("--region", "-r", default=None, help="Region slug (e.g. eap)")
@click.option("--subregion", "-S", default=None, help="Subregion slug")
@click.option("--country", "-c", default=None, help="Country slug")
@click.option("--source", "-s", default=None, help="Run a single source slug")
@click.option(
    "--from",
    "from_date",
    default=None,
    help="CDX cutoff (YYYY-MM-DD), the earliest snapshot to include. Default: 2010-01-01.",
)
@click.option(
    "--collapse",
    type=click.Choice(["day", "week", "month", "year"]),
    default="week",
    show_default=True,
    help="Snapshot collapse granularity (one snapshot kept per bucket).",
)
@click.option(
    "--discovery",
    type=click.Choice(["bulk", "per-url"]),
    default="bulk",
    show_default=True,
    help="bulk = one paged CDX query per host; per-url = one CDX call per URL.",
)
@click.option(
    "--universe",
    "universe_mode",
    type=click.Choice(["scraped", "archive"]),
    default="scraped",
    show_default=True,
    help=(
        "scraped = only URLs we collected live; archive = every product URL "
        "Wayback holds under the manifest's archive_prefix, including products "
        "delisted before we started scraping. Requires --discovery bulk and an "
        "archive_prefix on the manifest."
    ),
)
@click.option(
    "--max-snapshots-per-url",
    type=int,
    default=None,
    help="Cap snapshots fetched per URL (testing/cost control).",
)
@click.option(
    "--max-urls", type=int, default=None, help="Cap URLs processed per source."
)
@click.option(
    "--workers",
    type=int,
    default=8,
    show_default=True,
    help=(
        "Concurrent URLs per source. Measured against IA 2026-08-18: 8 sustains "
        "~0.91 fetch/s with no connection refusals; 16 collapses to 4% success "
        "and 32 to zero (per-IP TCP blackhole, ~100s to recover). Do not raise."
    ),
)
@click.option(
    "--requests-per-second",
    type=float,
    default=1.5,
    show_default=True,
    help="Global fetch rate cap across workers; 0 disables pacing.",
)
@click.option("--dry-run", is_flag=True, help="List sources + URL counts; don't fetch.")
def backfill_command(
    region,
    subregion,
    country,
    source,
    from_date,
    collapse,
    universe_mode,
    discovery,
    max_snapshots_per_url,
    max_urls,
    workers,
    requests_per_second,
    dry_run,
):
    """Recover historical prices from the Wayback Machine."""
    manifests = _load_manifests(region, subregion, country, source)
    if not manifests:
        raise click.ClickException(
            "No matching sources. Check --region/--subregion/--country/--source."
        )

    active = [m for m in manifests if m.active]
    if not active:
        raise click.ClickException("No active sources to back-fill.")

    collapse_digits = {"day": 8, "week": 8, "month": 6, "year": 4}[collapse]
    cutoff = _parse_iso_date(from_date)

    plan = []
    for m in active:
        sd = _source_dir_for(m)
        n_urls = len(load_url_universe(sd))
        plan.append((m, sd, n_urls))

    archive = universe_mode == "archive"
    for m, sd, n in plan:
        scope = f", archive_prefix={m.archive_prefix or 'MISSING'}" if archive else ""
        click.echo(
            f"  {m.region}/{m.subregion}/{m.country}/{m.source}  "
            f"(spider={m.spider}, urls={n}{scope})"
        )
    click.echo(f"\n{len(plan)} sources, {sum(n for _, _, n in plan)} unique URLs")

    if archive:
        no_prefix = [m.source for m, _, _ in plan if not m.archive_prefix]
        if no_prefix:
            click.echo(
                f"\n{len(no_prefix)} source(s) have no archive_prefix: and will be "
                f"skipped — {', '.join(sorted(no_prefix)[:10])}"
            )

    if dry_run:
        return

    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    for m, sd, n in plan:
        if archive and not m.archive_prefix:
            click.echo(f"Skipping {m.source}: no archive_prefix: on the manifest")
            continue
        if n == 0 and not archive:
            click.echo(f"Skipping {m.source}: no raw_items found at {sd}/raw_items/")
            continue
        click.echo(f"\n=== {m.source} ({n} URLs) ===")
        run_source_backfill(
            source_dir=sd,
            spider=m.spider,
            cutoff_override=cutoff,
            collapse_digits=collapse_digits,
            max_snapshots_per_url=max_snapshots_per_url,
            max_urls=max_urls,
            workers=workers,
            discovery=discovery,
            granularity=collapse,
            requests_per_second=requests_per_second,
            universe_mode=universe_mode,
            archive_prefix=m.archive_prefix,
            archive_path_re=m.archive_path_re,
            currency_override=m.currency,
        )
