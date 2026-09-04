"""Price series at every geography level — world, region, subregion, country.

A median over a group of countries moves whenever the scrape composition moves:
which country, and which item, happened to be collected that period. So the
level here is fitted, not taken raw — a two-way fixed-effects model on log
price, whose period effect is the price level with the item mix held fixed. The
strictly matched chained index rides alongside for anyone who wants it.

Both are built quarterly and monthly. This corpus carries roughly a hundred
recurring (country, leaf) cells a month before 2026, which is too thin to read
monthly; quarterly pools three times that and is the honest default.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from prices.explorer.sources import (
    DEFECT_LOG_RATIO,
    FE_ITERATIONS,
    FE_MIN_PAIRS,
    FE_MIN_PAIRS_LEAF,
    FREQ_MAX_GAP,
    GEO_MIN_LINK_PAIRS,
    GEO_MIN_LINK_PAIRS_LEAF,
    GEO_MIN_PERIODS,
    MIN_CELL_OBS,
    _levels,
)

__all__ = ["build_geo_series"]

PAIR = ["country", "coicop_code", "standard_unit"]
KEY = ["geo", "node", "standard_unit"]


def _join(d: pd.DataFrame, cols: list[str]) -> np.ndarray:
    out = d[cols[0]].astype(str)
    for c in cols[1:]:
        out = out + "\x00" + d[c].astype(str)
    return out.to_numpy()


def _pairs(exploded: pd.DataFrame, tax: dict, freq: str) -> pd.DataFrame:
    """Median unit value of each (country, leaf, unit) per period — the item."""
    leaf = exploded[
        exploded.coicop_code.map(lambda c: bool(tax.get(c, {}).get("leaf")))
    ]
    leaf = leaf[leaf.node == leaf.coicop_code]
    per = (
        leaf.period
        if freq == "M"
        else pd.PeriodIndex(leaf.period, freq="M").asfreq(freq).astype(str)
    )
    per = pd.Series(np.asarray(per), index=leaf.index, name="period")
    m = (
        leaf.groupby(PAIR + [per], observed=True)
        .agg(usd=("unit_value_usd", "median"), n=("unit_value_usd", "size"))
        .reset_index()
    )
    m = m[(m.n >= MIN_CELL_OBS) & (m.usd > 0)].sort_values(PAIR + ["period"])

    # Some scrapers store cents as units, so one period of an item reads x100.
    # Nothing real moves an item that far from its own history, and a single
    # flipped cell drags both the fit and the chain, so drop it here.
    ly = np.log(m.usd)
    med = ly.groupby([m[c] for c in PAIR]).transform("median")
    seen = m.groupby(PAIR, observed=True).period.transform("size")
    m = m[(seen < 3) | ((ly - med).abs() <= DEFECT_LOG_RATIO)]

    g = m.groupby(PAIR, observed=True)
    m["prev_usd"] = g.usd.shift()
    m["prev_period"] = g.period.shift()
    ok = m.prev_usd.notna()
    gap = np.asarray(
        pd.PeriodIndex(m.period, freq=freq).astype(int)
        - pd.PeriodIndex(m.prev_period.where(ok, m.period), freq=freq).astype(int)
    )
    link = ok.to_numpy() & (gap >= 1) & (gap <= FREQ_MAX_GAP[freq])
    m["lr"] = np.where(link, np.log(m.usd / m.prev_usd.where(ok, 1.0)), np.nan)
    m.loc[m.lr.isna(), "prev_period"] = None
    return m


def _fe_level(d: pd.DataFrame) -> pd.DataFrame:
    """Two-way fixed effects on log price: ln P = item effect + period effect.

    An unbalanced panel whose items churn every period cannot be read off a raw
    median — the median moves when the basket moves. Fitting an item effect and
    a period effect jointly absorbs the churn, and the period effect IS the
    level. Unlike a chain it uses every item that recurs at all, not only items
    that recur in CONSECUTIVE periods, which is what this corpus mostly lacks.
    """
    d = d[d.usd > 0].copy()
    d["pair"] = d.country.astype(str) + "\x00" + d.coicop_code.astype(str)
    # a period needs enough recurring items to identify its effect, and an item
    # only informs the fit if it appears in at least two surviving periods
    for _ in range(4):
        before = len(d)
        need = np.where(d.is_leaf.to_numpy(), FE_MIN_PAIRS_LEAF, FE_MIN_PAIRS)
        d = d[d.groupby(KEY + ["period"], observed=True).pair.transform("size") >= need]
        if d.empty:
            break
        d = d[d.groupby(KEY + ["pair"], observed=True).period.transform("nunique") >= 2]
        if d.empty or len(d) == before:
            break
    if d.empty:
        return pd.DataFrame(columns=KEY + ["period", "lvl", "k", "c"])

    y = np.log(d.usd.to_numpy())
    ic = pd.factorize(_join(d, KEY + ["pair"]))[0]
    tc = pd.factorize(_join(d, KEY + ["period"]))[0]
    gc = pd.factorize(_join(d, KEY))[0]
    ci = np.bincount(ic)
    ct = np.bincount(tc)
    alpha = np.zeros(len(ci))
    delta = np.zeros(len(ct))
    for _ in range(FE_ITERATIONS):
        alpha = np.bincount(ic, y - delta[tc], minlength=len(ci)) / ci
        delta = np.bincount(tc, y - alpha[ic], minlength=len(ct)) / ct
    # the item/period split is pinned down only up to a constant per group, so
    # anchor each group's periods on the mean item effect inside that group
    abar = np.bincount(gc, alpha[ic]) / np.bincount(gc)
    d["lvl"] = np.exp(delta[tc] + abar[gc])

    return (
        d.groupby(KEY + ["period"], observed=True)
        .agg(lvl=("lvl", "first"), k=("pair", "size"), c=("country", "nunique"))
        .reset_index()
    )


def _chain(linked: pd.DataFrame) -> pd.DataFrame:
    """Cumulate the MEDIAN log relative over matched items into an index at 100.

    The textbook elementary index averages the log relatives, but a single item
    whose price was scraped in cents rather than units moves that mean by ln 100
    over however many items are linked. The median is the same quantity for a
    clean link and ignores the flipped one, matching how the cross-sectional
    basket level is already built.
    """
    step = (
        linked.dropna(subset=["lr"])
        .groupby(KEY + ["period"], observed=True)
        .agg(
            lr=("lr", "median"),
            pairs=("lr", "size"),
            prev_period=("prev_period", "min"),
            is_leaf=("is_leaf", "first"),
        )
        .reset_index()
    )
    # the chain must not be gated harder than the fit it rides alongside
    need = np.where(
        step.is_leaf.to_numpy(), GEO_MIN_LINK_PAIRS_LEAF, GEO_MIN_LINK_PAIRS
    )
    step = step[step.pairs >= need]
    if step.empty:
        return pd.DataFrame(columns=KEY + ["period", "idx", "pairs"])
    step = step.sort_values(KEY + ["period"])
    step["idx"] = np.exp(step.groupby(KEY, observed=True).lr.cumsum()) * 100.0
    base = step.groupby(KEY, observed=True).head(1)[KEY + ["prev_period"]].copy()
    base = base.rename(columns={"prev_period": "period"})
    base["idx"] = 100.0
    base["pairs"] = 0
    out = pd.concat([base, step[KEY + ["period", "idx", "pairs"]]], ignore_index=True)
    return out.drop_duplicates(KEY + ["period"], keep="first")


def _geo_maps(cmeta: dict[str, dict]) -> dict[str, dict[str, str]]:
    return {
        "world": {s: "W" for s in cmeta},
        "region": {s: "R:" + v["region"] for s, v in cmeta.items()},
        "subregion": {s: "S:" + v["subregion"] for s, v in cmeta.items()},
        "country": {s: "C:" + s for s in cmeta},
    }


def build_geo_series(
    exploded: pd.DataFrame, tax: dict, cmeta: dict[str, dict]
) -> tuple[dict, dict]:
    """Return (series keyed `freq|geo|node|unit`, geography metadata by key)."""
    maps = _geo_maps(cmeta)
    geos: dict[str, dict] = {}
    labels = {
        "world": lambda s: "World",
        "region": lambda s: cmeta[s]["region"],
        "subregion": lambda s: cmeta[s]["subregion"],
        "country": lambda s: cmeta[s]["name"],
    }
    for kind, mp in maps.items():
        for slug, gk in mp.items():
            g = geos.setdefault(
                gk,
                {
                    "t": labels[kind](slug),
                    "kind": kind,
                    "n": 0,
                    "r": cmeta[slug]["region"] if kind == "subregion" else None,
                },
            )
            g["n"] += 1

    out: dict[str, dict] = {}
    for freq in FREQ_MAX_GAP:
        m = _pairs(exploded, tax, freq)
        ladder = pd.DataFrame(
            [(c, n) for c in m.coicop_code.unique() for n in _levels(c)],
            columns=["coicop_code", "node"],
        )
        linked = m.merge(ladder, on="coicop_code", how="inner")
        linked["is_leaf"] = linked.node.map(lambda c: bool(tax.get(c, {}).get("leaf")))
        for mp in maps.values():
            linked["geo"] = linked.country.map(mp)
            frame = _fe_level(linked).merge(
                _chain(linked), on=KEY + ["period"], how="outer"
            )
            frame = frame.sort_values(KEY + ["period"])
            depth = frame.groupby(KEY, observed=True).period.transform("nunique")
            for (gk, node, unit), g in frame[depth >= GEO_MIN_PERIODS].groupby(
                KEY, observed=True
            ):
                out[f"{freq}|{gk}|{node}|{unit}"] = {
                    "p": g.period.tolist(),
                    "lvl": [None if pd.isna(v) else round(float(v), 4) for v in g.lvl],
                    "idx": [None if pd.isna(v) else round(float(v), 2) for v in g.idx],
                    "k": [0 if pd.isna(v) else int(v) for v in g.k],
                    "c": [0 if pd.isna(v) else int(v) for v in g.c],
                }
    return out, geos
