"""Manifest utilities for incremental COICOP loading."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable


MANIFEST_VERSION = 1


def default_manifest() -> dict:
    return {
        "version": MANIFEST_VERSION,
        "last_run": None,
        "processed_scrapy_files": [],
        "processed_wayback_dirs": [],
    }


def load_manifest(path: Path) -> dict:
    if not path.exists():
        return default_manifest()
    return json.loads(path.read_text(encoding="utf-8"))


def save_manifest(path: Path, manifest: dict) -> None:
    manifest = dict(manifest)
    manifest["version"] = MANIFEST_VERSION
    manifest["last_run"] = datetime.now(UTC).isoformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _iter_country_source_dirs(root_dir: Path) -> Iterable[Path]:
    if not root_dir.exists():
        return []
    return [
        source_dir
        for country_dir in sorted(root_dir.iterdir())
        if country_dir.is_dir()
        for source_dir in sorted(country_dir.iterdir())
        if source_dir.is_dir()
    ]


def list_scrapy_files(root_dir: Path) -> list[str]:
    files: list[str] = []
    for source_dir in _iter_country_source_dirs(root_dir):
        raw_items_dir = source_dir / "raw_items"
        if not raw_items_dir.exists():
            continue
        for jsonl_file in sorted(raw_items_dir.glob("*.jsonl")):
            files.append(jsonl_file.relative_to(root_dir).as_posix())
    return files


def list_wayback_dirs(root_dir: Path) -> list[str]:
    dirs: list[str] = []
    for source_dir in _iter_country_source_dirs(root_dir):
        wayback_items_dir = source_dir / "wayback_machine_data" / "items"
        if not wayback_items_dir.exists():
            continue
        if list(wayback_items_dir.glob("*.json")):
            dirs.append(wayback_items_dir.relative_to(root_dir).as_posix())
    return dirs
