"""Read-only SC5 census: shape × regex_id fire distribution over the corpus.

Runs `extract()` under the armed §9 match recorder over every unique product
name whose `channel` is not in EXCLUDED_CHANNELS — `marketplace` (seller-
authored, long-tail names are unreliable tier-a input) and `real-estate`
(property listings, not products at all); `aggregator` is kept for corpus
snapshots written before the 2026-08-05 retag split it into those two values
plus `channel: null`. Chunk-flushing so a ~1.1M-row corpus never retains all
recorder events in RAM
(Pitfall 3). Each chunk arms the recorder into a throwaway shard dir, flushes,
reads the shard's `residual_log` (carries the Phase-1.65 `shape`) and
`match_log_long` (carries `regex_id`), tallies a running `(shape, regex_id)`
Counter, then discards the shard. After all chunks it writes a long-format
`census_shape_regex.parquet` to a gitignored scratch dir.

Data safety (CLAUDE.md): the population parquet is read READ-ONLY; per-chunk
shards live under the system temp dir; the only durable write is the census
parquet under `.planning/census/` (gitignored). Nothing under `data/` or
`outputs/` is ever created or modified.
"""

from __future__ import annotations

import shutil
import tempfile
from collections import Counter
from pathlib import Path

import click

from prices.enrich import config, match_record
from prices.enrich.extract import extract

NAME_CANDIDATES = ("product_name_original", "first_name")
NAME_COLUMN = NAME_CANDIDATES[0]
CHANNEL_COLUMN = "channel"
# `aggregator` was split into `marketplace` / `real-estate` / null on 2026-08-05.
# `marketplace` inherits the rationale — seller-authored names are unreliable
# input for tier-a. `real-estate` is excluded too: property-listing titles are
# not products and confirmed (read-only) to reach products_input.parquet via
# spiders like propertyguru_my / lamudi_ph / realestate_co_nz. The retired
# value is kept so this filter still applies to corpus snapshots written
# before the retag.
EXCLUDED_CHANNELS = frozenset({"marketplace", "real-estate", "aggregator"})
CENSUS_PARQUET_NAME = "census_shape_regex.parquet"
DEFAULT_OUT_DIR = config.REPO_ROOT / ".planning" / "census"


def _load_population(names_or_df):
    """Coerce the input into a DataFrame carrying at least `product_name_original`.

    Accepts a DataFrame (returned as-is) or an iterable of raw product names. A
    parquet path does NOT come through here any more — `run_census` streams it
    through `_unique_names_streaming` instead, for the reason recorded there.
    """
    import pandas as pd

    if isinstance(names_or_df, pd.DataFrame):
        return names_or_df
    return pd.DataFrame({NAME_COLUMN: list(names_or_df)})


def _unique_names(df, limit=None):
    """Drop excluded-channel rows (see EXCLUDED_CHANNELS), then the non-empty,
    order-preserving unique `product_name_original` values (optionally capped
    at `limit`)."""
    if CHANNEL_COLUMN in df.columns:
        df = df[~df[CHANNEL_COLUMN].isin(EXCLUDED_CHANNELS)]
    name_col = next((c for c in NAME_CANDIDATES if c in df.columns), None)
    if name_col is None:
        return []
    seen = set()
    unique = []
    for name in df[name_col].dropna().astype(str):
        if not name.strip() or name in seen:
            continue
        seen.add(name)
        unique.append(name)
        if limit is not None and len(unique) >= limit:
            break
    return unique


def _unique_names_streaming(path, limit=None):
    """`_unique_names` over a parquet, without the frame ever being resident.

    `pd.read_parquet` on the population took 27 GB of anon memory against 26 GB
    of RAM and was OOM-killed before a single name reached `extract()`. `--limit`
    could not help: it was applied to the frame AFTER the read, so every limit
    died identically. Census was written against the ~1.1M-row corpus in the
    module docstring and the corpus is 48.5M rows now, 44x that.

    So: the two columns this function actually reads, row group by row group,
    stopping the moment `limit` unique names are in hand. The result is the same
    order-preserving, non-empty, channel-filtered list `_unique_names` returns.
    """
    import pyarrow.parquet as pq

    handle = pq.ParquetFile(path)
    present = set(handle.schema_arrow.names)
    name_col = next((c for c in NAME_CANDIDATES if c in present), None)
    if name_col is None:
        return []
    has_channel = CHANNEL_COLUMN in present
    columns = [name_col] + ([CHANNEL_COLUMN] if has_channel else [])

    seen: set = set()
    unique: list = []
    for batch in handle.iter_batches(batch_size=1 << 17, columns=columns):
        names = batch.column(name_col).to_pylist()
        channels = (
            batch.column(CHANNEL_COLUMN).to_pylist()
            if has_channel
            else (None,) * len(names)
        )
        for name, channel in zip(names, channels):
            if name is None or channel in EXCLUDED_CHANNELS:
                continue
            name = str(name)
            if not name.strip() or name in seen:
                continue
            seen.add(name)
            unique.append(name)
            if limit is not None and len(unique) >= limit:
                return unique
    return unique


