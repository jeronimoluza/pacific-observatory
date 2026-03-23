import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

# Setup path before imports
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.text.analysis.epu import EPU  # noqa: E402
from src.text.analysis.indices import IndexCalculator  # noqa: E402
from src.text.analysis.translate_keywords import translate_keywords  # noqa: E402
from src.text.analysis.utils import load_all_groups  # noqa: E402


def _build_continuous_index_df(
    min_date, max_date, daily_tail_start: str | None
) -> pd.DataFrame:
    """Build hybrid monthly+daily date index (mirrors EPU._build_continuous_index)."""
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
            daily_dates = pd.date_range(start=tail_ts, end=max_date, freq="D")
        all_dates = monthly_dates.append(daily_dates)
    else:
        all_dates = pd.date_range(start=min_date, end=max_date, freq="MS")
    return pd.DataFrame({"date": all_dates})


PROJECT_ROOT = _PROJECT_ROOT

DATA_ROOT = PROJECT_ROOT / "data" / "text"


def append_missing_months(
    path: Path,
    new_df: pd.DataFrame,
    n_months: int = 2,
    daily_tail_start: str | None = None,
) -> None:
    """
    Append rows for periods not yet present in an existing CSV.

    For the current month (daily tail), compares by exact date.
    For past months, compares by calendar month period.
    If the file does not exist, writes new_df in full.
    """
    today = pd.Timestamp.today()

    if not path.exists():
        new_df.to_csv(path, index=False, encoding="utf-8")
        return

    existing = pd.read_csv(path, encoding="utf-8")

    # If the *schema* changed (new columns), rewrite the file even if there are
    # no new rows to append. This matters when we add new topic indices but the
    # underlying date coverage hasn't changed; plotting code discovers topics
    # from CSV columns.
    existing_cols = list(existing.columns)
    new_cols = list(new_df.columns)
    merged_cols = existing_cols + [c for c in new_cols if c not in existing_cols]
    schema_changed = merged_cols != existing_cols
    added_cols = [c for c in new_cols if c not in existing_cols]

    existing["date"] = pd.to_datetime(existing["date"])
    new_df = new_df.copy()
    new_df["date"] = pd.to_datetime(new_df["date"])

    # Fill missing values for columns that already exist on disk.
    # This is conservative: only fill existing NaNs from new_df; never overwrite
    # existing non-null values.
    fill_missing_cols = []
    for c in new_cols:
        if c in ("date", "ym"):
            continue
        if (
            c in existing_cols
            and existing[c].isna().any()
            and not new_df[c].isna().all()
        ):
            fill_missing_cols.append(c)

    cols_to_update = added_cols + fill_missing_cols
    updated_columns = bool(cols_to_update)

    if schema_changed:
        existing = existing.reindex(columns=merged_cols)

    if cols_to_update:
        add_src = new_df[["date"] + cols_to_update].copy()
        add_src = add_src.drop_duplicates(subset=["date"], keep="last")
        existing = existing.merge(
            add_src, on="date", how="left", suffixes=("", "__new")
        )
        for c in cols_to_update:
            new_c = f"{c}__new"
            if new_c in existing.columns:
                if c in added_cols:
                    existing[c] = existing[new_c]
                else:
                    existing[c] = existing[c].where(
                        existing[c].notna(), existing[new_c]
                    )
                existing = existing.drop(columns=[new_c])

    rows_to_add_list = []

    # ── Daily tail: always replace the entire tail window ────────────────
    # Drop any existing rows in the tail period (including stale monthly rows
    # for the current month written by a previous run) and re-add fresh ones.
    if daily_tail_start is not None:
        tail_ts = pd.Timestamp(daily_tail_start)
        existing = existing[existing["date"] < tail_ts]
        new_daily = new_df[new_df["date"] >= tail_ts]
        if not new_daily.empty:
            rows_to_add_list.append(new_daily)

    # ── Past months: compare by calendar month period ─────────────────────
    # target = last n_months completed months (not counting current month)
    if daily_tail_start is not None:
        # current month handled above; past months start from previous month
        target_months = {
            (today - pd.DateOffset(months=i)).to_period("M")
            for i in range(1, n_months + 1)
        }
        existing_past = existing[existing["date"] < pd.Timestamp(daily_tail_start)]
    else:
        target_months = {
            (today - pd.DateOffset(months=i)).to_period("M") for i in range(n_months)
        }
        existing_past = existing

    existing_months = set(existing_past["date"].dt.to_period("M"))
    missing_months = target_months - existing_months
    if missing_months:
        past_new_df = (
            new_df
            if daily_tail_start is None
            else new_df[new_df["date"] < pd.Timestamp(daily_tail_start)]
        )
        rows_for_months = past_new_df[
            past_new_df["date"].dt.to_period("M").isin(missing_months)
        ]
        if not rows_for_months.empty:
            rows_to_add_list.append(rows_for_months)

    if not rows_to_add_list:
        if schema_changed or updated_columns:
            # No new rows, but ensure column updates are persisted.
            existing.to_csv(path, index=False, encoding="utf-8")
        return

    rows_to_add = pd.concat(rows_to_add_list)
    combined = (
        pd.concat([existing, rows_to_add]).sort_values("date").reset_index(drop=True)
    )
    combined.to_csv(path, index=False, encoding="utf-8")


