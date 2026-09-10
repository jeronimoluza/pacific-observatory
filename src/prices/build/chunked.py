"""Country-partitioned observations build, for when the whole frame will not fit.

The unchunked path in `aggregate.build_observations` holds the joined frame twice
at two separate moments -- once when `pd.concat` materialises its output
alongside the pieces it consumed, and again for each of the five `.copy()` steps
chained inside `_finalize`. Measured on the 2026-09 corpus that frame is 17.16 GB
over 19,170,915 rows (895 B/row), so either doubling overruns a 27 GB box: the
kernel killed the 2026-09-10 build inside `_finalize` at 26.9 GB anon-rss, one
line after the date floor logged.

This module does the same work one country at a time. Country is the EXACT
partition key rather than merely a convenient one, because every grouping
downstream of the join is contained within a single country:

  * ``flag_uv_outliers``         groups on (coicop_code, country, standard_unit)
  * ``build_unit_value_summary`` groups on SUMMARY_KEYS, which carries country
  * ``build_analytical``         groups on GRAIN, which carries country
  * ``compute_qa``               is row-wise

so a chunked run and a whole-frame run see identical groups, and the split
changes peak memory without changing a single output value.

The two things that are NOT per-country are handled explicitly rather than left
to chance. Both would fail silently -- producing a plausible number computed
against the wrong population -- which is the only failure mode here worth real
fear:

  * ``derive_typical_mass`` groups by coicop_code ACROSS every country. Derived
    per chunk, a leaf's typical mass would come from one country's rows. It is
    derived once up front over a narrow projection and then PINNED for every
    chunk, which is the mechanism ``convert_item_rows`` already offers scoped
    builds for exactly this reason.
  * ``build_analytical`` anchors its trailing window on the GLOBAL maximum
    observation date. Chunked, each country would anchor on its own last month
    and quietly summarise a different window than the whole-frame run did. The
    anchor is computed once in a cheap two-column pre-pass and passed in.

Parallelism reuses ``partition.admits`` / ``partition.run_budgeted`` rather than
growing a second admission rule. The country units are as brutally skewed as the
shard units that scheduler was written for -- japan is 10.8% of all rows against
a median country in the low MB -- so a pool sized on cores is the version that
OOMs, and a pool sized on bytes in flight runs the small countries wide and
japan alone.
"""

from __future__ import annotations

import functools
import logging
import shutil
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from prices import partition

logger = logging.getLogger(__name__)

# On-disk parquet bytes -> peak resident bytes for ONE country inside `_finalize`.
#
# Deliberately not `partition.EXPANSION` (12), which is calibrated for the join,
# where a shard is read and merged once. This stage is heavier on both counts.
# Measured on the 2026-09 corpus: japan is 2,074,553 rows, 1.86 GB resident once
# finalized (895 B/row deep) against roughly 124 MB of parquet -- about 15x from
# compression and object-dtype strings alone -- and `_finalize` then chains five
# steps that each hold their input and their output at the same time, so the
# peak is a further ~2.4x on top. 36 is that product, rounded up.
#
# Wrong in the safe direction on purpose: too high costs wall clock, too low
# costs the run.
_FINALIZE_EXPANSION = 36

# Leave this much of MemAvailable unspent regardless of the arithmetic. The
# parent still holds open writers, the pool's own bookkeeping, and whatever the
# allocator has not returned to the OS.
_FINALIZE_HEADROOM_BYTES = 3 << 30

# Set in each pool worker by the initializer, so the pinned mass table is read
# once per worker instead of pickled once per country.
_PINNED_MASS: pd.DataFrame | None = None


def _init_finalize_worker(mass_csv: str | None) -> None:
    global _PINNED_MASS  # noqa: PLW0603
    _PINNED_MASS = None if mass_csv is None else pd.read_csv(mass_csv)


