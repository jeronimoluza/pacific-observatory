"""Merge staged collect runs into the archive (``data/text``) and the ledger.

A staging run is ``<staging>/<run_id>/<region>/<subregion>/<country>/<source>/``
holding only what that run collected. Merging a source appends its new
news.csv/urls.csv rows (deduplicated by url against the archive file), checks
the bytes it appended parse back to exactly those rows, replaces
failed_urls_seen.csv, copies failed/ and metadata/ files, and updates the
ledger. A region is marked merged in a run with ``<run_id>/<region>/.merged``.
"""

from __future__ import annotations

import csv
import io
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

import click
import pandas as pd

from text.ledger import Ledger, SourceState, URL_COLUMNS, iter_source_dirs, newest_date

MERGED_MARKER = ".merged"


class MergeError(RuntimeError):
    pass


def _header(path: Path) -> list[str]:
    with open(path, newline="", encoding="utf-8") as f:
        return next(csv.reader(f))


def _append_new_rows(stage_csv: Path, target_csv: Path) -> pd.DataFrame:
    """Append rows of ``stage_csv`` whose url is not in ``target_csv``; verify; return them."""
    delta = pd.read_csv(stage_csv, dtype=str, keep_default_na=False)
    if not target_csv.exists():
        delta = delta.drop_duplicates("url")
        tmp = target_csv.with_suffix(".csv.merging")
        delta.to_csv(tmp, index=False)
        os.replace(tmp, target_csv)
        return delta

    header = _header(target_csv)
    extra = [c for c in delta.columns if c not in header]
    if extra:
        raise MergeError(
            f"{target_csv}: staged columns {extra} missing in archive header"
        )
    target_urls = set(
        pd.read_csv(target_csv, usecols=["url"], dtype=str)["url"].dropna().astype(str)
    )
    delta = delta[~delta["url"].isin(target_urls)].drop_duplicates("url")
    if delta.empty:
        return delta
    delta = delta.reindex(columns=header, fill_value="")

    size_before = target_csv.stat().st_size
    with open(target_csv, "rb") as f:
        f.seek(max(size_before - 1, 0))
        needs_newline = size_before > 0 and f.read(1) != b"\n"
    with open(target_csv, "a", newline="", encoding="utf-8") as f:
        if needs_newline:
            f.write("\n")
        delta.to_csv(f, header=False, index=False)

    # Self-check: the appended bytes parse back to exactly the delta rows.
    with open(target_csv, "rb") as f:
        f.seek(size_before)
        tail = f.read().decode("utf-8")
    back = pd.read_csv(
        io.StringIO(tail), names=header, dtype=str, keep_default_na=False
    )
    if back["url"].tolist() != delta["url"].tolist():
        raise MergeError(
            f"{target_csv}: appended {len(delta)} rows but read back {len(back)}"
        )
    return delta


def _copy_dir_files(stage_dir: Path, target_dir: Path) -> None:
    """Copy snapshot files; same-named CSVs are concatenated and deduplicated."""
    if not stage_dir.is_dir():
        return
    target_dir.mkdir(parents=True, exist_ok=True)
    for src in stage_dir.iterdir():
        dst = target_dir / src.name
        if dst.exists() and src.suffix == ".csv":
            both = pd.concat(
                [pd.read_csv(p, dtype=str, keep_default_na=False) for p in (dst, src)]
            ).drop_duplicates()
            tmp = dst.with_suffix(".csv.merging")
            both.to_csv(tmp, index=False)
            os.replace(tmp, dst)
        elif not dst.exists():
            shutil.copy2(src, dst)


def merge_source(
    stage_dir: Path, target_dir: Path, state: SourceState | None
) -> tuple[SourceState, int, int]:
    """Merge one staged source. Returns (new ledger state, news rows, urls rows)."""
    target_dir.mkdir(parents=True, exist_ok=True)
    new_news = new_urls = pd.DataFrame(columns=URL_COLUMNS)
    if (stage_dir / "news.csv").exists():
        new_news = _append_new_rows(stage_dir / "news.csv", target_dir / "news.csv")
    if (stage_dir / "urls.csv").exists():
        new_urls = _append_new_rows(stage_dir / "urls.csv", target_dir / "urls.csv")

    failed_csv = stage_dir / "failed_urls_seen.csv"
    if failed_csv.exists():
        tmp = target_dir / "failed_urls_seen.csv.merging"
        shutil.copy2(failed_csv, tmp)
        os.replace(tmp, target_dir / "failed_urls_seen.csv")
    for sub in ("failed", "metadata"):
        _copy_dir_files(stage_dir / sub, target_dir / sub)

    if state is None:
        state = SourceState(set(), set(), pd.DataFrame(columns=URL_COLUMNS), None, None)
    news = state.news | set(new_news["url"].astype(str))
    urls = state.urls | set(new_urls["url"].astype(str))
    pending = pd.concat([state.pending, new_urls[URL_COLUMNS]])
    pending = pending[~pending["url"].isin(news)].drop_duplicates("url")
    marks = [m for m in (state.watermark, newest_date(new_news["date"])) if m]
    new_state = SourceState(
        urls=urls,
        news=news,
        pending=pending,
        failed=failed_csv.read_bytes() if failed_csv.exists() else state.failed,
        watermark=max(marks) if marks else None,
    )
    return new_state, len(new_news), len(new_urls)


def pending_runs(staging: Path, region: str) -> list[Path]:
    """Run dirs under ``staging`` holding an unmerged ``region``, oldest first."""
    return [
        run
        for run in sorted(p for p in staging.iterdir() if p.is_dir())
        if (run / region).is_dir() and not (run / region / MERGED_MARKER).exists()
    ]


def run_merge(region: str, staging: Path, data_base: Path) -> None:
    region_dir = data_base / region
    if not region_dir.is_dir():
        raise click.ClickException(f"archive not mounted: {region_dir} is missing")
    runs = pending_runs(staging, region)
    if not runs:
        click.echo(f"  No unmerged {region} runs under {staging}.")
        return

    ledger = Ledger(region)
    failed: list[str] = []
    try:
        for run in runs:
            click.echo(f"\n  === {run.name} / {region} ===")
            n_news = n_urls = n_sources = 0
            run_failed: list[str] = []
            for key, stage_dir in iter_source_dirs(run / region):
                try:
                    state, a, b = merge_source(
                        stage_dir, region_dir / key, ledger.get(key)
                    )
                except Exception as e:  # report every source, then fail the run
                    run_failed.append(key)
                    click.echo(f"  FAILED {key}: {e}")
                    continue
                ledger.put(key, state)
                n_sources += 1
                n_news += a
                n_urls += b
                if a or b:
                    click.echo(f"  {key}: +{a} news, +{b} urls")
            click.echo(
                f"  {run.name}: {n_sources} sources, +{n_news:,} news rows, "
                f"+{n_urls:,} urls rows, {len(run_failed)} failed"
            )
            if run_failed:
                failed.extend(f"{run.name}/{k}" for k in run_failed)
                continue
            stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            (run / region / MERGED_MARKER).write_text(
                f"{stamp} sources={n_sources} news={n_news} urls={n_urls}\n"
            )
            click.echo(
                f"  Verified. Remove the staged copy with:\n    rm -rf {run / region}"
            )
    finally:
        ledger.close()
    if failed:
        click.echo(f"\n  {len(failed)} source(s) failed to merge: {', '.join(failed)}")
        raise SystemExit(1)
