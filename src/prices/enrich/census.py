"""Read-only SC5 census: shape × regex_id fire distribution over the corpus.

Runs `extract()` under the armed §9 match recorder over every unique product
name with `channel != "aggregator"` (aggregators bypass tier-a by design),
chunk-flushing so a ~1.1M-row corpus never retains all recorder events in RAM
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

NAME_COLUMN = "product_name_original"
CHANNEL_COLUMN = "channel"
EXCLUDED_CHANNEL = "aggregator"
CENSUS_PARQUET_NAME = "census_shape_regex.parquet"
DEFAULT_OUT_DIR = config.REPO_ROOT / ".planning" / "census"


def _load_population(names_or_df):
    """Coerce the input into a DataFrame carrying at least `product_name_original`.

    Accepts a DataFrame (returned as-is), a path to a parquet, or an iterable of
    raw product names.
    """
    import pandas as pd

    if isinstance(names_or_df, pd.DataFrame):
        return names_or_df
    if isinstance(names_or_df, (str, Path)):
        return pd.read_parquet(names_or_df)
    return pd.DataFrame({NAME_COLUMN: list(names_or_df)})


def _unique_names(df, limit=None):
    """Drop aggregator-channel rows, then the non-empty, order-preserving unique
    `product_name_original` values (optionally capped at `limit`)."""
    if CHANNEL_COLUMN in df.columns:
        df = df[df[CHANNEL_COLUMN] != EXCLUDED_CHANNEL]
    if NAME_COLUMN not in df.columns:
        return []
    seen = set()
    unique = []
    for name in df[NAME_COLUMN].dropna().astype(str):
        if not name.strip() or name in seen:
            continue
        seen.add(name)
        unique.append(name)
        if limit is not None and len(unique) >= limit:
            break
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

    df = _load_population(names_or_df)
    names = _unique_names(df, limit=limit)

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

    Reads config.PRODUCTS_PARQUET (dropping channel == "aggregator"), chunk-runs
    extract() under the §9 recorder, and writes the fire-distribution parquet to
    a gitignored scratch dir. Writes nothing under data/ or outputs/.
    """
    target = Path(out_dir) if out_dir else DEFAULT_OUT_DIR
    counter = run_census(config.PRODUCTS_PARQUET, out_dir=target, limit=limit)
    total = sum(counter.values())
    click.echo(f"census: {len(counter)} (shape, regex_id) pairs, {total} fires")
    click.echo(f"wrote {target / CENSUS_PARQUET_NAME}")
