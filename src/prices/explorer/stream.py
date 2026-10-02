"""The row-level half of `build_payload`, run a batch of countries at a time.

Held whole, the trusted corpus exploded up the COICOP ladder is ~184M rows on
W40, and the render was OOM-killed inside `_cells` on a 26 GB box. Every
row-level step groups on a key that includes `country`, so the corpus is read a
batch of countries at a time and only the small per-country tables are kept.

Three inputs are NOT per country, and a cheap first pass over narrow columns
settles them before any batch is read:

  * the display unit per leaf, a vote over every country's rows;
  * the end of the current-cell window, the latest observation that converts
    to its leaf's display unit (the region's latest, for a regional build);
  * which countries there are, and how many trusted rows each holds.

The dominant-currency vote in `_cells` is the one cross-country step left: it
runs once, over the concatenated per-batch tables. Batches go in sorted country
order and every batch is a filter that keeps file order, so each concatenated
table comes out in the order one groupby over the whole build would give.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pandas as pd
import pyarrow.parquet as pq

from prices.build import leaf_typical_mass, unit_collapse
from prices.explorer import sources
from prices.explorer.aggregate import (
    _OBS_TAIL_COLS,
    _cell_groups,
    _cell_window,
    _cells,
    _chained_index,
    _country_rows,
    _fold_piece_units,
    _fx_rates,
    _lagged_changes,
    _pool,
    _region_label,
    _samples,
    _series,
)
from prices.explorer.geo import PAIR, _pairs
from prices.explorer.sources import COMPARABLE_UNITS, FREQ_MAX_GAP
from prices.rtcal.fills import drop_pruned, load_pruned_cells, load_released_fills

logger = logging.getLogger(__name__)

# Trusted rows per batch of countries. A batch explodes to roughly five times
# this up the ladder; a country holding more than this is a batch on its own.
BATCH_ROWS = 3_000_000
# Rows per chunk of the narrow first pass.
SCAN_ROWS = 4_000_000
_NARROW = [
    "country",
    "coicop_code",
    "standard_unit",
    "qa_status",
    "unit_value_usd",
    "observation_date",
]


def _reader(load):
    """(narrow chunks for the first pass, a reader for one batch of countries).

    A loader that is not the parquet one -- a synthetic corpus -- has no file to
    filter, so its frame is read once and sliced.
    """
    if load is not sources.load_observations:
        obs = load()
        return (lambda: [obs[_NARROW].copy()]), (
            lambda cs: obs[obs.country.isin(cs)].copy()
        )
    dtypes: dict = {}

    def read(cs: list[str]) -> pd.DataFrame:
        # A filtered read builds its Categoricals from the rows it kept, so two
        # batches can disagree on the categories, and their order is what a
        # groupby on `currency` sorts by. Every batch gets the whole file's.
        df = load(countries=cs)
        for col in df.columns:
            if isinstance(df[col].dtype, pd.CategoricalDtype):
                if col not in dtypes:
                    whole = pq.read_table(sources.OBS_PATH, columns=[col])
                    dtypes[col] = whole.to_pandas(categories=[col])[col].cat.categories
                # Not `astype`: an unordered CategoricalDtype compares equal
                # whatever its order, so `astype` would leave the order alone.
                df[col] = df[col].cat.set_categories(dtypes[col])
        return df

    def chunks():
        pf = pq.ParquetFile(sources.OBS_PATH)
        for b in pf.iter_batches(batch_size=SCAN_ROWS, columns=_NARROW):
            yield b.to_pandas()

    return chunks, read


def _scan(chunks, pruned: pd.DataFrame) -> tuple[pd.DataFrame, set]:
    """Trusted rows and their latest date per (country, leaf, unit, month), with
    the pruned cells taken out, and every country the corpus holds a row for."""
    seen: set = set()
    parts = []
    for df in chunks:
        seen.update(df.country.unique())
        _fold_piece_units(df)
        t = df[
            df.qa_status.eq("trusted")
            & df.standard_unit.isin(COMPARABLE_UNITS)
            & df.unit_value_usd.gt(0)
        ]
        per = t.observation_date.dt.to_period("M").astype(str).rename("period")
        parts.append(
            t.groupby(
                [t.country, t.coicop_code, t.standard_unit, per], dropna=False
            ).observation_date.agg(["size", "max"])
        )
    g = (
        pd.concat(parts)
        .groupby(level=[0, 1, 2, 3], dropna=False)
        .agg({"size": "sum", "max": "max"})
        .reset_index()
    )
    # Pruning drops whole cells, so dropping them here off the per-month table
    # removes exactly the rows it removes from each batch.
    return drop_pruned(g, pruned), seen


def _canonical(cells: pd.DataFrame) -> dict[str, str]:
    """`unit_collapse.canonical_units`, voted on summed row counts instead of
    rows. Same vote and the same tie-break, which is what keeps every batch on
    the display unit the whole corpus would have picked."""
    counts = cells.groupby(["coicop_code", "standard_unit"])["size"].sum()
    pref = unit_collapse.UNIT_PREFERENCE
    out: dict[str, str] = {}
    for code, grp in counts.groupby(level=0):
        by_unit = grp.droplevel(0)
        top = int(by_unit.max())
        tied = [u for u, n in by_unit.items() if int(n) == top]
        out[str(code)] = min(
            tied, key=lambda u: pref.index(u) if u in pref else len(pref)
        )
    return out


def _end(conv: pd.DataFrame) -> pd.Timestamp | None:
    end = conv["max"].max() if len(conv) else None
    return None if pd.isna(end) else end


def _batches(order: list[str], sizes: pd.Series, limit: int) -> list[list[str]]:
    out: list[list[str]] = []
    cur: list[str] = []
    n = 0
    for c in order:
        # At least one row, so a tiny BATCH_ROWS -- the equivalence check runs
        # one or two countries a batch -- also splits up the countries that
        # hold no trusted rows (those with only fills, or only rejected rows).
        k = max(int(sizes.get(c, 0)), 1)
        if cur and n + k > limit:
            out.append(cur)
            cur, n = [], 0
        cur.append(c)
        n += k
    if cur:
        out.append(cur)
    return out


def _cat(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Concatenate the non-empty frames. An empty one can carry other dtypes
    (an `object` column where the rest are float), so it is never mixed in."""
    full = [f for f in frames if not f.empty]
    if not full:
        return frames[0] if frames else pd.DataFrame()
    return pd.concat(full, ignore_index=True)


