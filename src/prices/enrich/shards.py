"""Reading and writing the per-source raw shards.

The shards are the pipeline's real unit of work; the 33 GB `raw_prices.csv`
monolith is only their concatenation. Writing them as Parquet under an explicit
schema removes the one thing CSV cannot express: a column's type. Today every
reader calls `pd.read_csv(..., low_memory=False)`, so pandas infers `price` per
file from its contents — the mechanism behind the x100 price corruption, since a
column of `"1.234"` infers as float where a column of `"R$ 1.234,56"` stays text.
Under this schema `price` is stored as the raw string it was scraped as, and
`parse_price` in the prepare stage remains the only thing that interprets it.

`date` is stored as raw text for the same reason: the corpus mixes ISO
timestamps with Common Crawl's compact `20251212100333`, and a single inferred
format silently coerces the other shape to null.

Reading is format-tolerant for the duration of the migration — a `.csv` shard is
read with every column pinned to text, so it lands in memory identically to a
`.parquet` one.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Iterator, Optional, Sequence

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

# The 15 raw columns concatenate emits, in order. Every one is text except
# `wayback`, which is a provenance flag the emitters set as a real bool.
BOOL_COLUMNS = ("wayback",)
SHARD_COLUMNS = (
    "url_hash",
    "product_name",
    "price",
    "currency",
    "country",
    "source",
    "date",
    "product_url",
    "product_id",
    "region",
    "subregion",
    "wayback",
    "channel",
    "category",
    "details",
)

SHARD_SCHEMA = pa.schema(
    [
        pa.field(name, pa.bool_() if name in BOOL_COLUMNS else pa.string())
        for name in SHARD_COLUMNS
    ]
)


def _as_text(series: pd.Series) -> pd.Series:
    """Text, with missing values preserved as None rather than the string
    "nan". `astype(str)` would turn a float NaN into "nan" and a float 12.0
    into "12.0"; only the first of those is wrong, and it is wrong silently."""
    return series.map(lambda v: None if pd.isna(v) else str(v)).astype(object)


def _as_bool(series: pd.Series) -> pd.Series:
    def one(value):
        if pd.isna(value):
            return None
        if isinstance(value, str):
            return value.strip().lower() in {"true", "1", "yes", "t"}
        return bool(value)

    return series.map(one).astype(object)


def coerce(df: pd.DataFrame) -> pd.DataFrame:
    """Return `df` with exactly SHARD_COLUMNS, in order, at shard dtypes.
    Columns absent from the frame are added empty."""
    out = pd.DataFrame(index=df.index)
    for name in SHARD_COLUMNS:
        if name not in df.columns:
            out[name] = None
            continue
        out[name] = _as_bool(df[name]) if name in BOOL_COLUMNS else _as_text(df[name])
    return out


def write_shard(df: pd.DataFrame, path: Path) -> Path:
    """Write one shard as Parquet under SHARD_SCHEMA. The schema is passed to
    pyarrow explicitly, so a frame that cannot be expressed under it raises here
    rather than being written at an inferred type."""
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(coerce(df), schema=SHARD_SCHEMA, preserve_index=False)
    pq.write_table(table, path, compression="zstd")
    return path


def read_shard(path: Path, columns: Optional[Sequence[str]] = None) -> pd.DataFrame:
    """Read one shard. Parquet and CSV land in memory identically: for CSV every
    column is pinned to text on the way in, so no per-file inference happens."""
    wanted = list(columns) if columns else list(SHARD_COLUMNS)
    if path.suffix == ".parquet":
        table = pq.read_table(path, columns=wanted)
        df = table.to_pandas()
    else:
        df = pd.read_csv(
            path,
            dtype=str,
            keep_default_na=True,
            na_filter=True,
            low_memory=False,
        )
        for name in wanted:
            if name not in df.columns:
                df[name] = None
        df = df[wanted]
        for name in wanted:
            # read_csv yields float NaN for a missing cell where parquet yields
            # None. Both are null to pd.isna, but only one of them survives
            # str() intact, so normalise here rather than at every reader.
            df[name] = (
                _as_bool(df[name]) if name in BOOL_COLUMNS else _as_text(df[name])
            )
    return df.reset_index(drop=True)


def iter_frames(
    shards: Iterable, columns: Optional[Sequence[str]] = None
) -> Iterator[pd.DataFrame]:
    """One frame per shard, read lazily. The point of the shards is that the
    whole corpus never has to be resident at once; anything that concatenates
    them all is back to the monolith by another name."""
    for shard in shards:
        path = shard.path if hasattr(shard, "path") else Path(shard)
        yield read_shard(path, columns=columns)


def read_shards(
    shards: Iterable, columns: Optional[Sequence[str]] = None
) -> pd.DataFrame:
    """Every shard as one frame. Only for slices small enough to hold."""
    frames = [f for f in iter_frames(shards, columns=columns) if not f.empty]
    if not frames:
        cols = list(columns) if columns else list(SHARD_COLUMNS)
        return pd.DataFrame({c: pd.Series(dtype=object) for c in cols})
    return pd.concat(frames, ignore_index=True)
