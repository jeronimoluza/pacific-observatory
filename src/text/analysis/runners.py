"""EPU computation engine.

Provides full and incremental EPU pipelines with shared article preloading,
group EPU computation, and cache restoration helpers.
"""

import numpy as np
import pandas as pd

from src.text.analysis.epu import EPU
from src.text.analysis.indices import IndexCalculator
from src.text.analysis.utils import load_all_groups


def _preload_articles(news_dirs, subset_condition, daily_tail_start):
    """Read and process all news CSV files into a shared dict.

    Returns dict[str, DataFrame] keyed by file path string.
    Files that fail to read are silently skipped.
    """
    preloaded = {}
    for fp in news_dirs:
        try:
            preloaded[str(fp)] = EPU.process_data(
                fp,
                subset_condition=subset_condition,
                daily_tail_start=daily_tail_start,
            )
        except Exception:
            pass
    return preloaded


def _run_group_epus(
    news_dirs,
    cutoff_start_date,
    cutoff_end_date,
    daily_tail_start,
    groups,
    subset_condition,
    preloaded,
    source_languages=None,
):
    """Run EPU computation for a dict of groups (topics or actors).

    Args:
        groups: dict mapping group_key -> additional_terms list.

    Returns dict[str, EPU] mapping group_key -> computed EPU instance.
    """
    result = {}
    for group_key, additional_terms in groups.items():
        epu = EPU(
            news_dirs,
            cutoff_start_date=cutoff_start_date,
            cutoff_end_date=cutoff_end_date,
            additional_terms=additional_terms,
            additional_name=group_key,
            daily_tail_start=daily_tail_start,
            source_languages=source_languages,
        )
        epu.get_epu_category(subset_condition=subset_condition, preloaded=preloaded)
        epu.get_count_stats(calculate_extended=False)
        epu.calculate_epu_score()
        epu.raw_files = []
        result[group_key] = epu
    return result


def _restore_from_cache(epu, tail_ts, pre_tail_cache):
    """Restore an EPU instance from cache for incremental mode.

    Injects skeleton daily spine if tail data is empty, prepends cached
    pre-tail rows, restores metadata columns, and recomputes source weights.
    Mutates epu in place.
    """
    if epu.epu_stats.empty or epu.epu_stats["date"].max() < tail_ts:
        _today = pd.Timestamp.today().normalize()
        _spine = epu._build_continuous_index(tail_ts, _today)
        if epu.daily_tail_start is not None:
            daily_tail_ts = pd.Timestamp(epu.daily_tail_start)
            _spine["ym"] = _spine["date"].apply(
                lambda d: (
                    d.strftime("%Y-%m-%d")
                    if d >= daily_tail_ts
                    else str(d.year) + "-" + str(d.month)
                )
            )
        else:
            _spine["ym"] = _spine["date"].apply(
                lambda d: str(d.year) + "-" + str(d.month)
            )
        _spine["news_total"] = 0
        epu.epu_stats = _spine
        epu.news_cols = []
        epu.ratio_cols = []

    epu.epu_stats = (
        pd.concat([pre_tail_cache, epu.epu_stats], ignore_index=True)
        .sort_values("date")
        .reset_index(drop=True)
    )

    epu.news_cols = [c for c in epu.epu_stats.columns if c.endswith("_body_count")]
    epu.ratio_cols = [c for c in epu.epu_stats.columns if c.endswith("_ratio")]
    epu.min_date = epu.epu_stats["date"].min()
    epu.max_date = epu.epu_stats["date"].max()

    total_counts = epu.epu_stats[epu.news_cols].sum(axis=1)
    for col in epu.news_cols:
        w_col = col.replace("_body_count", "_weights")
        epu.epu_stats[w_col] = epu.epu_stats[col].fillna(0).div(total_counts).fillna(0)


