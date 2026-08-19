"""Click command for the prices Common Crawl fetcher.

Split out of ``cc_warc_fetcher.py`` to keep both files under the 500-line cap,
mirroring the ``backfill.py`` / ``backfill_cli.py`` pair.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Tuple

import click

from prices.cc_config import (
    DEFAULT_CC_SINCE_YEAR,
    all_cc_configs,
    interleave_indexes,
    resolve_cc_indexes,
)
from prices.cc_warc_fetcher import CommonCrawlScraper, get_prices_data_root


@click.command("common-crawl")
@click.option(
    "--spider",
    "-s",
    "spider_name",
    default=None,
    help="Spider name (e.g. mh_online). Required unless --dry-run.",
)
@click.option(
    "--country",
    "-c",
    default=None,
    help="Country slug to attribute the records to (resolves region + subregion via regions.yaml).",
)
@click.option(
    "--index",
    "indexes",
    multiple=True,
    help=(
        "CC index name like 'CC-MAIN-2024-51'. Repeatable. "
        "Defaults to every monthly crawl since --since when omitted."
    ),
)
@click.option(
    "--since",
    "since_year",
    type=int,
    default=DEFAULT_CC_SINCE_YEAR,
    show_default=True,
    help="Earliest crawl year to query when --index is not given.",
)
@click.option(
    "--workers",
    "-w",
    type=int,
    default=8,
    show_default=True,
    help="WARC fetch concurrency.",
)
@click.option(
    "--max-per-index",
    type=int,
    default=None,
    help=(
        "Cap new records fetched per crawl. Without it a truncated run spends "
        "its whole budget on the first few crawls; with it the same budget "
        "spreads across the period, which is what yields repeat observations "
        "of the same product rather than a one-off census."
    ),
)
@click.option(
    "--interleave",
    is_flag=True,
    help=(
        "Bisect the crawl order (ends, then midpoints) so an interrupted run "
        "still spans the full period instead of only the newest crawls."
    ),
)
@click.option(
    "--manifest",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help=(
        "Fetch from a pre-resolved manifest instead of querying the crawl "
        "indexes. Skips cluster.idx entirely, so this runs on a machine "
        "without the 13 GB index cache."
    ),
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="List configured spiders with prefix + path_re, then exit.",
)
def common_crawl_command(
    spider_name: Optional[str],
    country: Optional[str],
    indexes: Tuple[str, ...],
    since_year: int,
    workers: int,
    max_per_index: Optional[int],
    interleave: bool,
    manifest: Optional[Path],
    dry_run: bool,
) -> None:
    """Fetch historical product data from Common Crawl WARC archives."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s"
    )

    if dry_run:
        configs = all_cc_configs()
        if spider_name and spider_name not in configs:
            raise click.BadParameter(
                f"unknown spider '{spider_name}'. Available: {sorted(configs)}"
            )
        target = {spider_name: configs[spider_name]} if spider_name else configs
        click.echo(f"{'SPIDER':<22} {'PREFIX':<48} PATH_RE")
        click.echo("-" * 100)
        for name, cfg in sorted(target.items()):
            click.echo(f"{name:<22} {cfg['prefix']:<48} {cfg['path_re']}")
        return

    if not spider_name:
        raise click.UsageError("--spider is required (or use --dry-run)")
    if not country:
        raise click.UsageError(
            "--country is required to place output under data/prices/<region>/<sub>/<country>/"
        )
    if not indexes and not manifest:
        indexes = tuple(resolve_cc_indexes(since_year))
        click.echo(
            f"No --index given; querying {len(indexes)} crawls since {since_year} "
            f"({indexes[0]} … {indexes[-1]})"
        )

    if interleave:
        indexes = tuple(interleave_indexes(list(indexes)))

    from core.config import get_country_path  # local import to keep startup cheap

    try:
        region, subregion, _ = get_country_path(country)
    except ValueError as exc:
        raise click.BadParameter(str(exc))

    output_dir = get_prices_data_root()
    scraper = CommonCrawlScraper(
        spider_name=spider_name,
        output_dir=output_dir,
        indexes=list(indexes),
    )
    if manifest:
        from prices.cc_fetch import run_from_manifest

        stats = run_from_manifest(
            scraper, (region, subregion, country), manifest, num_workers=workers
        )
    else:
        stats = scraper.run_scrape_cc(
            (region, subregion, country),
            num_workers=workers,
            max_per_index=max_per_index,
        )

    click.echo()
    click.echo(f"Run stats for {spider_name} ({region}/{subregion}/{country}):")
    for k, v in stats.items():
        click.echo(f"  {k:<16} {v}")


if __name__ == "__main__":
    common_crawl_command()