def _chunks(seq, size):
    for start in range(0, len(seq), size):
        yield seq[start : start + size]


def _tally(residual, match_df, counter):
    """Fold one shard's logs into the running `(shape, regex_id)` Counter."""
    shape_by_row = dict(zip(residual["row_id"], residual["shape"]))
    for row_id, regex_id in zip(match_df["row_id"], match_df["regex_id"]):
        counter[(shape_by_row.get(row_id), regex_id)] += 1


def _run_chunk(chunk, base_row_id, counter):
    """Arm the recorder into a temp shard, run extract() over the chunk, flush,
    tally `(shape, regex_id)` into `counter`, then delete the shard."""
    import pandas as pd

    shard = Path(tempfile.mkdtemp(prefix="census_shard_"))
    try:
        match_record.enable(out_dir=shard)
        try:
            for offset, name in enumerate(chunk):
                row_id = base_row_id + offset
                match_record.begin_row(row_id, name, name, None, "")
                tier_a = extract(item_name=name, category=None, country=None, lang=None)
                match_record.end_row(tier_a)
            match_record.flush(out_dir=shard)
        finally:
            match_record.disable()

        residual = pd.read_parquet(shard / "residual_log.parquet")
        match_df = pd.read_parquet(shard / "match_log_long.parquet")
        _tally(residual, match_df, counter)
    finally:
        shutil.rmtree(shard, ignore_errors=True)


def run_census(names_or_df, out_dir=None, chunk_size=50_000, limit=None):
    """Chunk-aggregate the shape × regex_id fire distribution over the corpus.

    `names_or_df` is a DataFrame, a parquet path, or an iterable of names.
    Writes `census_shape_regex.parquet` (columns: shape, regex_id, fire_count)
    to `out_dir` (default `.planning/census/`) and returns the `(shape,
    regex_id) -> fire_count` Counter. Read-only on the population; never touches
    `data/` or `outputs/`.
    """
    import pandas as pd

    if isinstance(names_or_df, (str, Path)):
        names = _unique_names_streaming(names_or_df, limit=limit)
    else:
        names = _unique_names(_load_population(names_or_df), limit=limit)

    target = Path(out_dir) if out_dir is not None else DEFAULT_OUT_DIR
    target.mkdir(parents=True, exist_ok=True)

    counter: Counter = Counter()
    base = 0
    for chunk in _chunks(names, chunk_size):
        _run_chunk(chunk, base, counter)
        base += len(chunk)

    rows = [
        {"shape": shape, "regex_id": regex_id, "fire_count": count}
        for (shape, regex_id), count in counter.items()
    ]
    out_df = pd.DataFrame(rows, columns=["shape", "regex_id", "fire_count"])
    out_df.to_parquet(target / CENSUS_PARQUET_NAME, index=False)
    return counter


@click.command(name="census")
@click.option(
    "--out",
    "out_dir",
    type=click.Path(file_okay=False),
    default=None,
    help="Output dir for census_shape_regex.parquet (default: .planning/census/).",
)
@click.option(
    "--limit",
    type=int,
    default=None,
    help="Cap the number of unique product names (quick runs).",
)
def census_command(out_dir, limit):
    """Run the read-only shape × regex_id census over the deduped corpus.

    Reads config.PRODUCTS_INPUT_PARQUET (dropping EXCLUDED_CHANNELS rows),
    chunk-runs extract() under the §9 recorder, and writes the fire-distribution
    parquet to a gitignored scratch dir. Writes nothing under data/ or outputs/.
    """
    target = Path(out_dir) if out_dir else DEFAULT_OUT_DIR
    counter = run_census(config.PRODUCTS_INPUT_PARQUET, out_dir=target, limit=limit)
    total = sum(counter.values())
    click.echo(f"census: {len(counter)} (shape, regex_id) pairs, {total} fires")
    click.echo(f"wrote {target / CENSUS_PARQUET_NAME}")
