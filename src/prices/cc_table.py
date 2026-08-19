"""Common Crawl columnar (Parquet) index scanner.

``cc_index.py`` binary-searches ``cluster.idx`` for one host at a time, which is
the right shape for "give me this storefront's URLs" and the wrong shape for a
sweep: 272 sources across 126 crawls is ~34k separate lookups.

Common Crawl also publishes the same index as a Parquet table, 300 parts per
crawl, ~7.3M rows each. One scan of a part answers both questions at once —
which URLs the storefronts we already know about had, and which *unknown* hosts
have product-looking paths — because both are predicates over the same columns.

The table carries ``warc_filename`` / ``warc_record_offset`` /
``warc_record_length``, so a row from here is directly fetchable; there is no
cdx lookup in between.

``data.commoncrawl.org`` returns sporadic 503s under load. A 503 read as "no
matching rows" is indistinguishable from a clean empty scan, so every part is
retried and a part that never succeeds is recorded as ``error`` in the ledger
rather than silently contributing zero.
"""

from __future__ import annotations

import gzip
import json
import logging
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from .cc_terms import known_domains, load_keyword_regex  # noqa: F401

logger = logging.getLogger(__name__)

CC_DATA_BASE = "https://data.commoncrawl.org"

# The two jobs have very different column costs, so they are separate modes.
#
# ENUMERATE reads the WARC pointers, which is what makes a row fetchable — but
# it only ever matches a few hundred known domains. The table is sorted by
# `url_surtkey`, so those rows are contiguous and DuckDB skips almost every row
# group via the column statistics; the wide projection is paid for on a sliver
# of the part.
#
# DISCOVER matches a keyword anywhere in `url_path`, which no statistic can
# prune, so every row group is read. Its projection is therefore kept to the
# two columns the candidate ranking actually needs. Reading the WARC pointers
# here as well is what trips data.commoncrawl.org's byte-volume throttle, which
# 503s every large object on the host — `cluster.idx` included — for minutes.
ENUMERATE_COLUMNS = (
    "url_host_name",
    "url_host_registered_domain",
    "url_path",
    "content_languages",
    "fetch_time",
    "warc_filename",
    "warc_record_offset",
    "warc_record_length",
)

# The WARC triple rides along even though discover mode wants a lean
# projection. Without it, triage has to re-scan the very same parts purely to
# recover the pointers, which doubles our exposure to Common Crawl's 503s on
# cold objects — and on 2026-08-18 that second pass is exactly what failed,
# after the first had already succeeded. These three columns are highly
# repetitive and dictionary-encode well, unlike url_path; the added scan cost
# has not been measured.
DISCOVER_COLUMNS = (
    "url_host_registered_domain",
    "url_host_name",
    "url_path",
    "warc_filename",
    "warc_record_offset",
    "warc_record_length",
)

# Which term fired, captured during the scan. A tech blog matches two or three
# product terms by accident (`android`, `windows`); a catalogue matches dozens,
# so distinct terms per domain separates the two far better than path count
# does. `load_keyword_regex` already wraps the alternation in slug boundaries,
# which makes capture group 2 the term itself. Costs one extra regex on the
# 2-3% of rows that already matched.
_MATCHED_TERM_SQL = "regexp_extract(url_path, '{pattern}', 2) AS matched_term"

# Editorial paths mention products without selling them. Excluded at
# aggregation rather than during the scan, so the raw hits stay re-analysable
# when the pattern turns out to be wrong.
_EDITORIAL_PATH_RE = (
    "/(blog|news|articles?|posts?|tags?|category|categories|author|forum|wiki"
    "|docs?|about|careers|events?|press|jobs|topics?)/"
)
_DATED_PATH_RE = "/[12][0-9]{3}/[0-9]{2}/"

# Few in-loop attempts, several passes. `data.commoncrawl.org` serves an object
# it has cached and 503s one it has to fetch from origin, so hammering a single
# cold part is close to useless while the next part may serve immediately.
# Coming back later beats waiting in place.
_MAX_PART_ATTEMPTS = 4
_RETRY_BASE_SECONDS = 15
_RETRY_MAX_SECONDS = 60
_DEFAULT_PASSES = 4
_PASS_PAUSE_SECONDS = 120

