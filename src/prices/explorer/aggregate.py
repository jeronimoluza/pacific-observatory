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

from prices.coicop import residual_leaves
from prices.explorer.cpi import DIVISION_OF, SERIES_LABEL, load_official
from prices.explorer.geo import build_geo_series
from prices.explorer.sources import (
    REGIONS_YAML,
    CHANGE_LAGS,
    COMPARABLE_UNITS,
    FE_MIN_PAIRS,
    FREQ_MAX_GAP,
    COUNTRY_DEFECT_SHARE,
    MAX_LINK_GAP_MONTHS,
    MIN_BASKET_LEAF_SHARE,
    MIN_BASKET_LEAVES,
    MIN_BASKET_SOURCES,
    MIN_BENCH_COUNTRIES,
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


def _mad(x: pd.Series) -> float:
    """Robust log dispersion of a unit-value cell — the reliability signal."""
    v = np.log(x[x > 0])
    if len(v) < 2:
        return float("nan")
    return float(np.median(np.abs(v - np.median(v))))


def _explode_nodes(trusted: pd.DataFrame) -> pd.DataFrame:
    """One row per (observation, ancestor node) so every tree level aggregates."""
    codes = trusted.coicop_code.unique()
    ladder = pd.DataFrame(
        [(c, n) for c in codes for n in _levels(c)], columns=["coicop_code", "node"]
    )
    return trusted.merge(ladder, on="coicop_code", how="inner")


def _cells(exploded: pd.DataFrame) -> pd.DataFrame:
    """Latest-period medians per (country, node, unit) plus quality flags."""
    keys = ["country", "node", "standard_unit"]
    latest = exploded.groupby(keys, observed=True).period.max().rename("period")
    cur = exploded.merge(latest, on=keys + ["period"], how="inner")

    agg = (
        cur.groupby(keys + ["period"], observed=True)
        .agg(
            usd=("unit_value_usd", "median"),
            n=("unit_value_usd", "size"),
            mad=("unit_value_usd", _mad),
            modelled=("is_modelled", "mean"),
            derived=("is_derived", "mean"),
            sources=("source", "nunique"),
        )
        .reset_index()
    )

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
    agg["mixed_currency"] = (agg.n_local / agg.n) < 0.9
    agg = agg[agg.n >= MIN_CELL_OBS].copy()

    lo = agg.standard_unit.map(lambda u: PLAUSIBLE_USD[u][0])
    hi = agg.standard_unit.map(lambda u: PLAUSIBLE_USD[u][1])
    agg["flagged"] = ~agg.usd.between(lo, hi)
    return agg


def _series(exploded: pd.DataFrame, fills: pd.DataFrame | None = None) -> pd.DataFrame:
    """Monthly medians per (country, node, unit), optionally with RT-CAL fills.

    Fills are appended as extra rows carrying `imputed`, never merged into an
    observed one. Three rules keep them honest, and each is load-bearing:

    LEAF ONLY. A fill is already a cell median; an observation is a single row.
    Exploding fills up the COICOP ladder the way observations are exploded would
    take a parent node's median over a mixture of the two, so a parent would
    silently change meaning as fills arrived. Fills join where `node` IS the
    leaf they were predicted for, and nowhere else.

    NEVER CREATES A SERIES. The depth filter runs on observed periods alone. A
    line that exists only because it was imputed is a line about the model, not
    about prices, and `MIN_SERIES_PERIODS` is the reader's guarantee that they
    are looking at something repeatedly measured.

    NO COLLISIONS TO RESOLVE. Cells the pruner rejected are removed from the
    observations upstream of here, so the bread priced at US$108/kg is already
    gone by the time this runs and the month it occupied is a genuine gap. A fill
    then occupies an empty slot rather than arguing with a drawn point, which is
    why there is no precedence rule to get wrong.
    """
    keys = ["country", "node", "standard_unit", "period"]
    s = (
        exploded.groupby(keys, observed=True)
        .agg(
            usd=("unit_value_usd", "median"),
            local=("unit_value_local", "median"),
            n=("unit_value_usd", "size"),
        )
        .reset_index()
    )
    s = s[s.n >= MIN_CELL_OBS]
    depth = s.groupby(["country", "node", "standard_unit"]).period.transform("nunique")
    s = s[depth >= MIN_SERIES_PERIODS].copy()
    s["imputed"] = False
    s["prob"] = np.nan
    if fills is None or fills.empty:
        return s

    f = fills.rename(columns={"coicop_code": "node"})
    f = f[f.standard_unit.isin(s.standard_unit.unique())]

    # Only onto series that already cleared the depth filter above.
    live = s[["country", "node", "standard_unit"]].drop_duplicates()
    f = f.merge(live, on=["country", "node", "standard_unit"], how="inner")

    # Belt and braces. RT-CAL only targets cells it considers missing, and the
    # cells it rejected were dropped from `trusted` before this frame was built,
    # so a fill sharing a period with a drawn observation should be impossible.
    # If one ever appears, the observation wins and the fill is discarded --
    # never draw two prices for one month.
    drawn = set(map(tuple, s[keys].astype(str).values))
    f = f[[tuple(r) not in drawn for r in f[keys].astype(str).values]]
    if f.empty:
        return s
    f = f.assign(local=np.nan, n=0, imputed=True)[
        keys + ["usd", "local", "n", "imputed", "prob"]
    ]
    return pd.concat([s, f], ignore_index=True)


def _leaf_census(tax: dict) -> dict[str, int]:
    """Leaves sitting under each node, counted from the taxonomy alone."""
    out: dict[str, int] = {}
    for code, meta in tax.items():
        if not meta.get("leaf"):
            continue
        for anc in _levels(code)[:-1]:
            out[anc] = out.get(anc, 0) + 1
    return out


def _leaf_panel(exploded: pd.DataFrame, tax: dict) -> pd.DataFrame:
    """Median unit value of each (country, leaf, unit) per month — the item.

    Both the chain and the year-over-year family are built on exactly this
    panel, so it is defined once: two measures of the same prices that disagreed
    about which observations count would be impossible to reconcile on screen.
    """
    leaf = exploded[
        exploded.coicop_code.map(lambda c: bool(tax.get(c, {}).get("leaf")))
    ]
    leaf = leaf[leaf.node == leaf.coicop_code]
    m = (
        leaf.groupby(
            ["country", "coicop_code", "standard_unit", "period"], observed=True
        )
        .agg(usd=("unit_value_usd", "median"), n=("unit_value_usd", "size"))
        .reset_index()
    )
    return m[(m.n >= MIN_CELL_OBS) & (m.usd > 0)]


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


def _lagged_changes(exploded: pd.DataFrame, tax: dict) -> pd.DataFrame:
    """Average log price change over k months, matched leaf by leaf.

    Unlike the chain this never links to "whatever the previous observation
    happened to be": period t is compared with period t-k exactly, over the
    leaves priced in BOTH, and the mean of those log changes is the group's
    change:  d ln P_gt = (1/n) sum_i ( ln p_it - ln p_i,t-k ).

    The MEAN, not the median. There are no expenditure weights in this corpus,
    so everything is equally weighted, and an unweighted mean of log relatives
    is the elementary index that follows from that. It is also what makes the
    number decomposable: the group change is the sum of each leaf's share of it,
    which a median is not.

    Nothing accumulates. A chained index carries every link's error forward and
    is read against a base month that is itself one noisy draw; a k-month change
    is two observations and stops there.
    """
    m = _leaf_panel(exploded, tax)
    if m.empty:
        return pd.DataFrame(
            columns=["country", "node", "standard_unit", "period", "lag", "lr", "k"]
        )
    m = m.copy()
    m["t"] = pd.PeriodIndex(m.period, freq="M").astype(int)
    keys = ["country", "coicop_code", "standard_unit"]
    ladder = pd.DataFrame(
        [(c, n) for c in m.coicop_code.unique() for n in _levels(c)],
        columns=["coicop_code", "node"],
    )

    out = []
    for months, lag in CHANGE_LAGS["M"].items():
        prev = m[keys + ["t", "usd"]].rename(columns={"usd": "prev_usd"})
        prev["t"] = prev.t + lag
        j = m.merge(prev, on=keys + ["t"], how="inner")
        if j.empty:
            continue
        j["lr"] = np.log(j.usd / j.prev_usd)
        step = (
            j.merge(ladder, on="coicop_code", how="inner")
            .groupby(["country", "node", "standard_unit", "period"], observed=True)
            .agg(lr=("lr", "mean"), k=("lr", "size"))
            .reset_index()
        )
        step = step[step.k >= _link_need(step.node, tax)]
        if step.empty:
            continue
        step["lag"] = months
        out.append(step)
    if not out:
        return pd.DataFrame(
            columns=["country", "node", "standard_unit", "period", "lag", "lr", "k"]
        )
    return pd.concat(out, ignore_index=True)


def _chained_index(exploded: pd.DataFrame, tax: dict) -> pd.DataFrame:
    """Composition-free price index for aggregate COICOP nodes.

    A raw median over an aggregate node moves whenever the scrape composition
    moves — which item got collected this month, not what it cost. So for every
    non-leaf node we chain the Jevons way: month over month, average the log
    price relative across the leaves observed in BOTH months, then cumulate.
    Only the US$ chain is built; the local chain follows exactly from the FX
    identity, which also sidesteps mixing two currencies inside one country.
    """
    m = _leaf_panel(exploded, tax)
    if m.empty:
        return pd.DataFrame(
            columns=["country", "node", "standard_unit", "period", "idx", "n_leaves"]
        )

    m = m.sort_values(["country", "coicop_code", "standard_unit", "period"])
    g = m.groupby(["country", "coicop_code", "standard_unit"], observed=True)
    m["prev_usd"] = g.usd.shift()
    m["prev_period"] = g.period.shift()
    m = m.dropna(subset=["prev_usd", "prev_period"])
    gap = pd.PeriodIndex(m.period, freq="M").astype(int) - pd.PeriodIndex(
        m.prev_period, freq="M"
    ).astype(int)
    m = m[(gap >= 1) & (gap <= MAX_LINK_GAP_MONTHS)].copy()
    m["lr"] = np.log(m.usd / m.prev_usd)

    ladder = pd.DataFrame(
        [(c, n) for c in m.coicop_code.unique() for n in _levels(c)[:-1]],
        columns=["coicop_code", "node"],
    )
    linked = m.merge(ladder, on="coicop_code", how="inner")
    step = (
        linked.groupby(["country", "node", "standard_unit", "period"], observed=True)
        .agg(
            lr=("lr", "mean"),
            n_leaves=("lr", "size"),
            prev_period=("prev_period", "min"),
        )
        .reset_index()
    )
    # Nodes that could always clear the flat bar keep it, so the scaling only
    # ever relaxes what the taxonomy made impossible, never what was merely thin
    # this month. Every node here is a strict ancestor, so the leaf case in
    # `_link_need` never fires and this is the gate it has always been.
    step = step[step.n_leaves >= _link_need(step.node, tax)]
    if step.empty:
        return pd.DataFrame(
            columns=["country", "node", "standard_unit", "period", "idx", "n_leaves"]
        )

    key = ["country", "node", "standard_unit"]
    step = step.sort_values(key + ["period"])
    step["idx"] = np.exp(step.groupby(key, observed=True).lr.cumsum()) * 100.0

    # the chain starts one period before its first link, at 100
    base = step.groupby(key, observed=True).head(1)[key + ["prev_period"]].copy()
    base = base.rename(columns={"prev_period": "period"})
    base["idx"] = 100.0
    base["n_leaves"] = 0

    out = pd.concat(
        [base, step[key + ["period", "idx", "n_leaves"]]], ignore_index=True
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


def _basket_levels(cells: pd.DataFrame, tax: dict) -> pd.DataFrame:
    """Matched-leaf Jevons price level: geometric mean of a country's leaf unit
    values relative to the global median for that same (leaf, unit).

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
    """
    residual = _residual_nodes(tax)
    leaves = cells[
        (cells.node.map(lambda c: bool(tax.get(c, {}).get("leaf"))))
        & (~cells.node.isin(residual))
        & (cells.modelled < 0.5)
        & cells.usd.gt(0)
    ].copy()
    defect = leaves.groupby("country").flagged.mean().rename("defect_share")
    leaves = leaves[~leaves.flagged]
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
    leaves = leaves[pd.MultiIndex.from_frame(leaves[keys]).isin(eligible)]
    glob = leaves.groupby(keys).usd.median().rename("g")
    leaves = leaves.join(glob, on=keys)
    leaves["rel"] = np.log(leaves.usd / leaves.g)
    out = (
        leaves.groupby("country")
        .agg(rel=("rel", "mean"), n_leaves=("rel", "size"), src=("sources", "max"))
        .reset_index()
    )
    out = out.join(defect, on="country")
    out["level"] = np.exp(out.rel) * 100
    out["ok"] = (
        (out.n_leaves >= MIN_BASKET_LEAVES)
        & (out.src >= MIN_BASKET_SOURCES)
        & (out.defect_share.fillna(0) < COUNTRY_DEFECT_SHARE)
    )
    return out[["country", "level", "n_leaves", "defect_share", "ok"]]


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


def build_payload(region: str | None = None) -> dict:
    """Aggregate the corpus, optionally restricted to one region's countries.

    The restriction narrows WHO is shown, not what they are measured against.
    Every "vs world" figure keeps its global yardstick, computed below from the
    unrestricted cells, because a regional dashboard whose world median is
    secretly its own median would report a country as typical when it is only
    typical for its neighbours.

    `nodeMeta[node].rmed` does publish a regional and subregional median beside
    `gmed`, and does not weaken that rule. The failure it guards against is a
    SILENT swap -- the screen saying "vs world" over a number that is not. An
    additional yardstick the reader selects, on a chart that renames its axis,
    its column and its tooltip when they do, is the opposite of that.
    """
    tax = load_taxonomy()
    countries = load_country_meta()
    obs = load_observations()
    # Both empty unless `prices rtcal run` has been executed.
    #
    # Fills reach the time-series display only -- not the cells, not the chain,
    # not the basket. Drawing a modelled point and letting it move an index are
    # different commitments and only the first is made here.
    #
    # PRUNED CELLS ARE DIFFERENT and come out everywhere, at the observation
    # level, before anything aggregates. Removing a value our own screen calls an
    # obvious error is a correction, not an imputation, and it would be incoherent
    # for the chain to keep pricing a cell the series view refuses to draw. This
    # is the other half of what the method is for: the historical view is full of
    # points that are wrong on their face, and they should stop being drawn.
    fills = load_released_fills()
    pruned = load_pruned_cells()

    trusted = obs[
        obs.qa_status.eq("trusted")
        & obs.standard_unit.isin(COMPARABLE_UNITS)
        & obs.unit_value_usd.gt(0)
    ].copy()
    before = len(trusted)
    trusted = drop_pruned(trusted, pruned).copy()
    if len(trusted) != before:
        logger.info(
            "rtcal pruning dropped %d of %d trusted rows (%d rejected cells)",
            before - len(trusted),
            before,
            len(pruned),
        )

    world_cells = _cells(_explode_nodes(trusted))
    if region:
        label = _region_label(region)
        keep = {s for s, m in countries.items() if m["region"] == label}
        trusted = trusted[trusted.country.isin(keep)].copy()
        if trusted.empty:
            raise SystemExit(f"no trusted observations for region {region!r} ({label})")

    exploded = _explode_nodes(trusted)
    cells = _cells(exploded)
    series = _series(exploded, fills)
    chained = _chained_index(exploded, tax)
    changed = _lagged_changes(exploded, tax)
    levels = _basket_levels(cells, tax)

    # ---- country meta -------------------------------------------------
    cmeta: dict[str, dict] = {}
    lvl_map = dict(zip(levels.country, levels.level))
    nleaf_map = dict(zip(levels.country, levels.n_leaves))
    ok_map = dict(zip(levels.country, levels.ok))
    defect_map = dict(zip(levels.country, levels.defect_share))
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
            "defect": round(float(defect_map.get(slug, 0.0) or 0.0), 3),
            "last": str(g.period.max()),
        }

    # ---- node meta: dominant unit + volume ----------------------------
    nodemeta: dict[str, dict] = {}
    nu = exploded.groupby(["node", "standard_unit"], observed=True).size()
    for node, sub in nu.groupby(level=0):
        by_unit = {u: int(v) for (_, u), v in sub.items()}
        nodemeta[node] = {
            "units": by_unit,
            "dom": max(by_unit, key=by_unit.get),
            "n": int(sum(by_unit.values())),
            "countries": 0,
        }
    for node, n in cells.groupby("node").country.nunique().items():
        if node in nodemeta:
            nodemeta[node]["countries"] = int(n)
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
    qa = {
        "status": {k: int(v) for k, v in obs.qa_status.value_counts().items()},
        "mass_source": {
            str(k): int(v)
            for k, v in obs[obs.qa_status.eq("trusted")]
            .mass_source.value_counts(dropna=False)
            .items()
        },
        "item_basis_rows": int(
            (obs.qa_status.eq("trusted") & obs.standard_unit.eq("item")).sum()
        ),
        "modelled_rows": int((obs.qa_status.eq("trusted") & obs.is_modelled).sum()),
        "modelled_sources": sorted(MODELLED_SOURCES),
        "plausible_bounds": PLAUSIBLE_USD,
        "min_basket_leaves": MIN_BASKET_LEAVES,
        # The leaf gate, published so the client can state the missing-price
        # policy in the same words the build applies it in.
        "min_basket_leaf_share": MIN_BASKET_LEAF_SHARE,
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
        # overruling it: every fill is labelled, is off by default, and carries
        # the calibrated probability that it lands within 25% of the truth.
        #
        # What did not change is what a fill is allowed to touch. Fills reach
        # the time-series display and nothing else -- not the chained index, not
        # the heatmap leaf counts, not the basket. Drawing a modelled point and
        # letting it move an index are different commitments, and only the first
        # one has been made. That is why the chain still says, truthfully, that
        # it interpolates nothing.
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
            "scope": ["series"],
            "excluded_from": ["cells", "chain", "changes", "basket", "heatmap"],
            "default_visible": False,
            "labelled": True,
            "probability": "calibrated P(within 25% of the observed median)",
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
    fxr = obs.dropna(subset=["fx_rate"])
    fx_tbl = (
        fxr.groupby(["country", "period"], observed=True).fx_rate.median().reset_index()
    )
    fx: dict[str, dict] = {}
    for c, g in fx_tbl.sort_values("period").groupby("country"):
        fx[c] = {"p": g.period.tolist(), "r": [round(v, 6) for v in g.fx_rate]}

    gseries_raw, geos = build_geo_series(exploded, tax, cmeta)

    official = load_official({s: countries.get(s, {}).get("iso3") for s in cmeta})
    used_series = {k for v in official.values() for k in v}

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
        # `imp`/`pr` are omitted entirely when a series carries no fill, so a
        # payload built without RT-CAL is byte-identical to the one before it.
        if bool(g.imputed.any()):
            entry["imp"] = [1 if v else 0 for v in g.imputed]
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
        }

    gseries: dict[str, dict] = {}
    for k, v in gseries_raw.items():
        freq, gk, node, unit = k.split("|")
        if node in node_pos and unit in unit_pos:
            gseries[f"{freq}|{gk}|{node_pos[node]}|{unit_pos[unit]}"] = v

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
            "geo_min_pairs": FE_MIN_PAIRS,
            "divisions": ["01", "02"],
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
        "cpi": official,
        "cpiMeta": {
            "labels": {k: v for k, v in SERIES_LABEL.items() if k in used_series},
            "division": {k: v for k, v in DIVISION_OF.items() if k in used_series},
            "source": "IMF, Consumer Price Index (IMF.STA:CPI), monthly index",
        },
        "samples": samples,
        "qa": qa,
    }


def write_payload(path: Path) -> Path:
    payload = build_payload()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, separators=(",", ":")))
    return path
