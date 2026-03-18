"""CLI for the fuel_prices package — 4 commands: fetch, build, publish, migrate."""

from __future__ import annotations

import argparse
from datetime import date

from .collect.pipeline import run_collection
from .constants import DATA_DIR, FETCH_STATE_JSON, STAGED_DATA_DIR

_CADENCE_CHOICES = ["daily", "weekly", "monthly", "quarterly", "irregular", "manual"]


def _cmd_fetch(args) -> None:
    """Fetch new data from one or all configured fuel sources."""
    if getattr(args, "status", False):
        _print_status(
            prune_orphans=getattr(args, "prune_orphans", False),
            force=getattr(args, "force", False),
        )
        return

    run_collection(
        source_key=getattr(args, "source", None),
        observations_base_dir=DATA_DIR,
        fetch_state_path=FETCH_STATE_JSON,
        cadence_filter=getattr(args, "cadence", None),
        force=getattr(args, "force", False),
        rebuild=getattr(args, "rebuild", False),
    )


def _print_status(prune_orphans: bool = False, force: bool = False) -> None:
    """Print a source health table and optionally prune orphaned state entries."""
    from .fetchers import FETCHER_REGISTRY
    from .loader import read_fetch_state, write_fetch_state

    state = read_fetch_state(FETCH_STATE_JSON)
    today = date.today()

    def _days_stale(last_data_date: str | None) -> int | None:
        if not last_data_date:
            return None
        try:
            d = date.fromisoformat(str(last_data_date))
            return (today - d).days
        except (ValueError, TypeError):
            return None

    def _status_indicator(cadence: str, days: int | None) -> str:
        if cadence == "manual":
            return "manual"
        if days is None:
            return "never"
        if days > 90:
            return "old"
        if days > 14:
            return "stale"
        return "current"

    # Column widths
    col_key = 42
    col_country = 22
    col_cadence = 10
    col_date = 14
    col_days = 9
    col_status = 9

    header = (
        f"{'SOURCE KEY':<{col_key}}"
        f"{'COUNTRY':<{col_country}}"
        f"{'CADENCE':<{col_cadence}}"
        f"{'LAST DATA':<{col_date}}"
        f"{'DAYS AGO':>{col_days}}"
        f"  {'STATUS':<{col_status}}"
    )
    sep = "-" * len(header)

    print(header)
    print(sep)

    for key, cfg in sorted(
        FETCHER_REGISTRY.items(), key=lambda x: (x[1].country, x[0])
    ):
        entry = state.get(key, {})
        last_date = entry.get("last_data_date") if entry else None
        days = _days_stale(last_date)
        status = _status_indicator(cfg.cadence, days)
        days_str = str(days) if days is not None else "—"
        date_str = last_date or "—"
        print(
            f"{key:<{col_key}}"
            f"{cfg.country:<{col_country}}"
            f"{cfg.cadence:<{col_cadence}}"
            f"{date_str:<{col_date}}"
            f"{days_str:>{col_days}}"
            f"  {status:<{col_status}}"
        )

    # Orphaned entries
    orphaned = [k for k in state if k not in FETCHER_REGISTRY]
    if orphaned:
        print()
        print(
            f"Orphaned state entries ({len(orphaned)} — in state but not in registry):"
        )
        for k in sorted(orphaned):
            entry = state[k]
            last_date = (
                entry.get("last_data_date") if isinstance(entry, dict) else str(entry)
            )
            print(f"  {k:<{col_key}} last_data_date={last_date}")

        if prune_orphans:
            if not force:
                answer = (
                    input(f"\nRemove {len(orphaned)} orphaned entries? [y/N] ")
                    .strip()
                    .lower()
                )
                if answer != "y":
                    print("Aborted.")
                    return
            for k in orphaned:
                del state[k]
            write_fetch_state(state, FETCH_STATE_JSON)
            print(f"Removed {len(orphaned)} orphaned entries.")
    elif prune_orphans:
        print("\nNo orphaned entries to prune.")


def _cmd_build(args) -> None:
    """Run processing pipeline and write enriched CSV to staged dir."""
    from .process import materialize_outputs

    result = materialize_outputs(
        staged_dir=STAGED_DATA_DIR,
        incremental=not getattr(args, "full", False),
    )
    print(
        f"Build complete — {result['enriched_rows']:,} rows -> {result['enriched_path']}"
    )