# data.commoncrawl.org throttles on sustained byte volume, not request rate:
# once tripped it 503s every large object, `cluster.idx` included, for minutes.
# Pausing between parts keeps a long sweep under that threshold.
_PART_PAUSE_SECONDS = 10


def duckdb_binary() -> str:
    exe = shutil.which("duckdb")
    if not exe:
        raise RuntimeError(
            "duckdb CLI not found on PATH. Install it (brew install duckdb) — "
            "the columnar index is read through it."
        )
    return exe


def work_dir(project_root: Optional[Path] = None) -> Path:
    if project_root is None:
        project_root = Path(__file__).parent.parent.parent
    d = project_root / "data" / "prices" / "_cc_table"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _paths_cache(index: str) -> Path:
    d = work_dir() / index
    d.mkdir(parents=True, exist_ok=True)
    return d / "parts.json"


def table_parts(index: str) -> List[str]:
    """Full URLs of the ``subset=warc`` Parquet parts for one crawl.

    The part filenames carry a per-crawl UUID, so they cannot be constructed —
    they have to be read from the crawl's ``cc-index-table.paths.gz``. The
    ``crawldiagnostics`` and ``robotstxt`` subsets share that manifest and are
    dropped here; only ``warc`` holds fetched pages.
    """
    cache = _paths_cache(index)
    if cache.exists():
        return json.loads(cache.read_text())

    url = f"{CC_DATA_BASE}/crawl-data/{index}/cc-index-table.paths.gz"
    result = subprocess.run(
        [
            "curl",
            "-sS",
            "--fail",
            "--connect-timeout",
            "30",
            "--max-time",
            "180",
            "--retry",
            "4",
            "--retry-delay",
            "5",
            "-o",
            "-",
            url,
        ],
        capture_output=True,
    )
    if result.returncode != 0 or not result.stdout:
        raise RuntimeError(
            f"could not fetch cc-index-table.paths.gz for {index}: "
            f"{result.stderr.decode()[:300]}"
        )
    listing = gzip.decompress(result.stdout).decode().splitlines()
    parts = [f"{CC_DATA_BASE}/{p}" for p in listing if "/subset=warc/" in p]
    if not parts:
        raise RuntimeError(f"{index} lists no subset=warc parts")
    cache.write_text(json.dumps(parts))
    return parts


def _sql_string_list(values: Iterable[str]) -> str:
    return ", ".join("'" + v.replace("'", "''") + "'" for v in sorted(set(values)))


def build_predicate(
    domains: Sequence[str] = (),
    keyword_regex: Optional[str] = None,
) -> str:
    """WHERE clause selecting known-storefront rows, keyword rows, or both.

    ``fetch_status=200`` drops redirects and errors; ``content_mime_detected``
    drops the images and PDFs that share a product path prefix.
    """
    if not domains and not keyword_regex:
        raise ValueError("need at least one of domains / keyword_regex")
    clauses = []
    if domains:
        clauses.append(f"url_host_registered_domain IN ({_sql_string_list(domains)})")
    if keyword_regex:
        escaped = keyword_regex.replace("'", "''")
        clauses.append(f"regexp_matches(url_path, '{escaped}')")
    return (
        "fetch_status = 200 AND content_mime_detected = 'text/html' "
        "AND (" + " OR ".join(clauses) + ")"
    )


def _part_sql(
    part_url: str,
    predicate: str,
    mode: str,
    out_path: Path,
    threads: int,
    keyword_regex: Optional[str] = None,
) -> str:
    cols = ",\n       ".join(
        ENUMERATE_COLUMNS if mode == "enumerate" else DISCOVER_COLUMNS
    )
    if mode == "discover" and keyword_regex:
        cols += ",\n       " + _MATCHED_TERM_SQL.format(
            pattern=keyword_regex.replace("'", "''")
        )
    return (
        "LOAD httpfs;\n"
        f"SET threads={threads};\n"
        "SET enable_progress_bar=false;\n"
        "COPY (\n"
        f"  SELECT {cols}\n"
        f"  FROM read_parquet('{part_url}')\n"
        f"  WHERE {predicate}\n"
        f") TO '{out_path}' (FORMAT PARQUET, COMPRESSION ZSTD);\n"
    )


