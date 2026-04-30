"""Two-tier text storage: local repo `data/text/` ↔ SSKJL drive `/Volumes/SSKJL/data/text/`.

Engine for `po text {archive,restore,storage-status}`. CLI handlers in `cli.py`
are thin wrappers; all rsync invocation, scope resolution, and verification
lives here.

Design: docs/plans/2026-04-30-text-storage-design.md
Plan:   docs/plans/2026-04-30-text-storage-cli-impl.md
"""

import subprocess
from pathlib import Path
from typing import Any, Iterable

from core.config import (
    get_country_path,
    resolve_subregion_region,
)


# ── Constants ──────────────────────────────────────────────────────

DRIVE_MOUNT = Path("/Volumes/SSKJL")
DRIVE_ROOT = DRIVE_MOUNT / "data" / "text"
LOCAL_ROOT = Path("data") / "text"

RSYNC_BASE = [
    "rsync",
    "-av",
    "--update",
    "--no-perms",
    "--no-owner",
    "--no-group",
]
# Filter set: keep dir entries (so rsync recurses), include the two CSVs we
# care about, exclude everything else. Order matters — rsync evaluates
# top-to-bottom and the first match wins.
NEWS_ONLY_FILTERS = [
    "--include=*/",
    "--include=news.csv",
    "--include=urls.csv",
    "--exclude=*",
]


# ── Mount checks ───────────────────────────────────────────────────


def is_drive_online() -> bool:
    if not DRIVE_MOUNT.exists():
        return False
    try:
        return DRIVE_MOUNT.is_mount() or DRIVE_MOUNT.is_dir()
    except OSError:
        return False


def ensure_drive_mounted() -> None:
    if not is_drive_online():
        raise RuntimeError(
            f"SSKJL drive not mounted at {DRIVE_MOUNT}. "
            "Plug it in (Disk Utility default name 'SSKJL') and retry."
        )


# ── Scope resolution ───────────────────────────────────────────────


def resolve_scope(
    region: str | None = None,
    subregion: str | None = None,
    country: str | None = None,
    source: str | None = None,
    path: str | None = None,
    local_root: Path = LOCAL_ROOT,
    drive_root: Path = DRIVE_ROOT,
) -> list[tuple[Path, Path]]:
    """Resolve scope flags to a list of (local_dir, drive_dir) pairs.

    Exactly one of {path, country, subregion, region} should be given as
    the anchor (with optional --source narrowing under country/path).
    """
    if path is not None:
        rel = Path(path)
        # Allow callers to give either "data/text/<...>" or just "<region>/<...>".
        try:
            rel = rel.relative_to(local_root) if rel.is_absolute() else rel
        except ValueError:
            pass
        if rel.parts and rel.parts[0] == "data":
            rel = Path(*rel.parts[2:])
        local_dir = local_root / rel
        drive_dir = drive_root / rel
        return [(local_dir, drive_dir)]

    if country is not None:
        region_, subregion_, _ = get_country_path(country)
        rel = Path(region_) / subregion_ / country
        if source:
            rel = rel / source
        return [(local_root / rel, drive_root / rel)]

    if source is not None and country is None:
        raise ValueError("--source requires --country (or --path)")

    if subregion is not None:
        region_ = resolve_subregion_region(subregion)
        rel = Path(region_) / subregion
        return [(local_root / rel, drive_root / rel)]

    if region is not None:
        rel = Path(region)
        return [(local_root / rel, drive_root / rel)]

    raise ValueError(
        "specify a scope: --region / --subregion / --country / --source / --path"
    )


# ── rsync invocation ───────────────────────────────────────────────


def _run_rsync(src: Path, dst: Path, news_only: bool) -> subprocess.CompletedProcess:
    dst.mkdir(parents=True, exist_ok=True)
    cmd = list(RSYNC_BASE)
    if news_only:
        cmd.extend(NEWS_ONLY_FILTERS)
    # Trailing slash on src ensures we copy contents into dst (not nest).
    cmd.extend([f"{src}/", f"{dst}/"])
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"rsync failed (exit {proc.returncode}):\n"
            f"  cmd: {' '.join(cmd)}\n"
            f"  stderr: {proc.stderr.strip()}"
        )
    return proc


# ── Verification helpers ───────────────────────────────────────────


def _walk_files(root: Path) -> Iterable[Path]:
    if not root.exists():
        return
    for p in root.rglob("*"):
        if p.is_file():
            yield p


def verify_size_match(
    src_dir: Path,
    dst_dir: Path,
    news_only: bool = False,
) -> list[dict]:
    """For every file under src_dir, ensure dst_dir has the same path + size.

    Returns list of mismatches. Empty list = perfect match.
    """
    mismatches: list[dict] = []
    if not src_dir.exists():
        return mismatches
    for src_file in _walk_files(src_dir):
        rel = src_file.relative_to(src_dir)
        if news_only and rel.name not in {"news.csv", "urls.csv"}:
            continue
        dst_file = dst_dir / rel
        if not dst_file.exists():
            mismatches.append(
                {
                    "path": str(rel),
                    "src": src_file.stat().st_size,
                    "dst": None,
                    "reason": "missing-on-dst",
                }
            )
            continue
        s_size = src_file.stat().st_size
        d_size = dst_file.stat().st_size
        if s_size != d_size:
            mismatches.append(
                {
                    "path": str(rel),
                    "src": s_size,
                    "dst": d_size,
                    "reason": "size-mismatch",
                }
            )
    return mismatches


