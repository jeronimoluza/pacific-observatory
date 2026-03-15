"""CLI for the fuel_prices package — 4 commands: fetch, build, publish, migrate."""

from __future__ import annotations

import argparse

from .collect.pipeline import run_collection
from .constants import DATA_DIR, FETCH_STATE_JSON, STAGED_DATA_DIR


def _cmd_fetch(args) -> None:
    """Fetch new data from one or all configured fuel sources."""
    run_collection(
        source_key=getattr(args, "source", None),
        observations_base_dir=DATA_DIR,
        fetch_state_path=FETCH_STATE_JSON,
    )


def _cmd_build(args) -> None:
    """Run full processing pipeline and write enriched CSV to staged dir."""
    from .process import materialize_outputs

    result = materialize_outputs(staged_dir=STAGED_DATA_DIR)
    print(
        f"Build complete — {result['enriched_rows']:,} rows -> {result['enriched_path']}"
    )


def _cmd_publish(args) -> None:
    """Regenerate fuel publish artifacts (HTML dashboards)."""
    from .loader import load_fuel_data
    from .visualize import gen_fuel_html
    from .visualize_policy import gen_policy_html, load_policy_data

    target = getattr(args, "target", "all")
    fuel_data = None

    if target in {"all", "prices", "policy"}:
        print("Loading fuel prices data...")
        fuel_data = load_fuel_data()

    if target in {"all", "prices"}:
        out = DATA_DIR / "fuel_prices.html"
        print(f"Generating fuel prices HTML -> {out}")
        gen_fuel_html(fuel_data, out)

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
  poetry run python -m src.cpi.fuel_prices fetch --source nz_mbie_weekly_fuel
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
    fetch.set_defaults(func=_cmd_fetch)

    build = sub.add_parser(
        "build", help="Run processing pipeline and write enriched staged outputs"
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
