"""Human-readable output: threshold tables, drift checks, the run report.

The drift checks are the reason this module is not just formatting. Every one of
them comes from FULL_DATASET_RUNBOOK.md and every one BLOCKS promotion rather
than warning. A method that quietly degrades between refreshes is worse than one
that fails loudly, because its output still looks like prices.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config


def _fmt(value, spec=".4f"):
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return "-"
    try:
        return format(value, spec)
    except (TypeError, ValueError):
        return str(value)


def threshold_table(thresholds: pd.DataFrame) -> str:
    if thresholds.empty:
        return "(no thresholds estimated)"
    lines = [
        "",
        f"{'role':<22} {'missingness':<32} {'thresh':>8} {'cover':>7} {'w25':>7} {'MAE':>7} {'MAPE':>7} {'n':>9}",
        "-" * 104,
    ]
    for _, row in thresholds.iterrows():
        lines.append(
            f"{row['implementation_role']:<22} {row['missingness_type']:<32} "
            f"{_fmt(row['gate_threshold'], '.4f'):>8} "
            f"{_fmt(row['validated_coverage'], '.4f'):>7} "
            f"{_fmt(row['validated_within_25pct'], '.4f'):>7} "
            f"{_fmt(row['validated_mae_log'], '.4f'):>7} "
            f"{_fmt(row['validated_mape_pct'], '.2f'):>7} "
            f"{int(row['validated_n_eval']):>9,}"
        )
    return "\n".join(lines)


def drift_checks(thresholds: pd.DataFrame, pruning: dict, previous: pd.DataFrame | None = None) -> list[dict]:
    """Every promotion block from the runbook, evaluated."""
    checks = []

    def add(name, ok, detail):
        checks.append({"check": name, "passed": bool(ok), "blocks_promotion": not ok, "detail": detail})

    share = pruning.get("flagged_share", 0.0)
    add(
        "pruned_share_within_limit",
        share <= config.DRIFT_MAX_PRUNED_SHARE,
        f"{share*100:.3f}% pruned (limit {config.DRIFT_MAX_PRUNED_SHARE*100:.1f}%)",
    )
    worst = pruning.get("worst_country_share", 0.0)
    over = pruning.get("countries_over_limit", [])
    add(
        "no_country_over_pruned",
        not over,
        f"worst country {worst*100:.2f}%; over limit: {over[:5] if over else 'none'}",
    )

    for missingness, floor, label in (
        ("country_month_gap", config.DRIFT_MIN_NORMAL_WITHIN25, "normal"),
        ("product_month_gap", config.DRIFT_MIN_NORMAL_WITHIN25, "normal"),
        ("future_or_latest_month_gap", config.DRIFT_MIN_FORWARD_WITHIN25, "forward"),
    ):
        hit = thresholds[
            (thresholds["missingness_type"] == missingness)
            & (thresholds["implementation_role"].str.endswith("_default"))
        ]
        if hit.empty:
            continue
        got = float(hit.iloc[0]["validated_within_25pct"])
        add(
            f"within25_floor_{missingness}",
            np.isfinite(got) and got >= floor,
            f"{label} gap achieved {got*100:.1f}% within 25% (floor {floor*100:.0f}%)",
        )

    normal = thresholds[thresholds["implementation_role"] == "normal_gap_default"]
    if not normal.empty and "gate_calibration_error" in normal:
        worst_cal = float(normal["gate_calibration_error"].max())
        add(
            "gate_calibration_within_limit",
            np.isfinite(worst_cal) and worst_cal <= config.DRIFT_MAX_CALIBRATION_ERROR,
            f"worst normal-gap calibration error {worst_cal*100:.2f}pp "
            f"(limit {config.DRIFT_MAX_CALIBRATION_ERROR*100:.0f}pp)",
        )

    if previous is not None and not previous.empty:
        merged = thresholds.merge(
            previous[["implementation_role", "missingness_type", "gate_threshold"]],
            on=["implementation_role", "missingness_type"],
            how="inner",
            suffixes=("", "_prev"),
        )
        if not merged.empty:
            move = (merged["gate_threshold"] - merged["gate_threshold_prev"]).abs()
            finite = move[np.isfinite(move)]
            worst_move = float(finite.max()) if len(finite) else 0.0
            add(
                "threshold_move_within_limit",
                worst_move <= config.DRIFT_MAX_THRESHOLD_MOVE,
                f"largest threshold move {worst_move:.4f} (limit {config.DRIFT_MAX_THRESHOLD_MOVE})",
            )
    return checks


def drift_table(checks: list[dict]) -> str:
    if not checks:
        return "\n(no drift checks evaluated)"
    lines = ["", "drift checks:"]
    for check in checks:
        mark = "PASS" if check["passed"] else "BLOCK"
        lines.append(f"  [{mark:>5}] {check['check']:<38} {check['detail']}")
    blocking = [c for c in checks if c["blocks_promotion"]]
    lines.append(f"  {len(blocking)} of {len(checks)} checks block promotion")
    return "\n".join(lines)


def run_report(out: pd.DataFrame, summary: dict, write: bool = False) -> str:
    lines = [
        f"# RT-CAL v1 run report",
        "",
        f"- run_id: `{summary.get('run_id', '?')}`",
        f"- scored targets: {len(out):,}",
        f"- released: {int((out['release_status'] == 'released').sum()):,}",
        "",
        "## Release status by missingness type",
        "",
        "| missingness | scored | released | coverage |",
        "| --- | ---: | ---: | ---: |",
    ]
    for missingness, block in out.groupby("missingness_type", sort=False):
        released = int((block["release_status"] == "released").sum())
        lines.append(
            f"| {missingness} | {len(block):,} | {released:,} | {released/len(block)*100:.1f}% |"
        )

    lines += ["", "## Released fills by thinness stratum", "",
              "| series_train_count | released | median calibrated p |", "| --- | ---: | ---: |"]
    released_only = out[out["release_status"] == "released"]
    for stratum, block in released_only.groupby("thinness_stratum", sort=False):
        lines.append(
            f"| {stratum} | {len(block):,} | {block['prob_within_25pct_calibrated'].median():.3f} |"
        )

    pruning = summary.get("pruning", {})
    if pruning:
        lines += [
            "",
            "## Pruning",
            "",
            f"- input {pruning.get('input_rows', 0):,}, flagged {pruning.get('flagged_rows', 0):,} "
            f"({pruning.get('flagged_share', 0)*100:.2f}%)",
            f"- reasons: {pruning.get('reason_counts', {})}",
        ]
    unmatched = summary.get("unmatched_countries") or []
    if unmatched:
        lines += ["", f"**{len(unmatched)} countries had no frozen context**: {unmatched[:10]}"]

    text = "\n".join(lines)
    if write:
        config.RTCAL_DIR.mkdir(parents=True, exist_ok=True)
        config.RUN_REPORT_MD.write_text(text)
    return text