def scan_part(
    part_url: str,
    predicate: str,
    mode: str,
    out_path: Path,
    threads: int = 4,
    keyword_regex: Optional[str] = None,
) -> int:
    """Scan one Parquet part, writing matching rows. Returns the row count.

    Retries the whole part on failure. ``data.commoncrawl.org`` 503s cold
    objects intermittently — measured at roughly one part in five served on a
    bad day, independent of request rate — and a lost part looks exactly like
    an empty one. Retries are therefore many and closely spaced rather than few
    and patient: the failure is on the origin side, so backing off politely
    buys nothing that trying again does not.
    """
    # Write to a process-private temp path and rename on success. A failed
    # attempt used to delete `out_path` itself, so two runs sharing a staging
    # directory destroyed each other's completed work — which is exactly how a
    # finished 3.4MB pointer scan was lost on 2026-08-18.
    tmp_path = out_path.with_suffix(f".{os.getpid()}.tmp")
    sql = _part_sql(part_url, predicate, mode, tmp_path, threads, keyword_regex)
    last_err = ""
    try:
        for attempt in range(1, _MAX_PART_ATTEMPTS + 1):
            result = subprocess.run(
                [duckdb_binary(), "-c", sql],
                capture_output=True,
                text=True,
                timeout=1800,
            )
            if result.returncode == 0 and tmp_path.exists():
                rows = _row_count(tmp_path)
                tmp_path.replace(out_path)
                return rows
            last_err = (result.stderr or result.stdout or "").strip()[:300]
            tmp_path.unlink(missing_ok=True)
            if attempt < _MAX_PART_ATTEMPTS:
                time.sleep(min(_RETRY_BASE_SECONDS * attempt, _RETRY_MAX_SECONDS))
    finally:
        tmp_path.unlink(missing_ok=True)
    raise RuntimeError(f"part failed after {_MAX_PART_ATTEMPTS} attempts: {last_err}")