def _window(acc: list, trusted: pd.DataFrame, fills: pd.DataFrame, end) -> None:
    """The current-cell window of one batch, pooled, as `_cells`' inputs."""
    tw, fw = _cell_window(trusted, fills, end)
    if tw.empty and fw.empty:
        return
    ex, ex_fill = _pool(tw, fw)
    acc.append((*_cell_groups(ex), ex_fill))


def _qa_rows(obs: pd.DataFrame) -> dict[str, dict]:
    out = {}
    for slug, g in obs.groupby("country"):
        tr = g.qa_status.eq("trusted")
        out[slug] = {
            "status": {k: int(v) for k, v in g.qa_status.value_counts().items()},
            "mass_source": {
                str(k): int(v)
                for k, v in g.mass_source[tr].value_counts(dropna=False).items()
            },
            "item_basis_rows": int((tr & g.item_basis).sum()),
            "modelled_rows": int((tr & g.is_modelled).sum()),
        }
    return out


def _batch(obs: pd.DataFrame, fills: pd.DataFrame, acc, ctx) -> None:
    """One batch of countries through every row-level step `build_payload` takes."""
    # Counted BEFORE the fold, and carried as a COLUMN rather than a scalar:
    # the honesty panel reports this scoped to the countries in THIS payload,
    # and by the time that scope is known the fold has relabelled these very
    # rows as `unit` and the count can no longer be recovered.
    obs["item_basis"] = obs.standard_unit.eq("item")
    _fold_piece_units(obs)
    trusted = obs[
        obs.qa_status.eq("trusted")
        & obs.standard_unit.isin(COMPARABLE_UNITS)
        & obs.unit_value_usd.gt(0)
    ]
    # The scope-aware QA counts and `_fx_table` both need every ROW of the
    # unfiltered frame, and between them nine of its thirteen columns. They are
    # taken off the projection here, per country, and the frame is let go.
    obs = obs[_OBS_TAIL_COLS]
    acc.qa.update(_qa_rows(obs))
    acc.fx.update(_fx_rates(obs, ctx.countries))
    del obs

    trusted = drop_pruned(trusted, ctx.pruned)
    if not trusted.empty:
        # ONE DISPLAY UNIT PER LEAF -- see `collect`. The units are the whole
        # corpus's vote, passed in, never this batch's own: two batches voting
        # apart could hand one leaf two display units.
        trusted, suppressed = unit_collapse.collapse(
            trusted, ctx.typical_mass, canonical=ctx.canonical
        )
        if not suppressed.empty:
            acc.suppressed.append(suppressed)
        # The provenance column has done its job by here, and the suppression
        # audit has already taken its copy. Carried on, `_explode_nodes` would
        # multiply an object column by every row's ancestor count.
        trusted = trusted.drop(columns="display_unit_source")

    # The world cells settle the two things a regional payload must NOT settle
    # for itself -- the eligible basket and the world median -- so every
    # country's window is pooled, whatever the region. A SECOND, SMALL POOL
    # rather than a flag on the big one: the grid needs a CELL_WINDOW_DAYS slice
    # and the series need all of history.
    _window(acc.world, trusted, fills, ctx.ends[0])
    if ctx.keep is not None:
        trusted = trusted[trusted.country.isin(ctx.keep)]
        fills = fills[fills.country.isin(ctx.keep)]
        _window(acc.region, trusted, fills, ctx.ends[1])
    if trusted.empty and fills.empty:
        return

    exploded, ex_fill = _pool(trusted, fills)
    acc.series.append(_series(exploded, ex_fill))
    acc.chained.append(_chained_index(exploded, ctx.tax, ex_fill))
    acc.changed.append(_lagged_changes(exploded, ctx.tax, ex_fill))
    acc.nu.append(exploded.groupby(["node", "standard_unit"], observed=True).size())
    if not ex_fill.empty:
        acc.nf.append(ex_fill.groupby(["node", "standard_unit"], observed=True).size())
    for freq in FREQ_MAX_GAP:
        acc.pairs[freq].append(_pairs(exploded, ctx.tax, freq, ex_fill))
    del exploded, ex_fill

    acc.stats.update(_country_rows(trusted))
    acc.samples.update(_samples(trusted))
    acc.periods.append(trusted.period.value_counts())
    acc.sources.update(trusted.source.dropna().unique())
    acc.n_obs += len(trusted)


