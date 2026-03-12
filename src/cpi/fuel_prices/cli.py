"""CLI parser for the fuel_prices package."""

from __future__ import annotations

import argparse

from .commands import (
    cmd_backfill_fuelcheck,
    cmd_fetch,
    cmd_kr_news,
    cmd_normalize,
    cmd_publish,
    cmd_th_news,
)


def _add_fetch_command(subparsers, name: str, help_text: str) -> None:
    parser = subparsers.add_parser(name, help=help_text)
    parser.add_argument(
        "--source", metavar="SOURCE_KEY", help="Fetch a single source key only"
    )
    parser.set_defaults(func=cmd_fetch)


def _add_normalize_command(subparsers, name: str, help_text: str) -> None:
    parser = subparsers.add_parser(name, help=help_text)
    parser.set_defaults(func=cmd_normalize)


def build_parser() -> argparse.ArgumentParser:
    """Build the public CLI parser for fuel_prices."""
    parser = argparse.ArgumentParser(
        prog="python -m src.cpi.fuel_prices",
        description="Pacific Observatory fuel prices CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.cpi.fuel_prices update
  python -m src.cpi.fuel_prices update --source au_aip_tgp_weekly
  python -m src.cpi.fuel_prices normalize
  python -m src.cpi.fuel_prices publish --target all
  python -m src.cpi.fuel_prices backfill-fuelcheck --overwrite
        """,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    _add_fetch_command(sub, "update", "Refresh stored fuel observations")
    _add_fetch_command(sub, "fetch", "Legacy alias for `update`")

    _add_normalize_command(sub, "normalize", "Apply targeted data-quality fixes")
    _add_normalize_command(sub, "migrate", "Legacy alias for `normalize`")

    publish = sub.add_parser("publish", help="Regenerate fuel publish artifacts")
    publish.add_argument(
        "--target",
        choices=["all", "prices", "policy"],
        default="all",
        help="Which publish artifact set to regenerate (default: all)",
    )
    publish.set_defaults(func=cmd_publish)

    visualize = sub.add_parser(
        "visualize", help="Legacy alias for `publish --target prices`"
    )
    visualize.set_defaults(func=cmd_publish, target="prices")

    policy = sub.add_parser("policy", help="Legacy alias for `publish --target policy`")
    policy.set_defaults(func=cmd_publish, target="policy")

    fuelcheck = sub.add_parser(
        "backfill-fuelcheck",
        help="Backfill NSW FuelCheck monthly resources into one observations.csv",
    )
    fuelcheck.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing data/cpi/fuel_prices/australia/au_nsw_fuelcheck_history/observations.csv",
    )
    fuelcheck.add_argument(
        "--from",
        dest="from_period",
        help="Only process periods >= YYYY-MM (disables resume skip)",
    )
    fuelcheck.add_argument(
        "--to",
        dest="to_period",
        help="Only process periods <= YYYY-MM",
    )
    fuelcheck.set_defaults(func=cmd_backfill_fuelcheck)

    thailand_news = sub.add_parser(
        "tracka-news", help="Collect Track A Thailand news evidence"
    )
    thailand_news.add_argument(
        "--max-items",
        type=int,
        default=50,
        help="Max RSS items to collect (default: 50)",
    )
    thailand_news.set_defaults(func=cmd_th_news)

    korea_news = sub.add_parser(
        "tracka-news-kr", help="Collect Track A Korea news evidence"
    )
    korea_news.add_argument(
        "--max-items",
        type=int,
        default=50,
        help="Max RSS items to collect (default: 50)",
    )
    korea_news.set_defaults(func=cmd_kr_news)

    return parser


def main(argv=None) -> None:
    """Run the fuel_prices CLI."""
    parser = build_parser()
    parsed = parser.parse_args(argv)
    parsed.func(parsed)
