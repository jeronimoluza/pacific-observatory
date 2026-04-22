"""Utilities for migrating flat fuel observations into canonical source paths."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from fuel.config import load_all_source_configs
    from fuel.paths import canonical_observations_path, legacy_observations_path
else:
    from .config import load_all_source_configs
    from .paths import canonical_observations_path, legacy_observations_path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = _PROJECT_ROOT / "data" / "fuel"


def build_migration_plan(
    *,
    region: str | None = None,
    subregion: str | None = None,
    country: str | None = None,
    data_dir: Path = DATA_DIR,
) -> list[dict[str, str | Path]]:
    """Map legacy flat observation files to canonical hierarchical targets."""
    configs = load_all_source_configs(
        region=region, subregion=subregion, country=country
    )
    plan: list[dict[str, str | Path]] = []
    for cfg in sorted(
        configs.values(),
        key=lambda item: (item.region, item.subregion, item.country_slug, item.source),
    ):
        legacy_path = legacy_observations_path(
            cfg.country_slug,
            cfg.source_key,
            base_dir=data_dir,
        )
        canonical_path = canonical_observations_path(
            cfg.region,
            cfg.subregion,
            cfg.country_slug,
            cfg.source,
            base_dir=data_dir,
        )
        plan.append(
            {
                "region": cfg.region,
                "subregion": cfg.subregion,
                "country_slug": cfg.country_slug,
                "source": cfg.source,
                "source_key": cfg.source_key,
                "legacy_path": legacy_path,
                "canonical_path": canonical_path,
            }
        )
    return plan


def migrate_legacy_observations(
    *,
    region: str | None = None,
    subregion: str | None = None,
    country: str | None = None,
    data_dir: Path = DATA_DIR,
    dry_run: bool = False,
) -> list[dict[str, str | Path]]:
    """Move flat legacy fuel observations into canonical source directories."""
    results: list[dict[str, str | Path]] = []
    for item in build_migration_plan(
        region=region,
        subregion=subregion,
        country=country,
        data_dir=data_dir,
    ):
        legacy_path = Path(item["legacy_path"])
        canonical_path = Path(item["canonical_path"])
        result = dict(item)

        if not legacy_path.exists():
            result["status"] = "missing"
            results.append(result)
            continue

        if canonical_path.exists():
            raise FileExistsError(
                "Conflict migrating "
                f"{item['source_key']}: both {legacy_path} and {canonical_path} exist"
            )

        if dry_run:
            result["status"] = "would_move"
            results.append(result)
            continue

        canonical_path.parent.mkdir(parents=True, exist_ok=True)
        legacy_path.rename(canonical_path)
        result["status"] = "moved"
        results.append(result)

    return results


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Preview or run migration of flat fuel observations into canonical paths.",
    )
    parser.add_argument("--region", default=None, help="Filter by region slug")
    parser.add_argument("--subregion", default=None, help="Filter by subregion slug")
    parser.add_argument("--country", default=None, help="Filter by country slug")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Move files instead of doing a dry-run preview",
    )
    return parser


def _print_results(results: list[dict[str, str | Path]], *, dry_run: bool) -> None:
    action = "Would move" if dry_run else "Moved"
    moved = [item for item in results if item["status"] in {"would_move", "moved"}]
    missing = [item for item in results if item["status"] == "missing"]

    if moved:
        print(f"{action} {len(moved)} source(s):")
        for item in moved:
            print(
                f"- {item['source_key']}: {item['legacy_path']} -> {item['canonical_path']}"
            )
    else:
        print("No legacy observation files matched the selected scope.")

    if missing:
        print(f"Skipped {len(missing)} source(s) with no legacy flat observations.")

    if dry_run:
        print("Dry run only. Re-run with --apply to move files.")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        results = migrate_legacy_observations(
            region=args.region,
            subregion=args.subregion,
            country=args.country,
            dry_run=not args.apply,
        )
    except FileExistsError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    _print_results(results, dry_run=not args.apply)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