def _cmd_publish(args) -> None:
    """Regenerate fuel publish artifacts (HTML dashboards)."""
    from .loader import load_fuel_data

    # from .visualize import gen_fuel_html
    from .visualize_policy import gen_policy_html, load_policy_data

    target = getattr(args, "target", "all")
    fuel_data = None

    if target in {"all", "prices", "policy"}:
        print("Loading fuel prices data...")
        fuel_data = load_fuel_data()

    if target in {"all", "prices"}:
        out = DATA_DIR / "fuel_prices.html"
        print(f"Generating fuel prices HTML -> {out}")
        # gen_fuel_html(fuel_data, out)

    if target in {"all", "policy"}:
        out = DATA_DIR / "fuel_policy_overview.html"
        print(f"Generating fuel policy HTML -> {out}")
        policy_data = load_policy_data()
        gen_policy_html(policy_data, fuel_data, out)

    print("Done.")


def _cmd_migrate(args) -> None:
    """Run per-source data migration (splits flat CSVs into per-source dirs)."""
    import subprocess
    import sys

    from .constants import PROJECT_ROOT

    script = PROJECT_ROOT / "scripts" / "migrate_flat_to_per_source.py"
    subprocess.run([sys.executable, str(script)], check=True)


def build_parser() -> argparse.ArgumentParser:
    """Build the public CLI parser for fuel_prices."""
    parser = argparse.ArgumentParser(
        prog="python -m src.cpi.fuel_prices",
        description="Pacific Observatory fuel prices CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  poetry run python -m src.cpi.fuel_prices fetch
  poetry run python -m src.cpi.fuel_prices fetch --status
  poetry run python -m src.cpi.fuel_prices fetch --source nz_mbie_weekly_fuel
  poetry run python -m src.cpi.fuel_prices fetch --source nz_mbie_weekly_fuel --rebuild
  poetry run python -m src.cpi.fuel_prices fetch --cadence daily
  poetry run python -m src.cpi.fuel_prices fetch --force
  poetry run python -m src.cpi.fuel_prices fetch --status --prune-orphans
  poetry run python -m src.cpi.fuel_prices build
  poetry run python -m src.cpi.fuel_prices publish --target prices
  poetry run python -m src.cpi.fuel_prices migrate
        """,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    fetch = sub.add_parser("fetch", help="Refresh stored fuel observations")
    fetch.add_argument(
        "--source", metavar="SOURCE_KEY", help="Fetch a single source key only"
    )
    fetch.add_argument(
        "--cadence",
        choices=_CADENCE_CHOICES,
        metavar="CADENCE",
        help="Only run sources matching this cadence (daily/weekly/monthly/quarterly/irregular/manual)",
    )
    fetch.add_argument(
        "--force",
        action="store_true",
        help="Ignore cadence skip logic and run all selected sources (including manual)",
    )
    fetch.add_argument(
        "--rebuild",
        action="store_true",
        help="Wipe and re-fetch from fallback_date for --source KEY (requires --source)",
    )
    fetch.add_argument(
        "--status",
        action="store_true",
        help="Print source health table (no fetching)",
    )
    fetch.add_argument(
        "--prune-orphans",
        action="store_true",
        dest="prune_orphans",
        help="With --status: remove orphaned state entries (prompts unless --force)",
    )
    fetch.set_defaults(func=_cmd_fetch)

    build = sub.add_parser(
        "build", help="Run processing pipeline and write enriched staged outputs"
    )
    build.add_argument(
        "--full",
        action="store_true",
        help="Force full rebuild (skip incremental check)",
    )
    build.set_defaults(func=_cmd_build)

    publish = sub.add_parser("publish", help="Regenerate fuel publish artifacts")
    publish.add_argument(
        "--target",
        choices=["all", "prices", "policy"],
        default="all",
        help="Which publish artifact set to regenerate (default: all)",
    )
    publish.set_defaults(func=_cmd_publish)

    migrate = sub.add_parser(
        "migrate",
        help="Run per-source migration (split flat CSVs into per-source dirs)",
    )
    migrate.set_defaults(func=_cmd_migrate)

    return parser


def main(argv=None) -> None:
    """Run the fuel_prices CLI."""
    parser = build_parser()
    parsed = parser.parse_args(argv)
    parsed.func(parsed)