def _finalize_budget_bytes() -> int:
    """On-disk bytes of country part allowed in flight across the pool at once.

    Read from MemAvailable for the same reason `_plan_join_workers` does: this
    box has been OOM-killed by a pool sized on core count while the arithmetic
    on memory said a much smaller number.
    """
    try:
        with open("/proc/meminfo") as fh:
            avail = next(
                int(line.split()[1]) * 1024
                for line in fh
                if line.startswith("MemAvailable:")
            )
    except (OSError, StopIteration):
        avail = 8 << 30
    usable = max(1 << 30, avail - _FINALIZE_HEADROOM_BYTES)
    return max(1 << 20, usable // _FINALIZE_EXPANSION)


def _normalized_schema(df: pd.DataFrame) -> pa.Schema:
    """Arrow schema for `df`, with all-null columns pinned to string.

    A column that happens to be entirely null in the FIRST piece infers as arrow
    `null`, and every later piece that carries real values for it then fails to
    convert. Pinning those to string keeps the reference schema usable; a column
    that is genuinely null everywhere lands as an all-null string column, which
    is what the unchunked path's object dtype would have produced anyway.
    """
    schema = pa.Table.from_pandas(df, preserve_index=False).schema
    fields = [
        pa.field(f.name, pa.string(), nullable=True)
        if pa.types.is_null(f.type)
        else f
        for f in schema
    ]
    return pa.schema(fields)


# --------------------------------------------------------------------------
# phase 1 -- spill
# --------------------------------------------------------------------------


def spill_by_country(pieces: list[pd.DataFrame], parts_dir: Path) -> dict[str, int]:
    """Write the joined pieces out per country, freeing each piece as it lands.

    This replaces `pd.concat(pieces)`, the first of the two places the full frame
    exists twice at once. Nothing here holds more than the pieces still queued
    plus the one being written, and the queue drains as it goes -- `pieces` is
    POPPED, not iterated, so the caller's list is consumed and each piece's
    memory is released at once rather than at the end of the loop.

    One open ParquetWriter per country, so the row-group count grows with the
    number of pieces while the file count stays at one per country. Buffering
    each country in memory until it were whole would rebuild exactly the frame
    this function exists to avoid.

    The rename and the date floor move in here from the caller because they are
    row-wise: doing them per piece costs the same and keeps the floor's dropped
    rows from ever occupying a partition file.
    """
    from prices.build.aggregate import FX_HISTORY_FLOOR  # noqa: PLC0415

    parts_dir.mkdir(parents=True, exist_ok=True)
    writers: dict[str, pq.ParquetWriter] = {}
    counts: dict[str, int] = {}
    ref_schema: pa.Schema | None = None
    kept = dropped = 0

    try:
        while pieces:
            piece = pieces.pop()
            piece = piece.rename(columns={"date": "observation_date"})
            # format="mixed" (not "ISO8601") for the reason the unchunked path
            # spells out: sources write RFC 2822, compact numeric and ISO dates,
            # and ISO8601 coerces the rest to NaT, which the floor below then
            # drops silently.
            piece["observation_date"] = pd.to_datetime(
                piece["observation_date"], errors="coerce", utc=True, format="mixed"
            ).dt.tz_localize(None)
            before = len(piece)
            piece = piece[piece["observation_date"] >= FX_HISTORY_FLOOR]
            dropped += before - len(piece)
            kept += len(piece)
            if piece.empty:
                del piece
                continue

            # Taken from the whole piece, not from the first country slice: a
            # slice is small enough that an all-null column is likely, and the
            # reference schema is what every later piece must fit.
            if ref_schema is None:
                ref_schema = _normalized_schema(piece)

            for country, part in piece.groupby("country", observed=True, sort=False):
                key = str(country)
                try:
                    table = pa.Table.from_pandas(
                        part, schema=ref_schema, preserve_index=False
                    )
                except (pa.ArrowInvalid, pa.ArrowTypeError, KeyError) as exc:
                    raise RuntimeError(
                        f"country {key}: a joined piece does not fit the schema the "
                        f"first piece established -- a column changed type between "
                        f"shards. Left alone this becomes a silently mistyped "
                        f"parquet column. Underlying error: {exc}"
                    ) from exc
                if key not in writers:
                    writers[key] = pq.ParquetWriter(
                        parts_dir / f"{key}.parquet", ref_schema
                    )
                writers[key].write_table(table)
                counts[key] = counts.get(key, 0) + len(part)
            del piece
    finally:
        for w in writers.values():
            w.close()

    logger.info(
        "[observations] spilled %d rows over %d countries to %s "
        "(date floor dropped %d)",
        kept,
        len(counts),
        parts_dir,
        dropped,
    )
    if not counts:
        raise RuntimeError("the join produced rows but none survived the date floor.")
    return counts


# --------------------------------------------------------------------------
# phase 2 -- the two quantities that are not per-country
# --------------------------------------------------------------------------


def derive_pinned_mass(parts_dir: Path) -> pd.DataFrame:
    """Derive the typical-mass table once, over every country, from a projection.

    `derive_typical_mass` groups by coicop_code across the whole corpus, so it
    cannot be computed per chunk without changing what it means. Reading only
    the columns it consumes keeps this pass at a small fraction of the frame.
    """
    from prices.build.leaf_typical_mass import (  # noqa: PLC0415
        derive_typical_mass,
        write_typical_mass,
    )

    # Every column the derivation actually reaches, which is more than the
    # amount/unit gate suggests. `apply_ratio_gate` -> `leaf_price_ratios`
    # groups its derived/measured ratio BY COUNTRY, and `_local_price` falls
    # back to parsing `price` with `currency` when `price_local` is absent --
    # which it is here, because `_compute_unit_values` has not run yet. Omit
    # `country` and the ratio gate silently pools every country into one group;
    # omit `price`/`currency` and it finds no prices and demotes nothing.
    want = [
        "coicop_code",
        "pricing_basis",
        "amount_value",
        "standard_unit",
        "country",
        "price_local",
        "price",
        "currency",
        "count",
        "multiplier",
    ]
    parts = sorted(parts_dir.glob("*.parquet"))
    available = set(pq.ParquetFile(parts[0]).schema_arrow.names)
    cols = [c for c in want if c in available]
    projection = pd.concat(
        [pd.read_parquet(p, columns=cols) for p in parts], ignore_index=True
    )
    # `_require_unit` runs before `convert_item_rows` in `_finalize`, so the
    # unchunked build derives this table from unit-bearing rows only. Same
    # filter, spelled out rather than imported, because importing `_require_unit`
    # would pull the whole frame's columns through a `.copy()` for a two-column
    # dropna.
    before = len(projection)
    projection = projection.dropna(subset=["coicop_code", "standard_unit"])
    logger.info(
        "[observations] deriving typical mass over %d rows x %d columns "
        "(unit filter dropped %d)",
        len(projection),
        len(cols),
        before - len(projection),
    )
    table = derive_typical_mass(projection)
    del projection
    write_typical_mass(table)
    logger.info("[observations] pinned typical-mass table: %d leaves", len(table))
    return table


def global_anchor(final_dir: Path) -> pd.Period | None:
    """The trailing-window anchor `build_analytical` would have used whole-frame.

    Two columns over every finalized part. Computed here so each country chunk
    summarises the SAME months the unchunked run would have, rather than
    anchoring on its own last observation -- which is the difference between a
    trailing-3-month figure and a per-country "last 3 months it happened to have
    data", and nothing downstream would have flagged the substitution.
    """
    best: pd.Timestamp | None = None
    for p in sorted(final_dir.glob("*.parquet")):
        cols = set(pq.ParquetFile(p).schema_arrow.names)
        if "observation_date" not in cols or "qa_status" not in cols:
            continue
        chunk = pd.read_parquet(p, columns=["observation_date", "qa_status"])
        chunk = chunk[chunk["qa_status"] == "trusted"]
        if chunk.empty:
            continue
        d = pd.to_datetime(chunk["observation_date"], errors="coerce").max()
        if pd.notna(d) and (best is None or d > best):
            best = d
    return None if best is None else best.to_period("M")


# --------------------------------------------------------------------------
# phase 3 -- finalize, in parallel
# --------------------------------------------------------------------------


def _finalize_one(payload: tuple[str, str, str]) -> tuple[str, str, int]:
    """Finalize one country's part. Runs in a pool worker.

    Returns paths and counts, never frames: a finalized country crossing the
    process boundary would be pickled into the parent, which is precisely the
    memory this module exists not to spend.
    """
    from prices.build.aggregate import _finalize  # noqa: PLC0415

    country, src, dst = payload
    df = pd.read_parquet(src)
    out = _finalize(df, typical_mass=_PINNED_MASS)
    del df
    out.to_parquet(dst, index=False)
    n = len(out)
    del out
    return country, dst, n


def _plan_finalize_workers(requested: int, budget: int, biggest: int) -> int:
    """How many finalize workers to run, which is NOT the join's worker count.

    `--workers` documents itself as the shard pool for the observations JOIN,
    and the two stages have different shapes: the join is bound by reading
    parquet, this one by pandas holding a country frame and its copies. A `1`
    there is the CLI default and says nothing about this stage, so taking it
    literally would serialise the part of the build that most wants the cores.

    PRICES_FINALIZE_WORKERS overrides outright. Otherwise plan from cores and
    from how many of the LARGEST unit fit in the budget -- `run_budgeted` then
    enforces the same budget per unit anyway, so this number is an upper bound
    on concurrency rather than a promise about it.
    """
    import os  # noqa: PLC0415

    override = os.environ.get("PRICES_FINALIZE_WORKERS")
    if override:
        return max(1, int(override))
    cores = os.cpu_count() or 4
    by_budget = int(budget // biggest) if biggest > 0 else cores
    return max(1, min(cores - 2, by_budget if by_budget > 0 else 1, 8))


def finalize_parts(
    parts_dir: Path,
    final_dir: Path,
    mass_csv: Path | None,
    workers: int,
) -> list[Path]:
    """Run `_finalize` over every country part, admitting work by bytes in flight."""
    final_dir.mkdir(parents=True, exist_ok=True)
    jobs = []
    for src in sorted(parts_dir.glob("*.parquet")):
        country = src.stem
        dst = final_dir / f"{country}.parquet"
        jobs.append((src.stat().st_size, (country, str(src), str(dst))))
    if not jobs:
        raise RuntimeError(f"no country parts to finalize under {parts_dir}")

    budget = _finalize_budget_bytes()
    biggest = max(j[0] for j in jobs)
    workers = _plan_finalize_workers(workers, budget, biggest)
    logger.info(
        "[observations] finalizing %d countries with %d workers; budget %.2f GB "
        "on disk (~%.1f GB resident), largest part %.2f GB on disk "
        "(~%.1f GB resident)",
        len(jobs),
        workers,
        budget / 1e9,
        budget * _FINALIZE_EXPANSION / 1e9,
        biggest / 1e9,
        biggest * _FINALIZE_EXPANSION / 1e9,
    )

    done: list[Path] = []
    total = {"rows": 0}

    def landed(result: tuple[str, str, int]) -> None:
        _country, dst, n = result
        done.append(Path(dst))
        total["rows"] += n
        if len(done) % 20 == 0 or len(done) == len(jobs):
            logger.info(
                "[observations] finalized %d/%d countries; %d rows",
                len(done),
                len(jobs),
                total["rows"],
            )

    partition.run_budgeted(
        jobs,
        _finalize_one,
        workers,
        budget,
        # `run_budgeted` passes no initargs, so the argument is bound here. A
        # partial over a module-level function stays picklable, which a closure
        # would not.
        initializer=functools.partial(
            _init_finalize_worker, str(mass_csv) if mass_csv else None
        ),
        on_result=landed,
    )
    return sorted(done)


# --------------------------------------------------------------------------
# phase 4 -- stream out
# --------------------------------------------------------------------------


def stream_concat(paths: list[Path], out_path: Path) -> int:
    """Write one parquet from many, a batch at a time.

    `pd.concat` then `to_parquet` would rebuild the 17 GB frame at the last
    possible moment, having spent the whole run avoiding it.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    writer: pq.ParquetWriter | None = None
    rows = 0
    try:
        for p in paths:
            pf = pq.ParquetFile(p)
            if pf.metadata.num_rows == 0:
                continue
            if writer is None:
                writer = pq.ParquetWriter(out_path, pf.schema_arrow)
            for batch in pf.iter_batches(batch_size=250_000):
                table = pa.Table.from_batches([batch])
                if table.schema != writer.schema:
                    table = table.cast(writer.schema)
                writer.write_table(table)
                rows += table.num_rows
    finally:
        if writer is not None:
            writer.close()
    if writer is None:
        raise RuntimeError(
            f"every finalized part was empty; nothing to write to {out_path}"
        )
    logger.info("wrote %s (%d rows)", out_path, rows)
    return rows


# --------------------------------------------------------------------------
# phase 5 -- consumables, same partitioning
# --------------------------------------------------------------------------


def write_consumables_chunked(
    final_paths: list[Path], anchor: pd.Period | None
) -> None:
    """The three curated deliverables, derived country by country.

    Same grain, same grouping keys and same values as `_write_consumables` -- the
    only difference is that the frame they come from is never whole.
    `trusted_observations` is streamed rather than gathered because it is the
    large one (15.4M of the 19.2M rows on the 2026-09 corpus); the summary and
    analytical outputs are aggregates, small enough to concatenate.
    """
    from prices.build.aggregate import (  # noqa: PLC0415
        TRUSTED_OBS_PARQUET,
        UNIT_VALUE_SUMMARY_PARQUET,
    )
    from prices.build.analytical import (  # noqa: PLC0415
        ANALYTICAL_PARQUET,
        build_analytical,
    )
    from prices.build.unit_value_summary import (  # noqa: PLC0415
        build_unit_value_summary,
        trusted_observations,
    )

    trusted_writer: pq.ParquetWriter | None = None
    trusted_rows = 0
    summaries: list[pd.DataFrame] = []
    analyticals: list[pd.DataFrame] = []

    try:
        for i, p in enumerate(final_paths):
            df = pd.read_parquet(p)
            if df.empty:
                continue

            obs = trusted_observations(df)
            if not obs.empty:
                table = pa.Table.from_pandas(obs, preserve_index=False)
                if trusted_writer is None:
                    trusted_writer = pq.ParquetWriter(TRUSTED_OBS_PARQUET, table.schema)
                elif table.schema != trusted_writer.schema:
                    table = table.cast(trusted_writer.schema)
                trusted_writer.write_table(table)
                trusted_rows += len(obs)
            del obs

            summary = build_unit_value_summary(df)
            if not summary.empty:
                summaries.append(summary)

            analytical = build_analytical(df, anchor=anchor)
            if not analytical.empty:
                analyticals.append(analytical)
            del df

            if (i + 1) % 40 == 0:
                logger.info(
                    "[consumables] %d/%d countries; %d trusted rows so far",
                    i + 1,
                    len(final_paths),
                    trusted_rows,
                )
    finally:
        if trusted_writer is not None:
            trusted_writer.close()

    logger.info("wrote %s (%d trusted rows)", TRUSTED_OBS_PARQUET, trusted_rows)

    summary_out = pd.concat(summaries, ignore_index=True) if summaries else pd.DataFrame()
    summary_out.to_parquet(UNIT_VALUE_SUMMARY_PARQUET, index=False)
    logger.info("wrote %s (%d cells)", UNIT_VALUE_SUMMARY_PARQUET, len(summary_out))

    analytical_out = (
        pd.concat(analyticals, ignore_index=True) if analyticals else pd.DataFrame()
    )
    analytical_out.to_parquet(ANALYTICAL_PARQUET, index=False)
    logger.info("wrote %s (%d rows)", ANALYTICAL_PARQUET, len(analytical_out))


# --------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------


def build_observations_chunked(
    pieces: list[pd.DataFrame],
    typical_mass: pd.DataFrame | None,
    workers: int,
    scratch: Path,
    keep_scratch: bool = False,
) -> list[Path]:
    """Spill, finalize in parallel, stream out, then derive the consumables.

    Deliberately returns paths rather than a frame. A caller handed paths cannot
    accidentally undo the saving by concatenating them; a caller that genuinely
    wants the whole frame in memory should use the unchunked path.
    """
    from prices.build.aggregate import OBSERVATIONS_PARQUET  # noqa: PLC0415
    from prices.build.leaf_typical_mass import TYPICAL_MASS_CSV  # noqa: PLC0415

    parts_dir = scratch / "by_country"
    final_dir = scratch / "finalized"
    for d in (parts_dir, final_dir):
        if d.exists():
            shutil.rmtree(d)

    counts = spill_by_country(pieces, parts_dir)
    top = sorted(counts.items(), key=lambda kv: -kv[1])[:3]
    logger.info(
        "[observations] largest parts: %s", ", ".join(f"{k} {v:,}" for k, v in top)
    )

    if typical_mass is None:
        derive_pinned_mass(parts_dir)
    mass_csv = TYPICAL_MASS_CSV if TYPICAL_MASS_CSV.exists() else None

    final_paths = finalize_parts(parts_dir, final_dir, mass_csv, workers)
    stream_concat(final_paths, OBSERVATIONS_PARQUET)

    anchor = global_anchor(final_dir)
    logger.info("[observations] analytical trailing-window anchor: %s", anchor)
    write_consumables_chunked(final_paths, anchor)

    if not keep_scratch:
        shutil.rmtree(parts_dir, ignore_errors=True)
        shutil.rmtree(final_dir, ignore_errors=True)
    return final_paths
