"""The decisions and classified tables as one parquet part per country.

A single-file decisions table makes every run a whole-corpus run. The rows are
independent per country -- `decide_rows` reads nothing across country lines --
so the only thing forcing a 37.4M-row rewrite to fix one country was the file
layout. One part per country removes that: a scoped run rewrites its own parts
and leaves the rest of the corpus untouched on disk.

Reading is unchanged for consumers. `pd.read_parquet` on a directory unions the
parts, so `coverage.py` and `prices build` keep the call they already make; the
only thing they must tolerate is being handed a directory where a file used to
be, which `read` below normalizes.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Optional, Sequence

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

# Country values reach us straight from the corpus, so they are not guaranteed
# to be filename-safe -- or even present. Everything outside this set collapses
# to `_`, and a missing country lands in one explicit part rather than being
# dropped: an unattributed row still belongs in the coverage denominator.
_SAFE = re.compile(r"[^A-Za-z0-9_.-]+")
UNKNOWN_COUNTRY = "_unknown"


def parts_root(path: Path) -> Path:
    """The directory that replaces a legacy single-file table.

    `.../decisions_hierlex.parquet` -> `.../decisions_hierlex/`. Derived rather
    than configured so the two can never drift apart, and so a caller holding
    the old path can always find the new one.
    """
    path = Path(path)
    return path.parent / path.name[: -len(path.suffix)] if path.suffix else path


def part_name(country) -> str:
    """Filename stem for one country's part."""
    if country is None or (isinstance(country, float) and pd.isna(country)):
        return UNKNOWN_COUNTRY
    text = _SAFE.sub("_", str(country).strip())
    return text or UNKNOWN_COUNTRY


def part_path(root: Path, country) -> Path:
    return Path(root) / f"{part_name(country)}.parquet"


def existing_countries(root: Path) -> set[str]:
    """Part stems already on disk. This is what makes a scoped run additive:
    the parts it does not write are the ones it must not touch."""
    root = Path(root)
    if not root.is_dir():
        return set()
    return {p.stem for p in root.glob("*.parquet")}


class PartitionedWriter:
    """Route frames to one open parquet writer per country.

    The decide loop streams chunks that are not country-sorted, so a country's
    rows arrive spread across many chunks. Holding one writer per country lets
    that happen in a single pass over the corpus instead of one pass per
    country -- which, on a file whose row groups are only *mostly* clustered by
    country, is the difference between one scan and two hundred.

    Parts are written to `.tmp` and renamed on close, so a killed run leaves the
    previous parts intact rather than a half-written one that reads as real.
    """

    def __init__(self, root: Path, schema: pa.Schema):
        self.root = Path(root)
        self.schema = schema
        self.root.mkdir(parents=True, exist_ok=True)
        self._writers: dict[str, pq.ParquetWriter] = {}
        self._tmp: dict[str, Path] = {}
        self.rows_by_country: dict[str, int] = {}

    def write(
        self,
        frame: pd.DataFrame,
        country_col: str = "country",
        countries: Optional[pd.Series] = None,
    ) -> None:
        """Append `frame`, split by country.

        `countries` lets the caller partition by a country the frame does not
        itself carry. `classified.parquet` is the case that needs it: its column
        list is a contract `prices build` reads, so the partition key is passed
        alongside rather than added to the table.
        """
        if frame.empty:
            return
        key = (countries if countries is not None else frame[country_col]).map(
            part_name
        )
        # Project to the declared schema so an extra partition-key column, or a
        # column order that drifted, cannot reach the writer as a cast error
        # thousands of chunks into a run.
        cols = [c for c in self.schema.names if c in frame.columns]
        for country, idx in frame.groupby(key.values, sort=False).groups.items():
            group = frame.loc[idx, cols]
            table = pa.Table.from_pandas(
                group, schema=self.schema, preserve_index=False
            )
            self._writer_for(country).write_table(table)
            self.rows_by_country[country] = self.rows_by_country.get(country, 0) + len(
                group
            )

    def _writer_for(self, name: str) -> pq.ParquetWriter:
        writer = self._writers.get(name)
        if writer is None:
            tmp = self.root / f"{name}.parquet.tmp"
            writer = pq.ParquetWriter(tmp, self.schema)
            self._writers[name] = writer
            self._tmp[name] = tmp
        return writer

    def close(self) -> list[Path]:
        """Close every writer and publish its part. Returns the paths written."""
        written = []
        for name, writer in self._writers.items():
            writer.close()
            final = self.root / f"{name}.parquet"
            self._tmp[name].replace(final)
            written.append(final)
        self._writers.clear()
        self._tmp.clear()
        return written

    def abort(self) -> None:
        """Drop the in-progress parts without publishing them."""
        for name, writer in self._writers.items():
            try:
                writer.close()
            finally:
                self._tmp[name].unlink(missing_ok=True)
        self._writers.clear()
        self._tmp.clear()

    def __enter__(self) -> "PartitionedWriter":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is None:
            self.close()
        else:
            self.abort()