EXCLUDED_COUNTRIES = {}


def _get_country_dirs(exclude_countries: set[str] | None = None) -> list[Path]:
    excluded = {name.lower() for name in EXCLUDED_COUNTRIES}
    if exclude_countries:
        excluded |= {name.lower() for name in exclude_countries}
    return sorted(
        [
            entry
            for entry in DATA_ROOT.iterdir()
            if entry.is_dir() and entry.name.lower() not in excluded
        ]
    )


OUTPUT_DIR = PROJECT_ROOT / "outputs" / "text"
CACHE_DIR = PROJECT_ROOT / "data" / "text" / "cache"


def _collect_params(
    country_name: str,
    cutoff: str,
    e_base: "EPU",
    topic_epus: dict,
    actor_epus: dict,
    calc_topics: "IndexCalculator",
    calc_actors: "IndexCalculator",
    all_news_dfs: list,
) -> dict:
    """
    Collect all standardization parameters into a single dict for params.json.
    """
    # n_articles_pre_cutoff: total rows across all sources with date < cutoff
    cutoff_ts = pd.Timestamp(cutoff)
    n_pre = sum(
        (df[df["date"] < cutoff_ts].shape[0] if "date" in df.columns else 0)
        for df in all_news_dfs
    )

    sources = [col.replace("_body_count", "") for col in e_base.news_cols]

    # Source weights: average share of total news over pre-cutoff period
    pre_cutoff_stats = e_base.epu_stats[e_base.epu_stats["date"] < cutoff_ts]
    source_weights = {}
    for src in sources:
        w_col = f"{src}_weights"
        if w_col in pre_cutoff_stats.columns:
            source_weights[src] = float(pre_cutoff_stats[w_col].mean())

    # Extended index params: reuse the IndexCalculator stored by calculate_all_indices
    extended_params_raw = e_base._extended_calc.get_params()

    # Reorganise extended params by index name.
    # ratio_stds keys have the form: "{source}_{index_name}_ratio"
    # scaling_factors keys have the form: "{index_name}_weighted" / "{index_name}_unweighted"
    extended = {}
    for index_name in [
        "E_breadth",
        "P_breadth",
        "U_breadth",
        "E_intensity",
        "P_intensity",
        "U_intensity",
        "EU_share",
        "PU_share",
        "EP_share",
    ]:
        suffix = f"_{index_name}_ratio"
        extended[index_name] = {
            "ratio_stds": {
                k: v
                for k, v in extended_params_raw["ratio_stds"].items()
                if k.endswith(suffix)
            },
            "scaling_weighted": extended_params_raw["scaling_factors"].get(
                f"{index_name}_weighted"
            ),
            "scaling_unweighted": extended_params_raw["scaling_factors"].get(
                f"{index_name}_unweighted"
            ),
        }

    # Attribution params
    def _attr_params(calc_idx):
        raw = calc_idx.get_params()
        return {
            "ratio_stds": raw["ratio_stds"],
            "scaling_factors": raw["scaling_factors"],
        }

    return {
        "cutoff": cutoff,
        "n_articles_pre_cutoff": int(n_pre),
        "sources": sources,
        "source_weights": source_weights,
        "epu": e_base.params,
        "topics_epu": {k: v.params for k, v in topic_epus.items()},
        "actors_epu": {k: v.params for k, v in actor_epus.items()},
        "extended": extended,
        "attribution": {
            "topics": _attr_params(calc_topics),
            "actors": _attr_params(calc_actors),
        },
    }


def _run_full_epu(
    news_dirs, cutoff, subset_condition, daily_tail_start, all_topics, all_actors
):
    """
    Run the full EPU pipeline (all articles). Returns (e_base, topic_epus, actor_epus, ug_counts_all).
    ug_counts_all is a dict: {"topics": df, "actors": df} of raw UG counts pre-merged.
    """
    # Pre-read all articles once; share across base EPU and all topic EPUs
    preloaded = {}
    for fp in news_dirs:
        try:
            preloaded[str(fp)] = EPU.process_data(
                fp, subset_condition=subset_condition, daily_tail_start=daily_tail_start
            )
        except Exception:
            pass

    e_base = EPU(news_dirs, cutoff=cutoff, daily_tail_start=daily_tail_start)
    e_base.get_epu_category(subset_condition=subset_condition, preloaded=preloaded)
    e_base.get_count_stats(calculate_extended=True)
    e_base.calculate_epu_score()
    e_base.calculate_all_indices()

    # UG counts need raw_files; compute before freeing them
    ug_counts_all = {}
    for source_file in ("topics", "actors"):
        groups = load_all_groups(source_file)
        ug_counts_all[source_file] = e_base.calculate_group_uncertainty_counts(groups)

    # Free article-level data — no longer needed after this point
    e_base.raw_files = []

    topic_epus = {}
    for topic_key, additional_terms in all_topics.items():
        e_topic = EPU(
            news_dirs,
            cutoff=cutoff,
            additional_terms=additional_terms,
            additional_name=topic_key,
            daily_tail_start=daily_tail_start,
        )
        e_topic.get_epu_category(subset_condition=subset_condition, preloaded=preloaded)
        e_topic.get_count_stats(calculate_extended=False)
        e_topic.calculate_epu_score()
        e_topic.raw_files = []  # free immediately
        topic_epus[topic_key] = e_topic

    actor_epus = {}
    for actor_key, additional_terms in all_actors.items():
        e_actor = EPU(
            news_dirs,
            cutoff=cutoff,
            additional_terms=additional_terms,
            additional_name=actor_key,
            daily_tail_start=daily_tail_start,
        )
        e_actor.get_epu_category(subset_condition=subset_condition, preloaded=preloaded)
        e_actor.get_count_stats(calculate_extended=False)
        e_actor.calculate_epu_score()
        e_actor.raw_files = []  # free immediately
        actor_epus[actor_key] = e_actor

    return e_base, topic_epus, actor_epus, ug_counts_all


