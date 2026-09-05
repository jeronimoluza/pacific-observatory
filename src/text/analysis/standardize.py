"""Pivot per-source-per-month counts into the wide layout the legacy
`build_outputs` and `IndexCalculator` expect, then run standardization.

`source_counts.parquet` (long: rows = source × ym) → wide (rows = ym, columns
per source × metric) → ratios → z-scores → aggregated EPU index.

Returns objects shaped like the legacy `EPU` instance — `.epu_stats`,
`.news_cols`, `.params`, `.min_date`, `.max_date`, `._extended_calc` —
so the existing `outputs.build_outputs` works without modification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import numpy as np
import pandas as pd

from src.text.analysis.baseline import baseline_mask
from src.text.analysis.indices import IndexCalculator


# ── Standardized-unit shim ───────────────────────────────────────────


@dataclass
class StandardizedUnit:
    """Mimics the public surface of the legacy `EPU` class so existing
    `outputs.build_outputs` consumes the same shape."""

    epu_stats: pd.DataFrame
    news_cols: list[str]
    params: dict
    min_date: pd.Timestamp | None
    max_date: pd.Timestamp | None
    _extended_calc: IndexCalculator | None = None
    raw_files: list = field(default_factory=list)


# ── Pivot ────────────────────────────────────────────────────────────


def _build_continuous_index(
    min_date, max_date, daily_tail_start: str | None
) -> pd.DataFrame:
    """Mirror the legacy hybrid monthly+daily date index."""
    if daily_tail_start is not None:
        tail_ts = pd.Timestamp(daily_tail_start)
        monthly_end = tail_ts - pd.DateOffset(months=1)
        if monthly_end >= pd.Timestamp(min_date):
            monthly_dates = pd.date_range(start=min_date, end=monthly_end, freq="MS")
        else:
            monthly_dates = pd.DatetimeIndex([])
        if pd.isna(max_date) or pd.Timestamp(max_date) < tail_ts:
            daily_dates = pd.DatetimeIndex([])
        else:
            # The dashboard buckets daily rows by day-of-month under a single
            # month key, so rows spanning two months collide (Sep 1 and Aug 1
            # are both "day 1"). Keep the daily run inside the tail month;
            # trailing days with no articles are dropped at render.
            month_end = tail_ts + pd.offsets.MonthEnd(0)
            daily_dates = pd.date_range(
                start=tail_ts, end=min(pd.Timestamp(max_date), month_end), freq="D"
            )
        all_dates = monthly_dates.append(daily_dates)
    else:
        all_dates = pd.date_range(start=min_date, end=max_date, freq="MS")
    return pd.DataFrame({"date": all_dates})


def _ym_to_date(ym: str) -> pd.Timestamp:
    """Mirror the legacy ym format: 'YYYY-M' (monthly) or 'YYYY-MM-DD' (daily)."""
    return pd.to_datetime(ym, format="mixed")


def pivot_to_wide(
    source_counts: pd.DataFrame,
    daily_tail_start: str | None,
) -> tuple[pd.DataFrame, list[str]]:
    """Pivot long-format source_counts into a single per-ym wide DataFrame.

    Output columns:
        date, ym, news_total,
        {source}_A_total, {source}_E_count, ..., {source}_EPU_count,
        {source}_E_kwsum, ..., {source}_EU_count, {source}_PU_count, {source}_EP_count,
        topic columns: {source}_<topic_k>_count, {source}_<topic_k>_U_count,
        actor columns: {source}_<actor_k>_count, {source}_<actor_k>_U_count,
        {source}_body_count (alias for A_total — legacy column),
        {source}_epu_count (alias for EPU_count — legacy column),
        {source}_ratio (= EPU_count / A_total),
        {source}_weights (= A_total / news_total per row).

    Returns (wide_df, sources_in_order).
    """
    if source_counts.empty:
        empty = pd.DataFrame(columns=["date", "ym", "news_total"])
        return empty, []

    sources = sorted(source_counts["source_key"].unique())
    metric_cols = [c for c in source_counts.columns if c not in ("source_key", "ym")]

    # Pivot on resolved date, not ym. Different sources can carry different ym
    # paddings ("2026-04" vs "2026-04-01") for the same date when a previous
    # tail_start ran while only some sources had daily data — pivoting on ym
    # would split those rows and break the downstream date-merge.
    sc = source_counts.copy()
    sc["_date"] = pd.to_datetime(sc["ym"], format="mixed")

    pivoted = sc.pivot_table(
        index="_date",
        columns="source_key",
        values=metric_cols,
        aggfunc="sum",
        fill_value=0,
    )
    pivoted.columns = [f"{src}_{metric}" for metric, src in pivoted.columns]
    pivoted = pivoted.reset_index().rename(columns={"_date": "date"})

    # Determine date range for continuous index
    min_date = pivoted["date"].min()
    max_date = pivoted["date"].max()
    if pd.isna(min_date):
        wide = pd.DataFrame(columns=["date", "ym", "news_total"])
        return wide, sources

    if daily_tail_start is not None:
        # Articles dated past the tail month cannot be shown — the daily index
        # is bounded to that month. End it on the last date inside the month
        # that actually carries articles, otherwise the merge below fills the
        # remaining days with zeros and the series plots a cliff to nought
        # after the real data stops.
        month_end = pd.Timestamp(daily_tail_start) + pd.offsets.MonthEnd(0)
        in_range = pivoted.loc[pivoted["date"] <= month_end, "date"]
        if len(in_range):
            max_date = in_range.max()

    dates_df = _build_continuous_index(min_date, max_date, daily_tail_start)
    wide = dates_df.merge(pivoted, on="date", how="left").fillna(0)

    # Recompute ym from date so it matches the canonical daily/monthly format
    if daily_tail_start is not None:
        tail_ts = pd.Timestamp(daily_tail_start)
        wide["ym"] = wide["date"].apply(
            lambda d: d.strftime("%Y-%m-%d") if d >= tail_ts else f"{d.year}-{d.month}"
        )
    else:
        wide["ym"] = wide["date"].apply(lambda d: f"{d.year}-{d.month}")

    # news_total + per-source weights + body_count + epu_count + ratio aliases.
    # Legacy `EPU.get_count_stats` fills NaN to 0 across the whole epu_stats
    # frame after the continuous-date-index merge, which means missing
    # source-months end up with ratio = 0 (not NaN). Mirror that here so the
    # downstream standardization arithmetic stays bit-faithful.
    body_cols = [f"{s}_A_total" for s in sources]
    wide["news_total"] = wide[body_cols].sum(axis=1)
    for s in sources:
        wide[f"{s}_body_count"] = wide[f"{s}_A_total"]
        if f"{s}_EPU_count" in wide.columns:
            wide[f"{s}_epu_count"] = wide[f"{s}_EPU_count"]
        else:
            wide[f"{s}_epu_count"] = 0
        wide[f"{s}_weights"] = wide[f"{s}_A_total"].div(wide["news_total"]).fillna(0)
        wide[f"{s}_ratio"] = (
            wide[f"{s}_epu_count"]
            .div(wide[f"{s}_A_total"])
            .replace([np.inf, -np.inf], np.nan)
            .fillna(0)
        )

    return wide, sources


# ── Standardization (base EPU + per-group EPUs) ──────────────────────


def _standardize_epu(
    wide: pd.DataFrame,
    sources: list[str],
    cutoff_start: str | None,
    cutoff_end: str | None,
    ratio_template: str,
) -> tuple[pd.DataFrame, dict, list[str]]:
    """Standardize a per-source ratio column into a single EPU index.

    `ratio_template` is the column name template: `"{source}_ratio"` for base
    EPU, or `"{source}_<topic_k>_ratio"` for per-topic EPU.

    Mutates a copy of `wide` and returns (df, params, ratio_cols_actually_used).
    """
    df = wide.copy()
    ratio_cols: list[str] = []
    z_cols: list[str] = []
    ratio_stds: dict = {}

    for src in sources:
        ratio_col = ratio_template.format(source=src)
        if ratio_col not in df.columns:
            continue
        ratio_cols.append(ratio_col)

        # Replace inf with NaN for safety
        df[ratio_col] = df[ratio_col].replace([np.inf, -np.inf], np.nan)

        std = df.loc[
            baseline_mask(df["date"], cutoff_start, cutoff_end), ratio_col
        ].std()
        col_key = ratio_col.replace("_ratio", "")
        z_col = f"{col_key}_z_score"
        if std == 0 or pd.isna(std):
            df[z_col] = np.nan
            ratio_stds[col_key] = None
        else:
            df[z_col] = df[ratio_col] / std
            ratio_stds[col_key] = float(std)
        z_cols.append(z_col)

    if not z_cols:
        df["z_score_unweighted"] = np.nan
        df["z_score_weighted"] = np.nan
        df["epu_unweighted"] = np.nan
        df["epu_weighted"] = np.nan
        return (
            df,
            {
                "ratio_stds": ratio_stds,
                "scaling_weighted": None,
                "scaling_unweighted": None,
            },
            ratio_cols,
        )

    df["z_score_unweighted"] = df[z_cols].mean(axis=1, skipna=True)
    df["z_score_weighted"] = 0.0
    for z_col in z_cols:
        # The weight column is per source, not per (source × topic). Strip
        # the suffix (`_z_score` or `_<topic>_z_score`) and find which known
        # source the prefix matches, then use `{source}_weights`.
        src = next((s for s in sources if z_col.startswith(f"{s}_")), None)
        weight_col = f"{src}_weights" if src is not None else None
        if weight_col and weight_col in df.columns:
            contrib = df[weight_col] * df[z_col]
            contrib = contrib.fillna(0)
            df["z_score_weighted"] = df["z_score_weighted"] + contrib

    scaling = {}
    for name, z_col in (
        ("weighted", "z_score_weighted"),
        ("unweighted", "z_score_unweighted"),
    ):
        mean_val = df.loc[
            baseline_mask(df["date"], cutoff_start, cutoff_end), z_col
        ].mean()
        if pd.isna(mean_val) or mean_val == 0:
            scaling[name] = None
            df[f"epu_{name}"] = np.nan
        else:
            sf = 100 / mean_val
            scaling[name] = float(sf)
            df[f"epu_{name}"] = sf * df[z_col]

    params = {
        "ratio_stds": ratio_stds,
        "scaling_weighted": scaling["weighted"],
        "scaling_unweighted": scaling["unweighted"],
    }
    return df, params, ratio_cols


def _build_topic_or_actor_ratios(
    wide: pd.DataFrame,
    sources: list[str],
    keys: Iterable[str],
    metric_prefix: str,
) -> pd.DataFrame:
    """For every (source, key) pair, derive a per-source ratio column for
    the per-topic or per-actor EPU index.

    `metric_prefix` is `"topic_"` or `"actor_"` — matches the parquet column
    naming `{source}_<metric_prefix>{key}_count`.
    """
    df = wide.copy()
    for src in sources:
        a_col = f"{src}_A_total"
        if a_col not in df.columns:
            continue
        for k in keys:
            count_col = f"{src}_{metric_prefix}{k}_count"
            ratio_col = f"{src}_{metric_prefix}{k}_ratio"
            if count_col in df.columns:
                df[ratio_col] = (
                    df[count_col]
                    .div(df[a_col])
                    .replace([np.inf, -np.inf], np.nan)
                    .fillna(0)
                )
    return df


def _build_ug_counts_frame(
    wide: pd.DataFrame,
    sources: list[str],
    group_keys: Iterable[str],
    metric_prefix: str,
) -> pd.DataFrame:
    """Materialize the UG counts frame consumed by `outputs.build_outputs`'s
    attribution path.

    Columns: ym, date, plus per-source A_total, U_count, UG_<g>_count and
    G_<g>_count. UG counts come from `<source>_<metric_prefix><g>_U_count`
    (articles that are both uncertain and on-topic); G counts come from
    `<source>_<metric_prefix><g>_A_count` (on-topic regardless of uncertainty),
    and feed the unconditional topic-intensity index.
    """
    cols = ["ym", "date"]
    for src in sources:
        a_col = f"{src}_A_total"
        u_col = f"{src}_U_count"
        if a_col in wide.columns:
            cols.append(a_col)
        if u_col in wide.columns:
            cols.append(u_col)
        for g in group_keys:
            for long in (
                f"{src}_{metric_prefix}{g}_U_count",
                f"{src}_{metric_prefix}{g}_A_count",
            ):
                if long in wide.columns:
                    cols.append(long)
    out = wide[[c for c in cols if c in wide.columns]].copy()
    rename: dict[str, str] = {}
    for src in sources:
        for g in group_keys:
            for long, short in (
                (f"{src}_{metric_prefix}{g}_U_count", f"{src}_UG_{g}_count"),
                (f"{src}_{metric_prefix}{g}_A_count", f"{src}_G_{g}_count"),
            ):
                if long in out.columns:
                    rename[long] = short
    return out.rename(columns=rename)


# ── Top-level entry point ────────────────────────────────────────────


def standardize_unit(
    source_counts: pd.DataFrame,
    cutoff_start: str | None,
    cutoff_end: str | None,
    daily_tail_start: str | None,
    topic_keys: Iterable[str],
    actor_keys: Iterable[str],
) -> dict:
    """Run the full standardization pipeline for a single unit.

    Returns dict with keys: `e_base`, `topic_epus`, `actor_epus`,
    `ug_counts_all` — same shape that the legacy `runners.run_full_epu`
    returned, so `outputs.build_outputs` works unchanged.
    """
    wide, sources = pivot_to_wide(source_counts, daily_tail_start)
    if not sources:
        empty = StandardizedUnit(
            epu_stats=wide,
            news_cols=[],
            params={
                "ratio_stds": {},
                "scaling_weighted": None,
                "scaling_unweighted": None,
            },
            min_date=None,
            max_date=None,
        )
        return {
            "e_base": empty,
            "topic_epus": {},
            "actor_epus": {},
            "ug_counts_all": {"topics": pd.DataFrame(), "actors": pd.DataFrame()},
        }

    # ── Base EPU ─────────────────────────────────────────────────────
    base_df, base_params, _ = _standardize_epu(
        wide, sources, cutoff_start, cutoff_end, ratio_template="{source}_ratio"
    )
    news_cols = [f"{s}_body_count" for s in sources]

    # Extended indices (breadth / intensity / pairwise) — IndexCalculator
    # consumes the wide layout we already built; just add the columns it needs.
    calc = IndexCalculator(cutoff_start, cutoff_end)
    base_df = calc.calculate_breadth_indices(base_df, sources)
    base_df = calc.calculate_intensity_indices(base_df, sources)
    base_df = calc.calculate_pairwise_indices(base_df, sources)

    e_base = StandardizedUnit(
        epu_stats=base_df,
        news_cols=news_cols,
        params=base_params,
        min_date=base_df["date"].min(),
        max_date=base_df["date"].max(),
        _extended_calc=calc,
    )

    # ── Per-topic EPU ────────────────────────────────────────────────
    wide_with_topic_ratios = _build_topic_or_actor_ratios(
        wide, sources, topic_keys, metric_prefix="topic_"
    )
    topic_epus: dict[str, StandardizedUnit] = {}
    for k in topic_keys:
        df_t, params_t, _ = _standardize_epu(
            wide_with_topic_ratios,
            sources,
            cutoff_start,
            cutoff_end,
            ratio_template=f"{{source}}_topic_{k}_ratio",
        )
        topic_epus[k] = StandardizedUnit(
            epu_stats=df_t,
            news_cols=news_cols,
            params=params_t,
            min_date=df_t["date"].min(),
            max_date=df_t["date"].max(),
        )

    # ── Per-actor EPU ────────────────────────────────────────────────
    wide_with_actor_ratios = _build_topic_or_actor_ratios(
        wide, sources, actor_keys, metric_prefix="actor_"
    )
    actor_epus: dict[str, StandardizedUnit] = {}
    for k in actor_keys:
        df_a, params_a, _ = _standardize_epu(
            wide_with_actor_ratios,
            sources,
            cutoff_start,
            cutoff_end,
            ratio_template=f"{{source}}_actor_{k}_ratio",
        )
        actor_epus[k] = StandardizedUnit(
            epu_stats=df_a,
            news_cols=news_cols,
            params=params_a,
            min_date=df_a["date"].min(),
            max_date=df_a["date"].max(),
        )

    # ── UG counts (uncertainty attribution) ──────────────────────────
    ug_topics = _build_ug_counts_frame(
        wide, sources, topic_keys, metric_prefix="topic_"
    )
    ug_actors = _build_ug_counts_frame(
        wide, sources, actor_keys, metric_prefix="actor_"
    )

    return {
        "e_base": e_base,
        "topic_epus": topic_epus,
        "actor_epus": actor_epus,
        "ug_counts_all": {"topics": ug_topics, "actors": ug_actors},
    }