def split_by_country(frame: pd.DataFrame, countries: pd.Series):
    """Yield `(part_stem, sub_frame)` for a frame keyed by a separate series.

    `countries` is positional, not label-aligned: `classified_view` resets its
    index while the decisions frame it came from keeps the chunk's, so joining
    them on labels would pair the wrong rows.
    """
    if frame.empty:
        return
    key = pd.Series(list(countries), index=frame.index).map(part_name)
    for name, idx in frame.groupby(key.values, sort=False).groups.items():
        yield str(name), frame.loc[idx]


def write_pandas_parts(
    frames_by_country: "dict[str, list[pd.DataFrame]]", root: Path
) -> list[Path]:
    """Write one part per country with pandas, replacing any part already there.

    Pandas rather than a declared arrow schema on purpose: `classified.parquet`
    has always been written this way and `prices build` reads its dtypes, so
    changing the layout must not quietly change `count` from int64 to float64.
    """
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    written = []
    for country, parts in frames_by_country.items():
        frame = parts[0] if len(parts) == 1 else pd.concat(parts, ignore_index=True)
        final = root / f"{country}.parquet"
        tmp = final.with_suffix(".parquet.tmp")
        frame.to_parquet(tmp, index=False)
        tmp.replace(final)
        written.append(final)
    return written


def prune(root: Path, keep: Iterable[str]) -> list[Path]:
    """Drop parts not in `keep`. Only a full run may call this.

    A country that stops producing rows would otherwise keep the part it wrote
    last time, and a stale part reads exactly like a live one. A SCOPED run must
    never prune: everything it did not write is simply out of its scope.
    """
    root = Path(root)
    if not root.is_dir():
        return []
    keep = set(keep)
    dropped = []
    for path in sorted(root.glob("*.parquet")):
        if path.stem not in keep:
            path.unlink()
            dropped.append(path)
    return dropped


def read(
    path: Path,
    columns: Optional[Sequence[str]] = None,
    countries: Optional[Iterable[str]] = None,
) -> pd.DataFrame:
    """Read a partitioned table, or the legacy single file, into one frame.

    `path` may name either the directory or the old `.parquet`; whichever the
    caller has, the other is found. Preferring the directory when both exist is
    deliberate -- after a migration the single file is stale by definition, and
    silently reading it would undo the port.
    """
    path = Path(path)
    root = parts_root(path)
    if root.is_dir():
        if countries is not None:
            wanted = {part_name(c) for c in countries}
            paths = sorted(p for p in root.glob("*.parquet") if p.stem in wanted)
        else:
            paths = sorted(root.glob("*.parquet"))
        if not paths:
            return pd.DataFrame(columns=list(columns) if columns else None)
        frames = [pd.read_parquet(p, columns=columns) for p in paths]
        return pd.concat(frames, ignore_index=True)
    if path.is_file():
        return pd.read_parquet(path, columns=columns)
    return pd.DataFrame(columns=list(columns) if columns else None)


def row_count(path: Path) -> int:
    """Total rows without materializing anything, for logging and assertions."""
    path = Path(path)
    root = parts_root(path)
    if root.is_dir():
        return sum(pq.ParquetFile(p).metadata.num_rows for p in root.glob("*.parquet"))
    if path.is_file():
        return pq.ParquetFile(path).metadata.num_rows
    return 0
