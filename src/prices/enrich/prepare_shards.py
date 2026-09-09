"""Run the prepare stage per country instead of over the whole corpus at once.

`prepare.run` today does `pd.read_csv(raw_prices.csv)` — the entire 33 GB
monolith resident before a single row is prepared. This runs the same
`prepare_input` over one country's shards at a time and writes one prepared
parquet per country, so the peak footprint is the largest country rather than
the corpus, and a country can be recomputed on its own.

**Why country and not source.** `prepare_input` groups on `input_hash`, and
`_row_input_dict` builds that hash from `(product_name_original, product_url)`,
falling back to `(product_name_original, country, currency)` when there is no
URL — which is most of the wayback and Common Crawl corpus. `source` appears in
neither. Two sources in one country selling the same URL-less product are
therefore one prepared row whose price is the *median across sources*, so
splitting the work by source would silently change the numbers: two rows at 10
and 30 where the full run produces one row at 20.

`country` is in the fallback key, so grouping at that level reproduces the full
run exactly. The one input it does not is a `product_url` occurring under two
different countries — and that case is already mishandled today, since the
global groupby collapses it to a single row and `_first_non_empty` picks one of
the two countries arbitrarily. `find_cross_country_urls` reports those rows
rather than leaving the question open.

The same argument fixes the grain of the cache. `_prepared/.state.json` records
the shards each country was last prepared from, and a country whose shards are
unchanged is skipped — but the unit has to be the whole country, because one
changed source can move the median of a group whose other members did not
change. `write_products_input` unions every prepared country off disk rather
than only the recomputed ones, so a skipped country still reaches the output.
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Iterable, Optional, Sequence

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from prices import partition
from prices.enrich import config, shards
from prices.enrich.stages.prepare import (
    SHUFFLE_BUCKETS,
    prepare_input,
    prepare_input_streaming,
)

logger = logging.getLogger(__name__)

PREPARED_DIR = config.ENRICH_DIR / "_prepared"

# Sidecar mapping `region/subregion/country` to the identity of the shards that
# country was last prepared from, so an unchanged country is not recomputed.
# It carries the same weakness as outputs/prices/raw/.state.json — a shard
# rewritten to the same mtime and the same size reads as unchanged — on purpose:
# two different cache-validity rules in one pipeline is the harder thing to
# reason about, and `--rebuild` is the escape hatch for both.
STATE_FILE = ".state.json"

# What prepare_input actually reads. url_hash, product_id and wayback are in the
# shard but unused here, so they are never paid for. input_hash IS read: it is
# already in the shard, so prepare reuses it rather than hashing every raw row.
#
# This is the THIRD definition of the raw schema, after concatenate.OUTPUT_COLS
# and shards.SHARD_COLUMNS, and it is an allowlist like the other two: a column
# missing here is never read off the shard, and `_derive` then fills it empty.
# That is how `unit` stayed dead after 71b1e9ef fixed the writer -- the column
# reached disk and prepare still asked for the other thirteen.
PREPARE_COLUMNS = (
    "input_hash",
    "product_name",
    "price",
    "currency",
    "country",
    "source",
    "date",
    "product_url",
    "region",
    "subregion",
    "channel",
    "category",
    "details",
    "unit",
    "declared_coicop_codes",
)


def _state_path(out_dir: Path) -> Path:
    return out_dir / STATE_FILE


def _load_state(out_dir: Path) -> dict:
    path = _state_path(out_dir)
    if path.exists():
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            logger.warning("state file %s is corrupt; ignoring", path)
    return {}


def _save_state(out_dir: Path, state: dict) -> None:
    """Written to a temp file and renamed. It is now rewritten on every country
    that finishes rather than once at the end of the run, so a crash landing
    inside the write is no longer a theoretical concern -- and `_load_state`
    treats unreadable state as NO state, which would mean preparing all 210
    countries again."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = _state_path(out_dir)
    tmp = path.parent / (path.name + ".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True))
    tmp.replace(path)


def _signature(country_shards: Sequence[partition.Shard]) -> list:
    """A country's identity: every member shard's (path, mtime, size).

    Not concatenate's (max mtime, count) pair: a country is a set of shards
    written by independent source runs, and a source that is dropped or moved
    changes neither of those two numbers reliably."""
    out = []
    for shard in sorted(country_shards, key=lambda s: s.key):
        try:
            stat = shard.path.stat()
        except OSError:  # vanished between select and here — treat as changed
            return []
        out.append([str(shard.path), stat.st_mtime, stat.st_size])
    return out


def prepared_path(key: Sequence[str], out_dir: Optional[Path] = None) -> Path:
    """`_prepared/<region>/<subregion>/<country>.parquet` for a country key."""
    out_dir = out_dir or PREPARED_DIR
    region, subregion, country = key
    return out_dir / region / subregion / f"{country}.parquet"


# Shard bytes above which a country is prepared through the disk-backed
# shuffle instead of as one resident frame.
#
# The country grain bounds the peak at the largest country, and japan is bigger
# than the box: 4.64 GB of shard over 52.0M rows, and every shard measured
# costs ~1 KB per raw row resident, so that frame is ~52 GB against 26 GB of
# RAM. `partition.EXPANSION` cannot fix it -- `admits()` returns True for any
# unit when the pool is idle, precisely so an oversized unit is not refused
# forever, so japan is handed to a worker whatever the budget says and the
# worker dies. The unit has to get smaller, and it cannot get smaller by
# splitting the COUNTRY (see the module docstring), so it gets smaller by
# splitting the HASH.
#
# 256 MB is where the bucketed path starts paying for itself. It is not free:
# every raw row makes a round trip through a parquet part on disk, so the 197
# countries below the threshold stay on the direct path and the 13 above it --
# japan, taiwan, uk, germany, turkiye, ukraine, russia, korea, chile, india,
# philippines, pakistan, australia -- take the shuffle.
STREAM_ABOVE_BYTES = 256 << 20


def _spill_dir(out_dir: Path, key: Sequence[str]) -> Path:
    """Pass-1 scratch for one country, a SIBLING of the prepared tree.

    Never inside it: `write_products_input` unions every parquet under
    `out_dir`, so a shuffle part left behind by a worker that died mid-pass
    would be unioned into products_input.parquet as though it were a prepared
    country. One directory per country, because two countries shuffling into
    one directory would read each other's parts."""
    return out_dir.parent / f"{out_dir.name}_spill" / "-".join(key)


def prepare_country(
    country_shards: Sequence[partition.Shard],
    key: Sequence[str],
    out_dir: Optional[Path] = None,
    stream_above: int = STREAM_ABOVE_BYTES,
) -> Path:
    """Prepare one country's shards into one parquet.

    A country over `stream_above` is shuffled to disk by `input_hash` and
    aggregated one bucket at a time. The grouping stays EXACT because the
    buckets partition the hash rather than the corpus: every row sharing an
    `input_hash` lands in the same bucket, so `_aggregate` still sees a whole
    group at once, which is what `price=median` and `_modal_or_empty` need and
    what a split by source would not give.
    """
    out_dir = out_dir or PREPARED_DIR
    path = prepared_path(key, out_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    total = sum(s.size for s in country_shards)
    if total > stream_above:
        spill = _spill_dir(out_dir, key)
        try:
            n_prepared = prepare_input_streaming(
                shards.iter_batches(country_shards, columns=list(PREPARE_COLUMNS)),
                path,
                shuffle_dir=spill,
                verbose=False,
            )
        finally:
            shutil.rmtree(spill, ignore_errors=True)
        logger.info(
            "[prepare] %s: %.2f GB of shard over %d buckets -> %d prepared",
            "/".join(key),
            total / 1e9,
            SHUFFLE_BUCKETS,
            n_prepared,
        )
        return path
    raw = shards.read_shards(country_shards, columns=list(PREPARE_COLUMNS))
    prepared = prepare_input(raw)
    prepared.to_parquet(path, index=False)
    logger.info(
        "[prepare] %s: %d raw rows -> %d prepared",
        "/".join(key),
        len(raw),
        len(prepared),
    )
    return path


def _prepare_one(args: tuple) -> Path:
    country_shards, key, out_dir = args
    return prepare_country(country_shards, key, out_dir)


def write_products_input(
    out_dir: Optional[Path] = None, target: Optional[Path] = None
) -> Optional[Path]:
    """Union every prepared country into products_input.parquet, streamed.

    Every country on disk, not only the ones just recomputed — a scoped run
    overlays its countries onto the corpus rather than truncating it to the
    slice. Written row group by row group so the union never has to be
    resident, which the 7.1 GB whole-corpus frame currently is."""
    out_dir = out_dir or PREPARED_DIR
    target = target or config.PRODUCTS_INPUT_PARQUET
    paths = sorted(out_dir.rglob("*.parquet"))
    if not paths:
        logger.warning("[prepare] nothing prepared under %s", out_dir)
        return None

    schema = pa.unify_schemas([pq.read_schema(p) for p in paths])
    target.parent.mkdir(parents=True, exist_ok=True)
    n_rows = 0
    with pq.ParquetWriter(target, schema) as writer:
        for path in paths:
            table = pq.read_table(path).cast(schema)
            writer.write_table(table)
            n_rows += table.num_rows
    logger.info(
        "[prepare] wrote %s (%d rows from %d countries)", target, n_rows, len(paths)
    )
    return target


def run(
    selectors: Optional[Sequence[str]] = None,
    root: Optional[Path] = None,
    out_dir: Optional[Path] = None,
    workers: int = 1,
    write_union: bool = True,
    union_target: Optional[Path] = None,
    force: bool = False,
) -> list[Path]:
    """Prepare every selected country whose shards changed, largest first and
    bounded by memory. Returns the countries actually recomputed.

    Largest-first alone is what broke: `pool.map` over countries sorted by size
    starts the biggest ones together, and japan — 3.32 GB of shard, 13.3 GB
    resident once pandas has it — was OOM-killed 38 seconds into a 6-worker run,
    taking the pool down with it. Admission is therefore by bytes in flight, so
    japan runs alone and the long tail of small countries still fans out wide.

    `force` prepares every selected country regardless of the state file.
    """
    selected = partition.select(selectors, root)
    if not selected:
        logger.warning("[prepare] no shards matched %s", selectors)
        return []
    prepared_dir = out_dir or PREPARED_DIR
    groups = partition.group_by(selected, "country")
    state = _load_state(prepared_dir)
    # Countries outside this run keep their entry, exactly as concatenate
    # carries a selector-excluded source forward: dropping it would make the
    # next unscoped run redo everything the selector happened to miss.
    new_state = dict(state)

    jobs = []
    pending: dict[str, tuple[str, list]] = {}
    n_skipped = 0
    for key, group in sorted(groups.items()):
        name = "/".join(key)
        signature = _signature(group)
        if (
            not force
            and signature
            and state.get(name) == signature
            and prepared_path(key, out_dir).exists()
        ):
            n_skipped += 1
            continue
        pending[str(prepared_path(key, out_dir))] = (name, signature)
        jobs.append((sum(s.size for s in group), (group, key, out_dir)))

    budget = partition.memory_budget_bytes()
    logger.info(
        "[prepare] %d countries (%d unchanged), %d workers, %.2f GB in flight "
        "at once",
        len(jobs),
        n_skipped,
        workers,
        budget / 1e9,
    )

    def record(path: Path) -> None:
        """Recorded from what came back, not from what was queued, so a country
        whose worker died is prepared again next run rather than cached as
        done -- and recorded AS it comes back, not once the run is over, so a
        later country that kills the pool does not take the finished ones with
        it. That is not hypothetical: japan broke the pool and 210 prepared
        countries were recomputed from scratch, because this used to run two
        lines below a `run_budgeted` the exception went straight past."""
        entry = pending.get(str(path))
        if entry is not None:
            new_state[entry[0]] = entry[1]
            _save_state(prepared_dir, new_state)

    # PartialFailure propagates: a run that lost a country has to stop rather
    # than union a tree in which that country is missing or stale.
    written = partition.run_budgeted(
        jobs, _prepare_one, workers, budget, on_result=record
    )
    _save_state(prepared_dir, new_state)

    if write_union:
        write_products_input(out_dir, union_target)
    return written


def read_prepared(
    paths: Iterable[Path], columns: Optional[Sequence[str]] = None
) -> pd.DataFrame:
    """Union the prepared country parquets back into one frame."""
    frames = [
        pd.read_parquet(p, columns=list(columns) if columns else None) for p in paths
    ]
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def find_cross_country_urls(
    selectors: Optional[Sequence[str]] = None, root: Optional[Path] = None
) -> pd.DataFrame:
    """Product URLs occurring under more than one country — the only input on
    which per-country preparation differs from a whole-corpus one. Returns
    (product_url, n_countries, countries); an empty frame means the country
    grain is exact for this corpus."""
    seen: dict[str, set[str]] = {}
    for shard in partition.select(selectors, root):
        frame = shards.read_shard(shard.path, columns=["product_url", "country"])
        frame = frame[frame["product_url"].notna() & frame["product_url"].ne("")]
        for url, country in zip(frame["product_url"], frame["country"]):
            seen.setdefault(url, set()).add(country)
    rows = [
        {"product_url": url, "n_countries": len(cs), "countries": "|".join(sorted(cs))}
        for url, cs in seen.items()
        if len(cs) > 1
    ]
    return pd.DataFrame(
        rows, columns=["product_url", "n_countries", "countries"]
    ).sort_values("n_countries", ascending=False, ignore_index=True)
