"""Helpers for shadow-writing raw scrape artifacts and local sidecars."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path


RAW_REQUIRED_FIELDS = ["product_name", "price", "url", "scraped_at", "url_hash"]
WAYBACK_SNAPSHOT_REQUIRED_FIELDS = [
    "wayback_url",
    "wayback_timestamp",
    "url_hash",
    "scraped_at",
]


def _read_jsonl_lines(file_path: Path) -> list[dict]:
    records = []
    with file_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records


def build_raw_scrape_checks(records: list[dict]) -> dict:
    missing_required_counts = {
        field: sum(1 for record in records if not record.get(field))
        for field in RAW_REQUIRED_FIELDS
    }
    url_hashes = [
        record.get("url_hash") for record in records if record.get("url_hash")
    ]

    return {
        "required_fields": RAW_REQUIRED_FIELDS,
        "row_count": len(records),
        "valid_jsonl": True,
        "missing_required_counts": missing_required_counts,
        "url_hash_unique": len(url_hashes) == len(set(url_hashes)),
        "passed": all(count == 0 for count in missing_required_counts.values())
        and len(url_hashes) == len(set(url_hashes)),
    }


def build_wayback_snapshot_checks(snapshots: list[str]) -> dict:
    unique_snapshots = list(dict.fromkeys(snapshots))
    return {
        "row_count": len(snapshots),
        "entries_unique": len(unique_snapshots) == len(snapshots),
        "entries_are_strings": all(isinstance(entry, str) for entry in snapshots),
        "passed": len(unique_snapshots) == len(snapshots)
        and all(isinstance(entry, str) for entry in snapshots),
    }


def build_wayback_item_checks(records: list[dict], url_hash: str) -> dict:
    missing_required_counts = {
        field: sum(1 for record in records if not record.get(field))
        for field in WAYBACK_SNAPSHOT_REQUIRED_FIELDS
    }
    url_hash_matches = all(record.get("url_hash") == url_hash for record in records)

    return {
        "required_fields": WAYBACK_SNAPSHOT_REQUIRED_FIELDS,
        "row_count": len(records),
        "missing_required_counts": missing_required_counts,
        "url_hash_matches": url_hash_matches,
        "passed": all(count == 0 for count in missing_required_counts.values())
        and url_hash_matches,
    }


def write_raw_scrape_shadow_artifact(
    legacy_file_path: Path,
    project_root: Path,
    country: str,
    spider_name: str,
) -> dict[str, Path | dict]:
    """Copy a raw JSONL scrape run into the new raw tree with sidecars."""
    target_dir = (
        project_root
        / "data"
        / "cpi"
        / "raw"
        / "online_prices"
        / "scrape_runs"
        / country
        / spider_name
    )
    target_dir.mkdir(parents=True, exist_ok=True)

    target_file_path = target_dir / legacy_file_path.name
    target_file_path.write_text(
        legacy_file_path.read_text(encoding="utf-8"), encoding="utf-8"
    )

    records = _read_jsonl_lines(target_file_path)
    checks = build_raw_scrape_checks(records)
    stem = legacy_file_path.stem

    manifest = {
        "artifact_name": stem,
        "artifact_type": "raw_scrape_run",
        "generated_at": datetime.now(UTC).isoformat(),
        "producer": "src/cpi/price_scraping/price_scraping/pipelines.py",
        "legacy_path": str(legacy_file_path),
        "storage_path": str(target_file_path),
        "country": country,
        "spider_name": spider_name,
        "row_count": len(records),
        "required_fields": RAW_REQUIRED_FIELDS,
    }

    manifest_path = target_dir / f"{stem}.manifest.json"
    checks_path = target_dir / f"{stem}.checks.json"
    markdown_path = target_dir / f"{stem}.md"

    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    checks_path.write_text(json.dumps(checks, indent=2), encoding="utf-8")
    markdown_path.write_text(
        "\n".join(
            [
                f"# {stem}",
                "",
                "Raw scrape run shadow artifact.",
                "",
                f"- Country: `{country}`",
                f"- Spider: `{spider_name}`",
                f"- Rows: `{len(records)}`",
                f"- Legacy source: `{legacy_file_path}`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    return {
        "artifact_path": target_file_path,
        "manifest_path": manifest_path,
        "checks_path": checks_path,
        "markdown_path": markdown_path,
        "manifest": manifest,
        "checks": checks,
    }


def write_wayback_snapshots_shadow_artifact(
    legacy_file_path: Path,
    project_root: Path,
    country: str,
    spider_name: str,
) -> dict[str, Path | dict]:
    """Copy Wayback snapshot list into the raw tree with sidecars."""
    target_dir = (
        project_root
        / "data"
        / "cpi"
        / "raw"
        / "online_prices"
        / "wayback_snapshots"
        / country
        / spider_name
    )
    target_dir.mkdir(parents=True, exist_ok=True)

    target_file_path = target_dir / legacy_file_path.name
    target_file_path.write_text(
        legacy_file_path.read_text(encoding="utf-8"), encoding="utf-8"
    )

    snapshots = json.loads(target_file_path.read_text(encoding="utf-8"))
    checks = build_wayback_snapshot_checks(snapshots)
    stem = legacy_file_path.stem

    manifest = {
        "artifact_name": stem,
        "artifact_type": "raw_wayback_snapshots",
        "generated_at": datetime.now(UTC).isoformat(),
        "producer": "src/cpi/price_scraping/price_scraping/wayback_scraper.py",
        "legacy_path": str(legacy_file_path),
        "storage_path": str(target_file_path),
        "country": country,
        "spider_name": spider_name,
        "row_count": len(snapshots),
    }

    manifest_path = target_dir / f"{stem}.manifest.json"
    checks_path = target_dir / f"{stem}.checks.json"
    markdown_path = target_dir / f"{stem}.md"

    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    checks_path.write_text(json.dumps(checks, indent=2), encoding="utf-8")
    markdown_path.write_text(
        "\n".join(
            [
                f"# {stem}",
                "",
                "Raw Wayback snapshot list shadow artifact.",
                "",
                f"- Country: `{country}`",
                f"- Spider: `{spider_name}`",
                f"- Rows: `{len(snapshots)}`",
                f"- Legacy source: `{legacy_file_path}`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    return {
        "artifact_path": target_file_path,
        "manifest_path": manifest_path,
        "checks_path": checks_path,
        "markdown_path": markdown_path,
        "manifest": manifest,
        "checks": checks,
    }


def write_wayback_items_shadow_artifact(
    legacy_file_path: Path,
    project_root: Path,
    country: str,
    spider_name: str,
) -> dict[str, Path | dict]:
    """Copy Wayback parsed items into the raw tree with sidecars."""
    target_dir = (
        project_root
        / "data"
        / "cpi"
        / "raw"
        / "online_prices"
        / "wayback_items"
        / country
        / spider_name
    )
    target_dir.mkdir(parents=True, exist_ok=True)

    target_file_path = target_dir / legacy_file_path.name
    target_file_path.write_text(
        legacy_file_path.read_text(encoding="utf-8"), encoding="utf-8"
    )

    records = json.loads(target_file_path.read_text(encoding="utf-8"))
    stem = legacy_file_path.stem
    checks = build_wayback_item_checks(records, url_hash=stem)

    manifest = {
        "artifact_name": stem,
        "artifact_type": "raw_wayback_items",
        "generated_at": datetime.now(UTC).isoformat(),
        "producer": "src/cpi/price_scraping/price_scraping/wayback_scraper.py",
        "legacy_path": str(legacy_file_path),
        "storage_path": str(target_file_path),
        "country": country,
        "spider_name": spider_name,
        "row_count": len(records),
    }

    manifest_path = target_dir / f"{stem}.manifest.json"
    checks_path = target_dir / f"{stem}.checks.json"
    markdown_path = target_dir / f"{stem}.md"

    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    checks_path.write_text(json.dumps(checks, indent=2), encoding="utf-8")
    markdown_path.write_text(
        "\n".join(
            [
                f"# {stem}",
                "",
                "Raw Wayback parsed items shadow artifact.",
                "",
                f"- Country: `{country}`",
                f"- Spider: `{spider_name}`",
                f"- Rows: `{len(records)}`",
                f"- Legacy source: `{legacy_file_path}`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    return {
        "artifact_path": target_file_path,
        "manifest_path": manifest_path,
        "checks_path": checks_path,
        "markdown_path": markdown_path,
        "manifest": manifest,
        "checks": checks,
    }
