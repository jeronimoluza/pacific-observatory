"""The global build: Stage B's per-country outputs as one dataset, plus RT-CAL.

Three steps, run in order:

* ``assemble`` stacks every country's ``observations.parquet`` into
  ``global_prices_observations.parquet`` and its trusted slice into
  ``global_prices_trusted_observations.parquet``. It adds ``country`` (Stage B
  keeps it in the folder name) and the four columns the old build's consumers
  read: ``qa_status``, ``trust_level``, ``confidence`` and ``mass_source``. It
  also writes the cell table RT-CAL reads, ``global_prices_unit_value_summary``.
* ``rtcal`` runs ``prices rtcal validate --promote`` then ``run`` against that
  cell table, with every RT-CAL path moved under ``<out>/rtcal``. The worktree's
  ``data/prices/build`` is a symlink to production, so RT-CAL's own defaults
  would overwrite the production gates, thresholds and fills.
* ``merge`` writes ``trusted_observations_rtcal.parquet``: the trusted rows,
  less those in cells RT-CAL pruned, plus one ``imputed`` row per released fill.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import click
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from prices.build.trust import K
from prices.enrich import config
from prices.enrich.stages import decisions_store

OBS = "global_prices_observations.parquet"
TRUSTED = "global_prices_trusted_observations.parquet"
SUMMARY = "global_prices_unit_value_summary.parquet"
RTCAL_OBS = "trusted_observations_rtcal.parquet"
MIN_CELL_N = 5
CELL_KEY = ["period", "coicop_code", "country", "standard_unit"]
CELL_COLS = ["month", "coicop_code", "country", "standard_unit", "trusted", "qa_level",
             "unit_value_local", "unit_value_usd", "confidence"]
BATCH_ROWS = 1_000_000

# The old build's vocabulary. `per_kg` is a price the shop already quotes per
# kg, so it is a measured unit value, not a typical-mass conversion.
MASS_SOURCE = {
    "extracted": "measured",
    "per_kg": "measured",
    "imputed_fit": "derived_typical",
    "imputed_mode": "derived_typical",
}


def _country_dirs(stage_b: Path) -> list[Path]:
    dirs = sorted(p.parent for p in stage_b.glob("*/observations.parquet"))
    if not dirs:
        raise click.ClickException(f"no Stage B outputs under {stage_b}")
    return dirs


def _classifier(country: str) -> pd.DataFrame:
    part = decisions_store.parts_root(config.CLASSIFIED_HIERLEX_PARQUET) / (
        decisions_store.part_name(country) + ".parquet"
    )
    c = pd.read_parquet(part, columns=["input_hash", "confidence", "trust_level"])
    return c.drop_duplicates("input_hash")


def _with_old_columns(obs: pd.DataFrame, country: str, classifier: pd.DataFrame) -> pd.DataFrame:
    obs = obs.assign(country=country)
    obs["qa_status"] = np.where(obs["trusted"], "trusted", obs["stage_b_status"])
    obs["mass_source"] = obs["size_source"].map(MASS_SOURCE)
    # William's rule on its own: |robust z| <= 5 on the log-MAD band. Null where
    # the band could not score the row.
    z = obs["uv_robust_z"]
    obs["log_mad_pass"] = z.abs().le(K).astype("boolean").mask(z.isna())
    # The old files hold naive UTC timestamps; consumers compare against those.
    obs["observation_date"] = obs["observation_date"].dt.tz_convert("UTC").dt.tz_localize(None)
    n = len(obs)
    obs = obs.merge(classifier, on="input_hash", how="left", validate="many_to_one")
    if len(obs) != n:
        raise RuntimeError(f"{country}: classifier join moved the row count")
    return obs


def _schema(first: Path) -> pa.Schema:
    s = pq.read_schema(first / "observations.parquet").remove_metadata()
    s = s.set(s.get_field_index("observation_date"), pa.field("observation_date", pa.timestamp("ns")))
    for name, typ in [
        ("country", pa.string()),
        ("qa_status", pa.string()),
        ("mass_source", pa.string()),
        ("log_mad_pass", pa.bool_()),
        ("confidence", pa.float64()),
        ("trust_level", pa.string()),
    ]:
        s = s.append(pa.field(name, typ))
    return s


def _log_mad(v: pd.Series) -> float:
    lv = np.log(v[v > 0])
    return float(np.median(np.abs(lv - np.median(lv)))) if len(lv) else np.nan


def _cells(obs: pd.DataFrame) -> pd.DataFrame:
    """One row per (month, leaf, country, unit): the grain RT-CAL fits on.

    Medians come from trusted rows only, as in the old build. The `n_A/B/C`
    and `n_official` columns split `n_trusted` by `qa_level`, so a reader can
    see how much of a cell rests on the tight band and how much on the loose
    one.
    """
    w = obs.dropna(subset=["month", "coicop_code", "standard_unit"]).rename(columns={"month": "period"})
    total = w.groupby(CELL_KEY).size().rename("n_total")
    t = w[w["trusted"]]
    g = t.groupby(CELL_KEY)
    agg = g.agg(
        n_trusted=("unit_value_local", "size"),
        median_unit_value_local=("unit_value_local", "median"),
        median_unit_value_usd=("unit_value_usd", "median"),
        confidence_median=("confidence", "median"),
    )
    agg["uv_log_mad"] = g["unit_value_local"].apply(_log_mad) if len(t) else np.nan
    levels = t.groupby(CELL_KEY + ["qa_level"]).size().unstack("qa_level")
    levels = levels.reindex(columns=["A", "B", "C", "official"]).add_prefix("n_")
    out = agg.join(levels).join(total, how="right").reset_index()
    for c in ["n_trusted", "n_A", "n_B", "n_C", "n_official"]:
        out[c] = out[c].fillna(0).astype("int64")
    out["cell_status"] = np.where(out["n_trusted"] >= MIN_CELL_N, "usable", "thin")
    return out


@click.group("global-build")
def cli():
    """Stage B outputs -> the global observation files, then RT-CAL."""


@cli.command("assemble")
@click.option("--stage-b", type=click.Path(path_type=Path), required=True)
@click.option("--out", type=click.Path(path_type=Path), required=True)
@click.option("--as-of", type=click.DateTime(["%Y-%m-%d"]), default=None,
              help="Drop rows dated after this day (default: today, UTC).")
def assemble(stage_b: Path, out: Path, as_of):
    dirs = _country_dirs(stage_b)
    # A row dated after the build is not an observation yet: a weekly board
    # dated by the END of its validity week (namboard_ehis_swz) made the
    # dashboards claim data through a day that had not happened. The next
    # build after that day picks the row up.
    as_of = pd.Timestamp(as_of or datetime.now(timezone.utc).date()).normalize()
    cutoff = as_of + pd.Timedelta(days=1)
    out.mkdir(parents=True, exist_ok=True)
    schema = _schema(dirs[0])
    w_all = pq.ParquetWriter(out / OBS, schema, compression="zstd")
    w_tr = pq.ParquetWriter(out / TRUSTED, schema, compression="zstd")
    cells, n_all, n_tr, expect_all, expect_tr = [], 0, 0, 0, 0
    future_all, future_tr = 0, 0
    try:
        for d in dirs:
            country, src = d.name, pq.ParquetFile(d / "observations.parquet")
            expect_all += src.metadata.num_rows
            expect_tr += pq.ParquetFile(d / "trusted_observations.parquet").metadata.num_rows
            classifier = _classifier(country)
            keep, c_all, c_tr = [], 0, 0
            # Streamed: a country is read BATCH_ROWS at a time and only the
            # cell columns are held until its cells are taken.
            for batch in src.iter_batches(batch_size=BATCH_ROWS):
                obs = _with_old_columns(batch.to_pandas(), country, classifier)
                future = obs["observation_date"].ge(cutoff).to_numpy()
                if future.any():
                    future_all += int(future.sum())
                    future_tr += int((future & obs["trusted"].to_numpy()).sum())
                    for source, n in obs.loc[future, "source"].value_counts().items():
                        click.echo(f"{country}: dropped {n:,} rows of {source} dated after {as_of.date()}")
                    obs = obs[~future]
                table = pa.Table.from_pandas(obs[schema.names], schema=schema, preserve_index=False)
                tr = table.filter(pa.array(obs["trusted"].to_numpy()))
                w_all.write_table(table)
                w_tr.write_table(tr)
                c_all, c_tr = c_all + table.num_rows, c_tr + tr.num_rows
                keep.append(obs[CELL_COLS])
                del obs, table, tr
            cells.append(_cells(pd.concat(keep, ignore_index=True)))
            n_all, n_tr = n_all + c_all, n_tr + c_tr
            click.echo(f"{country}: {c_all:,} rows, {c_tr:,} trusted")
    finally:
        w_all.close()
        w_tr.close()
    if (n_all + future_all, n_tr + future_tr) != (expect_all, expect_tr):
        raise click.ClickException(
            f"row counts moved: wrote {n_all:,}/{n_tr:,} + {future_all:,}/{future_tr:,} future, "
            f"Stage B has {expect_all:,}/{expect_tr:,}"
        )
    summary = pd.concat(cells, ignore_index=True)
    summary.to_parquet(out / SUMMARY, index=False)
    click.echo(
        f"{len(dirs)} countries; {n_all:,} rows, {n_tr:,} trusted; "
        f"{future_all:,} ({future_tr:,} trusted) dated after {as_of.date()} dropped; "
        f"{len(summary):,} cells, {int((summary['n_trusted'] > 0).sum()):,} with a trusted row"
    )


def _point_rtcal_at(out: Path):
    """Move every RT-CAL output path under `out`, and refuse to run otherwise."""
    from prices.rtcal import config as rc

    d = out / "rtcal"
    rc.BUILD_DIR = out
    rc.UNIT_VALUE_SUMMARY_PARQUET = out / SUMMARY
    rc.RTCAL_DIR = d
    rc.RELEASE_THRESHOLDS_CSV = d / "selected_release_thresholds.csv"
    rc.SCORED_TARGETS_PARQUET = d / "rtcal_v1_scored_targets.parquet"
    rc.RELEASED_FILLS_PARQUET = d / "rtcal_v1_released_fills.parquet"
    rc.REVIEW_QUEUE_PARQUET = d / "rtcal_v1_holdout_review_queue.parquet"
    rc.PRUNED_CELLS_PARQUET = d / "rtcal_v1_pruned_cells.parquet"
    rc.RUN_REPORT_MD = d / "rtcal_v1_run_report.md"
    rc.MODEL_ARTIFACTS_DIR = d / "rtcal_v1_model_artifacts"
    rc.VALIDATION_DIR = d / "validation"
    for name in dir(rc):
        v = getattr(rc, name)
        if isinstance(v, Path) and "/data/" in str(v.resolve()):
            raise click.ClickException(f"rtcal.{name} still points into data/: {v}")
    return rc


@cli.command("rtcal")
@click.option("--out", type=click.Path(path_type=Path), required=True)
def rtcal_cmd(out: Path):
    """Train, approve and run, with no human step.

    `validate` cross-validates the method's predictors, fits the release gates
    and solves the thresholds; this run's estimates are then promoted
    unconditionally. The drift checks are still evaluated, against the
    packaged seed, but they are recorded in `promotion.json` rather than
    blocking: a W40 build has no earlier promoted policy of its own to drift
    from. `cli.py` writes the promoted file through the same `to_csv` as
    `threshold_metrics.csv`, so the copy is what `--promote` would write.
    """
    rc = _point_rtcal_at(out)
    from prices.rtcal import report
    from prices.rtcal.cli import rtcal

    rtcal.main(["validate", "--no-promote"], standalone_mode=False)
    thresholds = pd.read_csv(rc.VALIDATION_DIR / "threshold_metrics.csv")
    pruning = json.loads((rc.VALIDATION_DIR / "pruning_summary.json").read_text())
    drift = report.drift_checks(thresholds, pruning, previous=pd.read_csv(rc.RELEASE_THRESHOLDS_SEED))
    shutil.copyfile(rc.VALIDATION_DIR / "threshold_metrics.csv", rc.RELEASE_THRESHOLDS_CSV)
    (rc.RTCAL_DIR / "promotion.json").write_text(
        json.dumps({"promoted": "automatic", "drift_checks": drift}, indent=2, default=str)
    )
    failed = [d["check"] for d in drift if not d["passed"]]
    click.echo(f"promoted automatically; drift checks failed: {failed or 'none'}")
    rtcal.main(["run", "--label-batch", out.name], standalone_mode=False)


def _fill_local(fills: pd.DataFrame, local: pd.Series) -> pd.DataFrame:
    """Each fill in its country's currency, at Stage B's rate for that month.

    `local` is the country's currency as its trusted rows carry it (Stage B
    reprices every row into one), and the rate is `stage_b_fx.month_rates`, the
    same monthly mean the observed rows were converted with. A month whose rate
    is missing or `fx_suspect` keeps USD only rather than an untrusted figure.
    """
    from prices.fx import attach as fx
    from prices.stage_b_fx import month_rates

    cur = fills["country"].map(local).map(fx.normalize_currency_safe)
    pm = pd.DataFrame({"currency": cur, "month": fills["period"]}).dropna()
    rates = month_rates(pm, "USD")
    key = pd.MultiIndex.from_arrays([cur, fills["period"]])
    rate = pd.Series(rates["fx_rate"].reindex(key).to_numpy(), index=fills.index, dtype=float)
    bad = pd.Series(rates["fx_suspect"].reindex(key).to_numpy(), index=fills.index)
    bad = bad.astype("boolean").fillna(True).astype(bool)
    usd = cur.eq("USD")
    rate[usd], bad[usd] = 1.0, False
    rate = rate.where(~bad & rate.gt(0))
    return pd.DataFrame(
        {"currency": cur.where(rate.notna()), "fx_rate": rate, "unit_value_local": fills["usd"] * rate}
    )


@cli.command("merge")
@click.option("--out", type=click.Path(path_type=Path), required=True)
def merge(out: Path):
    rc = _point_rtcal_at(out)
    from prices.rtcal.fills import CELL_KEY as FILL_KEY, load_pruned_cells, load_released_fills

    fills = load_released_fills(rc.RELEASED_FILLS_PARQUET)
    kind = pd.read_parquet(rc.RELEASED_FILLS_PARQUET, columns=FILL_KEY + ["missingness_type"])
    fills = fills.merge(kind.drop_duplicates(FILL_KEY), on=FILL_KEY, how="left", validate="one_to_one")
    pruned = load_pruned_cells(rc.PRUNED_CELLS_PARQUET)
    bad = set(map(tuple, pruned[FILL_KEY].astype(str).to_numpy()))

    src = pq.ParquetFile(out / TRUSTED)
    schema = src.schema_arrow
    for name, typ in [
        ("imputed", pa.bool_()),
        ("rtcal_prob_within_25pct", pa.float64()),
        ("rtcal_missingness_type", pa.string()),
    ]:
        schema = schema.append(pa.field(name, typ))
    n_in = n_drop = 0
    currencies = []
    with pq.ParquetWriter(out / RTCAL_OBS, schema, compression="zstd") as w:
        for batch in src.iter_batches(batch_size=BATCH_ROWS):
            df = batch.to_pandas()
            key = zip(df["country"], df["coicop_code"], df["standard_unit"], df["month"])
            keep = np.fromiter((k not in bad for k in key), bool, len(df))
            n_in, n_drop = n_in + len(df), n_drop + int((~keep).sum())
            currencies.append(df.groupby(["country", "currency"]).size())
            df = df[keep].assign(imputed=False, rtcal_prob_within_25pct=np.nan, rtcal_missingness_type=None)
            w.write_table(pa.Table.from_pandas(df, schema=schema, preserve_index=False))
        counts = pd.concat(currencies).groupby(level=[0, 1]).sum()
        local = counts.sort_values().groupby(level=0).tail(1).reset_index(level=1)["currency"]
        lc = _fill_local(fills, local)
        f = pd.DataFrame(
            {
                # One synthetic id per imputed series, never a product's hash.
                "input_hash": "rtcal_v1:" + fills["country"] + "|" + fills["coicop_code"]
                + "|" + fills["standard_unit"],
                "source": "rtcal_v1",
                "currency": lc["currency"],
                "currency_quoted": lc["currency"],
                "fx_rate": lc["fx_rate"],
                "unit_value_local": lc["unit_value_local"],
                "country": fills["country"],
                "coicop_code": fills["coicop_code"],
                "standard_unit": fills["standard_unit"],
                "month": fills["period"],
                "observation_date": pd.to_datetime(fills["period"] + "-01"),
                "unit_value_usd": fills["usd"],
                "qa_status": "imputed",
                "qa_level": "imputed",
                "trusted": False,
                "imputed": True,
                "rtcal_prob_within_25pct": fills["prob"],
                "rtcal_missingness_type": fills["missingness_type"],
            }
        ).reindex(columns=schema.names)
        w.write_table(pa.Table.from_pandas(f, schema=schema, preserve_index=False))
    n_out = pq.ParquetFile(out / RTCAL_OBS).metadata.num_rows
    if n_out != n_in - n_drop + len(fills):
        raise click.ClickException(f"rtcal file has {n_out:,} rows, expected {n_in - n_drop + len(fills):,}")
    click.echo(
        f"trusted {n_in:,} - {n_drop:,} in {len(pruned):,} pruned cells + {len(fills):,} fills = {n_out:,}"
    )
    no_fx = lc["fx_rate"].isna()
    click.echo(f"fills in local currency: {int((~no_fx).sum()):,}; USD only (no or suspect rate): {int(no_fx.sum()):,}")
    for country, n in fills.loc[no_fx, "country"].value_counts().head(10).items():
        click.echo(f"  {country}: {n:,} USD-only fills")


if __name__ == "__main__":
    cli()