def _run_full_actors_only(
    news_dirs,
    cutoff,
    subset_condition,
    daily_tail_start,
    actors_subset: dict,
):
    """Compute full-history actor EPUs for a subset of actors.

    Used to backfill new actors without re-running the full base pipeline.
    Returns a dict: {actor_key: EPU instance}.
    """
    preloaded = {}
    for fp in news_dirs:
        try:
            preloaded[str(fp)] = EPU.process_data(
                fp, subset_condition=subset_condition, daily_tail_start=daily_tail_start
            )
        except Exception:
            pass

    actor_epus = {}
    for actor_key, additional_terms in actors_subset.items():
        e_actor = EPU(
            news_dirs,
            cutoff=cutoff,
            additional_terms=additional_terms,
            additional_name=actor_key,
            daily_tail_start=daily_tail_start,
        )
        e_actor.get_epu_category(subset_condition=subset_condition, preloaded=preloaded)
        e_actor.get_count_stats(calculate_extended=False)
        e_actor.calculate_epu_score()
        e_actor.raw_files = []  # free immediately
        actor_epus[actor_key] = e_actor

    return actor_epus


def _run_full_topics_only(
    news_dirs,
    cutoff,
    subset_condition,
    daily_tail_start,
    topics_subset: dict,
):
    """Compute full-history topic EPUs for a subset of topics.

    Used to backfill new topics without re-running the full base pipeline.
    Returns a dict: {topic_key: EPU instance}.
    """
    # Pre-read all articles once; shared across all topic EPUs
    preloaded = {}
    for fp in news_dirs:
        try:
            preloaded[str(fp)] = EPU.process_data(
                fp, subset_condition=subset_condition, daily_tail_start=daily_tail_start
            )
        except Exception:
            pass

    topic_epus = {}
    for topic_key, additional_terms in topics_subset.items():
        e_topic = EPU(
            news_dirs,
            cutoff=cutoff,
            additional_terms=additional_terms,
            additional_name=topic_key,
            daily_tail_start=daily_tail_start,
        )
        e_topic.get_epu_category(subset_condition=subset_condition, preloaded=preloaded)
        e_topic.get_count_stats(calculate_extended=False)
        e_topic.calculate_epu_score()
        e_topic.raw_files = []  # free immediately
        topic_epus[topic_key] = e_topic

    return topic_epus


