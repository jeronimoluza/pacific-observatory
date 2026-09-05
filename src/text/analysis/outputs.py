"""Output writing and serialization for EPU analysis.

Provides incremental CSV append logic, output CSV building,
parameter collection, and JSON serialization helpers.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from src.text.analysis.baseline import baseline_mask
from src.text.analysis.indices import IndexCalculator
from src.text.analysis.utils import collapse_to_index_grid, load_all_groups


def json_default(x):
    """JSON serialization helper: convert NaN to None."""
    if isinstance(x, float) and np.isnan(x):
        return None
    return x


def build_continuous_index_df(
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


def append_missing_months(
    path: Path,
    new_df: pd.DataFrame,
    n_months: int = 2,
    daily_tail_start: str | None = None,
    replace_from: str | None = None,
) -> None:
    """Append rows for periods not yet present in an existing CSV.

    For the current month (daily tail), compares by exact date.
    For past months, compares by calendar month period.
    If the file does not exist, writes new_df in full.
    """
    today = pd.Timestamp.today()

    if not path.exists():
        new_df.to_csv(path, index=False, encoding="utf-8")
        return

    existing = pd.read_csv(path, encoding="utf-8")

    existing_cols = list(existing.columns)
    new_cols = list(new_df.columns)
    merged_cols = existing_cols + [c for c in new_cols if c not in existing_cols]
    schema_changed = merged_cols != existing_cols
    added_cols = [c for c in new_cols if c not in existing_cols]

    existing["date"] = pd.to_datetime(existing["date"])
    new_df = new_df.copy()
    new_df["date"] = pd.to_datetime(new_df["date"])

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

    if replace_from is not None:
        replace_ts = pd.Timestamp(replace_from)
        existing = existing[existing["date"] < replace_ts]
        replacement_rows = new_df[new_df["date"] >= replace_ts]
        if not replacement_rows.empty:
            rows_to_add_list.append(replacement_rows)
    elif daily_tail_start is not None:
        tail_ts = pd.Timestamp(daily_tail_start)
        existing = existing[existing["date"] < tail_ts]
        new_daily = new_df[new_df["date"] >= tail_ts]
        if not new_daily.empty:
            rows_to_add_list.append(new_daily)

    # ── Past months: compare by calendar month period ────────────────
    if replace_from is not None:
        existing_past = existing
        missing_months = set()
    elif daily_tail_start is not None:
        target_months = {
            (today - pd.DateOffset(months=i)).to_period("M")
            for i in range(1, n_months + 1)
        }
        existing_past = existing[existing["date"] < pd.Timestamp(daily_tail_start)]
        existing_months = set(existing_past["date"].dt.to_period("M"))
        missing_months = target_months - existing_months
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
            existing.to_csv(path, index=False, encoding="utf-8")
        return

    rows_to_add = pd.concat(rows_to_add_list)
    combined = (
        pd.concat([existing, rows_to_add]).sort_values("date").reset_index(drop=True)
    )
    combined.to_csv(path, index=False, encoding="utf-8")


def collect_params(
    country_name: str,
    cutoff_start_date: str | None,
    cutoff_end_date: str | None,
    e_base,
    topic_epus: dict,
    actor_epus: dict,
    calc_topics,
    calc_actors,
    all_news_dfs: list,
) -> dict:
    """Collect all standardization parameters into a single dict for params.json."""
    n_pre = sum(
        (
            df[baseline_mask(df["date"], cutoff_start_date, cutoff_end_date)].shape[0]
            if "date" in df.columns
            else 0
        )
        for df in all_news_dfs
    )

    sources = [col.replace("_body_count", "") for col in e_base.news_cols]

    pre_cutoff_stats = e_base.epu_stats[
        baseline_mask(e_base.epu_stats["date"], cutoff_start_date, cutoff_end_date)
    ]
    source_weights = {}
    for src in sources:
        w_col = f"{src}_weights"
        if w_col in pre_cutoff_stats.columns:
            source_weights[src] = float(pre_cutoff_stats[w_col].mean())

    extended_params_raw = e_base._extended_calc.get_params()

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

    def _attr_params(calc_idx):
        raw = calc_idx.get_params()
        return {
            "ratio_stds": raw["ratio_stds"],
            "scaling_factors": raw["scaling_factors"],
        }

    return {
        "cutoff_start_date": cutoff_start_date,
        "cutoff_end_date": cutoff_end_date,
        "n_articles_in_baseline": int(n_pre),
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


def build_outputs(
    e_base,
    topic_epus,
    actor_epus,
    ug_counts_all,
    cutoff_start_date,
    cutoff_end_date,
    daily_tail_start,
    country_name,
    full_write=False,
    replace_from: str | None = None,
    output_dir: Path = None,
):
    """Build and write all output CSVs.

    Returns (calc_topics_idx, calc_actors_idx) IndexCalculator instances.
    """
    base_out = output_dir
    epu_folder = base_out / "epu"
    epu_folder.mkdir(parents=True, exist_ok=True)

    def _write_csv(path, df):
        if full_write:
            path.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(path, index=False, encoding="utf-8")
        else:
            append_missing_months(
                path,
                df,
                daily_tail_start=daily_tail_start,
                replace_from=replace_from,
            )

    # ── epu.csv ──────────────────────────────────────────────────────
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
    _write_csv(epu_folder / "epu.csv", result)

    # ── topics_epu.csv ───────────────────────────────────────────────
    topic_epu = e_base.epu_stats[["date", "ym"]].copy()
    for topic_key, e_topic in topic_epus.items():
        aligned = pd.merge(
            topic_epu[["date"]],
            e_topic.epu_stats[["date", "epu_weighted"]].rename(
                columns={"epu_weighted": f"EPU_{topic_key}_index"}
            ),
            on="date",
            how="left",
        )
        topic_epu[f"EPU_{topic_key}_index"] = aligned[f"EPU_{topic_key}_index"].values
    _write_csv(epu_folder / "topics_epu.csv", topic_epu)

    # ── actors_epu.csv ───────────────────────────────────────────────
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
    _write_csv(epu_folder / "actors_epu.csv", actor_epu)

    # ── uncertainty_attribution ───────────────────────────────────────
    sources = [col.replace("_body_count", "") for col in e_base.news_cols]
    calc_topics_idx = IndexCalculator(cutoff_start_date, cutoff_end_date)
    calc_actors_idx = IndexCalculator(cutoff_start_date, cutoff_end_date)

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
        dates_df = build_continuous_index_df(
            e_base.min_date, e_base.max_date, daily_tail_start
        )
        ug_counts = collapse_to_index_grid(ug_counts, daily_tail_start)
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
        attr_df = calc.calculate_topic_intensity_attribution(
            attr_df, sources, group_names
        )

        # Both scales ship. The `*_weighted` columns are normalized to mean 100
        # over the cutoff window, which is what makes series comparable across
        # units; the `*_z_weighted` columns are the standard deviations that
        # normalization was applied to, and are the honest scale when the
        # question is "how unusual is this month" rather than "how does this
        # unit compare to that one".
        out_cols = ["date", "ym"]
        for g in group_names:
            for stem, label in (
                (f"UG_{g}_abs", f"{g}_absolute"),
                (f"UG_{g}_frm", f"{g}_framing"),
                (f"G_{g}_int", f"{g}_intensity"),
            ):
                for src_col, out_col in (
                    (f"{stem}_weighted", label),
                    (f"{stem}_z_weighted", f"{label}_z"),
                ):
                    if src_col in attr_df.columns:
                        attr_df = attr_df.rename(columns={src_col: out_col})
                        out_cols.append(out_col)

        attr_out = attr_df[[c for c in out_cols if c in attr_df.columns]]
        attr_folder = base_out / "uncertainty_attribution"
        attr_folder.mkdir(parents=True, exist_ok=True)
        _write_csv(attr_folder / f"{output_name}.csv", attr_out)

    return calc_topics_idx, calc_actors_idx
