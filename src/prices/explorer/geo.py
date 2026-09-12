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
    ladder_agg,
    CHANGE_LAGS,
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


def _period(frame: pd.DataFrame, freq: str) -> pd.Series:
    per = (
        frame.period
        if freq == "M"
        else pd.PeriodIndex(frame.period, freq="M").asfreq(freq).astype(str)
    )
    return pd.Series(np.asarray(per), index=frame.index, name="period")


def _leaf_rows(exploded: pd.DataFrame, tax: dict) -> pd.DataFrame:
    leaf = exploded[
        exploded.coicop_code.map(lambda c: bool(tax.get(c, {}).get("leaf")))
    ]
    return leaf[leaf.node == leaf.coicop_code]


def _pairs(
    exploded: pd.DataFrame, tax: dict, freq: str, ex_fill: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Median unit value of each (country, leaf, unit) per period — the item.

    `exploded` already POOLS observations with RT-CAL fills, and `ex_fill` is
    the fills alone, which is how an item's imputed share is counted. Without
    the second frame a wholly-modelled item would be indistinguishable from a
    one-observation item here and would be cut by `MIN_CELL_OBS` -- which is
    exactly how the geography series stayed blank while the leaf series filled.
    """
    leaf = _leaf_rows(exploded, tax)
    per = _period(leaf, freq)
    m = (
        leaf.groupby(PAIR + [per], observed=True)
        .agg(usd=("unit_value_usd", "median"), n_all=("unit_value_usd", "size"))
        .reset_index()
    )
    if ex_fill is None or ex_fill.empty:
        m["nimp"] = 0
    else:
        f = _leaf_rows(ex_fill, tax)
        fper = _period(f, freq)
        nimp = (
            f.groupby(PAIR + [fper], observed=True)
            .unit_value_usd.size()
            .rename("nimp")
            .reset_index()
        )
        m = m.merge(nimp, on=PAIR + ["period"], how="left")
        m["nimp"] = m.nimp.fillna(0)
    m["nimp"] = m.nimp.astype("int64")
    m["n"] = (m.n_all - m.nimp).astype("int64")
    m["imp"] = (m.nimp / m.n_all.where(m.n_all > 0)).fillna(0.0)
    m = m.drop(columns="n_all")
    m = m[((m.n >= MIN_CELL_OBS) | (m.nimp > 0)) & (m.usd > 0)].sort_values(
        PAIR + ["period"]
    )

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
    m["prev_imp"] = g.imp.shift()
    ok = m.prev_usd.notna()
    gap = np.asarray(
        pd.PeriodIndex(m.period, freq=freq).astype(int)
        - pd.PeriodIndex(m.prev_period.where(ok, m.period), freq=freq).astype(int)
    )
    link = ok.to_numpy() & (gap >= 1) & (gap <= FREQ_MAX_GAP[freq])
    m["lr"] = np.where(link, np.log(m.usd / m.prev_usd.where(ok, 1.0)), np.nan)
    # A link is only as measured as its less measured end.
    m["imp_link"] = np.maximum(m.imp, m.prev_imp.fillna(m.imp))
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
        return pd.DataFrame(columns=KEY + ["period", "lvl", "k", "c", "imp"])

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
        .agg(
            lvl=("lvl", "first"),
            k=("pair", "size"),
            c=("country", "nunique"),
            # The fitted level absorbs item churn, so a modelled item moves it
            # the way any other item does. This is the share of the items behind
            # THIS period's effect that were modelled.
            imp=("imp", "mean"),
        )
        .reset_index()
    )


def _chain(linked: pd.DataFrame, tax: dict) -> pd.DataFrame:
    """Cumulate the MEDIAN log relative over matched items into an index at 100.

    The textbook elementary index averages the log relatives, but a single item
    whose price was scraped in cents rather than units moves that mean by ln 100
    over however many items are linked. The median is the same quantity for a
    clean link and ignores the flipped one, matching how the cross-sectional
    basket level is already built.

    Two aggregations, in this order and not the other one. Countries first, at
    a FIXED leaf, where the thing being averaged is the same good everywhere;
    then up the COICOP tree a level at a time. Collapsing both at once let the
    finely split corners of the taxonomy speak for their parents.
    """
    leaf = linked.dropna(subset=["lr"]).drop_duplicates(PAIR + ["period", "geo"])
    per_leaf = (
        leaf.groupby(["geo", "coicop_code", "standard_unit", "period"], observed=True)
        .agg(
            lr=("lr", "median"),
            pairs=("lr", "size"),
            prev_period=("prev_period", "min"),
            imp=("imp_link", "mean"),
        )
        .reset_index()
    )
    if per_leaf.empty:
        return pd.DataFrame(columns=KEY + ["period", "idx", "pairs", "imp"])
    step = ladder_agg(
        per_leaf,
        ["geo", "standard_unit", "period"],
        "lr",
        how="median",
        k0="pairs",
        extra={"prev_period": ("prev_period", "min"), "imp": ("imp", "mean")},
    ).rename(columns={"k": "pairs"})
    step["is_leaf"] = step.node.map(lambda c: bool(tax.get(c, {}).get("leaf")))
    # the chain must not be gated harder than the fit it rides alongside
    need = np.where(
        step.is_leaf.to_numpy(), GEO_MIN_LINK_PAIRS_LEAF, GEO_MIN_LINK_PAIRS
    )
    step = step[step.pairs >= need]
    if step.empty:
        return pd.DataFrame(columns=KEY + ["period", "idx", "pairs", "imp"])
    step = step.sort_values(KEY + ["period"])
    step["idx"] = np.exp(step.groupby(KEY, observed=True).lr.cumsum()) * 100.0
    base = step.groupby(KEY, observed=True).head(1)[KEY + ["prev_period"]].copy()
    base = base.rename(columns={"prev_period": "period"})
    base["idx"] = 100.0
    base["pairs"] = 0
    base["imp"] = 0.0
    out = pd.concat(
        [base, step[KEY + ["period", "idx", "pairs", "imp"]]], ignore_index=True
    )
    return out.drop_duplicates(KEY + ["period"], keep="first")


def _lagged(linked: pd.DataFrame, tax: dict, freq: str) -> pd.DataFrame:
    """Average log change over each horizon, matched (country, leaf) by pair.

    The chain beside this one links an item to whatever its previous
    observation happened to be and cumulates from a base period; this compares
    period t with period t-k exactly and stops there. Nothing accumulates, so
    no link's error is carried forward, and there is no base month whose own
    noise sets the level of the whole line.

    The MEAN, deliberately. `_chain` above takes the MEDIAN of the same log
    relatives, chosen so one cents-for-units item cannot move the link by
    ln 100 -- but `_pairs` already drops those cells (DEFECT_LOG_RATIO), and the
    mean is the elementary index that follows from "everything is equally
    weighted". The divergence between the two is pre-existing and left in place
    rather than silently changed underneath the chain.

    The ORDER is now shared with the chain, whatever the estimator: the change
    is taken at the leaf, averaged across the countries in the geography at
    that same leaf, and only then averaged up the COICOP tree one level at a
    time. Division 01's twelve-month change is the mean of its groups' changes,
    each of which is the mean of its classes', down to rice against rice.
    """
    m = linked.drop_duplicates(PAIR + ["period"])[
        PAIR + ["period", "usd", "imp"]
    ].copy()
    m["t"] = pd.PeriodIndex(m.period, freq=freq).astype(int)
    out = []
    for months, lag in CHANGE_LAGS[freq].items():
        prev = m[PAIR + ["t", "usd", "imp"]].rename(
            columns={"usd": "prev_usd", "imp": "prev_imp"}
        )
        prev["t"] = prev.t + lag
        j = m.merge(prev, on=PAIR + ["t"], how="inner")
        if j.empty:
            continue
        j["lr"] = np.log(j.usd / j.prev_usd)
        j["imp_pair"] = np.maximum(j.imp, j.prev_imp)
        per_leaf = (
            j.merge(
                linked[PAIR + ["period", "geo"]].drop_duplicates(),
                on=PAIR + ["period"],
                how="inner",
            )
            .groupby(["geo", "coicop_code", "standard_unit", "period"], observed=True)
            .agg(lr=("lr", "mean"), pairs=("lr", "size"), imp=("imp_pair", "mean"))
            .reset_index()
        )
        if per_leaf.empty:
            continue
        step = ladder_agg(
            per_leaf,
            ["geo", "standard_unit", "period"],
            "lr",
            k0="pairs",
            extra={"imp": ("imp", "mean")},
        ).rename(columns={"k": "pairs"})
        step["is_leaf"] = step.node.map(lambda c: bool(tax.get(c, {}).get("leaf")))
        need = np.where(
            step.is_leaf.to_numpy(), GEO_MIN_LINK_PAIRS_LEAF, GEO_MIN_LINK_PAIRS
        )
        step = step[step.pairs >= need]
        if step.empty:
            continue
        out.append(
            step.assign(months=months)[KEY + ["period", "months", "lr", "pairs", "imp"]]
        )
    if not out:
        return pd.DataFrame(columns=KEY + ["period", "months", "lr", "pairs", "imp"])
    return pd.concat(out, ignore_index=True)


def _geo_maps(cmeta: dict[str, dict]) -> dict[str, dict[str, str]]:
    return {
        "world": {s: "W" for s in cmeta},
        "region": {s: "R:" + v["region"] for s, v in cmeta.items()},
        "subregion": {s: "S:" + v["subregion"] for s, v in cmeta.items()},
        "country": {s: "C:" + s for s in cmeta},
    }


def build_geo_series(
    exploded: pd.DataFrame,
    tax: dict,
    cmeta: dict[str, dict],
    ex_fill: pd.DataFrame | None = None,
) -> tuple[dict, dict]:
    """Return (series keyed `freq|geo|node|unit`, geography metadata by key).

    `exploded` pools observations and RT-CAL fills; `ex_fill` is the fills on
    their own, and every series this builds carries `ish` -- the share of the
    items behind each point that were modelled.
    """
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
        m = _pairs(exploded, tax, freq, ex_fill)
        ladder = pd.DataFrame(
            [(c, n) for c in m.coicop_code.unique() for n in _levels(c)],
            columns=["coicop_code", "node"],
        )
        linked = m.merge(ladder, on="coicop_code", how="inner")
        linked["is_leaf"] = linked.node.map(lambda c: bool(tax.get(c, {}).get("leaf")))
        for mp in maps.values():
            linked["geo"] = linked.country.map(mp)
            # Both estimators carry an `imp`; the chain's is renamed on the
            # way in so the merge cannot hand back `imp_x` / `imp_y` and leave
            # which-is-which to column order.
            frame = _fe_level(linked).merge(
                _chain(linked, tax).rename(columns={"imp": "imp_idx"}),
                on=KEY + ["period"],
                how="outer",
            )
            chg = _lagged(linked, tax, freq)
            # A k-month change can exist in a period the fit could not identify
            # and the chain could not link, so the change periods join the grid
            # rather than being clipped to it.
            frame = frame.merge(
                chg[KEY + ["period"]].drop_duplicates(),
                on=KEY + ["period"],
                how="outer",
            )
            frame = frame.sort_values(KEY + ["period"])
            depth = frame.groupby(KEY, observed=True).period.transform("nunique")
            by_key = {k: v for k, v in chg.groupby(KEY, observed=True)}
            for (gk, node, unit), g in frame[depth >= GEO_MIN_PERIODS].groupby(
                KEY, observed=True
            ):
                pos = {p: i for i, p in enumerate(g.period)}
                horizons: dict[str, dict] = {}
                for months, h in by_key.get((gk, node, unit), chg.iloc[:0]).groupby(
                    "months"
                ):
                    v = [None] * len(pos)
                    n = [0] * len(pos)
                    sh = [None] * len(pos)
                    for period, lr, pairs, imp in zip(
                        h.period, h.lr, h.pairs, h.imp
                    ):
                        i = pos.get(period)
                        if i is None:
                            continue
                        v[i] = round(float(np.expm1(lr)) * 100, 3)
                        n[i] = int(pairs)
                        sh[i] = round(float(imp), 4)
                    horizons[str(months)] = {"v": v, "k": n, "ish": sh}
                out[f"{freq}|{gk}|{node}|{unit}"] = {
                    "p": g.period.tolist(),
                    "lvl": [None if pd.isna(v) else round(float(v), 4) for v in g.lvl],
                    "idx": [None if pd.isna(v) else round(float(v), 2) for v in g.idx],
                    "k": [0 if pd.isna(v) else int(v) for v in g.k],
                    "c": [0 if pd.isna(v) else int(v) for v in g.c],
                    # `ish` is the fitted level's imputed share; `ish_idx` the
                    # chained index's. They come off two different estimators
                    # over the same items and are reported apart for that reason.
                    "ish": [None if pd.isna(v) else round(float(v), 4) for v in g.imp],
                    "ish_idx": [
                        None if pd.isna(v) else round(float(v), 4) for v in g.imp_idx
                    ],
                    "chg": horizons,
                }
    return out, geos
