"""Manifest utilities for incremental price-enrichment loading (v2).

The manifest lives at ``data/prices/_enrich/manifest.json`` and tracks
which input files / directories have already been folded into
``prepared_cache.parquet``. The schema is:

    {
      "version": 2,
      "last_run": "2026-05-20T...",
      "processed_scrapy_files":        ["<region>/<sub>/<country>/<source>/raw_items/...jsonl"],
      "processed_wayback_items_files": ["<...>/wayback_items/...jsonl"],
      "processed_wayback_dirs":        ["<...>/wayback_machine_data/items"],   # legacy stragglers only
      "processed_common_crawl_dirs":   ["<...>/common_crawl_data/items"]
    }
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

MANIFEST_VERSION = 2

# v2 manifest keys → subdir glob spec. Keep in one place so loaders, manifest
# producers, and migration scripts stay aligned.
_PROCESSED_KEYS = (
    "processed_scrapy_files",
    "processed_wayback_items_files",
    "processed_wayback_dirs",
    "processed_common_crawl_dirs",
)


def default_manifest() -> dict:
    return {
        "version": MANIFEST_VERSION,
        "last_run": None,
        **{key: [] for key in _PROCESSED_KEYS},
    }


def load_manifest(path: Path) -> dict:
    if not path.exists():
        return default_manifest()
    data = json.loads(path.read_text(encoding="utf-8"))
    # Forward-fill any missing v2 keys for manifests written by older code.
    for key in _PROCESSED_KEYS:
        data.setdefault(key, [])
    return data


def save_manifest(path: Path, manifest: dict) -> None:
    manifest = dict(manifest)
    manifest["version"] = MANIFEST_VERSION
    manifest["last_run"] = datetime.now(UTC).isoformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _iter_source_dirs(root_dir: Path) -> Iterable[Path]:
    """Yield 4-level ``<region>/<sub>/<country>/<source>`` directories."""
    if not root_dir.exists():
        return
    for region_dir in sorted(root_dir.iterdir()):
        if not region_dir.is_dir() or region_dir.name.startswith("_"):
            continue
        for sub_dir in sorted(region_dir.iterdir()):
            if not sub_dir.is_dir() or sub_dir.name.startswith("_"):
                continue
            for country_dir in sorted(sub_dir.iterdir()):
                if not country_dir.is_dir() or country_dir.name.startswith("_"):
                    continue
                for source_dir in sorted(country_dir.iterdir()):
                    if not source_dir.is_dir() or source_dir.name.startswith("_"):
                        continue
                    yield source_dir


def list_scrapy_files(root_dir: Path) -> list[str]:
    files: list[str] = []
    for source_dir in _iter_source_dirs(root_dir):
        raw_items_dir = source_dir / "raw_items"
        if not raw_items_dir.exists():
            continue
        for jsonl_file in sorted(raw_items_dir.glob("*.jsonl")):
            files.append(jsonl_file.relative_to(root_dir).as_posix())
    return files


def list_wayback_items_files(root_dir: Path) -> list[str]:
    files: list[str] = []
    for source_dir in _iter_source_dirs(root_dir):
        wayback_items_dir = source_dir / "wayback_items"
        if not wayback_items_dir.exists():
            continue
        for jsonl_file in sorted(wayback_items_dir.glob("*.jsonl")):
            files.append(jsonl_file.relative_to(root_dir).as_posix())
    return files


def list_common_crawl_dirs(root_dir: Path) -> list[str]:
    """Per-source ``common_crawl_data/items`` dirs that contain at least one file."""
    dirs: list[str] = []
    for source_dir in _iter_source_dirs(root_dir):
        cc_items_dir = source_dir / "common_crawl_data" / "items"
        if not cc_items_dir.exists():
            continue
        if list(cc_items_dir.glob("*.json")):
            dirs.append(cc_items_dir.relative_to(root_dir).as_posix())
    return dirs


def list_legacy_wayback_dirs(root_dir: Path) -> list[str]:
    """Per-source ``wayback_machine_data/items`` dirs (legacy stragglers)."""
    dirs: list[str] = []
    for source_dir in _iter_source_dirs(root_dir):
        items_dir = source_dir / "wayback_machine_data" / "items"
        if not items_dir.exists():
            continue
        if list(items_dir.glob("*.json")):
            dirs.append(items_dir.relative_to(root_dir).as_posix())
    return dirs
