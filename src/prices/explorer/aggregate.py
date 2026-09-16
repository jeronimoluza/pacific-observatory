"""Aggregate the trusted unit-value corpus into the explorer payload.

The grain that matters is (country, COICOP node, standard_unit) — unit values
are never pooled across `standard_unit`, and local-currency medians always key
on the cell's dominant `currency`. Nodes are every level of the COICOP tree
(division/group/class/subclass/leaf), so the UI can walk up and down.
"""

from __future__ import annotations

import logging

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from prices.build import unit_collapse
from prices.build.leaf_typical_mass import TYPICAL_MASS_CSV
from prices.build.sold_by_item import SOLD_BY_ITEM_LEAVES
from prices.coicop import residual_leaves
from prices.explorer.cpi import DIVISION_OF, SERIES_LABEL, load_official
from prices.explorer.geo import build_geo_series
from prices.explorer.ppp import load_benchmark
from prices.explorer.weights import default_weights, equal_weights
from prices.explorer.sources import (
    ladder_agg,
    REGIONS_YAML,
    CHANGE_LAGS,
    COMPARABLE_UNITS,
    CURRENCY_ALIASES,
    SUPPRESSED_PARQUET,
    FE_MIN_PAIRS,
    FX_EXCURSION_MAX_RUN,
    FX_EXCURSION_RATIO,
    FX_EXCURSION_RETURN,
    FX_SPAN_WARN,
    FREQ_MAX_GAP,
    COUNTRY_DEFECT_SHARE,
    MAX_LINK_GAP_MONTHS,
    BASKET_WEIGHT_LEVEL,
    MIN_BASKET_LEAF_SHARE,
    MIN_BASKET_WEIGHT_COVERED,
    MIN_BASKET_LEAVES,
    MIN_BASKET_SOURCES,
    MIN_BENCH_COUNTRIES,
    CELL_WINDOW_DAYS,
    MIN_CELL_OBS,
    MIN_CHAIN_PERIODS,
    MIN_LINK_LEAVES,
    MIN_LINK_LEAVES_FLOOR,
    MIN_LINK_LEAVES_FRAC,
    MIN_SERIES_PERIODS,
    MODELLED_SOURCES,
    PLAUSIBLE_USD,
    REPO_ROOT,
    _levels,
    load_country_meta,
    load_observations,
    load_taxonomy,
)

from prices.rtcal.fills import drop_pruned, load_pruned_cells, load_released_fills

__all__ = ["REPO_ROOT", "build_payload", "write_payload"]

logger = logging.getLogger(__name__)


def _fold_piece_units(obs: pd.DataFrame) -> int:
    """Relabel `item` as `unit`, IN PLACE, on the leaves that vet it as a piece.

    `unit` and `item` are both a price per ONE countable piece; they differ only
    in how the denominator was reached. `unit` divided a pack price by an
    explicit count marker, `item` is the extraction ladder's catch-all, trusted
    only where SOLD_BY_ITEM_LEAVES says the commodity really is an indivisible
    piece. `COMPARABLE_UNITS` omits `item` because off-allowlist it means "no
    quantity found" -- but that slice never reaches here: `qa.py::_row_has_quantity`
    only lets an `item` row reach `trusted` when the leaf is on the allowlist.
    So the filter was discarding 92,223 rows that had passed every gate, and
    with them 531 (country, leaf) cells across ~100 countries.

    `publish.py` has folded these two labels together since 2026-09-04; the
    explorer never grew the equivalent, which is one of the ways the two
    dashboards disagree about what the corpus contains.

    In place, and not for tidiness: this runs before the trusted filter, on the
    whole 18.9M-row observation frame with nine object columns in it. Copying
    that frame to change 92,223 cells peaks around 23 GB and the render is
    OOM-killed on a 26 GB box. `build_payload` owns the frame `load_observations`
    just handed it, so mutating it costs one boolean mask and nothing else.
    Returns the number of rows relabelled.
    """
    fold = obs.coicop_code.isin(SOLD_BY_ITEM_LEAVES) & obs.standard_unit.eq("item")
    n = int(fold.sum())
    if n:
        obs.loc[fold, "standard_unit"] = "unit"
    return n


def _mad(x: pd.Series) -> float:
    """Robust log dispersion of a unit-value cell — the reliability signal."""
    v = np.log(x[x > 0])
    if len(v) < 2:
        return float("nan")
    return float(np.median(np.abs(v - np.median(v))))


# Columns no consumer of the exploded frame reads. The ladder merge multiplies
# every row by its ancestor count (~5x), so carrying these multiplies them too:
# `product_name` alone is ~1.4 GB on `trusted` and ~7 GB once exploded, on a
# render the OOM killer took three times at ~24 GB. Each is read off a frame
# that is NOT the exploded one -- `_samples` takes `product_name` and
# `observation_date` from `trusted`, and the FX table takes `fx_rate` from
# `obs`. A drop-list, not an allow-list: a column overlooked here still
# survives the merge.
# The only columns any consumer reads off the UNFILTERED frame once `trusted`
# has been taken: the QA panel needs the first five, `_fx_table` the next four.
# Projecting to these drops `obs` from ~11 GB to well under one, which is what
# lets the scope-aware QA counts keep reading every row on a 26 GB box.
_OBS_TAIL_COLS = [
    "country",
    "qa_status",
    "mass_source",
    "standard_unit",
    "is_modelled",
    "item_basis",
    "period",
    "currency",
    "fx_rate",
]


_EXPLODE_DROP = [
    "product_name",
    "observation_date",
    "fx_rate",
    "qa_status",
    "mass_source",
    "pricing_basis",
]


def _explode_nodes(rows: pd.DataFrame) -> pd.DataFrame:
    """One row per (observation, ancestor node) so every tree level aggregates."""
    codes = rows.coicop_code.unique()
    ladder = pd.DataFrame(
        [(c, n) for c in codes for n in _levels(c)], columns=["coicop_code", "node"]
    )
    slim = rows.drop(columns=_EXPLODE_DROP, errors="ignore")
    return slim.merge(ladder, on="coicop_code", how="inner")


def _fill_rows(fills: pd.DataFrame, like: pd.DataFrame) -> pd.DataFrame:
    """RT-CAL cell medians shaped as rows of the observation frame `like`.

    A fill is a CELL median and an observation is a single shelf price, so this
    is not a like-for-like promotion: one fill enters an aggregate as one value,
    beside however many rows the observed leaves contributed. That is the same
    arithmetic every aggregate on this dashboard already does -- a node's median
    is a median over rows -- and it is why `imp` below is a share of the pooled
    VALUES rather than a share of the leaves.

    Every column the observation frame carries is reproduced at its own dtype.
    `source` and `currency` in particular are Categorical and stay Categorical:
    a fill votes in neither, so it is left null in both, which keeps `sources`
    honest (a fill is not a source) and keeps the dominant-currency vote clean.
    """
    n = len(fills)
    out = pd.DataFrame(index=pd.RangeIndex(n))
    for col, dt in like.dtypes.items():
        # `node` is the ladder's own column and is put back by `_explode_nodes`.
        # Carrying it here would leave the merge with two of them.
        if col == "node":
            continue
        if isinstance(dt, pd.CategoricalDtype):
            out[col] = pd.Categorical([None] * n, dtype=dt)
        elif dt == bool:
            out[col] = np.zeros(n, dtype=bool)
        elif np.issubdtype(dt, np.number):
            out[col] = np.full(n, np.nan)
        else:
            out[col] = pd.Series([None] * n, dtype=object)
    out["country"] = fills.country.to_numpy()
    out["coicop_code"] = fills.coicop_code.to_numpy()
    out["standard_unit"] = fills.standard_unit.to_numpy()
    out["period"] = fills.period.to_numpy()
    out["unit_value_usd"] = fills.usd.to_numpy(dtype=float)
    # `prob` rides along on the fill frame ONLY. Carrying it on the pooled frame
    # would cost a float per observation for a number only fills have.
    out["prob"] = fills.prob.to_numpy(dtype=float)
    return out


def _concat_rows(a: pd.DataFrame, b: pd.DataFrame) -> pd.DataFrame:
    """Append `b`'s rows to `a`, one column at a time, CONSUMING `a`.

    `pd.concat` on the exploded frame needs a second copy of it alive at once,
    and the exploded frame is the largest object a render builds -- a global
    build peaks around 21 GB on a 26 GB box, so doubling it is not available.
    Popping each column off `a` as it is consumed keeps the transient down to
    one column. `a` is empty when this returns, which is the point; callers must
    use the return value.
    """
    cols = list(a.columns)
    out = {}
    for col in cols:
        left = a.pop(col)
        right = b[col]
        if right.dtype != left.dtype:
            right = right.astype(left.dtype)
        out[col] = pd.concat([left, right], ignore_index=True)
    return pd.DataFrame(out, columns=cols)