def _row_count(parquet_path: Path) -> int:
    result = subprocess.run(
        [
            duckdb_binary(),
            "-noheader",
            "-list",
            "-c",
            f"SELECT count(*) FROM read_parquet('{parquet_path}');",
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"row count failed for {parquet_path}: {result.stderr[:200]}"
        )
    return int(result.stdout.strip() or 0)


class Ledger:
    """Append-only per-part record, so an interrupted crawl scan resumes.

    Only ``ok`` parts are treated as done. An ``error`` part is retried on the
    next run rather than left as a silent hole in the coverage.
    """

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def done_parts(self) -> Dict[str, int]:
        if not self.path.exists():
            return {}
        done: Dict[str, int] = {}
        for line in self.path.read_text().splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("status") == "ok":
                done[rec["part"]] = rec.get("rows", 0)
            else:
                done.pop(rec["part"], None)
        return done

    def record(self, part: str, status: str, rows: int = 0, error: str = "") -> None:
        rec = {"part": part, "status": status, "rows": rows}
        if error:
            rec["error"] = error[:300]
        with self.path.open("a") as fh:
            fh.write(json.dumps(rec) + "\n")


def scan_index(
    index: str,
    mode: str,
    domains: Sequence[str] = (),
    keyword_regex: Optional[str] = None,
    threads: int = 4,
    limit_parts: Optional[int] = None,
    passes: int = _DEFAULT_PASSES,
    progress=None,
) -> Dict[str, object]:
    """Scan every Parquet part of one crawl in one mode, resuming from its ledger.

    Runs the parts serially. Each DuckDB process already opens ``threads``
    connections to ``data.commoncrawl.org``, and sustained load past about a
    dozen gets the whole host throttled, so part-level parallelism is
    deliberately not offered here.
    """
    if mode not in ("enumerate", "discover"):
        raise ValueError(f"mode must be 'enumerate' or 'discover', got {mode!r}")
    if mode == "enumerate":
        predicate = build_predicate(domains=domains)
    else:
        predicate = build_predicate(keyword_regex=keyword_regex)

    out_dir = work_dir() / index / f"hits_{mode}"
    out_dir.mkdir(parents=True, exist_ok=True)
    ledger = Ledger(work_dir() / index / f"ledger_{mode}.jsonl")
    done = ledger.done_parts()

    parts = table_parts(index)
    if limit_parts:
        parts = parts[:limit_parts]

    total_rows = sum(done.get(Path(p).name, 0) for p in parts if Path(p).name in done)
    failed: List[str] = []
    for pass_no in range(1, passes + 1):
        done = ledger.done_parts()
        pending = [p for p in parts if Path(p).name not in done]
        if not pending:
            break
        if pass_no > 1:
            logger.info(f"{index} {mode}: pass {pass_no}, {len(pending)} parts left")
            time.sleep(_PASS_PAUSE_SECONDS)
        for part_url in pending:
            name = Path(part_url).name
            out_path = out_dir / (name.split("-")[1] + ".parquet")
            try:
                rows = scan_part(
                    part_url,
                    predicate,
                    mode,
                    out_path,
                    threads=threads,
                    keyword_regex=keyword_regex,
                )
            except Exception as exc:  # noqa: BLE001 - recorded, sweep continues
                ledger.record(name, "error", error=str(exc))
                logger.warning(f"{index} {name}: {exc}")
                continue
            ledger.record(name, "ok", rows=rows)
            total_rows += rows
            if progress:
                progress(name, rows)
            time.sleep(_PART_PAUSE_SECONDS)

    failed = [p for p in (Path(x).name for x in parts) if p not in ledger.done_parts()]

    return {
        "index": index,
        "mode": mode,
        "parts": len(parts),
        "parts_failed": len(failed),
        "failed": failed,
        "rows": total_rows,
        "hits_dir": str(out_dir),
    }


def hits_glob(index: str, mode: str = "discover") -> str:
    return str(work_dir() / index / f"hits_{mode}" / "*.parquet")


def summarize_candidates(
    index: str,
    known_domains_list: Sequence[str] = (),
    min_paths: int = 3,
    min_terms: int = 2,
    out_path: Optional[Path] = None,
) -> Path:
    """Aggregate keyword hits into a per-domain candidate list.

    Ranked by how many *distinct* product terms the domain matched, then by
    matching paths. A blog that happens to mention two gadgets scores 2 no
    matter how many posts it has; a catalogue scores in the dozens.
    """
    if out_path is None:
        out_path = work_dir() / index / "candidates.parquet"
    exclude = (
        f"AND url_host_registered_domain NOT IN ({_sql_string_list(known_domains_list)})"
        if known_domains_list
        else ""
    )
    sql = (
        "LOAD httpfs;\n"
        "SET enable_progress_bar=false;\n"
        "COPY (\n"
        "  SELECT url_host_registered_domain AS domain,\n"
        "         any_value(regexp_extract(url_host_registered_domain,"
        " '\\.([^.]+)$', 1)) AS tld,\n"
        "         count(DISTINCT matched_term) AS n_terms,\n"
        "         count(DISTINCT url_path) AS n_paths,\n"
        "         count(*) AS n_rows,\n"
        "         list(DISTINCT matched_term)[1:8] AS sample_terms,\n"
        "         list(DISTINCT url_path)[1:5] AS sample_paths\n"
        f"  FROM read_parquet('{hits_glob(index)}')\n"
        f"  WHERE NOT regexp_matches(url_path, '{_EDITORIAL_PATH_RE}')\n"
        f"    AND NOT regexp_matches(url_path, '{_DATED_PATH_RE}')\n"
        f"    {exclude}\n"
        "  GROUP BY 1\n"
        f"  HAVING count(DISTINCT url_path) >= {min_paths}\n"
        f"     AND count(DISTINCT matched_term) >= {min_terms}\n"
        "  ORDER BY n_terms DESC, n_paths DESC\n"
        f") TO '{out_path}' (FORMAT PARQUET, COMPRESSION ZSTD);\n"
    )
    result = subprocess.run(
        [duckdb_binary(), "-c", sql], capture_output=True, text=True, timeout=3600
    )
    if result.returncode != 0:
        raise RuntimeError(f"candidate summary failed: {result.stderr[:400]}")
    return out_path