def _run_incremental_epu(
    news_dirs,
    cutoff,
    subset_condition,
    daily_tail_start,
    all_topics,
    all_actors,
    params,
    cache,
):
    """
    Run the incremental EPU pipeline using cached pre-tail epu_stats.
    Only reads articles from the current month (date >= daily_tail_start).
    Applies stored σ and scaling factors from params instead of recalculating.
    Returns (e_base, topic_epus, actor_epus, ug_counts_all).
    """
    tail_condition = f"date >= '{daily_tail_start}'"
    combined_condition = (
        f"{subset_condition} and {tail_condition}"
        if subset_condition
        else tail_condition
    )

    # ── Pre-read tail articles once; share across base + all topic EPUs ─
    preloaded = {}
    for fp in news_dirs:
        try:
            preloaded[str(fp)] = EPU.process_data(
                fp,
                subset_condition=combined_condition,
                daily_tail_start=daily_tail_start,
            )
        except Exception:
            pass

    # ── Base EPU: tail-only articles ───────────────────────────────────
    e_base = EPU(news_dirs, cutoff=cutoff, daily_tail_start=daily_tail_start)
    e_base.get_epu_category(subset_condition=combined_condition, preloaded=preloaded)
    e_base.get_count_stats(calculate_extended=False)

    # If no tail articles, epu_stats is empty; inject a skeleton daily spine so
    # that daily rows are still written for the current month (with zeros/NaN).
    tail_ts = pd.Timestamp(daily_tail_start)
    if e_base.epu_stats.empty or e_base.epu_stats["date"].max() < tail_ts:
        _today = pd.Timestamp.today().normalize()
        _daily_spine = pd.date_range(start=tail_ts, end=_today, freq="D")
        e_base.epu_stats = pd.DataFrame(
            {
                "date": _daily_spine,
                "ym": [d.strftime("%Y-%m-%d") for d in _daily_spine],
                "news_total": 0,
            }
        )
        e_base.news_cols = []
        e_base.ratio_cols = []
        e_base.min_date = e_base.epu_stats["date"].min()
        e_base.max_date = e_base.epu_stats["date"].max()

    # Prepend cached pre-tail rows, restore metadata
    pre_tail_cache = cache[cache["date"] < pd.Timestamp(daily_tail_start)].copy()
    e_base.epu_stats = (
        pd.concat([pre_tail_cache, e_base.epu_stats], ignore_index=True)
        .sort_values("date")
        .reset_index(drop=True)
    )

    e_base.news_cols = [
        c for c in e_base.epu_stats.columns if c.endswith("_body_count")
    ]
    e_base.ratio_cols = [c for c in e_base.epu_stats.columns if c.endswith("_ratio")]
    e_base.min_date = e_base.epu_stats["date"].min()
    e_base.max_date = e_base.epu_stats["date"].max()

    # Recompute weights from counts; NaN body_count (source absent in tail) → weight 0
    total_counts = e_base.epu_stats[e_base.news_cols].sum(axis=1)
    for col in e_base.news_cols:
        new_col = col.replace("_body_count", "_weights")
        e_base.epu_stats[new_col] = (
            e_base.epu_stats[col].fillna(0).div(total_counts).fillna(0)
        )

    # Apply stored params instead of recalculating σ
    epu_params = params["epu"]
    e_base._apply_stored_params(
        ratio_stds=epu_params["ratio_stds"],
        scaling_weighted=epu_params["scaling_weighted"],
        scaling_unweighted=epu_params["scaling_unweighted"],
    )

    # Extended index columns: pre-tail values already present from cache concat.
    # Compute fresh extended indices only for tail rows and write back.
    from src.text.analysis.indices import IndexCalculator as _IC

    sources = [c.replace("_body_count", "") for c in e_base.news_cols]
    tail_ts = pd.Timestamp(daily_tail_start)
    tail_mask = e_base.epu_stats["date"] >= tail_ts
    tail_df = e_base.epu_stats[tail_mask].copy().reset_index(drop=True)

    _calc = _IC(cutoff)
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

    # ── Topic EPU: tail-only ────────────────────────────────────────────
    topic_epus = {}

    for topic_key, additional_terms in all_topics.items():  # noqa: E501 (kept for symmetry)
        e_topic = EPU(
            news_dirs,
            cutoff=cutoff,
            additional_terms=additional_terms,
            additional_name=topic_key,
            daily_tail_start=daily_tail_start,
        )
        e_topic.get_epu_category(
            subset_condition=combined_condition, preloaded=preloaded
        )
        e_topic.get_count_stats(calculate_extended=False)

        # Skeleton spine for zero-article topic tail (mirrors base EPU guard above)
        if e_topic.epu_stats.empty or e_topic.epu_stats["date"].max() < tail_ts:
            _today = pd.Timestamp.today().normalize()
            _daily_spine = pd.date_range(start=tail_ts, end=_today, freq="D")
            e_topic.epu_stats = pd.DataFrame(
                {
                    "date": _daily_spine,
                    "ym": [d.strftime("%Y-%m-%d") for d in _daily_spine],
                    "news_total": 0,
                }
            )
            e_topic.news_cols = []
            e_topic.ratio_cols = []

        # Prepend cache pre-tail rows
        e_topic.epu_stats = (
            pd.concat([pre_tail_cache, e_topic.epu_stats], ignore_index=True)
            .sort_values("date")
            .reset_index(drop=True)
        )
        e_topic.news_cols = [
            c for c in e_topic.epu_stats.columns if c.endswith("_body_count")
        ]
        e_topic.ratio_cols = [
            c for c in e_topic.epu_stats.columns if c.endswith("_ratio")
        ]

        # Recompute weights; NaN body_count (source absent in tail) → weight 0
        _total = e_topic.epu_stats[e_topic.news_cols].sum(axis=1)
        for _col in e_topic.news_cols:
            _w = _col.replace("_body_count", "_weights")
            e_topic.epu_stats[_w] = (
                e_topic.epu_stats[_col].fillna(0).div(_total).fillna(0)
            )

        topic_params = params.get("topics_epu", {}).get(topic_key, {})
        e_topic._apply_stored_params(
            ratio_stds=topic_params.get("ratio_stds", {}),
            scaling_weighted=topic_params.get("scaling_weighted"),
            scaling_unweighted=topic_params.get("scaling_unweighted"),
        )
        topic_epus[topic_key] = e_topic

    # ── Actor EPU: tail-only ─────────────────────────────────────────────
    actor_epus = {}

    for actor_key, additional_terms in all_actors.items():
        e_actor = EPU(
            news_dirs,
            cutoff=cutoff,
            additional_terms=additional_terms,
            additional_name=actor_key,
            daily_tail_start=daily_tail_start,
        )
        e_actor.get_epu_category(
            subset_condition=combined_condition, preloaded=preloaded
        )
        e_actor.get_count_stats(calculate_extended=False)

        # Skeleton spine for zero-article actor tail
        if e_actor.epu_stats.empty or e_actor.epu_stats["date"].max() < tail_ts:
            _today = pd.Timestamp.today().normalize()
            _daily_spine = pd.date_range(start=tail_ts, end=_today, freq="D")
            e_actor.epu_stats = pd.DataFrame(
                {
                    "date": _daily_spine,
                    "ym": [d.strftime("%Y-%m-%d") for d in _daily_spine],
                    "news_total": 0,
                }
            )
            e_actor.news_cols = []
            e_actor.ratio_cols = []

        # Prepend cache pre-tail rows
        e_actor.epu_stats = (
            pd.concat([pre_tail_cache, e_actor.epu_stats], ignore_index=True)
            .sort_values("date")
            .reset_index(drop=True)
        )
        e_actor.news_cols = [
            c for c in e_actor.epu_stats.columns if c.endswith("_body_count")
        ]
        e_actor.ratio_cols = [
            c for c in e_actor.epu_stats.columns if c.endswith("_ratio")
        ]

        # Recompute weights; NaN body_count (source absent in tail) → weight 0
        _total = e_actor.epu_stats[e_actor.news_cols].sum(axis=1)
        for _col in e_actor.news_cols:
            _w = _col.replace("_body_count", "_weights")
            e_actor.epu_stats[_w] = (
                e_actor.epu_stats[_col].fillna(0).div(_total).fillna(0)
            )

        actor_params = params.get("actors_epu", {}).get(actor_key, {})
        e_actor._apply_stored_params(
            ratio_stds=actor_params.get("ratio_stds", {}),
            scaling_weighted=actor_params.get("scaling_weighted"),
            scaling_unweighted=actor_params.get("scaling_unweighted"),
        )
        actor_epus[actor_key] = e_actor

    # ── Attribution UG counts: tail-only ───────────────────────────────
    ug_counts_all = {}

    for source_file in ("topics", "actors"):
        groups = load_all_groups(source_file)
        # Compute UG counts only for tail articles
        tail_ug = e_base.calculate_group_uncertainty_counts(groups)
        tail_ug["date"] = pd.to_datetime(tail_ug["ym"], format="mixed")
        tail_ug = tail_ug[tail_ug["date"] >= tail_ts]
        # If no tail UG rows, synthesise an empty skeleton so the date merge works
        if tail_ug.empty:
            _today = pd.Timestamp.today().normalize()
            _daily_spine = pd.date_range(start=tail_ts, end=_today, freq="D")
            tail_ug = pd.DataFrame(
                {
                    "date": _daily_spine,
                    "ym": [d.strftime("%Y-%m-%d") for d in _daily_spine],
                }
            )

        # Load pre-tail UG counts from cache (include _U_count/_A_total for framing std)
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
            pre_tail_ug = cache[cache["date"] < pd.Timestamp(daily_tail_start)][
                ["date", "ym"] + ug_cols
            ].copy()
            combined_ug = pd.concat([pre_tail_ug, tail_ug], ignore_index=True)
        else:
            combined_ug = tail_ug

        ug_counts_all[source_file] = combined_ug

    return e_base, topic_epus, actor_epus, ug_counts_all