def _run_incremental_group_epus(
    news_dirs,
    cutoff_start_date,
    cutoff_end_date,
    daily_tail_start,
    groups,
    combined_condition,
    preloaded,
    tail_ts,
    pre_tail_cache,
    params_section,
    source_languages=None,
):
    """Run incremental EPU for a dict of groups with cache restoration.

    Args:
        groups: dict mapping group_key -> additional_terms list.
        params_section: dict mapping group_key -> stored EPU params.

    Returns dict[str, EPU].
    """
    result = {}
    for key, additional_terms in groups.items():
        e = EPU(
            news_dirs,
            cutoff_start_date=cutoff_start_date,
            cutoff_end_date=cutoff_end_date,
            additional_terms=additional_terms,
            additional_name=key,
            daily_tail_start=daily_tail_start,
            source_languages=source_languages,
        )
        e.get_epu_category(subset_condition=combined_condition, preloaded=preloaded)
        e.get_count_stats(calculate_extended=False)
        _restore_from_cache(e, tail_ts, pre_tail_cache)
        gp = params_section.get(key, {})
        e._apply_stored_params(
            ratio_stds=gp.get("ratio_stds", {}),
            scaling_weighted=gp.get("scaling_weighted"),
            scaling_unweighted=gp.get("scaling_unweighted"),
        )
        result[key] = e
    return result


def run_full_epu(
    news_dirs,
    cutoff_start_date,
    cutoff_end_date,
    subset_condition,
    daily_tail_start,
    all_topics,
    all_actors,
    source_languages=None,
):
    """Run the full EPU pipeline (all articles).

    Returns (e_base, topic_epus, actor_epus, ug_counts_all).
    ug_counts_all is a dict: {"topics": df, "actors": df}.
    """
    preloaded = _preload_articles(news_dirs, subset_condition, daily_tail_start)

    e_base = EPU(
        news_dirs,
        cutoff_start_date=cutoff_start_date,
        cutoff_end_date=cutoff_end_date,
        daily_tail_start=daily_tail_start,
        source_languages=source_languages,
    )
    e_base.get_epu_category(subset_condition=subset_condition, preloaded=preloaded)
    e_base.get_count_stats(calculate_extended=True)
    e_base.calculate_epu_score()
    e_base.calculate_all_indices()

    # UG counts need raw_files; compute before freeing them
    ug_counts_all = {}
    for source_file in ("topics", "actors"):
        groups = load_all_groups(source_file)
        ug_counts_all[source_file] = e_base.calculate_group_uncertainty_counts(groups)

    e_base.raw_files = []

    topic_epus = _run_group_epus(
        news_dirs,
        cutoff_start_date,
        cutoff_end_date,
        daily_tail_start,
        all_topics,
        subset_condition,
        preloaded,
        source_languages=source_languages,
    )
    actor_epus = _run_group_epus(
        news_dirs,
        cutoff_start_date,
        cutoff_end_date,
        daily_tail_start,
        all_actors,
        subset_condition,
        preloaded,
        source_languages=source_languages,
    )

    return e_base, topic_epus, actor_epus, ug_counts_all


def run_full_groups_only(
    news_dirs,
    cutoff_start_date,
    cutoff_end_date,
    subset_condition,
    daily_tail_start,
    groups_subset,
    source_languages=None,
):
    """Compute full-history EPUs for a subset of groups (topics or actors).

    Used to backfill new topics/actors without re-running the full base pipeline.
    Returns dict[str, EPU].
    """
    preloaded = _preload_articles(news_dirs, subset_condition, daily_tail_start)
    return _run_group_epus(
        news_dirs,
        cutoff_start_date,
        cutoff_end_date,
        daily_tail_start,
        groups_subset,
        subset_condition,
        preloaded,
        source_languages=source_languages,
    )


