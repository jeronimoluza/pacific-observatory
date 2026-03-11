"""Track A shadow artifact helpers for fuel_prices evidence outputs."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

SCHEMA_VERSION = "1.0.0-draft"


def _track_a_root(project_root: Path) -> Path:
    return project_root / "data" / "cpi" / "published" / "track_a" / "fuel_prices"


def write_news_evidence_artifact(
    records: list[dict],
    project_root: Path,
    country_slug: str,
    artifact_name: str,
    source_url: str,
    producer: str,
) -> dict[str, Path | dict]:
    """Write Track A news evidence JSONL + manifest/checks sidecars."""
    target_dir = _track_a_root(project_root) / country_slug / "news"
    target_dir.mkdir(parents=True, exist_ok=True)

    artifact_path = target_dir / f"{artifact_name}.jsonl"
    manifest_path = target_dir / f"{artifact_name}.manifest.json"
    checks_path = target_dir / f"{artifact_name}.checks.json"

    with artifact_path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")

    manifest = {
        "artifact_name": artifact_name,
        "artifact_version": "shadow-v1",
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "producer": producer,
        "source_url": source_url,
        "row_count": len(records),
        "storage_path": str(artifact_path),
    }
    checks = {
        "artifact_name": artifact_name,
        "schema_version": SCHEMA_VERSION,
        "row_count": len(records),
        "non_empty": len(records) > 0,
    }

    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    checks_path.write_text(json.dumps(checks, indent=2), encoding="utf-8")

    return {
        "artifact_path": artifact_path,
        "manifest_path": manifest_path,
        "checks_path": checks_path,
        "manifest": manifest,
        "checks": checks,
    }