def _build_outputs(
    e_base,
    topic_epus,
    actor_epus,
    ug_counts_all,
    cutoff,
    daily_tail_start,
    country_name,
    all_topics,
    all_actors,
):
    """Build and write all output CSVs from a computed e_base + topic_epus + actor_epus + ug_counts."""
    epu_folder = OUTPUT_DIR / country_name / "epu"
    epu_folder.mkdir(parents=True, exist_ok=True)

    # ── epu.csv ────────────────────────────────────────────────────────
    result = e_base.epu_stats[["date", "ym", "news_total"]].copy()
    result["EPU_index"] = e_base.epu_stats["epu_weighted"]
    for cat in ["E", "P", "U"]:
        col_b = f"{cat}_breadth_weighted"
        col_i = f"{cat}_intensity_weighted"
        result[f"{cat}_breadth"] = (
            e_base.epu_stats[col_b] if col_b in e_base.epu_stats.columns else np.nan
        )
        result[f"{cat}_intensity"] = (
            e_base.epu_stats[col_i] if col_i in e_base.epu_stats.columns else np.nan
        )
    for pair in ["EU", "PU", "EP"]:
        col_p = f"{pair}_share_weighted"
        result[f"{pair}_index"] = (
            e_base.epu_stats[col_p] if col_p in e_base.epu_stats.columns else np.nan
        )
    append_missing_months(
        epu_folder / "epu.csv", result, daily_tail_start=daily_tail_start
    )

    # ── topics_epu.csv ─────────────────────────────────────────────────
    topic_epu = e_base.epu_stats[["date", "ym"]].copy()
    for topic_key, e_topic in topic_epus.items():
        # Align on date to handle any row-count mismatches
        aligned = pd.merge(
            topic_epu[["date"]],
            e_topic.epu_stats[["date", "epu_weighted"]].rename(
                columns={"epu_weighted": f"EPU_{topic_key}_index"}
            ),
            on="date",
            how="left",
        )
        topic_epu[f"EPU_{topic_key}_index"] = aligned[f"EPU_{topic_key}_index"].values
    append_missing_months(
        epu_folder / "topics_epu.csv", topic_epu, daily_tail_start=daily_tail_start
    )

    # ── actors_epu.csv ─────────────────────────────────────────────────
    actor_epu = e_base.epu_stats[["date", "ym"]].copy()
    for actor_key, e_actor in actor_epus.items():
        aligned = pd.merge(
            actor_epu[["date"]],
            e_actor.epu_stats[["date", "epu_weighted"]].rename(
                columns={"epu_weighted": f"EPU_{actor_key}_index"}
            ),
            on="date",
            how="left",
        )
        actor_epu[f"EPU_{actor_key}_index"] = aligned[f"EPU_{actor_key}_index"].values
    append_missing_months(
        epu_folder / "actors_epu.csv", actor_epu, daily_tail_start=daily_tail_start
    )

    # ── uncertainty_attribution ────────────────────────────────────────
    sources = [col.replace("_body_count", "") for col in e_base.news_cols]
    calc_topics_idx = IndexCalculator(cutoff)
    calc_actors_idx = IndexCalculator(cutoff)

    for (source_file, output_name), calc in [
        (("topics", "topics"), calc_topics_idx),
        (("actors", "actors"), calc_actors_idx),
    ]:
        groups = load_all_groups(source_file)
        group_names = list(groups.keys())

        ug_counts = ug_counts_all[source_file]
        attr_df = e_base.epu_stats[["date", "ym"]].copy()
        weight_cols = [c for c in e_base.epu_stats.columns if c.endswith("_weights")]
        for wc in weight_cols:
            attr_df[wc] = e_base.epu_stats[wc]

        ug_counts["date"] = pd.to_datetime(ug_counts["ym"], format="mixed")
        dates_df = _build_continuous_index_df(
            e_base.min_date, e_base.max_date, daily_tail_start
        )
        ug_counts = dates_df.merge(ug_counts, how="left", on="date").fillna(0)
        attr_df = pd.merge(
            attr_df, ug_counts.drop(columns=["ym"]), on="date", how="left"
        )

        attr_df = calc.calculate_absolute_uncertainty_attribution(
            attr_df, sources, group_names
        )
        attr_df = calc.calculate_framing_uncertainty_attribution(
            attr_df, sources, group_names
        )

        out_cols = ["date", "ym"]
        for g in group_names:
            abs_col = f"UG_{g}_abs_weighted"
            frm_col = f"UG_{g}_frm_weighted"
            if abs_col in attr_df.columns:
                attr_df = attr_df.rename(columns={abs_col: f"{g}_absolute"})
                out_cols.append(f"{g}_absolute")
            if frm_col in attr_df.columns:
                attr_df = attr_df.rename(columns={frm_col: f"{g}_framing"})
                out_cols.append(f"{g}_framing")

        attr_out = attr_df[[c for c in out_cols if c in attr_df.columns]]
        attr_folder = OUTPUT_DIR / country_name / "uncertainty_attribution"
        attr_folder.mkdir(parents=True, exist_ok=True)
        append_missing_months(
            attr_folder / f"{output_name}.csv",
            attr_out,
            daily_tail_start=daily_tail_start,
        )

    return calc_topics_idx, calc_actors_idx