def _sum(series: list[pd.Series]) -> pd.Series | None:
    if not series:
        return None
    levels = list(range(series[0].index.nlevels))
    return pd.concat(series).groupby(level=levels).sum()


def collect(region: str | None, tax: dict, countries: dict, load) -> SimpleNamespace:
    """Everything `build_payload` reads off rows, as small cross-country tables."""
    chunks, read = _reader(load)
    # Both empty unless `prices rtcal run` has been executed.
    #
    # FILLS NOW REACH EVERYTHING: the cells, the chain, the changes, the basket,
    # the geography series, the regional and world medians. The old split --
    # draw a modelled point, but never let it move an index -- kept every
    # aggregate above the leaf exactly as blank as it was before, which is what
    # the dashboard was being asked about. What replaces the exclusion is
    # measurement: every figure derived from a fill carries the share of itself
    # that was imputed, so a client can show, dim or hide it.
    #
    # PRUNED CELLS ARE DIFFERENT and come out everywhere, at the observation
    # level, before anything aggregates. Removing a value our own screen calls an
    # obvious error is a correction, not an imputation, and it would be incoherent
    # for the chain to keep pricing a cell the series view refuses to draw. This
    # is the other half of what the method is for: the historical view is full of
    # points that are wrong on their face, and they should stop being drawn.
    fills = load_released_fills()
    pruned = load_pruned_cells()
    tm_csv = leaf_typical_mass.TYPICAL_MASS_CSV
    typical_mass = pd.read_csv(tm_csv) if tm_csv.exists() else pd.DataFrame()
    if typical_mass.empty:
        logger.warning("%s missing -- piece rows cannot convert", tm_csv)

    # ONE DISPLAY UNIT PER LEAF, the same collapse `publish.py` has applied
    # since 2026-09-04 and the explorer never grew. Without it a leaf's rows sit
    # in whatever units they were extracted in, and two things break. A per-piece
    # price is ranked against a per-PIECE world median, so Japanese milk reads
    # +2305% as a carton and +16% as a litre, and 13 of the 15 "most expensive"
    # items on the screen are pieces. And a country's leaves scatter across the
    # kg/lt/unit buckets, so American Samoa's three dairy leaves -- two priced by
    # the piece, one by the kilo -- clear no bucket's three-leaf floor and the
    # class cell renders empty when the data is there.
    #
    # The piece fold has already run on what `_scan` counted, which matters:
    # `unit_collapse` votes on unit LABELS, and `item`/`unit` are two spellings
    # of one piece price on the allowlisted leaves, so voting before the fold
    # could hand a leaf to the loser.
    cells, seen = _scan(chunks(), pruned)
    canonical = _canonical(cells)
    # The window ends on the last observation that SURVIVES the collapse, so it
    # is found by collapsing the per-month table onto the same display units.
    conv, _ = unit_collapse.collapse(
        cells, typical_mass, value_cols=(), canonical=canonical
    )
    # Fills are collapsed against the units the OBSERVATIONS voted for rather
    # than voting again on their own rows. Voting twice can give one leaf two
    # display units -- the split row this exists to remove -- and a modelled row
    # should never get a say in how a commodity is sold.
    fills = fills[fills.standard_unit.isin(COMPARABLE_UNITS)]
    fills, _ = unit_collapse.collapse(
        fills, typical_mass, value_cols=("usd",), canonical=canonical
    )

    ctx = SimpleNamespace(
        pruned=pruned,
        typical_mass=typical_mass,
        canonical=canonical,
        ends=(_end(conv), None),
        keep=None,
        tax=tax,
        countries=countries,
    )
    if region:
        label = _region_label(region)
        ctx.keep = {s for s, m in countries.items() if m["region"] == label}
        mine = conv[conv.country.isin(ctx.keep)]
        if mine.empty:
            raise SystemExit(f"no trusted observations for region {region!r} ({label})")
        ctx.ends = (ctx.ends[0], _end(mine))

    acc = SimpleNamespace(
        world=[],
        region=[],
        series=[],
        chained=[],
        changed=[],
        nu=[],
        nf=[],
        pairs={f: [] for f in FREQ_MAX_GAP},
        stats={},
        samples={},
        periods=[],
        sources=set(),
        n_obs=0,
        qa={},
        fx={},
        suppressed=[],
    )
    order = sorted(seen | set(fills.country))
    sizes = cells.groupby("country")["size"].sum()
    batches = _batches(order, sizes, BATCH_ROWS)
    for i, cs in enumerate(batches, 1):
        logger.info(
            "batch %d/%d: %d countries, %d trusted rows (%s .. %s)",
            i,
            len(batches),
            len(cs),
            int(sizes.reindex(cs).fillna(0).sum()),
            cs[0],
            cs[-1],
        )
        _batch(read(cs), fills[fills.country.isin(cs)], acc, ctx)

    # `collapse` hands back the dropped rows carrying `drop_reason` and the
    # `display_unit` they could not reach: the suppression audit.
    if acc.suppressed:
        suppressed = pd.concat(acc.suppressed, ignore_index=True)
        sources.SUPPRESSED_PARQUET.parent.mkdir(parents=True, exist_ok=True)
        suppressed.to_parquet(sources.SUPPRESSED_PARQUET, index=False)
        logger.info(
            "wrote %d suppressed rows over %d leaves -> %s",
            len(suppressed),
            suppressed.coicop_code.nunique(),
            sources.SUPPRESSED_PARQUET,
        )

    world_cells = _cells(*(_cat(list(part)) for part in zip(*acc.world)))
    # Identical inputs, so the global build takes its cells from the world's.
    cells = (
        _cells(*(_cat(list(part)) for part in zip(*acc.region)))
        if region
        else world_cells
    )
    qa = {"status": {}, "mass_source": {}, "item_basis_rows": 0, "modelled_rows": 0}
    for slug in acc.stats if region else acc.qa:
        row = acc.qa[slug]
        for key in ("status", "mass_source"):
            for k, v in row[key].items():
                qa[key][k] = qa[key].get(k, 0) + v
        qa["item_basis_rows"] += row["item_basis_rows"]
        qa["modelled_rows"] += row["modelled_rows"]
    periods = _sum(acc.periods)
    return SimpleNamespace(
        fills=fills[fills.country.isin(ctx.keep)] if region else fills,
        world_cells=world_cells,
        cells=cells,
        series=_cat(acc.series),
        chained=_cat(acc.chained),
        changed=_cat(acc.changed),
        stats=acc.stats,
        nu=_sum(acc.nu),
        nf=_sum(acc.nf),
        qa=qa,
        periods=periods,
        through=periods.index.max(),
        n_obs=acc.n_obs,
        sources=acc.sources,
        fx=acc.fx,
        seen=seen,
        pairs={f: _cat(m).sort_values(PAIR + ["period"]) for f, m in acc.pairs.items()},
        samples=acc.samples,
    )
