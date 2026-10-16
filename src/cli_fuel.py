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
    @click.option("--force-parallel", is_flag=True, help="Refetch RTFX even if fresh")
    def fuel_refresh_fx(region, force_parallel):
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

        # Parallel-market rates are mostly monthly; refetch at most weekly.
        import time

        from fuel.fx_parallel import PARALLEL_CACHE, refresh_parallel_cache

        age = (
            time.time() - PARALLEL_CACHE.stat().st_mtime
            if PARALLEL_CACHE.exists()
            else None
        )
        if age is not None and age < 6 * 86400 and not force_parallel:
            click.echo("Parallel FX cache is < 6 days old; skipped")
            return
        n_par = refresh_parallel_cache()
        click.echo(f"Parallel FX cache: {n_par} monthly rows")

    @fuel_group.command("gate-baseline")
    @region_opt
    @click.option("--seed", is_flag=True, help="Write the baseline (default: show it)")
    @click.option("--outputs-dir", type=click.Path(path_type=Path), default=None)
    @click.option("--status-dir", type=click.Path(path_type=Path), default=None)
    def fuel_gate_baseline(region, seed, outputs_dir, status_dir):
        """Show or seed the publish gate's country baseline from current build outputs."""
        from fuel import gates
        from fuel.publish import _OUTPUTS_DIR, discover_publish_countries

        outputs_dir = outputs_dir or _OUTPUTS_DIR
        status_dir = status_dir or gates.STATUS_DIR
        regions = [region] if region else ["eca", "menaap", "sar", "ssa", "lac"]
        for reg in regions:
            countries = discover_publish_countries(outputs_dir, region=reg)
            if seed:
                with_data, path = gates.seed_baseline(reg, countries, status_dir)
                click.echo(f"{reg}: {len(with_data)} countries seeded -> {path}")
            else:
                with_data = gates.countries_with_data(reg, countries)
                click.echo(f"{reg}: {len(with_data)} countries with data (dry run)")
            skipped = sorted({c["country_slug"] for c in countries} - set(with_data))
            if skipped:
                click.echo(f"  not counted: {', '.join(skipped)}")

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