def process_country(
    country, cutoff: str, subset_condition: str, recalculate_params: bool = False
):
    """
    Process all EPU and uncertainty attribution indices for a single country.

    Full mode (no cache or --recalculate-params): reads all articles, writes
    params.json and epu_stats_cache.csv.

    Incremental mode (cache exists): reads only current-month articles, applies
    stored σ/scaling from params.json, prepends cached pre-tail rows.
    """
    country_name = country.name
    news_dirs = list(country.glob("*/news.csv"))
    params_path = CACHE_DIR / country_name / "params.json"
    cache_path = CACHE_DIR / country_name / "epu_stats_cache.csv"

    today = pd.Timestamp.today()
    daily_tail_start = today.replace(day=1).strftime("%Y-%m-%d")
    all_topics = load_all_groups("topics")
    all_actors = load_all_groups("actors")

    use_cache = params_path.exists() and cache_path.exists() and not recalculate_params

    # Optional backfill when new topics or actors are added to the keyword taxonomy.
    missing_topic_epus_full = {}
    missing_actor_epus_full = {}
    if use_cache:
        params = json.loads(params_path.read_text(encoding="utf-8"))
        have_topics = set((params.get("topics_epu") or {}).keys())
        want_topics = set(all_topics.keys())
        missing_topics = sorted(want_topics - have_topics)

        have_actors = set((params.get("actors_epu") or {}).keys())
        want_actors = set(all_actors.keys())
        missing_actors = sorted(want_actors - have_actors)

        if missing_topics:
            print(
                "  [cache] missing topic params; recomputing only missing topics: "
                + ", ".join(missing_topics)
            )

            topics_subset = {k: all_topics[k] for k in missing_topics}
            missing_topic_epus_full = _run_full_topics_only(
                news_dirs,
                cutoff,
                subset_condition,
                daily_tail_start,
                topics_subset,
            )

            # Update params.json in place (add only missing topics)
            params.setdefault("topics_epu", {})
            for k, e_topic in missing_topic_epus_full.items():
                params["topics_epu"][k] = e_topic.params

            def _json_default(x):
                return None if (isinstance(x, float) and np.isnan(x)) else x

            params_path.parent.mkdir(parents=True, exist_ok=True)
            with open(params_path, "w", encoding="utf-8") as f:
                json.dump(params, f, indent=2, default=_json_default)
            print(f"  params.json updated with {len(missing_topics)} topics")

            # Update cache with pre-tail topic index columns
            tail_ts = pd.Timestamp(daily_tail_start)
            cache_df = pd.read_csv(cache_path, encoding="utf-8", low_memory=False)
            cache_df["date"] = pd.to_datetime(cache_df["date"])
            for k, e_topic in missing_topic_epus_full.items():
                col = f"EPU_{k}_index"
                topic_pre = e_topic.epu_stats[e_topic.epu_stats["date"] < tail_ts][
                    ["date", "epu_weighted"]
                ].rename(columns={"epu_weighted": col})
                cache_df = cache_df.drop(columns=[col], errors="ignore")
                cache_df = cache_df.merge(topic_pre, on="date", how="left")
            cache_df.to_csv(cache_path, index=False, encoding="utf-8")
            print(f"  epu_stats_cache.csv updated with {len(missing_topics)} topics")

        if missing_actors:
            print(
                "  [cache] missing actor params; recomputing only missing actors: "
                + ", ".join(missing_actors)
            )

            actors_subset = {k: all_actors[k] for k in missing_actors}
            missing_actor_epus_full = _run_full_actors_only(
                news_dirs,
                cutoff,
                subset_condition,
                daily_tail_start,
                actors_subset,
            )

            # Update params.json in place (add only missing actors)
            params.setdefault("actors_epu", {})
            for k, e_actor in missing_actor_epus_full.items():
                params["actors_epu"][k] = e_actor.params

            def _json_default(x):  # noqa: F811
                return None if (isinstance(x, float) and np.isnan(x)) else x

            params_path.parent.mkdir(parents=True, exist_ok=True)
            with open(params_path, "w", encoding="utf-8") as f:
                json.dump(params, f, indent=2, default=_json_default)
            print(f"  params.json updated with {len(missing_actors)} actors")

            # Update cache with pre-tail actor index columns
            tail_ts = pd.Timestamp(daily_tail_start)
            cache_df = pd.read_csv(cache_path, encoding="utf-8", low_memory=False)
            cache_df["date"] = pd.to_datetime(cache_df["date"])
            for k, e_actor in missing_actor_epus_full.items():
                col = f"EPU_{k}_index"
                actor_pre = e_actor.epu_stats[e_actor.epu_stats["date"] < tail_ts][
                    ["date", "epu_weighted"]
                ].rename(columns={"epu_weighted": col})
                cache_df = cache_df.drop(columns=[col], errors="ignore")
                cache_df = cache_df.merge(actor_pre, on="date", how="left")
            cache_df.to_csv(cache_path, index=False, encoding="utf-8")
            print(f"  epu_stats_cache.csv updated with {len(missing_actors)} actors")

    if use_cache:
        print("  [incremental] loading cache...")
        # Reload params in case we just updated it.
        params = json.loads(params_path.read_text(encoding="utf-8"))
        cache = pd.read_csv(cache_path, encoding="utf-8", low_memory=False)
        cache["date"] = pd.to_datetime(cache["date"])
        e_base, topic_epus, actor_epus, ug_counts_all = _run_incremental_epu(
            news_dirs,
            cutoff,
            subset_condition,
            daily_tail_start,
            all_topics,
            all_actors,
            params,
            cache,
        )

        # If we recomputed any missing topics/actors in full-history mode, use those
        # EPU objects for output building so historical values can be backfilled.
        if missing_topic_epus_full:
            topic_epus.update(missing_topic_epus_full)
        if missing_actor_epus_full:
            actor_epus.update(missing_actor_epus_full)
    else:
        print("  [full] running full EPU computation...")
        e_base, topic_epus, actor_epus, ug_counts_all = _run_full_epu(
            news_dirs,
            cutoff,
            subset_condition,
            daily_tail_start,
            all_topics,
            all_actors,
        )

    calc_topics_idx, calc_actors_idx = _build_outputs(
        e_base,
        topic_epus,
        actor_epus,
        ug_counts_all,
        cutoff,
        daily_tail_start,
        country_name,
        all_topics,
        all_actors,
    )

    # ── Write params.json + cache (full mode only) ─────────────────────
    if not use_cache:
        all_news_dfs = [
            pd.read_csv(fp, encoding="utf-8", usecols=["date"], low_memory=False)
            for fp in news_dirs
            if fp.exists()
        ]
        for df in all_news_dfs:
            df["date"] = pd.to_datetime(df["date"], format="mixed", errors="coerce")

        params = _collect_params(
            country_name=country_name,
            cutoff=cutoff,
            e_base=e_base,
            topic_epus=topic_epus,
            actor_epus=actor_epus,
            calc_topics=calc_topics_idx,
            calc_actors=calc_actors_idx,
            all_news_dfs=all_news_dfs,
        )
        params_path.parent.mkdir(parents=True, exist_ok=True)
        with open(params_path, "w", encoding="utf-8") as f:
            json.dump(
                params,
                f,
                indent=2,
                default=lambda x: None if (isinstance(x, float) and np.isnan(x)) else x,
            )
        print(f"  params.json written to {params_path}")

        # Build cache: pre-tail epu_stats + topic EPU columns + UG count columns
        tail_ts = pd.Timestamp(daily_tail_start)
        cache_df = e_base.epu_stats[e_base.epu_stats["date"] < tail_ts].copy()

        # Add topic EPU columns
        for topic_key, e_topic in topic_epus.items():
            col = f"EPU_{topic_key}_index"
            topic_pre = e_topic.epu_stats[e_topic.epu_stats["date"] < tail_ts][
                ["date", "epu_weighted"]
            ].rename(columns={"epu_weighted": col})
            cache_df = cache_df.drop(columns=[col], errors="ignore")
            cache_df = cache_df.merge(topic_pre, on="date", how="left")

        # Add actor EPU columns
        for actor_key, e_actor in actor_epus.items():
            col = f"EPU_{actor_key}_index"
            actor_pre = e_actor.epu_stats[e_actor.epu_stats["date"] < tail_ts][
                ["date", "epu_weighted"]
            ].rename(columns={"epu_weighted": col})
            cache_df = cache_df.drop(columns=[col], errors="ignore")
            cache_df = cache_df.merge(actor_pre, on="date", how="left")

        # Add UG count columns from both topics and actors
        for source_file in ("topics", "actors"):
            ug_raw = ug_counts_all[source_file]
            if "date" not in ug_raw.columns:
                ug_raw = ug_raw.copy()
                ug_raw["date"] = pd.to_datetime(ug_raw["ym"], format="mixed")
            ug_pre = ug_raw[ug_raw["date"] < tail_ts].copy()
            ug_count_cols = [
                c for c in ug_pre.columns if "_UG_" in c and c.endswith("_count")
            ]
            if ug_count_cols:
                cache_df = pd.merge(
                    cache_df,
                    ug_pre[["date"] + ug_count_cols],
                    on="date",
                    how="left",
                )

        cache_df.to_csv(cache_path, index=False, encoding="utf-8")
        print(f"  epu_stats_cache.csv written ({len(cache_df)} rows)")


