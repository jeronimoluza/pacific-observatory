"""One row per (source, crawl): what Common Crawl holds and how far we got.

The sweep has no manifest of its own. Resume is reconstructed by globbing the
source tree, and a glob cannot represent a negative -- "this host does not
appear in this crawl" has no filename -- so it can never produce a
denominator. That is what this ledger is for: a row exists for every
(source, crawl) pair we know something about, including the ones that
produced nothing.

The backfill below fills only the POSITIVE side, because that is all disk can
prove. `host_absent` and `prefix_rejected` are distinguishable only by
resolving against the index, so they arrive from the resolve path, not here.
An unresolved crawl has no row at all rather than a guessed one.

Two filename conventions carry the same meaning and both must be globbed:

    cc_parsed_CC-MAIN-*.jsonl
    cc_recovered_CC-MAIN-*.jsonl

`livingcost` uses only the second. The plan's first pass globbed only the
first and silently lost 1,346 files across 56 sources, so the count that
matters is the union.

A third layout predates both: one hash-named JSON per record. It is NOT an
unparsed page. The parser ran at fetch time and wrote its result into the
file, and `concatenate` has always read that layout alongside the JSONL
(`concatenate.py:363`), so those records are already in the corpus. Status is
therefore decided by whether a record carries a `product_name`, never by which
filename it happens to live under -- reading the absence of a
`cc_parsed_*.jsonl` as "never parsed" reports 51,727 already-ingested records
as recoverable work.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

import click
import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "prices"

# region/subregion/country/source/common_crawl_data/items
ITEMS_GLOB = "*/*/*/*/common_crawl_data/items"
PARSED_RE = re.compile(r"^cc_(?:parsed|recovered)_(CC-MAIN-(\d{4})-\d{2})\.jsonl$")

COLUMNS = [
    "source",
    "crawl_id",
    "crawl_year",
    "status",
    "records",
    "rows",
    "reason",
    "parser_version",
    "run_id",
    "ts",
]

# Disk can only prove these two. The rest of the vocabulary -- unresolved,
# host_absent, prefix_rejected, resolved, failed -- is written by resolve and
# by the sweep, which are the only things that see a crawl produce nothing.
STATUS_PARSED = "parsed"
STATUS_FETCHED = "fetched"


def ledger_path(data_root: Path) -> Path:
    return Path(data_root) / "_cc_ledger" / "ledger.parquet"


def _count_lines(path: Path) -> int:
    try:
        with open(path, "rb") as fh:
            return sum(1 for line in fh if line.strip())
    except OSError:
        return 0


def _legacy_by_crawl(items: Path) -> dict[str, tuple[int, int]]:
    """Crawl -> (records carrying a parse, records held in total).

    The pre-compaction layout is one JSON per record with the crawl only
    inside the file, so this is 88k opens corpus-wide.

    Reading `product_name` is what makes the status honest. A hash-named
    record is not a saved page: the parser ran at fetch time and wrote its
    result into the file, so a record carrying a name was PARSED, in the older
    layout. Deciding that from the absence of `cc_parsed_*.jsonl` instead
    confuses layout with state.
    """
    out: dict[str, list[int]] = {}
    for path in items.glob("*.json"):
        try:
            with open(path, encoding="utf-8") as fh:
                rec = json.load(fh)
        except (OSError, ValueError):
            continue
        index = rec.get("cc_index")
        if not index:
            continue
        seen = out.setdefault(index, [0, 0])
        seen[1] += 1
        if rec.get("product_name"):
            seen[0] += 1
    return {k: (v[0], v[1]) for k, v in out.items()}


def iter_disk_state(
    data_root: Path, *, count_rows: bool = True, run_id: str = "", ts: str = ""
) -> Iterator[dict]:
    """Every (source, crawl) the source tree can prove something about.

    `_quarantine/` sits at the tree root, not under a region, so the fixed
    four-level glob excludes it by construction -- quarantined rows are
    withdrawn claims and must not count toward coverage.
    """
    data_root = Path(data_root)
    for items in sorted(data_root.glob(ITEMS_GLOB)):
        if not items.is_dir():
            continue
        source = items.parts[-3]
        parsed: dict[str, int] = {}
        for path in items.iterdir():
            m = PARSED_RE.match(path.name)
            if not m:
                continue
            crawl = m.group(1)
            parsed[crawl] = parsed.get(crawl, 0) + (
                _count_lines(path) if count_rows else 0
            )

        for crawl, rows in sorted(parsed.items()):
            yield {
                "source": source,
                "crawl_id": crawl,
                "crawl_year": int(crawl.split("-")[2]),
                "status": STATUS_PARSED,
                "records": None,
                "rows": rows if count_rows else None,
                "reason": None,
                "parser_version": None,
                "run_id": run_id,
                "ts": ts,
            }

        # Parsed beats fetched: a crawl with a parsed file got further, and
        # its legacy records are the same pages read by the older layout.
        #
        # One row per crawl still, never two: a crawl whose legacy records are
        # part parsed and part not reports both numbers in one row (`records`
        # total, `rows` parsed) rather than splitting the grain.
        for crawl, (done, total) in sorted(_legacy_by_crawl(items).items()):
            if crawl in parsed:
                continue
            yield {
                "source": source,
                "crawl_id": crawl,
                "crawl_year": int(crawl.split("-")[2]),
                "status": STATUS_PARSED if done else STATUS_FETCHED,
                "records": total,
                "rows": done,
                "reason": "legacy_layout" if done else "fetched_never_parsed",
                "parser_version": None,
                "run_id": run_id,
                "ts": ts,
            }


def backfill(
    data_root: Path, *, count_rows: bool = True, out: Optional[Path] = None
) -> pd.DataFrame:
    """Rebuild the ledger's positive side from the source tree."""
    run_id = f"backfill_{uuid.uuid4().hex[:8]}"
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows = list(iter_disk_state(data_root, count_rows=count_rows, run_id=run_id, ts=ts))
    df = pd.DataFrame(rows, columns=COLUMNS)
    target = Path(out) if out else ledger_path(data_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(target, index=False)
    return df


@click.command("cc-ledger")
@click.option(
    "--no-count-rows",
    is_flag=True,
    help="Skip line-counting the 34 GB of parsed JSONL. Faster, leaves rows null.",
)
@click.option(
    "--out", type=click.Path(path_type=Path), default=None,
    help="Write somewhere other than data/prices/_cc_ledger/ledger.parquet.",
)
def cc_ledger_command(no_count_rows: bool, out) -> None:
    """Rebuild the Common Crawl ledger's positive side from the source tree."""
    root = DATA_DIR
    df = backfill(root, count_rows=not no_count_rows, out=out)
    parsed = df[df.status == STATUS_PARSED]
    per_source = parsed.groupby("source").crawl_id.nunique()
    click.echo(f"{len(df):,} rows -> {out or ledger_path(root)}")
    click.echo(
        f"  parsed {len(parsed):,} | fetched {len(df) - len(parsed):,} | "
        f"{df.crawl_id.nunique()} indexes | {df.source.nunique()} sources"
    )
    if len(per_source):
        click.echo(
            f"  crawls/source: median {per_source.median():.0f} "
            f"max {per_source.max()} ({per_source.idxmax()})"
        )
