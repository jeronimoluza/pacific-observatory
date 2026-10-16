"""`po text gnews-gap`: weekly Google News coverage-gap report (outside collect).

Reads configs and the ledgers (TEXT_STATE_DIR) read-only, queries Google News RSS
once per source and edition, and writes a fresh
outputs/text/reports/gnews_gap/<week_start>_<run UTC>/ with gap.csv and summary.txt.
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone

import click

from core.config import make_slug_validator


def _week_start(value: str | None) -> date:
    """Monday of the week holding `value`; default: the last complete ISO week (UTC)."""
    if value:
        d = date.fromisoformat(value)
        return d - timedelta(days=d.weekday())
    today = datetime.now(timezone.utc).date()
    return today - timedelta(days=today.weekday() + 7)


@click.command("gnews-gap")
@click.option(
    "--region",
    "-r",
    default=None,
    callback=make_slug_validator("region"),
    help="Filter by region slug",
)
@click.option(
    "--country", "-c", "countries", multiple=True, help="Country slug (repeatable)"
)
@click.option(
    "--source", "-s", "sources", multiple=True, help="Source key (repeatable)"
)
@click.option(
    "--week",
    default=None,
    help="Any date in the week (YYYY-MM-DD); default last complete week",
)
@click.option(
    "--gap-ratio",
    type=float,
    default=0.5,
    show_default=True,
    help="gap if ours/google is below this",
)
@click.option(
    "--min-google",
    type=int,
    default=10,
    show_default=True,
    help="...and google has at least this many",
)
@click.option(
    "--sample",
    type=int,
    default=0,
    help="Decode N Google links for each of the 5 largest gaps",
)
def gnews_gap(region, countries, sources, week, gap_ratio, min_google, sample):
    """Compare Google News' weekly item count per source with what the ledger collected."""
    from text.gnews_gap.report import run
    from text.gnews_gap.sources import load_sources

    srcs = load_sources(region, set(countries), set(sources))
    if not srcs:
        raise click.ClickException("no enabled sources match")
    start = _week_start(week)
    click.echo(f"  {len(srcs)} sources, week {start}..{start + timedelta(days=6)}")
    out_dir, code = run(srcs, start, gap_ratio, min_google, sample)
    click.echo(f"\n  Wrote {out_dir}")
    sys.exit(code)