if __name__ == "__main__":
    cutoff = "2020-12-31"
    today = pd.Timestamp.today().strftime("%Y-%m-%d")
    subset_condition = f"date >= '2015-01-01' and date <= '{today}'"

    parser = argparse.ArgumentParser(description="EPU Analysis")
    parser.add_argument(
        "--country",
        type=str,
        default=None,
        help="Process a single country (e.g. thailand). Default: all countries.",
    )
    parser.add_argument(
        "--recalculate-params",
        action="store_true",
        default=False,
        help="Force recalculation of params.json even if it already exists.",
    )
    parser.add_argument(
        "--exclude-countries",
        type=str,
        default="",
        help="Comma-separated list of country names to exclude from processing.",
    )
    args = parser.parse_args()

    exclude_countries = set()
    if args.exclude_countries:
        exclude_countries = {
            name.strip().lower()
            for name in args.exclude_countries.split(",")
            if name.strip()
        }
        if exclude_countries:
            print(f"⏭️  Excluding countries: {', '.join(sorted(exclude_countries))}")

    country_dirs = _get_country_dirs(exclude_countries)

    if args.country:
        matched = [d for d in country_dirs if d.name == args.country]
        if not matched:
            available = [d.name for d in country_dirs]
            print(f"Error: country '{args.country}' not found.")
            print(f"Available countries: {', '.join(available)}")
            sys.exit(1)
        country_dirs = matched

    # Ensure all keyword translations are up to date before analysis
    print("\nChecking keyword translations...")
    asyncio.run(translate_keywords())

    total_countries = len(country_dirs)
    start_time = time.time()

    print(f"\n{'=' * 60}")
    print(f"EPU Analysis - Processing {total_countries} countries")
    print(f"{'=' * 60}\n")

    for i, country in enumerate(country_dirs):
        country_start = time.time()

        # Calculate ETA
        elapsed = time.time() - start_time
        if i > 0:
            avg_per_country = elapsed / i
            remaining = (total_countries - i) * avg_per_country
            eta_min = int(remaining // 60)
            eta_sec = int(remaining % 60)
            eta_str = f"ETA: {eta_min}m {eta_sec}s"
        else:
            eta_str = "ETA: calculating..."

        print(f"\n[{i + 1}/{total_countries}] {country.name} - {eta_str}")
        try:
            process_country(
                country,
                cutoff,
                subset_condition,
                recalculate_params=args.recalculate_params,
            )
            print("  ✓ EPU processing completed")
        except Exception as e:
            print(f"  ✗ EPU processing FAILED: {e}")
            print(f"    Skipping {country.name} due to error")
            continue

        country_elapsed = time.time() - country_start
        print(f"  Done in {country_elapsed:.1f}s")

    total_elapsed = time.time() - start_time
    print(f"\n{'=' * 60}")
    print(f"Completed in {total_elapsed / 60:.1f} minutes")
    print(f"{'=' * 60}")
