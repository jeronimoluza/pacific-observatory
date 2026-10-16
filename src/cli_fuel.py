"""Click commands for fuel refresh-fx and publish.

Kept out of `cli.py` so it stays under the 500-line cap. `register(fuel_group,
opts)` attaches the commands, reusing the shared option decorators.
"""

from pathlib import Path

import click


def register(fuel_group, opts: dict):
    region_opt = opts["region"]
    subregion_opt = opts["subregion"]

    @fuel_group.command("refresh-fx")
    @region_opt
    def fuel_refresh_fx(region):
        """Bring the shared FX cache current to today (UTC).

        Run once per weekly run, after the parallel collects and before the
        builds: one writer instead of five racing on fx_cache_v2.csv.
        """
        import logging

        from fuel.config import build_fuel_registry
        from fuel.fx import refresh_fx_cache

        logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
        registry = build_fuel_registry(region=region)
        currencies = {e["currency"] for e in registry.values() if e.get("currency")}
        n_new = refresh_fx_cache(sorted(currencies))
        click.echo(f"FX cache: {n_new} new rows for {len(currencies)} currencies")

    @fuel_group.command("publish")
    @region_opt
    @subregion_opt
    @click.option(
        "--allow-country-drop",
        is_flag=True,
        help="Publish even if fewer countries were built than at the last publish",
    )
    @click.option(
        "--known-failures",
        type=click.Path(path_type=Path),
        default=None,
        help="Known source failures catalog (default: refresh-fuel-dashboards skill)",
    )
    def fuel_publish(region, subregion, allow_country_drop, known_failures):
        """Generate fuel policy dashboards and per-region Excels, behind gates."""
        import logging

        from fuel import gates
        from fuel.publish import run_publish

        logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
        try:
            run_publish(
                region=region,
                subregion=subregion,
                allow_country_drop=allow_country_drop,
                known_failures=known_failures or gates.KNOWN_FAILURES,
            )
        except ValueError as exc:
            raise click.ClickException(str(exc))
