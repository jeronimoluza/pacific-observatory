"""Prices collect stage: run Scrapy spiders + Python fetchers in one pass."""

from __future__ import annotations

import importlib
import logging
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import click

from prices.config import PriceSourceConfig, discover_prices_configs
from prices.writers import (
    append_observations,
    columns_for,
    cutoff_from_csv,
    output_path_for,
)

_PRICES_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _PRICES_DIR.parent.parent
_PRICES_CONFIGS_DIR = _PRICES_DIR / "configs"
_DATA_ROOT = _PROJECT_ROOT / "data"
_FETCHERS_PACKAGE = "prices.fetchers"

logger = logging.getLogger(__name__)


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


def _setup_run_logging(run_ts: str) -> tuple[Path, logging.Handler]:
    runs_dir = _PROJECT_ROOT / "logs" / "prices" / "_runs" / run_ts
    runs_dir.mkdir(parents=True, exist_ok=True)
    master_log = runs_dir / "master.log"

    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for h in list(root.handlers):
        root.removeHandler(h)

    stream = logging.StreamHandler()
    stream.setFormatter(fmt)
    root.addHandler(stream)

    master = logging.FileHandler(master_log, encoding="utf-8")
    master.setFormatter(fmt)
    root.addHandler(master)

    return runs_dir, master


def _print_plan(manifests: list[PriceSourceConfig]) -> None:
    for m in manifests:
        marker = " " if m.active else "*"
        if m.scaffolding == "fetcher":
            handler = f"fetcher={m.module}:{m.function}"
        else:
            handler = f"spider={m.spider}"
        click.echo(
            f"{marker} {m.region}/{m.subregion}/{m.country}/{m.source}  "
            f"({handler}, lang={m.language or '-'})"
        )
    inactive = sum(1 for m in manifests if not m.active)
    click.echo(f"\n{len(manifests)} sources ({inactive} inactive marked *)")


def _run_fetcher(m: PriceSourceConfig) -> None:
    out_path = output_path_for(
        data_root=_DATA_ROOT,
        region=m.region,
        subregion=m.subregion,
        country=m.country,
        source=m.source,
        analytical_role=m.analytical_role,
    )
    columns = columns_for(m.analytical_role)
    fallback = m.fallback_date or date(1970, 1, 1)
    cutoff = cutoff_from_csv(out_path, fallback)

    logger.info(
        "Running fetcher: %s (%s/%s/%s, cutoff=%s)",
        m.source,
        m.region,
        m.subregion,
        m.country,
        cutoff,
    )

    module = importlib.import_module(f"{_FETCHERS_PACKAGE}.{m.module}")
    fn = getattr(module, m.function)
    df = fn(cutoff)
    if df is None or df.empty:
        logger.info("Fetcher %s returned no new rows", m.source)
        return
    append_observations(df, out_path, columns=columns)


@click.command()
@click.option("--region", "-r", default=None, help="Region slug (e.g. eap)")
@click.option("--subregion", "-S", default=None, help="Subregion slug")
@click.option("--country", "-c", default=None, help="Country slug")
@click.option("--source", "-s", default=None, help="Run a single source slug")
@click.option(
    "--max-items",
    type=int,
    default=None,
    help="Per-source item cap (passed as Scrapy CLOSESPIDER_ITEMCOUNT, applies independently to every spider).",
)
@click.option(
    "--closespider-timeout",
    type=int,
    default=None,
    help="Per-spider scrape budget in seconds (Scrapy CLOSESPIDER_TIMEOUT); the spider closes itself gracefully at this mark.",
)
@click.option("--dry-run", is_flag=True, help="List sources without running")
@click.option(
    "--list",
    "list_sources",
    is_flag=True,
    help="List sources without running (alias for --dry-run).",
)
@click.option(
    "--skip-fetchers",
    is_flag=True,
    help="Skip the synchronous fetcher phase and go straight to Scrapy spiders.",
)
@click.option(
    "-P",
    "--parallel",
    type=int,
    default=1,
    show_default=True,
    help=(
        "Run this many sources at once, one detached child process each, so a "
        "hung source cannot stall the rest. 1 keeps every source in a single "
        "Scrapy reactor."
    ),
)
@click.option(
    "--timeout",
    type=int,
    default=5400,
    show_default=True,
    help="Per-source wall-clock cap in seconds. Only applies with -P > 1.",
)
@click.option(
    "--resume",
    is_flag=False,
    flag_value="ALL",
    default=None,
    help=(
        "With -P > 1, skip sources already recorded ok/ok_norows. Pass a run "
        "directory (logs/prices/_fullrun_<TS>) to continue that run only; bare "
        "--resume reads EVERY prior ledger, including stale ones, and will skip "
        "sources that are overdue for a refresh."
    ),
)
def collect(
    region,
    subregion,
    country,
    source,
    max_items,
    closespider_timeout,
    dry_run,
    list_sources,
    skip_fetchers,
    parallel,
    timeout,
    resume,
):
    """Run Scrapy spiders and/or Python fetchers to collect price data."""

    manifests = _load_manifests(region, subregion, country, source)
    if not manifests:
        raise click.ClickException(
            "No matching sources. Check --region/--subregion/--country/--source filters."
        )

    if dry_run or list_sources:
        _print_plan(manifests)
        return

    active = [m for m in manifests if m.active]
    skipped = [m for m in manifests if not m.active]
    for m in skipped:
        click.echo(
            f"Skipping inactive source: {m.region}/{m.subregion}/{m.country}/{m.source}"
        )

    if not active:
        raise click.ClickException("No active sources to run.")

    if parallel < 1:
        raise click.BadParameter("-P/--parallel must be >= 1")

    run_ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    runs_dir, _ = _setup_run_logging(run_ts)

    if parallel > 1:
        from prices.collect_parallel import (
            DiskSpaceError,
            ResumeTargetError,
            run_parallel,
            summarize,
        )

        try:
            run_dir = run_parallel(
                active,
                workers=parallel,
                timeout=timeout,
                project_root=_PROJECT_ROOT,
                data_root=_DATA_ROOT,
                resume=resume,
                max_items=max_items,
            )
        except (DiskSpaceError, ResumeTargetError) as exc:
            raise click.ClickException(str(exc)) from exc
        result = summarize(run_dir)
        logger.info(
            "Prices collect -P %d done: %s, %d new rows; ledger: %s",
            parallel,
            result["counts"],
            result["new_rows"],
            run_dir / "status.jsonl",
        )
        return

    fetchers = [m for m in active if m.scaffolding == "fetcher"]
    spiders = [m for m in active if m.scaffolding == "spider"]

    logger.info(
        "Prices collect — %d fetcher(s) + %d spider(s); run log dir: %s",
        len(fetchers),
        len(spiders),
        runs_dir,
    )

    # Run fetchers first — they're synchronous and finish before we hand
    # control to Scrapy's blocking reactor.
    if skip_fetchers:
        logger.info("Skipping %d fetcher(s) (--skip-fetchers).", len(fetchers))
    else:
        for m in fetchers:
            try:
                _run_fetcher(m)
            except Exception:
                logger.exception("Fetcher %s failed", m.source)

    if not spiders:
        logger.info("No spiders queued; done.")
        return

    # Scrapy's project discovery walks UP from CWD looking for scrapy.cfg.
    # We chdir into src/prices/ so it finds ours. Spiders import from
    # `price_scraping.utils`; that package lives at src/prices/price_scraping/
    # so we must also have src/prices on sys.path.
    os.chdir(_PRICES_DIR)
    if str(_PRICES_DIR) not in sys.path:
        sys.path.insert(0, str(_PRICES_DIR))

    from scrapy.crawler import CrawlerProcess
    from scrapy.utils.project import get_project_settings

    settings = get_project_settings()
    if max_items is not None:
        settings.set("CLOSESPIDER_ITEMCOUNT", int(max_items))
    if closespider_timeout is not None:
        settings.set("CLOSESPIDER_TIMEOUT", int(closespider_timeout))

    process = CrawlerProcess(settings, install_root_handler=False)
    loader = process.spider_loader

    for m in spiders:
        try:
            spider_cls = loader.load(m.spider)
        except KeyError as exc:
            raise click.ClickException(
                f"Spider '{m.spider}' from {m.config_path} not found in "
                f"price_scraping.spiders: {exc}"
            ) from exc

        crawl_kwargs: dict = {
            "prices_region": m.region,
            "prices_subregion": m.subregion,
            "prices_country": m.country,
            "prices_source": m.source,
            "prices_data_root": str(_DATA_ROOT),
        }
        if m.start_urls:
            crawl_kwargs["start_urls"] = list(m.start_urls)
        if m.spider_kwargs:
            crawl_kwargs.update(m.spider_kwargs)

        logger.info(
            "Scheduling spider: %s (%s/%s/%s)",
            m.spider,
            m.region,
            m.subregion,
            m.country,
        )
        process.crawl(spider_cls, **crawl_kwargs)

    try:
        process.start()
        logger.info("All spiders completed.")
    except Exception:
        logger.exception("Crawler process failed.")
        raise click.ClickException("Crawler process failed; see logs.")
