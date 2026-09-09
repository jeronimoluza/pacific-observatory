"""`prices rtcal` -- validate, run, report."""

from __future__ import annotations

import json
import pickle
from pathlib import Path

import click
import pandas as pd

from . import config, folds as folds_mod, frames, prune as prune_mod, report as report_mod, validate as validate_mod


@click.group("rtcal")
def rtcal():
    """RT-CAL v1 selective price imputation.

    Runs between `prices build` and `prices publish`: it reads the cell matrix
    build writes, predicts missing cells, and releases only the subset whose
    gate clears a cross-validated correctness threshold.
    """


@rtcal.command("validate")
@click.option("--summary", type=click.Path(path_type=Path), default=None, help="Override the unit-value summary parquet.")
@click.option("--promote/--no-promote", default=False, help="Overwrite selected_release_thresholds.csv with this run's estimates.")
@click.option("--scheme", "schemes", multiple=True, help="Restrict to named fold families. Repeatable.")
def validate_cmd(summary, promote, schemes):
    """Re-estimate release thresholds by cross-validation.

    Must be re-run whenever the cell matrix changes -- new labels mean a new
    matrix, and a threshold solved against a different matrix belongs to a
    different model.
    """
    observed, unmatched = frames.prepare_observed(summary)
    kept, _, pruning = prune_mod.prune(observed)
    click.echo(f"observed {pruning['input_rows']:,} -> train {pruning['pruned_rows']:,} "
               f"(flagged {pruning['flagged_rows']:,}, {pruning['flagged_share']*100:.2f}%)")
    if unmatched:
        click.echo(f"WARNING unmatched country context: {unmatched}")

    df = folds_mod.add_folds(kept).reset_index(drop=True)
    scored, thresholds, thin = validate_mod.run_validation(df, schemes=schemes or None)

    outdir = config.VALIDATION_DIR
    outdir.mkdir(parents=True, exist_ok=True)
    # Keep the absdiff_* columns. They ARE gate features, so dropping them to
    # save disk makes the saved frame unable to refit or re-score a gate --
    # which turns a cheap re-fit into a full re-run of the sweep.
    scored.to_parquet(outdir / "gate_predictions.parquet", index=False)
    thresholds.to_csv(outdir / "threshold_metrics.csv", index=False)
    thin.to_csv(outdir / "thinness_report.csv", index=False)
    (outdir / "pruning_summary.json").write_text(json.dumps(pruning, indent=2))

    config.MODEL_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    gates = validate_mod.fit_production_gates(scored)
    with open(config.MODEL_ARTIFACTS_DIR / "gates.pkl", "wb") as fh:
        pickle.dump(gates, fh)
    click.echo(f"saved {len(gates)} production gates")

    click.echo(report_mod.threshold_table(thresholds))
    drift = report_mod.drift_checks(thresholds, pruning, previous=_previous_thresholds())
    click.echo(report_mod.drift_table(drift))

    if promote:
        config.RTCAL_DIR.mkdir(parents=True, exist_ok=True)
        if any(d["blocks_promotion"] for d in drift):
            raise click.ClickException("drift checks block promotion; re-run with --no-promote and review")
        thresholds.to_csv(config.RELEASE_THRESHOLDS_CSV, index=False)
        click.echo(f"promoted thresholds -> {config.RELEASE_THRESHOLDS_CSV}")
    else:
        click.echo("not promoted (pass --promote to overwrite the release policy)")


def _previous_thresholds():
    """Whatever policy is currently in force, for the threshold-drift check."""
    for path in (config.RELEASE_THRESHOLDS_CSV, config.RELEASE_THRESHOLDS_SEED):
        try:
            return pd.read_csv(path)
        except Exception:
            continue
    return None


@rtcal.command("run")
@click.option("--summary", type=click.Path(path_type=Path), default=None, help="Override the unit-value summary parquet.")
@click.option("--label-batch", default="unknown", help="Label snapshot id recorded on every output row.")
def run_cmd(summary, label_batch):
    """Score every missing cell and write the released fills."""
    from . import run as run_mod

    if not (config.MODEL_ARTIFACTS_DIR / "gates.pkl").exists():
        raise click.ClickException("no fitted gates; run `prices rtcal validate` first")
    out, summary_dict = run_mod.run(summary_path=summary, label_batch_version=label_batch)
    click.echo(report_mod.run_report(out, summary_dict, write=True))


@rtcal.command("report")
def report_cmd():
    """Re-render the run report from the last run's outputs."""
    if not config.SCORED_TARGETS_PARQUET.exists():
        raise click.ClickException("no scored targets; run `prices rtcal run` first")
    out = pd.read_parquet(config.SCORED_TARGETS_PARQUET)
    summary_path = config.RTCAL_DIR / "rtcal_v1_run_summary.json"
    summary_dict = json.loads(summary_path.read_text()) if summary_path.exists() else {}
    click.echo(report_mod.run_report(out, summary_dict, write=True))