def _count_news_rows(news_csv: Path) -> int:
    """Count data rows (excluding header) in a news.csv. Stream-friendly."""
    if not news_csv.exists():
        return 0
    n = 0
    with open(news_csv, "rb") as f:
        for _ in f:
            n += 1
    return max(0, n - 1)


def verify_news_row_counts(src_dir: Path, dst_dir: Path) -> list[dict]:
    mismatches: list[dict] = []
    if not src_dir.exists():
        return mismatches
    for src_file in src_dir.rglob("news.csv"):
        rel = src_file.relative_to(src_dir)
        dst_file = dst_dir / rel
        s_rows = _count_news_rows(src_file)
        d_rows = _count_news_rows(dst_file) if dst_file.exists() else None
        if d_rows is None:
            mismatches.append(
                {
                    "path": str(rel),
                    "src_rows": s_rows,
                    "dst_rows": None,
                    "reason": "missing-on-dst",
                }
            )
        elif s_rows != d_rows:
            mismatches.append(
                {
                    "path": str(rel),
                    "src_rows": s_rows,
                    "dst_rows": d_rows,
                    "reason": "row-count-mismatch",
                }
            )
    return mismatches


# ── Archive / restore workers ──────────────────────────────────────


def _scope_stats(local_dir: Path) -> tuple[int, int, int]:
    files = 0
    bytes_ = 0
    news_files = 0
    for f in _walk_files(local_dir):
        files += 1
        try:
            bytes_ += f.stat().st_size
        except OSError:
            pass
        if f.name == "news.csv":
            news_files += 1
    return files, bytes_, news_files


def archive_scope(
    pairs: list[tuple[Path, Path]],
    news_only: bool = False,
) -> dict[str, Any]:
    """Run rsync local→drive for each pair, then verify."""
    ensure_drive_mounted()
    total_files = 0
    total_bytes = 0
    total_news = 0
    all_mismatches: list[dict] = []
    verified_pairs: list[tuple[Path, Path]] = []

    for local_dir, drive_dir in pairs:
        if not local_dir.exists():
            raise FileNotFoundError(f"local dir does not exist: {local_dir}")
        _run_rsync(local_dir, drive_dir, news_only=news_only)
        size_miss = verify_size_match(local_dir, drive_dir, news_only=news_only)
        row_miss = verify_news_row_counts(local_dir, drive_dir)
        miss = size_miss + row_miss
        files, bytes_, news = _scope_stats(local_dir)
        total_files += files
        total_bytes += bytes_
        total_news += news
        if miss:
            all_mismatches.extend({**m, "scope": str(local_dir)} for m in miss)
        else:
            verified_pairs.append((local_dir, drive_dir))

    return {
        "ok": not all_mismatches,
        "files": total_files,
        "bytes": total_bytes,
        "news_files_verified": total_news if not all_mismatches else 0,
        "mismatches": all_mismatches,
        "verified_pairs": verified_pairs,
        "news_only": news_only,
    }


def restore_scope(pairs: list[tuple[Path, Path]]) -> dict[str, Any]:
    """Run rsync drive→local for each pair, then verify."""
    ensure_drive_mounted()
    total_files = 0
    total_bytes = 0
    total_news = 0
    all_mismatches: list[dict] = []
    local_newer: list[dict] = []

    for local_dir, drive_dir in pairs:
        if not drive_dir.exists():
            raise FileNotFoundError(f"drive dir does not exist: {drive_dir}")
        _run_rsync(drive_dir, local_dir, news_only=False)
        # Verify drive→local (canonical=drive).
        miss = verify_size_match(drive_dir, local_dir) + verify_news_row_counts(
            drive_dir, local_dir
        )
        # Detect local-newer (files local has but drive doesn't, or local rows > drive rows).
        for src_file in _walk_files(local_dir):
            rel = src_file.relative_to(local_dir)
            d_file = drive_dir / rel
            if not d_file.exists():
                local_newer.append({"path": str(rel), "reason": "local-only-file"})
        for src_file in local_dir.rglob("news.csv"):
            rel = src_file.relative_to(local_dir)
            d_file = drive_dir / rel
            if d_file.exists():
                l_rows = _count_news_rows(src_file)
                d_rows = _count_news_rows(d_file)
                if l_rows > d_rows:
                    local_newer.append(
                        {
                            "path": str(rel),
                            "local_rows": l_rows,
                            "drive_rows": d_rows,
                            "reason": "local-rows-newer",
                        }
                    )
        files, bytes_, news = _scope_stats(local_dir)
        total_files += files
        total_bytes += bytes_
        total_news += news
        if miss:
            all_mismatches.extend({**m, "scope": str(drive_dir)} for m in miss)

    return {
        "ok": not all_mismatches,
        "files": total_files,
        "bytes": total_bytes,
        "news_files_verified": total_news if not all_mismatches else 0,
        "mismatches": all_mismatches,
        "local_newer": local_newer,
    }


__all__ = [
    "DRIVE_MOUNT",
    "DRIVE_ROOT",
    "LOCAL_ROOT",
    "is_drive_online",
    "ensure_drive_mounted",
    "resolve_scope",
    "archive_scope",
    "restore_scope",
    "verify_size_match",
    "verify_news_row_counts",
]