def _pool(
    trusted: pd.DataFrame, fills: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(observations + fills exploded up the ladder, the fills alone).

    THE FILLS GO UP THE LADDER TOO. They used to join only at the leaf they were
    predicted for, on the argument that a parent's median would otherwise mix
    modelled and measured values. It does mix them, and that is now the intent:
    a parent node blank because two of its leaves were never collected is the
    complaint this method exists to answer, and holding fills at the leaf left
    every aggregate above them exactly as blank as before.

    What pays for it is provenance rather than exclusion. Every figure derived
    from this frame carries the share of the values behind it that were
    imputed, so "mixed" is a number on the cell rather than a caveat in a
    docstring. The second return value is the fill rows alone, which is what
    that share is counted from -- the pooled frame deliberately carries no
    per-row imputed flag, because a byte per row over ~90M rows buys nothing a
    small group-by on the fills cannot say better.
    """
    ex = _explode_nodes(trusted)
    if fills is None or fills.empty:
        return ex, ex.iloc[:0].assign(prob=np.nan)
    ex_fill = _explode_nodes(_fill_rows(fills, ex))
    return _concat_rows(ex, ex_fill), ex_fill


def _cell_window(
    trusted: pd.DataFrame, fills: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The last CELL_WINDOW_DAYS of the corpus -- observations and fills alike.

    ANCHORED ON THE CORPUS, NOT THE CLOCK. `Timestamp.now()` would reintroduce
    the very failure this window exists to fix: a build run any distance after
    the last collection would open a window with nothing in it, and the grid
    would quietly empty rather than say so. The corpus's own last observation is
    what "current" can honestly mean.

    Fills carry no `observation_date` -- a fill is a cell median for a MONTH --
    so they are admitted on `period`, by whichever months the window touches. A
    window ending mid-month therefore admits that month's fill and the previous
    month's, and the cell median pools both. Admitting them on a date they do
    not have would have dropped every fill from the grid.
    """
    if trusted.empty:
        return trusted, fills
    end = trusted.observation_date.max()
    start = end - pd.Timedelta(days=CELL_WINDOW_DAYS)
    tw = trusted[trusted.observation_date >= start]
    if fills is None or fills.empty:
        return tw, fills
    months = set(pd.period_range(start, end, freq="M").astype(str))
    return tw, fills[fills.period.astype(str).isin(months)]


def _imputed_share(ex_fill: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """Per group: how many pooled values were fills, and their mean probability.

    `prob` is the isotonic-calibrated P(within 25% of the truth) RT-CAL puts on
    each cell. It is carried as DATA, per cell, and is never collapsed into a
    headline accuracy figure anywhere in this payload: the released population
    now mixes normal gaps that validate around 80% with cold-start cells that
    validate around 42%, and one number over that mixture describes neither.
    """
    return (
        ex_fill.groupby(keys, observed=True)
        .agg(nimp=("unit_value_usd", "size"), prob=("prob", "mean"))
        .reset_index()
    )


def _with_imputed(
    agg: pd.DataFrame, ex_fill: pd.DataFrame, keys: list[str], code_col: str = "node"
) -> pd.DataFrame:
    """Split a pooled group count into observed and imputed, and add the share.

    `n_all` in, `n` / `nimp` / `imp` / `prob` out. `n` keeps the meaning it has
    always had -- observations behind this figure -- so every gate written
    against it still reads the same thing.
    """
    if ex_fill.empty:
        agg["nimp"] = 0
        agg["prob"] = np.nan
    else:
        fkeys = [code_col if k == "coicop_code" else k for k in keys]
        imp = _imputed_share(ex_fill, fkeys)
        if code_col != "coicop_code":
            imp = imp.rename(columns=dict(zip(fkeys, keys)))
        agg = agg.merge(imp, on=keys, how="left")
        agg["nimp"] = agg.nimp.fillna(0)
    agg["nimp"] = agg.nimp.astype("int64")
    agg["n"] = (agg.n_all - agg.nimp).astype("int64")
    agg["imp"] = (agg.nimp / agg.n_all.where(agg.n_all > 0)).fillna(0.0)
    return agg.drop(columns="n_all")


def _publishable(agg: pd.DataFrame) -> pd.Series:
    """A cell publishes on enough observations, OR on any fill at all.

    The evidence bar for MEASURED prices is untouched: MIN_CELL_OBS or the cell
    is not drawn. What is new is the second clause, and it is the whole point of
    releasing fills -- a cell nobody priced has no observations to count, so any
    rule phrased only in observations keeps it blank forever.

    A cell with one or two observations AND a fill now publishes where it used
    to be suppressed. That is a real change and it is deliberate: RT-CAL only
    targets a cell it considers missing, so such a cell was already below the
    summary's own bar, and the pooled median plus `imp` says more about it than
    an empty square does.
    """
    return (agg.n >= MIN_CELL_OBS) | (agg.nimp > 0)


def _cells(exploded: pd.DataFrame, ex_fill: pd.DataFrame) -> pd.DataFrame:
    """Current-window medians per (country, node, unit) plus quality flags.

    THE WINDOW IS THE CALLER'S: `exploded` here is the pooled last
    CELL_WINDOW_DAYS, not the whole corpus. This used to be the whole corpus
    with `max(period)` taken per cell, and that is why a cell could rest on a
    single reading -- the newest month a cell happened to be scraped in was
    often only days old. Pooling a fixed window instead means every cell reports
    over the same stretch of time, whatever month it happens to fall in.
    """
    keys = ["country", "node", "standard_unit"]
    cur = exploded
    latest = (
        cur.groupby(keys, observed=True).period.max().rename("period").reset_index()
    )

    agg = (
        cur.groupby(keys, observed=True)
        .agg(
            usd=("unit_value_usd", "median"),
            n_all=("unit_value_usd", "size"),
            mad=("unit_value_usd", _mad),
            modelled=("is_modelled", "mean"),
            derived=("is_derived", "mean"),
            sources=("source", "nunique"),
        )
        .reset_index()
    )
    # `period` is a LABEL -- the newest month this cell was seen in -- not the
    # slice the median was taken over. The median is over the whole window.
    agg = agg.merge(latest, on=keys, how="left")

    # Local currency medians key on the cell's dominant currency, never country.
    dom = (
        cur.groupby(keys + ["currency"], observed=True)
        .unit_value_local.agg(["median", "size"])
        .reset_index()
        .sort_values("size", ascending=False)
        .drop_duplicates(keys)
        .rename(columns={"median": "local", "size": "n_local"})
    )
    agg = agg.merge(dom, on=keys, how="left")
    agg = _with_imputed(agg, ex_fill, keys)
    # A fill has no local price and votes in no currency, so a cell that is all
    # fill has no dominant currency to be mixed about.
    ratio = (agg.n_local / agg.n.where(agg.n > 0)).fillna(1.0)
    agg["mixed_currency"] = ratio < 0.9
    agg = agg[_publishable(agg)].copy()

    lo = agg.standard_unit.map(lambda u: PLAUSIBLE_USD[u][0])
    hi = agg.standard_unit.map(lambda u: PLAUSIBLE_USD[u][1])
    agg["flagged"] = ~agg.usd.between(lo, hi)
    return agg


def _series(exploded: pd.DataFrame, ex_fill: pd.DataFrame) -> pd.DataFrame:
    """Monthly medians per (country, node, unit) over observations AND fills.

    Three rules used to keep fills out of everything but a leaf-grain line, and
    all three are gone. They are worth naming, because each was removed for a
    reason and each removal costs something:

    LEAF ONLY is gone. Fills ride the same COICOP ladder observations ride, so a
    group and a division see them too. A parent's median is now a median over a
    mixture of measured and modelled values, which is exactly what the old rule
    refused -- `imp` is the price of that, carried on every point.

    NEVER CREATES A SERIES is gone. `MIN_SERIES_PERIODS` now counts periods
    however they arrived, so a (country, node, unit) nobody ever measured twice
    can carry a line. `imputed` marks the points that are entirely modelled and
    `n` is 0 on them, so a wholly-imputed series is legible as one.

    NO COLLISIONS TO RESOLVE still holds, and is now structural rather than
    enforced: an observation and a fill for the same cell simply pool into one
    median, and RT-CAL does not target a cell it can see, so it hardly arises.
    """
    keys = ["country", "node", "standard_unit", "period"]
    s = (
        exploded.groupby(keys, observed=True)
        .agg(
            usd=("unit_value_usd", "median"),
            local=("unit_value_local", "median"),
            n_all=("unit_value_usd", "size"),
        )
        .reset_index()
    )
    s = _with_imputed(s, ex_fill, keys)
    s = s[_publishable(s)]
    depth = s.groupby(["country", "node", "standard_unit"]).period.transform("nunique")
    s = s[depth >= MIN_SERIES_PERIODS].copy()
    s["imputed"] = s.n.eq(0)
    return s


def _leaf_census(tax: dict) -> dict[str, int]:
    """Leaves sitting under each node, counted from the taxonomy alone."""
    out: dict[str, int] = {}
    for code, meta in tax.items():
        if not meta.get("leaf"):
            continue
        for anc in _levels(code)[:-1]:
            out[anc] = out.get(anc, 0) + 1
    return out


def _leaf_panel(
    exploded: pd.DataFrame, tax: dict, ex_fill: pd.DataFrame
) -> pd.DataFrame:
    """Median unit value of each (country, leaf, unit) per month — the item.

    Both the chain and the year-over-year family are built on exactly this
    panel, so it is defined once: two measures of the same prices that disagreed
    about which observations count would be impossible to reconcile on screen.
    Fills are items here like anything else, and every item carries `imp` so the
    chain and the changes can report how much of a link was modelled.
    """
    keys = ["country", "coicop_code", "standard_unit", "period"]
    is_leaf = exploded.coicop_code.map(lambda c: bool(tax.get(c, {}).get("leaf")))
    leaf = exploded[is_leaf]
    leaf = leaf[leaf.node == leaf.coicop_code]
    m = (
        leaf.groupby(keys, observed=True)
        .agg(usd=("unit_value_usd", "median"), n_all=("unit_value_usd", "size"))
        .reset_index()
    )
    if not ex_fill.empty:
        ex_fill = ex_fill[ex_fill.node == ex_fill.coicop_code]
    m = _with_imputed(m, ex_fill, keys, code_col="coicop_code")
    return m[_publishable(m) & (m.usd > 0)]


def _link_need(nodes: pd.Series, tax: dict) -> np.ndarray:
    """Matched leaves a node must carry before its average is published.

    Scaled to the node's own leaf census, because 78 of the 102 non-leaf nodes
    in divisions 01/02 hold fewer than MIN_LINK_LEAVES leaves in the taxonomy at
    all -- a taxonomy-shape problem wearing the clothes of a data problem. A
    LEAF needs one: it is its own basket, and there is nothing to average.
    """
    n_desc = nodes.map(_leaf_census(tax)).fillna(0).to_numpy()
    scaled = np.where(
        n_desc >= MIN_LINK_LEAVES,
        MIN_LINK_LEAVES,
        np.maximum(MIN_LINK_LEAVES_FLOOR, np.ceil(MIN_LINK_LEAVES_FRAC * n_desc)),
    )
    is_leaf = nodes.map(lambda c: bool(tax.get(c, {}).get("leaf"))).to_numpy()
    return np.where(is_leaf, 1, scaled)


def _lagged_changes(
    exploded: pd.DataFrame, tax: dict, ex_fill: pd.DataFrame
) -> pd.DataFrame:
    """Average log price change over k months, matched leaf by leaf.

    Unlike the chain this never links to "whatever the previous observation
    happened to be": period t is compared with period t-k exactly, over the
    leaves priced in BOTH.

    The comparison happens at the leaf and the averaging happens afterwards,
    one level of the tree at a time -- see `ladder_agg`. Rice this year over
    rice last year, then the mean across the cereals, then across the classes,
    then across the groups, and the mean of those is what division 01 changed
    by. Taking a price per kilo across a whole class first and differencing
    that would difference two different baskets.

    The MEAN, not the median. There are no expenditure weights in this corpus,
    so everything is equally weighted, and an unweighted mean of log relatives
    is the elementary index that follows from that. It is also what makes the
    number decomposable: the group change is the sum of each child's share of
    it, which a median is not.

    Nothing accumulates. A chained index carries every link's error forward and
    is read against a base month that is itself one noisy draw; a k-month change
    is two observations and stops there.
    """
    cols = ["country", "node", "standard_unit", "period", "lag", "lr", "k", "imp"]
    m = _leaf_panel(exploded, tax, ex_fill)
    if m.empty:
        return pd.DataFrame(columns=cols)
    m = m.copy()
    m["t"] = pd.PeriodIndex(m.period, freq="M").astype(int)
    keys = ["country", "coicop_code", "standard_unit"]

    out = []
    for months, lag in CHANGE_LAGS["M"].items():
        prev = m[keys + ["t", "usd", "imp"]].rename(
            columns={"usd": "prev_usd", "imp": "prev_imp"}
        )
        prev["t"] = prev.t + lag
        j = m.merge(prev, on=keys + ["t"], how="inner")
        if j.empty:
            continue
        j["lr"] = np.log(j.usd / j.prev_usd)
        # A change is only as measured as its LESS measured end, so the pair
        # takes the larger of the two shares rather than their average. Written
        # back over `imp` because `ladder_agg` carries an extra up the tree
        # under its own name; see `_chained_index`.
        j["imp"] = np.maximum(j.imp, j.prev_imp)
        step = ladder_agg(
            j,
            ["country", "standard_unit", "period"],
            "lr",
            extra={"imp": ("imp", "mean")},
        )
        step = step[step.k >= _link_need(step.node, tax)]
        if step.empty:
            continue
        step["lag"] = months
        out.append(step)
    if not out:
        return pd.DataFrame(columns=cols)
    return pd.concat(out, ignore_index=True)


def _chained_index(
    exploded: pd.DataFrame, tax: dict, ex_fill: pd.DataFrame
) -> pd.DataFrame:
    """Composition-free price index for aggregate COICOP nodes.

    A raw median over an aggregate node moves whenever the scrape composition
    moves — which item got collected this month, not what it cost. So for every
    non-leaf node we chain the Jevons way: month over month, take the log price
    relative at the leaf where both months are observed, average it up the tree
    one level at a time (`ladder_agg`), then cumulate.
    Only the US$ chain is built; the local chain follows exactly from the FX
    identity, which also sidesteps mixing two currencies inside one country.
    """
    cols = ["country", "node", "standard_unit", "period", "idx", "n_leaves", "imp"]
    m = _leaf_panel(exploded, tax, ex_fill)
    if m.empty:
        return pd.DataFrame(columns=cols)

    m = m.sort_values(["country", "coicop_code", "standard_unit", "period"])
    g = m.groupby(["country", "coicop_code", "standard_unit"], observed=True)
    m["prev_usd"] = g.usd.shift()
    m["prev_period"] = g.period.shift()
    m["prev_imp"] = g.imp.shift()
    m = m.dropna(subset=["prev_usd", "prev_period"])
    gap = pd.PeriodIndex(m.period, freq="M").astype(int) - pd.PeriodIndex(
        m.prev_period, freq="M"
    ).astype(int)
    m = m[(gap >= 1) & (gap <= MAX_LINK_GAP_MONTHS)].copy()
    m["lr"] = np.log(m.usd / m.prev_usd)
    # A link is only as measured as its less measured end. Written back over
    # `imp` rather than into a new column because `ladder_agg` carries an extra
    # up the tree under ITS OWN name -- an extra whose output name differs from
    # its source is lost above the first level.
    m["imp"] = np.maximum(m.imp, m.prev_imp)

    step = ladder_agg(
        m,
        ["country", "standard_unit", "period"],
        "lr",
        extra={
            "prev_period": ("prev_period", "min"),
            "imp": ("imp", "mean"),
        },
    ).rename(columns={"k": "n_leaves"})
    # The chain is an aggregate-node measure. A leaf holds nothing constant by
    # chaining -- its own monthly median already is its series -- so the ladder's
    # leaf rows, which exist only to feed their parents, come out here.
    step = step[~step.node.map(lambda c: bool(tax.get(c, {}).get("leaf")))]
    # Nodes that could always clear the flat bar keep it, so the scaling only
    # ever relaxes what the taxonomy made impossible, never what was merely thin
    # this month. Every node here is a strict ancestor, so the leaf case in
    # `_link_need` never fires and this is the gate it has always been.
    step = step[step.n_leaves >= _link_need(step.node, tax)]
    if step.empty:
        return pd.DataFrame(columns=cols)

    key = ["country", "node", "standard_unit"]
    step = step.sort_values(key + ["period"])
    step["idx"] = np.exp(step.groupby(key, observed=True).lr.cumsum()) * 100.0

    # the chain starts one period before its first link, at 100
    base = step.groupby(key, observed=True).head(1)[key + ["prev_period"]].copy()
    base = base.rename(columns={"prev_period": "period"})
    base["idx"] = 100.0
    base["n_leaves"] = 0
    # The base is a definition, not a measurement, so nothing about it is
    # imputed: it is 100 because the chain says so.
    base["imp"] = 0.0

    out = pd.concat(
        [base, step[key + ["period", "idx", "n_leaves", "imp"]]], ignore_index=True
    )
    out = out.drop_duplicates(key + ["period"], keep="first").sort_values(
        key + ["period"]
    )
    depth = out.groupby(key, observed=True).period.transform("nunique")
    return out[depth >= MIN_CHAIN_PERIODS]


def _residual_nodes(tax: dict) -> frozenset[str]:
    """Catch-all LEAVES only. An aggregate node is excluded from every level
    view by being an aggregate, whatever its title says."""
    return residual_leaves(
        {code: meta["t"] for code, meta in tax.items() if meta.get("leaf")}
    )


def _basket_leaves(cells: pd.DataFrame, tax: dict) -> pd.DataFrame:
    """The leaf cells a matched basket may be drawn from, before eligibility."""
    residual = _residual_nodes(tax)
    return cells[
        (cells.node.map(lambda c: bool(tax.get(c, {}).get("leaf"))))
        & (~cells.node.isin(residual))
        & (cells.modelled < 0.5)
        & cells.usd.gt(0)
        & ~cells.flagged
    ].copy()


def basket_reference(cells: pd.DataFrame, tax: dict) -> tuple[pd.Index, pd.Series]:
    """The eligible (leaf, unit) set and the world median for each -- ONCE.

    Both halves of the matched-basket construction have to be settled over the
    WHOLE corpus, not over whoever happens to be in the payload being built.

    THE ELIGIBLE SET, because `MIN_BASKET_LEAF_SHARE` counts the share of the
    countries being compared that price a leaf, and that share is a different
    question in a 209-country payload than in a 38-country one. Recomputed per
    payload it produced a different basket per region, which is precisely the
    thing a matched basket claims not to be -- and on EAP it produced no basket
    at all: the best country reached 14 eligible leaves against a
    `MIN_BASKET_LEAVES` of 15, so `level_ok` was False for all 38 countries and
    the heatmap, the ranking and the waterfall went blank together.

    THE REFERENCE MEDIAN, for the same reason and with worse consequences. A
    regional payload was dividing each country by the median of its own
    neighbours while every label on screen said "world = 100". A regional level
    and a global level were therefore not on the same scale and could not be
    read side by side, which is what the dashboard is about to ask of them.
    """
    leaves = _basket_leaves(cells, tax)
    keys = ["node", "standard_unit"]
    n_cty = leaves.country.nunique()
    cover = leaves.groupby(keys).country.nunique()
    eligible = cover[cover >= MIN_BASKET_LEAF_SHARE * n_cty].index
    logger.info(
        "basket eligibility: %d of %d (leaf, unit) pairs priced in %.0f%%+ of %d countries",
        len(eligible),
        len(cover),
        MIN_BASKET_LEAF_SHARE * 100,
        n_cty,
    )
    sel = leaves[pd.MultiIndex.from_frame(leaves[keys]).isin(eligible)]
    return eligible, sel.groupby(keys).usd.median().rename("g")


def _basket_levels(
    cells: pd.DataFrame,
    tax: dict,
    weights: dict[str, float] | None = None,
    detail: dict | None = None,
    reference: tuple[pd.Index, pd.Series] | None = None,
) -> pd.DataFrame:
    """Matched-leaf Jevons price level: a country's leaf unit values against the
    global median for that same (leaf, unit), averaged up the COICOP tree.

    Catch-all leaves are dropped. The construction's whole claim is that it
    compares like with like -- a kilo of rice against a kilo of rice -- and
    "other bakery products" in one country is not the same basket as "other
    bakery products" in another, so a leaf-matched ratio over one is exactly
    the composition effect the matching exists to remove.

    ELIGIBILITY. The same claim fails a second way if the basket is allowed to
    differ from one country to the next, so a leaf enters only where
    MIN_BASKET_LEAF_SHARE of the countries being compared price it. That is a
    real cut -- a thinly-priced leaf leaves every basket, not just the baskets
    missing it -- and it is the point: a rule about which leaves count beats a
    basket whose contents are whatever each scrape happened to catch.

    The mean, not the median. This docstring said "geometric mean" while the
    code took a median of the log gaps; the two are only the same on a
    symmetric spread, and the app said as much out loud on the waterfall, which
    already averaged. Averaging the differences is now what every reading here
    does, so the sentence above is true rather than aspirational. What paid for
    it is the evidence filter: thin single-source cells, which are where an
    outlier comes from, are out before the mean ever sees them.

    `detail`, when a dict is passed, is filled with the per-(country, category)
    matrix the collapsed level is a weighted sum OF -- see the block that writes
    it below. It is an out-parameter rather than a second return value because
    six tests already pin this function's signature and none of them want the
    matrix; the caller that does asks for it explicitly.
    """
    residual = _residual_nodes(tax)
    candidates = cells[
        (cells.node.map(lambda c: bool(tax.get(c, {}).get("leaf"))))
        & (~cells.node.isin(residual))
        & (cells.modelled < 0.5)
        & cells.usd.gt(0)
    ]
    defect = candidates.groupby("country").flagged.mean().rename("defect_share")
    leaves = _basket_leaves(cells, tax)
    keys = ["node", "standard_unit"]
    eligible, glob = (
        reference if reference is not None else basket_reference(cells, tax)
    )
    leaves = leaves[pd.MultiIndex.from_frame(leaves[keys]).isin(eligible)]
    leaves = leaves.join(glob, on=keys)
    leaves = leaves[leaves.g.gt(0)]
    leaves["rel"] = np.log(leaves.usd / leaves.g)
    # Up the tree one level at a time -- the same order every other figure here
    # uses -- and then a WEIGHTED sum across the categories at
    # BASKET_WEIGHT_LEVEL. The ladder alone still lets the taxonomy decide: it
    # gives every child of a node one vote, so a class holding a single leaf
    # speaks as loudly as a class holding twelve. That is how Macao reached 347
    # against a world median of 100 -- six of its classes hold one beverage leaf
    # each, every one of them with a broken unit value, and together they took
    # about a third of the basket. Expenditure weights put those six at under
    # eight per cent, which is what they are.
    lad = ladder_agg(
        leaves.rename(columns={"node": "coicop_code"}),
        ["country"],
        "rel",
        extra={"imp": ("imp", "mean")},
    )
    depth = BASKET_WEIGHT_LEVEL - 1 if weights else 0
    lvl = lad[lad.node.str.count(r"\.").eq(depth)].copy()

    if detail is not None and weights:
        # THE MATRIX BEHIND THE HEADLINE. One row per (country, category),
        # carrying the category-level log ratio and the leaf count behind it.
        # Everything below this point collapses it to one number per country
        # under one weight vector, and a reader who wants to know what a
        # different vector would say cannot get there from the collapsed
        # figure -- the sliders need the terms, not the sum.
        #
        # Shipping it also makes the client checkable: apply `w0` to this and
        # the `level` computed below must come back. `test_basket_matrix`
        # asserts exactly that, which is the only thing standing between a
        # slider at its default and a number that quietly disagrees with the
        # published one.
        #
        # Keyed by the country SLUG, not by ISO3, because every other country
        # key in this payload is a slug and two of them carry an empty iso3.
        for cty, grp in lvl.groupby("country", observed=True):
            # `[rel, k, imp]`. The third slot is an APPEND: `bwLevel` in the
            # client indexes 0 and 1 by position and is unaffected by a longer
            # row, so a client that has not been taught about imputation keeps
            # reading exactly what it read before.
            detail[str(cty)] = {
                str(node): [round(float(rel), 6), int(k), round(float(imp), 4)]
                for node, rel, k, imp in zip(grp.node, grp.rel, grp.k, grp.imp)
            }

    if weights:
        lvl["w"] = lvl.node.map(weights).astype(float).fillna(0.0)
        # A category this country does not price is an ABSENT TERM, never a
        # zero and never an imputed price. Its weight goes to the categories the
        # country does price, in proportion to their own -- so the weights the
        # reader sees always sum to one, over the basket that actually exists.
        # What the redistribution hides is how much of the intended basket went
        # missing, which is why `covered` is carried out of here and gated on.
        cov = lvl.groupby("country").w.sum().rename("covered")
        lvl["w"] = lvl.w / lvl.groupby("country").w.transform("sum")
        lvl["wr"] = lvl.w * lvl.rel
        # The imputed share of the LEVEL, aggregated the way the level is: the
        # same weights over the same categories, so `imp` answers "how much of
        # this exact number came from a model" rather than "how much of this
        # country's corpus is modelled", which is a different question.
        lvl["wi"] = lvl.w * lvl.imp.fillna(0.0)
        out = (
            lvl.groupby("country")
            .agg(rel=("wr", "sum"), n_leaves=("k", "sum"), imp=("wi", "sum"))
            .reset_index()
            .join(cov, on="country")
        )
    else:
        out = (
            lvl.groupby("country")
            .agg(rel=("rel", "mean"), n_leaves=("k", "sum"), imp=("imp", "mean"))
            .reset_index()
        )
        out["covered"] = 1.0
    out = out.join(leaves.groupby("country").sources.max().rename("src"), on="country")
    out = out.join(defect, on="country")
    out["level"] = np.exp(out.rel) * 100
    # The publication gate, in two halves. `gate` is everything that is a
    # property of the CORPUS -- how many items were matched, how many sources
    # stood behind them, how much of the country reads as defective -- none of
    # which a weight vector can move. Coverage is the half that does move, and
    # it is separated out so a client re-weighting the basket can re-apply it
    # without having to re-derive the other three, which it has no way to do.
    out["gate"] = (
        (out.n_leaves >= MIN_BASKET_LEAVES)
        & (out.src >= MIN_BASKET_SOURCES)
        & (out.defect_share.fillna(0) < COUNTRY_DEFECT_SHARE)
    )
    out["ok"] = out.gate & (out.covered.fillna(0) >= MIN_BASKET_WEIGHT_COVERED)
    logger.info(
        "basket: %d of %d countries ranked; %d fail on weight coverage alone",
        int(out.ok.sum()),
        len(out),
        int(
            (
                (out.covered.fillna(0) < MIN_BASKET_WEIGHT_COVERED)
                & (out.n_leaves >= MIN_BASKET_LEAVES)
                & (out.src >= MIN_BASKET_SOURCES)
                & (out.defect_share.fillna(0) < COUNTRY_DEFECT_SHARE)
            ).sum()
        ),
    )
    return out[
        ["country", "level", "n_leaves", "covered", "defect_share", "imp", "gate", "ok"]
    ]


def _weight_modes(
    tax: dict, icp_w: dict[str, float], icp_meta: dict, priced: set[str]
) -> dict:
    """The fixed weight vectors a reader can switch the ranking between.

    ICP is the published default and is passed in rather than refetched, so the
    vector on screen under "World Bank" is byte-for-byte the vector the `level`
    in this payload was built with.

    IMF IS A DIVISION VECTOR. `WGT_PT` publishes at CP01..CP12 and no deeper, so
    the IMF mode sets the food versus alcohol-and-tobacco split and spreads each
    division equally over what is inside it -- exactly the construction that was
    asked for, and exactly the thing a reader will misread as two institutions
    disagreeing about meat versus dairy unless it is labelled. The `note`
    travels with the vector so the label cannot be lost on the way.

    THE UNIVERSES ARE NOT ALL THE SAME, and the reason is worth stating because
    the obvious design does not work. ICP and IMF are external vectors and keep
    the categories their publishers publish -- ICP's 21, which is also what the
    published `level` was built on. Equal is not external: it is this
    dashboard's own statement, and the honest version of that statement is one
    vote per category THIS DASHBOARD CAN PRICE.

    Spreading it over ICP's 21 instead was tried and is unusable. This corpus
    prices twelve of those categories anywhere at all -- there is no alcohol,
    no tobacco, no oils and fats, no tea, no cocoa -- so a flat vector over 21
    puts 43% of every basket on categories nothing can fill, no country reaches
    a coverage of 0.60, and the mode ranks NOBODY. That is not the coverage gate
    catching a thin country; it is the gate charging every country for a hole
    none of them could fill, which is the failure `covered` exists to
    distinguish itself from.

    The cost is that `covered` is a share of a different denominator in each
    mode, so the ranked counts move between modes for two reasons at once. What
    pays for it is `unpriced`, carried on every vector below: the share of it
    that nothing in this build can price, which is the ceiling on anybody's
    coverage and the thing that actually explains the counts.

    A mode with no rows behind it is OMITTED, never fabricated.
    """
    if not icp_w:
        # No weights table at all: the build is on the unweighted path, the
        # level is a division mean, and there is no vector to switch between.
        return {}
    codes = sorted(icp_w)

    def entry(w: dict[str, float], meta: dict, name: str, note: str) -> dict:
        # `unpriced` is the share of THIS vector that no country in this build
        # prices -- so `1 - unpriced` is the highest coverage anyone can reach
        # under it, and a mode where that falls under the gate ranks nobody.
        return {
            "w": {k: round(v, 6) for k, v in sorted(w.items())},
            "meta": dict(
                meta,
                name=name,
                note=note,
                unpriced=round(1.0 - sum(v for c, v in w.items() if c in priced), 4),
                n_priced=sum(1 for c in w if c in priced),
            ),
        }

    modes = {
        "icp": entry(
            icp_w,
            icp_meta,
            "World Bank (ICP)",
            "Household expenditure shares at COICOP class depth for "
            "food and at group depth for beverages, alcohol and "
            "tobacco, spread equally below that.",
        ),
    }
    eq_codes = sorted(c for c in codes if c in priced) or codes
    eq_w, eq_meta = equal_weights(eq_codes)
    modes["equal"] = entry(
        eq_w,
        eq_meta,
        "Equal",
        f"One vote per category, over the {len(eq_codes)} categories this "
        "build actually prices. This is the taxonomy's own shape rather than "
        "anything about consumption.",
    )
    imf_w, imf_meta = default_weights(
        tax, BASKET_WEIGHT_LEVEL, source="imf_wgt_pt", universe=set(icp_w)
    )
    if imf_w:
        modes["imf"] = entry(
            imf_w,
            imf_meta,
            "IMF (national CPI weights)",
            "Published at DIVISION depth only, so this sets the food versus "
            "alcohol-and-tobacco split and nothing below it: every category "
            "inside a division carries the same weight as its neighbours.",
        )
    else:
        logger.info("no usable imf_wgt_pt rows -- the IMF weighting mode is omitted")
    for key, m in modes.items():
        logger.info(
            "weight mode %s: %d categories, %d priced, %.1f%% unpriced",
            key,
            len(m["w"]),
            m["meta"]["n_priced"],
            m["meta"]["unpriced"] * 100,
        )
    return modes


def _weight_labels(weights: dict[str, float]) -> set[str]:
    """Every code the slider panel has to name: the weighted categories and the
    ancestors it groups them under."""
    out: set[str] = set()
    for code in weights:
        parts = code.split(".")
        for i in range(1, len(parts) + 1):
            out.add(".".join(parts[:i]))
    return out


def _samples(trusted: pd.DataFrame) -> dict[str, list[str]]:
    """Three real product names per leaf cell, so a user can audit what is in it."""
    s = trusted[trusted.standard_unit.isin(COMPARABLE_UNITS)]
    s = s.sort_values("observation_date", ascending=False)
    s = s.groupby(["country", "coicop_code", "standard_unit"], observed=True).head(3)
    out: dict[str, list[str]] = {}
    for (c, code, unit), grp in s.groupby(
        ["country", "coicop_code", "standard_unit"], observed=True
    ):
        names = [str(n)[:70] for n in grp.product_name.tolist()]
        out[f"{c}|{code}|{unit}"] = names
    return out


def _columnar(df: pd.DataFrame, cols: dict[str, str]) -> dict:
    return {out: df[src].tolist() for out, src in cols.items()}


def _region_label(key: str) -> str:
    topo = yaml.safe_load(REGIONS_YAML.read_text()) or {}
    if key not in topo:
        raise SystemExit(f"unknown region {key!r}; known: {', '.join(sorted(topo))}")
    return topo[key].get("name", key)


def _fx_table(obs: pd.DataFrame, countries: dict[str, dict]) -> dict[str, dict]:
    """Monthly local-per-USD rate per country, from the country's OWN currency.

    The rate is the median of the per-row `fx_rate` over the country's declared
    currency and nothing else. Taking it over every row in the country-month
    regardless of currency -- which is what this did -- averages two different
    units: where a country's rows are part local and part USD (`fx_rate` = 1.0),
    whichever side is more numerous that month wins the median outright, and the
    series steps between two scales that are 4,000x apart. See CURRENCY_ALIASES
    in `sources` for why a legacy code is aliased rather than dropped.

    A country with no rows in its declared currency gets NO entry at all. An
    empty or one-sided entry is worse than none: `_app.js` returns null on a
    missing rate and draws an honest gap, but a series built from the wrong unit
    draws a confident wrong line.
    """
    declared = {c: (m.get("currency") or "").upper() for c, m in countries.items()}
    fxr = obs.dropna(subset=["fx_rate"])
    ccy = fxr.currency.astype(str).str.upper().map(lambda c: CURRENCY_ALIASES.get(c, c))
    keep = ccy.eq(fxr.country.map(declared).astype(str).str.upper())
    fxr = fxr[keep]

    fx_tbl = (
        fxr.groupby(["country", "period"], observed=True).fx_rate.median().reset_index()
    )
    fx: dict[str, dict] = {}
    for c, g in fx_tbl.sort_values("period").groupby("country"):
        fx[c] = {"p": g.period.tolist(), "r": [round(v, 6) for v in g.fx_rate]}

    dropped = sorted(set(obs.country.unique()) - set(fx))
    if dropped:
        logger.warning(
            "FX: %d countries have no observation in their declared currency and "
            "get no overlay: %s",
            len(dropped),
            ", ".join(f"{c} (declared {declared.get(c) or '?'})" for c in dropped[:20]),
        )
    _warn_on_fx_span(fx)
    _warn_on_fx_excursion(fx)
    return fx


def _warn_on_fx_span(fx: dict[str, dict]) -> None:
    """Shout when a country's rate travels further than any currency should.

    A tripwire, not a filter. The Cambodia defect ran for months because the
    build never looked at the table it had just written; every cause -- a mixed
    median, a missed alias, a bad rate upstream -- shows up as an implausible
    span, so one check catches all of them. Genuine hyperinflation trips it too,
    and should: it is exactly the case a reader needs told about.
    """
    for c, g in sorted(fx.items()):
        rates = [r for r in g["r"] if r > 0]
        if len(rates) < 2:
            continue
        lo, hi = min(rates), max(rates)
        if hi / lo < FX_SPAN_WARN:
            continue
        logger.warning(
            "FX SPAN: %s moves %.0fx over %d months (%.6g at %s -> %.6g at %s). "
            "Either real hyperinflation or an upstream FX defect -- check before "
            "trusting the local-currency overlay for this country.",
            c,
            hi / lo,
            len(rates),
            lo,
            g["p"][g["r"].index(lo)],
            hi,
            g["p"][g["r"].index(hi)],
        )


def _warn_on_fx_excursion(fx: dict[str, dict]) -> None:
    """Shout when a rate leaves its own level by orders of magnitude and returns.

    The span check above says something is odd; this one says what. Distance
    from a currency's own long-run level is a BAD detector on its own -- it
    fires on SDG, VES, ARS, LBP, BYN, ZWL, SYP and IRR, where the move is a real
    redenomination or real hyperinflation and the series is right. What
    separates a bad RATE from a bad ECONOMY is the return: hyperinflation goes
    one way and a redenomination steps once and stays, whereas a wrong rate is
    an excursion whose two shoulders agree with each other and not with it.

    Mongolia is the case in hand: MNT sits at ~3,597 per USD, drops to 0.753181
    for 2025-11, and is back at 3,547 in 2025-12. The shoulders are 1.4% apart
    and the middle is 4,775x away from both. Underneath, the shared FX cache
    holds a 22-day block (2025-10-25 .. 2025-11-15) of sub-1 MNT rates that
    drift daily and copy no other currency in the cache -- the signature of a
    provider whose MNT is cross-derived rather than quoted, merged in during the
    Frankfurter backfill. Clean edges and a date-bounded interior; not a write
    race, and nothing to do with the currency LABEL, which is correct.

    What this does NOT catch, and is worth knowing: a bad rate in the first or
    last months of a series, because there is no shoulder to return to; a bad
    rate that persists past FX_EXCURSION_MAX_RUN months; anything under
    FX_EXCURSION_RATIO; and a bad rate that lands while the true rate is itself
    moving, because then the shoulders will not agree. The span check is the
    backstop for those -- an excursion large enough to matter also widens the
    span -- and neither is a substitute for fixing the cache.
    """
    for c, g in sorted(fx.items()):
        p, r = g["p"], g["r"]
        n = len(r)
        i = 1
        while i < n - 1:
            # widen a run of months that all sit off the level set by p[i-1]
            j = i
            while (
                j < n - 1
                and j - i < FX_EXCURSION_MAX_RUN
                and r[i - 1] > 0
                and r[j] > 0
                and max(r[i - 1] / r[j], r[j] / r[i - 1]) > FX_EXCURSION_RATIO
            ):
                j += 1
            if j > i and j < n and r[j] > 0 and r[i - 1] > 0:
                before, after = r[i - 1], r[j]
                shoulders = max(before / after, after / before)
                off = max(before / min(r[i:j]), max(r[i:j]) / before)
                if shoulders <= FX_EXCURSION_RETURN and off > FX_EXCURSION_RATIO:
                    logger.warning(
                        "FX EXCURSION: %s leaves %.6g (%s) by %.0fx for %d month(s) "
                        "(%s..%s) and returns to %.6g (%s). Shoulders agree to "
                        "within %.1f%%, so this is an upstream RATE defect, not a "
                        "currency move -- do not publish this month's overlay.",
                        c,
                        before,
                        p[i - 1],
                        off,
                        j - i,
                        p[i],
                        p[j - 1],
                        after,
                        p[j],
                        (shoulders - 1) * 100,
                    )
                    i = j
                    continue
            i += 1


def build_payload(region: str | None = None) -> dict:
    """Aggregate the corpus, optionally restricted to one region's countries.

    The restriction narrows WHO is shown, not what they are measured against.
    Every "vs world" figure keeps its global yardstick, computed below from the
    unrestricted cells, because a regional dashboard whose world median is
    secretly its own median would report a country as typical when it is only
    typical for its neighbours. That now includes the matched basket, which used
    to break the rule in silence -- see `basket_reference`.

    `nodeMeta[node].rmed` does publish a regional and subregional median beside
    `gmed`, and does not weaken that rule. The failure it guards against is a
    SILENT swap -- the screen saying "vs world" over a number that is not. An
    additional yardstick the reader selects, on a chart that renames its axis,
    its column and its tooltip when they do, is the opposite of that.
    """
    tax = load_taxonomy()
    countries = load_country_meta()
    topo = yaml.safe_load(REGIONS_YAML.read_text()) or {}
    region_labels = [m.get("name", k) for k, m in topo.items()]
    subregion_labels = sorted(
        {
            sm.get("name", sk)
            for m in topo.values()
            for sk, sm in (m.get("subregions") or {}).items()
        }
    )
    obs = load_observations()
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

    # Counted BEFORE the fold, and carried as a COLUMN rather than a scalar:
    # the honesty panel reports this scoped to the countries in THIS payload,
    # and that scope is not known until `cmeta` exists, hundreds of lines below
    # -- by which time the fold has relabelled these very rows as `unit` and the
    # count can no longer be recovered. One bool over 18.9M rows is ~19 MB.
    obs["item_basis"] = obs.standard_unit.eq("item")
    _fold_piece_units(obs)

    is_trusted = obs.qa_status.eq("trusted")
    # No `.copy()`: boolean-mask indexing already returns a frame that owns its
    # data, so the copy was a second 9 GB allocation taken at the one moment the
    # full `obs` was still alive -- the peak that got the render killed. Nothing
    # below writes to `trusted`; it is only read, merged, grouped and reassigned.
    trusted = obs[
        is_trusted & obs.standard_unit.isin(COMPARABLE_UNITS) & obs.unit_value_usd.gt(0)
    ]
    del is_trusted

    # PROJECTED, not freed. The scope-aware QA counts and `_fx_table` both still
    # need every ROW of the unfiltered frame, so it cannot be released here the
    # way it was when those counts were global -- but between them they read
    # nine of its thirteen columns, and none of the wide object ones. Held whole
    # to the end, `obs` (11 GB, nine object columns over 18.9M rows) sat
    # alongside `trusted` and the exploded ladder and the render was OOM-killed
    # at 23.4 GB. This is also why `_fx_table`'s `dropna` is now cheap: it
    # copies a narrow frame instead of the whole corpus.
    obs = obs[_OBS_TAIL_COLS]

    # Pruned AFTER the projection, not before: `drop_pruned` returns a filtered
    # frame that owns its data, so this never holds two full copies.
    before = len(trusted)
    trusted = drop_pruned(trusted, pruned)
    if len(trusted) != before:
        logger.info(
            "rtcal pruning dropped %d of %d trusted rows (%d rejected cells)",
            before - len(trusted),
            before,
            len(pruned),
        )

    fills = fills[fills.standard_unit.isin(COMPARABLE_UNITS)]

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
    # Here, and not on `obs`: `collapse` copies the rows it keeps, and the
    # unfiltered 18.9M-row frame cannot be copied on this box. By this line it
    # has been projected down to `_OBS_TAIL_COLS` and `trusted` is the only large
    # object alive. This also lands before `_pool`, so every median, series,
    # chain and `gmed` below is computed on collapsed units.
    #
    # The piece fold above already ran, which matters: `unit_collapse` votes on
    # unit LABELS, and `item`/`unit` are two spellings of one piece price on the
    # allowlisted leaves, so voting before the fold could hand a leaf to the loser.
    #
    # Fills are collapsed against the units the OBSERVATIONS voted for rather
    # than voting again on their own rows. Voting twice can give one leaf two
    # display units -- the split row this exists to remove -- and a modelled row
    # should never get a say in how a commodity is sold.
    typical_mass = (
        pd.read_csv(TYPICAL_MASS_CSV) if TYPICAL_MASS_CSV.exists() else pd.DataFrame()
    )
    if typical_mass.empty:
        logger.warning("%s missing -- piece rows cannot convert", TYPICAL_MASS_CSV)
    before = len(trusted)
    trusted, suppressed = unit_collapse.collapse(trusted, typical_mass)
    display = (
        trusted.groupby("coicop_code")["standard_unit"]
        .agg(lambda s: s.iloc[0])
        .to_dict()
    )
    fills, _ = unit_collapse.collapse(
        fills, typical_mass, value_cols=("usd",), canonical=display
    )
    logger.info(
        "unit collapse: %d trusted rows -> %d in %d display units, "
        "dropped %d unconvertible over %d leaves",
        before,
        len(trusted),
        trusted.standard_unit.nunique(),
        len(suppressed),
        suppressed.coicop_code.nunique(),
    )
    # `collapse` already hands back the dropped rows carrying `drop_reason` and
    # the `display_unit` they could not reach. Discarding that was the whole
    # cost of "the explorer writes no suppression audit": the count reached the
    # log and the evidence reached nothing.
    if not suppressed.empty:
        SUPPRESSED_PARQUET.parent.mkdir(parents=True, exist_ok=True)
        suppressed.to_parquet(SUPPRESSED_PARQUET, index=False)
        logger.info(
            "wrote %d suppressed rows over %d leaves -> %s",
            len(suppressed),
            suppressed.coicop_code.nunique(),
            SUPPRESSED_PARQUET,
        )
    # The provenance column has done its job by here, and the suppression audit
    # above has already taken its copy. Carried on, `_explode_nodes` would multiply an object
    # column by every row's ancestor count.
    trusted = trusted.drop(columns="display_unit_source")

    # The global pass, over every country in the corpus. It settles the two
    # things a regional payload must NOT settle for itself -- the eligible
    # basket and the world median -- and it is thrown away immediately
    # afterwards, because the exploded frame is the largest object here.
    world_ex, world_ex_fill = _pool(trusted, fills)
    # A SECOND, SMALL POOL rather than a flag on the big one. The current grid
    # needs a CELL_WINDOW_DAYS slice; the series needs all of history. Carrying a marker
    # per row on the exploded frame would cost a byte across ~90M rows, so the
    # window is exploded on its own and thrown away as soon as the grid is out.
    _cw_ex, _cw_fill = _pool(*_cell_window(trusted, fills))
    world_cells = _cells(_cw_ex, _cw_fill)
    del _cw_ex, _cw_fill
    reference = basket_reference(world_cells, tax)
    n_ref_countries = world_cells.country.nunique()

    if region:
        label = _region_label(region)
        keep = {s for s, m in countries.items() if m["region"] == label}
        del world_ex, world_ex_fill
        trusted = trusted[trusted.country.isin(keep)].copy()
        fills = fills[fills.country.isin(keep)]
        if trusted.empty:
            raise SystemExit(f"no trusted observations for region {region!r} ({label})")
        exploded, ex_fill = _pool(trusted, fills)
        _cw_ex, _cw_fill = _pool(*_cell_window(trusted, fills))
        cells = _cells(_cw_ex, _cw_fill)
        del _cw_ex, _cw_fill
    else:
        # Identical inputs, so the global build does this exactly once. It used
        # to explode and aggregate the whole corpus twice for the same answer.
        exploded, ex_fill = world_ex, world_ex_fill
        cells = world_cells

    series = _series(exploded, ex_fill)
    chained = _chained_index(exploded, tax, ex_fill)
    changed = _lagged_changes(exploded, tax, ex_fill)
    basket_w, wmeta = default_weights(tax, BASKET_WEIGHT_LEVEL)
    basket_cty: dict[str, dict] = {}
    levels = _basket_levels(cells, tax, basket_w, basket_cty, reference=reference)
    basket_modes = _weight_modes(
        tax, basket_w, wmeta, {c for m in basket_cty.values() for c in m}
    )

    # ---- country meta -------------------------------------------------
    cmeta: dict[str, dict] = {}
    lvl_map = dict(zip(levels.country, levels.level))
    nleaf_map = dict(zip(levels.country, levels.n_leaves))
    ok_map = dict(zip(levels.country, levels.ok))
    gate_map = dict(zip(levels.country, levels.gate))
    defect_map = dict(zip(levels.country, levels.defect_share))
    cov_map = dict(zip(levels.country, levels.covered))
    imp_map = dict(zip(levels.country, levels.imp))
    fill_n = fills.groupby("country").size().to_dict() if not fills.empty else {}
    grp = trusted.groupby("country", observed=True)
    for slug, g in grp:
        base = countries.get(
            slug,
            {
                "name": slug,
                "iso3": "",
                "region": "Unassigned",
                "subregion": "Unassigned",
            },
        )
        retail = g[~g.is_modelled]
        cmeta[slug] = {
            "name": base["name"],
            "iso3": base["iso3"],
            "region": base["region"],
            "subregion": base["subregion"],
            "obs": int(len(g)),
            "src": int(g.source.nunique()),
            "retail_src": int(retail.source.nunique()),
            "cur": sorted(g.currency.dropna().unique().tolist()),
            "leaves": int(g.coicop_code.nunique()),
            "level": round(float(lvl_map[slug]), 1) if slug in lvl_map else None,
            "level_n": int(nleaf_map.get(slug, 0)),
            "level_ok": bool(ok_map.get(slug, False)),
            # The corpus half of the gate, published so a client that has moved
            # the weights can re-decide the coverage half on its own. `level_ok`
            # already folds coverage in and therefore cannot answer "would this
            # country be ranked if coverage were not the question".
            "level_gate": bool(gate_map.get(slug, False)),
            "level_cov": (
                round(float(cov_map[slug]), 3)
                if slug in cov_map and pd.notna(cov_map[slug])
                else None
            ),
            # THE COUNTRY'S IMPUTED SHARE, weighted exactly the way its price
            # level is -- the same categories under the same weights -- so this
            # answers "how much of the number this country is ranked on came
            # from a model" rather than "how modelled is this country's corpus",
            # which is a different and much less useful question. Null where the
            # country has no basket at all.
            "imp": (
                round(float(imp_map[slug]), 4)
                if slug in imp_map and pd.notna(imp_map[slug])
                else None
            ),
            # Released fills standing behind this country at any node. A count,
            # not a share; `obs` above counts measured rows and never counts
            # these.
            "n_imp": int(fill_n.get(slug, 0)),
            "defect": round(float(defect_map.get(slug, 0.0) or 0.0), 3),
            "last": str(g.period.max()),
        }

    # ---- node meta: dominant unit + volume ----------------------------
    # OBSERVED VOLUME ONLY. `units` decides which unit a node is quoted in on
    # screen, and `dom` is the winner of that count -- so a fill must not vote.
    # How a commodity is sold is a fact about the commodity, and a modelled row
    # is not evidence about it. The pooled frame is netted down by the fills
    # rather than rebuilt, because the group-by over ~90M rows is the expensive
    # half and the fills are a rounding error beside it.
    nodemeta: dict[str, dict] = {}
    nu = exploded.groupby(["node", "standard_unit"], observed=True).size()
    if not ex_fill.empty:
        nu = nu.subtract(
            ex_fill.groupby(["node", "standard_unit"], observed=True).size(),
            fill_value=0,
        ).astype("int64")
        nu = nu[nu > 0]
    for node, sub in nu.groupby(level=0):
        by_unit = {u: int(v) for (_, u), v in sub.items()}
        nodemeta[node] = {
            "units": by_unit,
            "dom": max(by_unit, key=by_unit.get),
            "n": int(sum(by_unit.values())),
            "countries": 0,
        }
    # A node nothing measured but something modelled has no observed volume and
    # so no entry above. It still has cells, and dropping it here would throw
    # away exactly the cells this whole change exists to publish.
    if not ex_fill.empty:
        nf = ex_fill.groupby(["node", "standard_unit"], observed=True).size()
        for node, sub in nf.groupby(level=0):
            if node in nodemeta:
                continue
            by_unit = {u: int(v) for (_, u), v in sub.items()}
            nodemeta[node] = {
                "units": {},
                "dom": max(by_unit, key=by_unit.get),
                "n": 0,
                "countries": 0,
            }
    for node, n in cells.groupby("node").country.nunique().items():
        if node in nodemeta:
            nodemeta[node]["countries"] = int(n)
    # `countries` counts every country with a published cell here, measured or
    # modelled. `countries_obs` counts the ones that measured it. A node where
    # the two differ is a node the fills opened up, and the client can say so
    # without having to re-derive it from the cell array.
    obs_cells = cells[cells.n > 0]
    for node, n in obs_cells.groupby("node").country.nunique().items():
        if node in nodemeta:
            nodemeta[node]["countries_obs"] = int(n)
    for meta in nodemeta.values():
        meta.setdefault("countries_obs", 0)

    # SUPPRESS THE NODES NOTHING PRICES. A category filter that offers a
    # category with nothing behind it is a filter that produces empty screens on
    # purpose. "Nothing behind it" means no published cell in ANY country in
    # this payload -- not a depth test and not a taxonomy test, both of which
    # have been wrong here before: maize `01.1.1.4.0` is priced in 181 countries
    # and rice `01.1.1.1.2` in 202, and a node that looks blank on screen while
    # carrying cells is a gate to go and find, never a node to delete.
    #
    # An ancestor pools every row its descendants pool, so it can never have
    # fewer, and dropping on this rule cannot orphan a surviving child.
    priced = set(cells.node.unique())
    dropped = [n for n in nodemeta if n not in priced]
    for node in dropped:
        del nodemeta[node]
    if dropped:
        logger.info(
            "suppressed %d taxonomy nodes no country prices: %s",
            len(dropped),
            ", ".join(sorted(dropped)[:12]) + (" ..." if len(dropped) > 12 else ""),
        )
    # World median per (node, unit) over unflagged retail cells — the yardstick
    # every "vs world" figure divides by. Catch-all leaves get none: a median of
    # "other bakery products" across countries pools croissants against
    # flatbread, which is the comparison `publish` has always withheld.
    # An aggregate node gets none either. "$4.10/kg for Cereals" divides one
    # country's mix of rice, bread and pasta by another's, and the ratio moves
    # with whichever items each happened to price. Withholding it server-side is
    # what keeps a client from reconstructing the figure from the payload.
    residual_nodes = _residual_nodes(tax)
    leafy = world_cells.node.map(lambda c: bool(tax.get(c, {}).get("leaf")))
    clean = world_cells[
        leafy
        & ~world_cells.flagged
        & (world_cells.modelled < 0.5)
        & ~world_cells.node.isin(residual_nodes)
    ]
    for (node, unit), v in (
        clean.groupby(["node", "standard_unit"]).usd.median().items()
    ):
        if node in nodemeta:
            nodemeta[node].setdefault("gmed", {})[unit] = round(float(v), 4)

    # Regional and subregional yardsticks, keyed by the label the geography
    # carries in `cty`. This is an ADDITION to `gmed` and never a replacement
    # for it: `gmed` above stays the default reading on every screen, and the
    # only way to be read against neighbours instead of against the world is to
    # ask for it, on a chart that then says which yardstick it is using. The
    # invariant in this function's docstring is about substitution, not about
    # supply -- a regional benchmark the reader has explicitly selected and the
    # chart has explicitly labelled is not the "secretly its own median" failure
    # that rule exists to prevent.
    #
    # Same cells and the same filters as `gmed`; only the population being taken
    # a median of changes. Under MIN_BENCH_COUNTRIES nothing is written at all,
    # so a two-country "region" has no entry rather than a private price wearing
    # a region's name.
    where = clean.country.map(lambda s: countries.get(s, {}))
    geo_cells = clean.assign(
        region=[m.get("region", "Unassigned") for m in where],
        subregion=[m.get("subregion", "Unassigned") for m in where],
    )
    for field in ("region", "subregion"):
        grouped = geo_cells.groupby([field, "node", "standard_unit"]).agg(
            med=("usd", "median"), n=("country", "nunique")
        )
        for (label, node, unit), row in grouped.iterrows():
            if row.n < MIN_BENCH_COUNTRIES or node not in nodemeta:
                continue
            rmed = nodemeta[node].setdefault("rmed", {})
            rmed.setdefault(label, {})[unit] = round(float(row.med), 4)

    # ---- QA / honesty panel -------------------------------------------
    # SCOPED TO THIS PAYLOAD. These four counts used to be taken off the whole
    # unrestricted parquet, so an EAP build reported the world's QA mix beside
    # EAP's prices and a reader comparing them to anything else on the page was
    # comparing two different populations. `in_scope` is every row of every
    # status for the countries this payload shows.
    in_scope = (
        obs.country.isin(set(cmeta)) if region else pd.Series(True, index=obs.index)
    )
    scoped_trusted = in_scope & obs.qa_status.eq("trusted")
    qa = {
        "status": {
            k: int(v) for k, v in obs.qa_status[in_scope].value_counts().items()
        },
        "mass_source": {
            str(k): int(v)
            for k, v in obs.mass_source[scoped_trusted]
            .value_counts(dropna=False)
            .items()
        },
        "item_basis_rows": int((scoped_trusted & obs.item_basis).sum()),
        "modelled_rows": int((scoped_trusted & obs.is_modelled).sum()),
        # Every count in this block, and every count in `meta`, describes the
        # countries in THIS payload and nothing wider.
        "scope": {"region": region, "countries": len(cmeta)},
        # THE GEOGRAPHY VOCABULARY. `nodeMeta[*].rmed` is one flat map keyed by
        # label, holding regions and subregions together with nothing in the key
        # to say which is which -- so these two lists are the discriminator, and
        # they come from `regions.yaml` rather than from a copy of it in the
        # client. Every label in `cty[*].region` appears in the first list and
        # every `cty[*].subregion` in the second.
        "regions": region_labels,
        "subregions": subregion_labels,
        "modelled_sources": sorted(MODELLED_SOURCES),
        "plausible_bounds": PLAUSIBLE_USD,
        "min_basket_leaves": MIN_BASKET_LEAVES,
        # The leaf gate, published so the client can state the missing-price
        # policy in the same words the build applies it in.
        "min_basket_leaf_share": MIN_BASKET_LEAF_SHARE,
        "min_basket_weight_covered": MIN_BASKET_WEIGHT_COVERED,
        # The regional yardstick is an addition, and the payload says so, so a
        # future reader of `rmed` cannot mistake it for the default.
        "benchmark": {
            "default": "world",
            "alternatives": ["region", "subregion"],
            "min_countries": MIN_BENCH_COUNTRIES,
            "labelled": True,
        },
        # Some gaps are now filled, and the reason the old promise existed is
        # the reason the new one is shaped the way it is. That promise --
        # "nothing is interpolated" -- was never about imputation being wrong.
        # It was about an imputed value being INDISTINGUISHABLE on screen from a
        # measured price move. RT-CAL answers that objection rather than
        # overruling it: every fill is labelled and is off by default.
        #
        # What HAS changed is what a fill is allowed to touch, and the change is
        # total. Fills reach the series, the cells, the chained index, the
        # change family, the basket level, the geography series and the regional
        # and world medians -- everything this payload publishes. Holding them
        # at the leaf left every aggregate above them as blank as it had ever
        # been, which was the complaint.
        #
        # The exclusion is replaced by a MEASURE. Wherever a figure could have
        # been touched by a fill it carries the share of the values behind it
        # that were imputed, under the field named in `share_field` below, and a
        # figure with no measured evidence at all is flagged outright. So the
        # honest sentence is no longer "nothing here is modelled" but "here is
        # exactly how much of this is", which is a stronger claim and a checkable
        # one.
        #
        # NO ACCURACY FIGURE IS PUBLISHED. Each fill carries its own calibrated
        # probability, which is a statement about that cell. The released
        # population now mixes normal gaps validating near 80% within 25% with
        # cold-start cells near 42%, and a single headline number over that
        # mixture would describe neither of them.
        #
        # Two older behaviours come close enough to need saying out loud, so they
        # are published rather than left in the source:
        #
        # `link_gap_months` -- a chain link may span this many periods, and the
        # WHOLE log relative is booked onto the later one. A three-month move
        # then reads as a one-month move on the monthly chain.
        #
        # `fitted_level` -- the US$ level at a geography is a two-way
        # fixed-effects FITTED value, not an observed median. That is
        # model-based, and the client labels it as such.
        "link_gap_months": {"chain": MAX_LINK_GAP_MONTHS, **FREQ_MAX_GAP},
        "fitted_level": "two-way fixed effects on log price (item + period)",
        "interpolated": {
            "cells": int(len(fills)),
            "scope": [
                "series",
                "cells",
                "chain",
                "changes",
                "basket",
                "heatmap",
                "gseries",
                "gmed",
                "rmed",
            ],
            "excluded_from": [],
            "default_visible": False,
            "labelled": True,
            # WHERE THE PROVENANCE LIVES, per structure, because it is not one
            # field name everywhere and pretending otherwise would be worse than
            # saying so. `cells[*].imp` is a share; `series[*].imp` is a 0/1
            # flag with the share beside it as `ish`, because the app has read
            # that field as a flag since before fills reached the cells and a
            # drawn point is either modelled or it is not.
            "fields": {
                "cells": {"share": "imp", "count": "nim", "prob": "pr"},
                "series": {"share": "ish", "flag": "imp", "count": "nim", "prob": "pr"},
                "chain": {"share": "ish"},
                "changes": {"share": "ish"},
                "gseries": {"share": "ish", "share_index": "ish_idx"},
                "gseries.chg": {"share": "ish"},
                "cty": {"share": "imp", "count": "n_imp"},
            },
            "share_of": "the values pooled into the figure, not the leaves",
            "probability": "per cell: calibrated P(within 25% of the observed median)",
            "headline_accuracy": None,
            "method": "rtcal_v1",
        },
    }

    recent = trusted.period.max()
    qa["history"] = {
        "latest_period": str(recent),
        "share_latest_period": round(float((trusted.period == recent).mean()), 4),
        "share_last_12m": round(
            float(
                (
                    pd.PeriodIndex(trusted.period, freq="M")
                    >= pd.Period(recent, freq="M") - 11
                ).mean()
            ),
            4,
        ),
        "min_link_leaves": MIN_LINK_LEAVES,
    }

    # ---- FX: local per USD, monthly ------------------------------------
    fx = _fx_table(obs, countries)

    gseries_raw, geos = build_geo_series(exploded, tax, cmeta, ex_fill)

    official = load_official({s: countries.get(s, {}).get("iso3") for s in cmeta})
    used_series = {k for v in official.values() for k in v}

    # An EXTERNAL price level, to check our own against. ICP prices about a
    # thousand products per economy under a common specification and publishes
    # a food-and-beverage price level on the SAME World = 100 base this
    # dashboard uses; the WDI publishes a whole-economy one. Neither is blended
    # into our figure or corrects it -- it is an overlay, the way the official
    # CPI is an overlay on the change series. The basket weight vector goes in
    # with it so the benchmark is aggregated the way our own number is, and the
    # difference between the two is prices rather than method. Empty when the
    # standalone table has not been built.
    # `basket_cty` is the per-country matrix the level was collapsed FROM, so
    # its keys are exactly the categories that country priced. Handing it over
    # is what keeps the benchmark on our scope as well as on our weights.
    ppp, ppp_meta = load_benchmark(
        {s: countries.get(s, {}).get("iso3") for s in cmeta},
        basket_w,
        {s: set(m) for s, m in basket_cty.items()},
    )

    # `nodemeta` has already had the unpriced nodes taken out of it, so the
    # index, the taxonomy and every keyed structure below follow from that one
    # decision rather than each re-deciding it.
    node_idx = sorted(nodemeta)
    node_pos = {n: i for i, n in enumerate(node_idx)}
    cty_idx = sorted(cmeta)
    cty_pos = {c: i for i, c in enumerate(cty_idx)}
    unit_idx = list(COMPARABLE_UNITS)
    unit_pos = {u: i for i, u in enumerate(unit_idx)}
    cur_idx = sorted(cells.currency.dropna().unique().tolist())
    cur_pos = {c: i for i, c in enumerate(cur_idx)}

    cells = cells[cells.country.isin(cty_pos) & cells.node.isin(node_pos)]
    cell_payload = {
        "c": [cty_pos[c] for c in cells.country],
        "n": [node_pos[n] for n in cells.node],
        "u": [unit_pos[u] for u in cells.standard_unit],
        "usd": [round(float(v), 4) for v in cells.usd],
        "loc": [None if pd.isna(v) else round(float(v), 4) for v in cells.local],
        "cur": [cur_pos.get(c, -1) for c in cells.currency],
        "obs": [int(v) for v in cells.n],
        "mad": [None if pd.isna(v) else round(float(v), 3) for v in cells.mad],
        "src": [int(v) for v in cells.sources],
        "mod": [round(float(v), 2) for v in cells.modelled],
        "der": [round(float(v), 2) for v in cells.derived],
        "mix": [bool(v) for v in cells.mixed_currency],
        "flag": [bool(v) for v in cells.flagged],
        "per": cells.period.tolist(),
        # ---- provenance, parallel arrays over the same cells -------------
        # `imp` is a SHARE in [0, 1]: how much of the median in this cell came
        # from a fill rather than from a measured price. At a leaf it is 0 or 1;
        # at an aggregate node it is the mixture the ladder produced, which is
        # the number that makes exploding fills up the tree honest rather than
        # silent. A wholly modelled cell is `obs == 0`, equivalently `imp == 1`,
        # so no separate flag is shipped.
        #
        # NOTE the asymmetry with `series[*].imp`, which is a 0/1 FLAG: a series
        # point is either drawn as modelled or it is not, and the app has read
        # that field as a flag since before fills reached the cells. The series
        # share is `ish`.
        #
        # `nim` is the count behind the share, and `pr` the mean calibrated
        # probability of the fills in the cell (null where there are none).
        "imp": [round(float(v), 4) for v in cells.imp],
        "nim": [int(v) for v in cells.nimp],
        "pr": [None if pd.isna(v) else round(float(v), 3) for v in cells.prob],
    }

    ser: dict[str, dict] = {}
    for (c, n, u), g in series.sort_values("period").groupby(
        ["country", "node", "standard_unit"], observed=True
    ):
        if c not in cty_pos or n not in node_pos:
            continue
        entry = {
            "p": g.period.tolist(),
            "usd": [round(float(v), 4) for v in g.usd],
            "loc": [None if pd.isna(v) else round(float(v), 4) for v in g.local],
            "n": [int(v) for v in g.n],
        }
        # Omitted entirely when a series carries no fill, so a payload built
        # without RT-CAL is byte-identical to the one before it. `imp` keeps the
        # meaning it always had -- 1 where the point is wholly modelled, which
        # is what the client's "hide imputed" filter drops -- and `ish` is new:
        # a partly-modelled point at an aggregate node has imp 0 and ish > 0,
        # so hiding wholly-modelled points does not silently hide those too.
        if bool((g.nimp > 0).any()):
            entry["imp"] = [1 if v else 0 for v in g.imputed]
            entry["ish"] = [round(float(v), 4) for v in g.imp]
            entry["nim"] = [int(v) for v in g.nimp]
            entry["pr"] = [None if pd.isna(v) else round(float(v), 3) for v in g.prob]
        ser[f"{cty_pos[c]}|{node_pos[n]}|{unit_pos[u]}"] = entry

    chain: dict[str, dict] = {}
    for (c, n, u), g in chained.groupby(
        ["country", "node", "standard_unit"], observed=True
    ):
        if c not in cty_pos or n not in node_pos:
            continue
        chain[f"{cty_pos[c]}|{node_pos[n]}|{unit_pos[u]}"] = {
            "p": g.period.tolist(),
            "idx": [round(float(v), 2) for v in g.idx],
            "k": [int(v) for v in g.n_leaves],
            # The imputed share of the LINKS averaged into this period's step,
            # where a link counts as imputed to the degree its LESS measured end
            # was. It is per step and does not accumulate: the index at t is the
            # product of every link before it, but "how modelled was this move"
            # is a question about this move.
            "ish": [round(float(v), 4) for v in g.imp],
        }

    # Country-grain changes, keyed like `chain`: one entry per (country, node,
    # unit), each horizon a period-aligned list of percent changes and the count
    # of leaves the average was taken over.
    changes: dict[str, dict] = {}
    for (c, n, u, lag), g in changed.sort_values("period").groupby(
        ["country", "node", "standard_unit", "lag"], observed=True
    ):
        if c not in cty_pos or n not in node_pos:
            continue
        entry = changes.setdefault(f"{cty_pos[c]}|{node_pos[n]}|{unit_pos[u]}", {})
        entry[str(lag)] = {
            "p": g.period.tolist(),
            "v": [round(float(np.expm1(v)) * 100, 3) for v in g.lr],
            "k": [int(v) for v in g.k],
            "ish": [round(float(v), 4) for v in g.imp],
        }

    gseries: dict[str, dict] = {}
    for k, v in gseries_raw.items():
        freq, gk, node, unit = k.split("|")
        if node in node_pos and unit in unit_pos:
            gseries[f"{freq}|{gk}|{node_pos[node]}|{unit_pos[unit]}"] = v

    # HEADLINE COUNTS, each naming its own population. Two of these are
    # legitimately different numbers over different things -- the corpus and the
    # grid -- and the failure they are here to prevent is a reader taking the
    # difference for an error. Every one is scoped to this payload's countries.
    #
    # THE GRID IS THE LEAF CELLS. `cells` also carries a row for every ancestor
    # node, because the tree views read them, and an observation of rice is
    # pooled into its class, its group and its division as well as into rice. So
    # summing `n` over the whole array counts most observations about five times
    # and lands nowhere near the total a reader gets by adding up the column the
    # heatmap shows them. Every "grid" figure below is taken over leaves only,
    # which is both what is drawn and the only count that does not double.
    grid = cells[cells.node.map(lambda c: bool(tax.get(c, {}).get("leaf")))]
    counts = [
        {
            "key": "countries",
            "label": "Countries",
            "value": len(cty_idx),
            "note": "shown in this view",
        },
        {
            "key": "obs",
            "label": "Trusted price observations",
            "value": int(len(trusted)),
            "note": "every shelf price collected for these countries, all of "
            "history, in kilograms, litres or pieces",
        },
        {
            "key": "grid_obs",
            "label": "Observations behind the current grid",
            "value": int(grid.n.sum()),
            "note": "the latest month of each published category cell only -- "
            "this is the population the heatmap totals",
        },
        {
            "key": "grid_cells",
            "label": "Cells in the current grid",
            "value": int(len(grid)),
            "note": "one per (country, category, unit) with enough evidence to "
            "publish",
        },
        {
            "key": "grid_imputed",
            "label": "Grid cells with no measured price",
            "value": int((grid.n == 0).sum()),
            "note": "modelled in full; every cell also carries the share of "
            "itself that was modelled",
        },
        {
            "key": "sources",
            "label": "Retail sources",
            "value": int(trusted.source.nunique()),
            "note": "distinct scraped sources behind the observations",
        },
        {
            "key": "categories",
            "label": "Categories priced",
            "value": int(sum(1 for c in node_idx if tax.get(c, {}).get("leaf"))),
            "note": "COICOP leaves with a published cell somewhere in this view",
        },
    ]

    samples = {}
    for k, v in _samples(trusted).items():
        c, code, unit = k.split("|")
        if c in cty_pos and code in node_pos:
            samples[f"{cty_pos[c]}|{node_pos[code]}|{unit_pos[unit]}"] = v

    return {
        "meta": {
            "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "through": str(trusted.period.max()),
            "n_obs": int(len(trusted)),
            "n_countries": len(cty_idx),
            "n_nodes": len(node_idx),
            "n_sources": int(trusted.source.nunique()),
            "min_cell_obs": MIN_CELL_OBS,
            "cell_window_days": CELL_WINDOW_DAYS,
            "geo_min_pairs": FE_MIN_PAIRS,
            "divisions": ["01", "02"],
            # THE BUILD'S OWN SCOPE, stated rather than inferred. `region` is
            # the key passed on the command line and null for a global build;
            # `region_label` is what that key is called on screen. A client was
            # otherwise reduced to asking whether every country happens to share
            # a region, which is true of a global build restricted to one region
            # and also true of a region that happens to hold one country.
            "region": region,
            "region_label": _region_label(region) if region else None,
            # ---- what the grid actually draws from ----------------------
            # `n_obs` above is the whole trusted corpus for the countries in
            # this payload, over all of history. The grid is a much smaller
            # thing: one period per cell, comparable units, cells that cleared
            # the evidence bar. Reporting the first while the second is on
            # screen is what made a header say 7.4 million over a table
            # totalling a bit under 1.1 million, and no reader could tell those
            # were two populations rather than a discrepancy. Both are published
            # here, each with its own name, and `counts` below labels them.
            "n_grid_cells": int(len(grid)),
            "n_grid_obs": int(grid.n.sum()),
            "n_grid_imputed": int(grid.nimp.sum()),
            "n_grid_cells_imputed": int((grid.n == 0).sum()),
            # The whole `cells` array, aggregate nodes included. Kept apart from
            # the grid figures above because summing anything over it
            # double-counts up the tree.
            "n_cells_all": int(len(cells)),
            "n_fills": int(len(fills)),
            "n_leaves_priced": int(
                sum(1 for c in node_idx if tax.get(c, {}).get("leaf"))
            ),
            "counts": counts,
        },
        "tax": {k: v for k, v in tax.items() if k in node_pos},
        # Catch-all leaves, shipped so the client can hold them out of every
        # LEVEL view and keep them in the change views, where a group compared
        # with its own past is a perfectly good basket.
        "residual": sorted(_residual_nodes(tax) & set(node_pos)),
        "nodeIdx": node_idx,
        "nodeMeta": {node_idx[i]: nodemeta[node_idx[i]] for i in range(len(node_idx))},
        "ctyIdx": cty_idx,
        "cty": cmeta,
        "unitIdx": unit_idx,
        "curIdx": cur_idx,
        "cells": cell_payload,
        "series": ser,
        "chain": chain,
        "changes": changes,
        "geos": geos,
        "gseries": gseries,
        "fx": fx,
        # Official CPI, straight from the IMF and untouched: a local-currency
        # index the client draws beside our own series after converting OURS
        # into local terms. Empty when the standalone table has not been built.
        "basket": {
            # The weight vector the build used, the level it acts on, and where
            # it came from. Shipped rather than recomputed on the client so a
            # figure on screen and a figure in the parquet cannot drift, and so
            # a reader who moves a slider can be shown what they moved it FROM.
            "lvl": BASKET_WEIGHT_LEVEL,
            "within": "equal-within-parent below the weighted level",
            "w0": {k: round(v, 6) for k, v in sorted(basket_w.items())},
            "wmeta": wmeta,
            # The per-(country, category) terms, `{slug: {code: [rel, k]}}`.
            # `rel` is the category-level log ratio against the world, `k` the
            # leaves behind it. Roughly 200 countries x 21 categories, so a few
            # thousand numbers and no encoding worth inventing.
            "cty": basket_cty,
            # The selectable vectors, `{key: {"w": vector, "meta": provenance}}`.
            # `w0` above is the ICP entry repeated: it is what the `level` in
            # this payload was actually built with, and the client checks
            # itself against it. `mode0` names the one that is published.
            "modes": basket_modes,
            "mode0": "icp",
            # Titles for the categories the sliders act on and for the groups
            # and divisions above them. `tax` carries all of this ALREADY for
            # every node the corpus prices -- but a category in `w0` that no
            # country priced at all is absent from `tax` and still needs a
            # slider, because it is still in the denominator of `covered`.
            "lab": {
                c: tax[c]["t"]
                for c in sorted(
                    _weight_labels(
                        {c: 1.0 for m in basket_modes.values() for c in m["w"]}
                    )
                )
                if c in tax
            },
            "gates": {
                "leaf_share": MIN_BASKET_LEAF_SHARE,
                "min_leaves": MIN_BASKET_LEAVES,
                "min_sources": MIN_BASKET_SOURCES,
                "defect_share": COUNTRY_DEFECT_SHARE,
                "min_covered": MIN_BASKET_WEIGHT_COVERED,
                # WHERE THE BASKET WAS DECIDED. Both the eligible (leaf, unit)
                # set and the reference median are settled over the whole
                # corpus, so a regional payload is on the same scale and holds
                # the same items as the global one and the two can be read side
                # by side. `n_eligible` is the size of that set.
                "eligible_over": "global",
                "eligible_countries": int(n_ref_countries),
                "n_eligible": int(len(reference[0])),
            },
        },
        "cpi": official,
        "cpiMeta": {
            "labels": {k: v for k, v in SERIES_LABEL.items() if k in used_series},
            "division": {k: v for k, v in DIVISION_OF.items() if k in used_series},
            "source": "IMF, Consumer Price Index (IMF.STA:CPI), monthly index",
        },
        "ppp": ppp,
        "pppMeta": ppp_meta,
        "samples": samples,
        "qa": qa,
    }


def write_payload(path: Path) -> Path:
    payload = build_payload()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, separators=(",", ":")))
    return path
