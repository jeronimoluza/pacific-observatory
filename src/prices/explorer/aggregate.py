"""Aggregate the trusted unit-value corpus into the explorer payload.

The grain that matters is (country, COICOP node, standard_unit) — unit values
are never pooled across `standard_unit`, and local-currency medians always key
on the cell's dominant `currency`. Nodes are every level of the COICOP tree
(division/group/class/subclass/leaf), so the UI can walk up and down.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from prices.explorer.sources import (
    COMPARABLE_UNITS,
    COUNTRY_DEFECT_SHARE,
    MAX_LINK_GAP_MONTHS,
    MIN_BASKET_LEAVES,
    MIN_BASKET_SOURCES,
    MIN_CELL_OBS,
    MIN_CHAIN_PERIODS,
    MIN_LINK_LEAVES,
    MIN_SERIES_PERIODS,
    MODELLED_SOURCES,
    PLAUSIBLE_USD,
    REPO_ROOT,
    _levels,
    load_country_meta,
    load_observations,
    load_taxonomy,
)

__all__ = ["REPO_ROOT", "build_payload", "write_payload"]


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


def _series(exploded: pd.DataFrame) -> pd.DataFrame:
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
    return s[depth >= MIN_SERIES_PERIODS].copy()


def _chained_index(exploded: pd.DataFrame, tax: dict) -> pd.DataFrame:
    """Composition-free price index for aggregate COICOP nodes.

    A raw median over an aggregate node moves whenever the scrape composition
    moves — which item got collected this month, not what it cost. So for every
    non-leaf node we chain the Jevons way: month over month, average the log
    price relative across the leaves observed in BOTH months, then cumulate.
    Only the US$ chain is built; the local chain follows exactly from the FX
    identity, which also sidesteps mixing two currencies inside one country.
    """
    leaf = exploded[
        exploded.coicop_code.map(lambda c: tax.get(c, {}).get("lvl", 0)) == 5
    ]
    leaf = leaf[leaf.node == leaf.coicop_code]
    m = (
        leaf.groupby(
            ["country", "coicop_code", "standard_unit", "period"], observed=True
        )
        .agg(usd=("unit_value_usd", "median"), n=("unit_value_usd", "size"))
        .reset_index()
    )
    m = m[(m.n >= MIN_CELL_OBS) & (m.usd > 0)]
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
    step = step[step.n_leaves >= MIN_LINK_LEAVES]
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


def _basket_levels(cells: pd.DataFrame, tax: dict) -> pd.DataFrame:
    """Matched-leaf Jevons price level: geometric mean of a country's leaf unit
    values relative to the global median for that same (leaf, unit)."""
    leaves = cells[
        (cells.node.map(lambda c: tax.get(c, {}).get("lvl", 0)) == 5)
        & (cells.modelled < 0.5)
        & cells.usd.gt(0)
    ].copy()
    defect = leaves.groupby("country").flagged.mean().rename("defect_share")
    leaves = leaves[~leaves.flagged]
    glob = leaves.groupby(["node", "standard_unit"]).usd.median().rename("g")
    leaves = leaves.join(glob, on=["node", "standard_unit"])
    leaves["rel"] = np.log(leaves.usd / leaves.g)
    out = (
        leaves.groupby("country")
        .agg(rel=("rel", "median"), n_leaves=("rel", "size"), src=("sources", "max"))
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


def build_payload() -> dict:
    tax = load_taxonomy()
    countries = load_country_meta()
    obs = load_observations()

    trusted = obs[
        obs.qa_status.eq("trusted")
        & obs.standard_unit.isin(COMPARABLE_UNITS)
        & obs.unit_value_usd.gt(0)
    ].copy()

    exploded = _explode_nodes(trusted)
    cells = _cells(exploded)
    series = _series(exploded)
    chained = _chained_index(exploded, tax)
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
    # the relative-price (FX-free) view divides by.
    clean = cells[~cells.flagged & (cells.modelled < 0.5)]
    for (node, unit), v in (
        clean.groupby(["node", "standard_unit"]).usd.median().items()
    ):
        if node in nodemeta:
            nodemeta[node].setdefault("gmed", {})[unit] = round(float(v), 4)

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
        ser[f"{cty_pos[c]}|{node_pos[n]}|{unit_pos[u]}"] = {
            "p": g.period.tolist(),
            "usd": [round(float(v), 4) for v in g.usd],
            "loc": [None if pd.isna(v) else round(float(v), 4) for v in g.local],
            "n": [int(v) for v in g.n],
        }

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
            "divisions": ["01", "02"],
        },
        "tax": {k: v for k, v in tax.items() if k in node_pos},
        "nodeIdx": node_idx,
        "nodeMeta": {node_idx[i]: nodemeta[node_idx[i]] for i in range(len(node_idx))},
        "ctyIdx": cty_idx,
        "cty": cmeta,
        "unitIdx": unit_idx,
        "curIdx": cur_idx,
        "cells": cell_payload,
        "series": ser,
        "chain": chain,
        "fx": fx,
        "samples": samples,
        "qa": qa,
    }


def write_payload(path: Path) -> Path:
    payload = build_payload()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, separators=(",", ":")))
    return path