def run_incremental_epu(
    news_dirs,
    cutoff_start_date,
    cutoff_end_date,
    subset_condition,
    recompute_start,
    daily_tail_start,
    all_topics,
    all_actors,
    params,
    cache,
    source_languages=None,
):
    """Run the incremental EPU pipeline using cached pre-tail epu_stats.

    Reads articles from the recompute window forward while keeping only the
    current month as daily output.
    Applies stored sigma and scaling factors from params instead of recalculating.
    Returns (e_base, topic_epus, actor_epus, ug_counts_all).
    """
    tail_condition = f"date >= '{recompute_start}'"
    combined_condition = (
        f"{subset_condition} and {tail_condition}"
        if subset_condition
        else tail_condition
    )

    preloaded = _preload_articles(news_dirs, combined_condition, daily_tail_start)

    # ── Base EPU: tail-only articles ────────────────────────────────
    e_base = EPU(
        news_dirs,
        cutoff_start_date=cutoff_start_date,
        cutoff_end_date=cutoff_end_date,
        daily_tail_start=daily_tail_start,
        source_languages=source_languages,
    )
    e_base.get_epu_category(subset_condition=combined_condition, preloaded=preloaded)
    e_base.get_count_stats(calculate_extended=True)

    tail_ts = pd.Timestamp(recompute_start)
    pre_tail_cache = cache[cache["date"] < tail_ts].copy()
    _restore_from_cache(e_base, tail_ts, pre_tail_cache)

    # Apply stored params instead of recalculating sigma
    epu_params = params["epu"]
    e_base._apply_stored_params(
        ratio_stds=epu_params["ratio_stds"],
        scaling_weighted=epu_params["scaling_weighted"],
        scaling_unweighted=epu_params["scaling_unweighted"],
    )

    # Compute fresh extended indices only for tail rows
    sources = [c.replace("_body_count", "") for c in e_base.news_cols]
    tail_mask = e_base.epu_stats["date"] >= tail_ts
    tail_df = e_base.epu_stats[tail_mask].copy().reset_index(drop=True)

    _calc = IndexCalculator(cutoff_start_date, cutoff_end_date)
    tail_df = _calc.calculate_breadth_indices(tail_df, sources)
    tail_df = _calc.calculate_intensity_indices(tail_df, sources)
    tail_df = _calc.calculate_pairwise_indices(tail_df, sources)

    extended_cols = [
        c
        for c in tail_df.columns
        if any(
            c.endswith(sfx)
            for sfx in (
                "_breadth_weighted",
                "_breadth_unweighted",
                "_intensity_weighted",
                "_intensity_unweighted",
                "_share_weighted",
                "_share_unweighted",
            )
        )
    ]
    tail_indices = e_base.epu_stats.index[tail_mask]
    for ec in extended_cols:
        if ec not in e_base.epu_stats.columns:
            e_base.epu_stats[ec] = np.nan
        e_base.epu_stats.loc[tail_indices, ec] = tail_df[ec].values

    # ── Topic/Actor EPU: tail-only with cache restoration ──────────
    topic_epus = _run_incremental_group_epus(
        news_dirs,
        cutoff_start_date,
        cutoff_end_date,
        daily_tail_start,
        all_topics,
        combined_condition,
        preloaded,
        tail_ts,
        pre_tail_cache,
        params.get("topics_epu", {}),
        source_languages=source_languages,
    )
    actor_epus = _run_incremental_group_epus(
        news_dirs,
        cutoff_start_date,
        cutoff_end_date,
        daily_tail_start,
        all_actors,
        combined_condition,
        preloaded,
        tail_ts,
        pre_tail_cache,
        params.get("actors_epu", {}),
        source_languages=source_languages,
    )

    # ── Attribution UG counts: tail-only ───────────────────────────
    ug_counts_all = {}
    for source_file in ("topics", "actors"):
        groups = load_all_groups(source_file)
        tail_ug = e_base.calculate_group_uncertainty_counts(groups)
        tail_ug["date"] = pd.to_datetime(tail_ug["ym"], format="mixed")
        tail_ug = tail_ug[tail_ug["date"] >= tail_ts]

        if tail_ug.empty:
            _today = pd.Timestamp.today().normalize()
            tail_ug = e_base._build_continuous_index(tail_ts, _today)
            daily_tail_ts = pd.Timestamp(daily_tail_start)
            tail_ug["ym"] = tail_ug["date"].apply(
                lambda d: (
                    d.strftime("%Y-%m-%d")
                    if d >= daily_tail_ts
                    else str(d.year) + "-" + str(d.month)
                )
            )

        ug_cols = [
            c
            for c in cache.columns
            if (
                any(f"_UG_{g}_count" in c for g in groups)
                or c.endswith("_U_count")
                or c.endswith("_A_total")
            )
        ]
        if ug_cols:
            pre_tail_ug = cache[cache["date"] < tail_ts][
                ["date", "ym"] + ug_cols
            ].copy()
            combined_ug = pd.concat([pre_tail_ug, tail_ug], ignore_index=True)
        else:
            combined_ug = tail_ug

        ug_counts_all[source_file] = combined_ug

    return e_base, topic_epus, actor_epus, ug_counts_all
