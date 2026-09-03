"""Click command for the Common Crawl fleet. See `prices.cc_fleet`."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import click

from prices import cc_fleet


@click.command("cc-fleet")
@click.option(
    "--backend",
    type=click.Choice(["local", "ec2"]),
    default="local",
    show_default=True,
    help="Where the fetch runs. Both use the same fetcher; ec2 also uses a bucket.",
)
@click.option(
    "--instances",
    type=int,
    default=1,
    show_default=True,
    help="ec2 only: how many instances to spread the manifest shards across.",
)
@click.option(
    "--manifest",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="local only: the resolved manifest to fetch from.",
)
@click.option(
    "--check",
    is_flag=True,
    help="Report which parse tiers this checkout can ship, and stop.",
)
@click.option(
    "--allow-partial",
    is_flag=True,
    help=(
        "Proceed with parse tiers missing. The fetch costs the same and parses "
        "less, so the shortfall reads as a thin crawl rather than a missing file."
    ),
)
def cc_fleet_command(
    backend: str,
    instances: int,
    manifest: Optional[Path],
    check: bool,
    allow_partial: bool,
) -> None:
    """Fetch archived pages from Common Crawl, here or across an EC2 fleet.

    Stages and prints; fetches and launches nothing. Instances bill by the hour
    and are keyless by design, so a bad run is only visible hours later in a
    shipped log — which is why the parse-tier preflight runs first.
    """
    if check:
        cc_fleet.report_preflight(cc_fleet.preflight())
        return
    try:
        cc_fleet.run(
            backend=backend,
            instances=instances,
            manifest=manifest,
            allow_partial=allow_partial,
        )
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc
