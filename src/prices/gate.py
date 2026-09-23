"""Per-source quality gates: hard floors, a verdict per source, and a status view.

The operating model (vault spec `2026-09-23-prices-ai-operating-model`) runs
every judgement stage one source at a time, and a source moves on only when its
gate passes. A gate is floors in code plus the agent's judgement above them;
this module is the floors half. It exits non-zero when any judged source fails,
because that exit code is what an agent session ends on.

**A failed gate blocks that source, never the run.** Every source is judged and
recorded before the exit code is decided.

**Floors are approved, not computed.** `floors` prints each metric's
distribution over healthy sources and proposes a cutoff near the 10th
percentile (90th for a share that should be low). A human approves the numbers
and they are pasted into `FLOORS`. Until then `run` refuses: a proposal that
gated anything would be a threshold nobody chose.

**One ledger, not four.** Every verdict is a `prices.lineage` event
(stage="gate"). The status table under `outputs/prices/` is a view rebuilt
from those events by `status`; delete it and nothing is lost.

What the extraction metrics read, and how stale each can be:

- `qty_coverage`, `dup_keys`, `n_rows`: the extraction table, as of the last
  extraction run that covered the source. A scoped run does not stamp the
  table's fingerprint, so the gate cannot tell whether a source's rows were
  extracted by the current code -- run extraction for the source first.
- `price_parse_rate`: concatenate's "missing product_name/price/currency/
  country" counter, from the newest lineage run that recorded one for the
  source. A source that never dropped a row has no counter and rates 1.0.
- `uv_flag_share`: the build's `qa_status` in {review_uv_outlier,
  review_uv_implausible}, over the source's build rows. Build is country-grain
  (`partition.STAGE_FLOOR["build"]`), so this moves only when the source's
  country is rebuilt; a scoped build of that country refreshes it exactly.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Sequence

import click
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from prices import lineage
from prices.partition import compile_selector, select

REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD_PARQUET = REPO_ROOT / "data" / "prices" / "build" / "global_prices_observations.parquet"
STATUS_PARQUET = REPO_ROOT / "outputs" / "prices" / "gate_status.parquet"

# Healthy, for the floor distributions (spec "Open", Q8): passes source-sanity
# Tier 1 and has at least this many extracted rows.
HEALTHY_MIN_ROWS = 1_000

MAX_ATTEMPTS = 3  # failed attempts before the one escalation (Q2)

UV_REVIEW = ("review_uv_outlier", "review_uv_implausible")

# metric -> "min" (value must be >= floor) or "max" (value must be <= floor).
DIRECTION = {
    "extraction": {
        "price_parse_rate": "min",
        "qty_coverage": "min",
        "dup_keys": "max",
        "uv_flag_share": "max",
    },
}

# Human-approved cutoffs. Empty until approved; `run` refuses without them.
FLOORS: dict[str, dict[str, float]] = {
    "extraction": {},
}


def code_fingerprint(stage: str) -> str:
    if stage == "extraction":
        from prices.enrich.stages import extraction

        return extraction.code_fingerprint()
    raise click.BadParameter(f"no gate for stage {stage!r}")


# ── extraction metrics ─────────────────────────────────────────────


def _source_keys() -> dict[tuple[str, str], str]:
    """(country, source) -> region/subregion/country/source, from the shard tree."""
    out = {}
    for shard in select(None):
        parts = shard.key.split("/")
        out[(parts[2], parts[3])] = shard.key
    return out


def _extraction_counts() -> pd.DataFrame:
    """n_rows, qty rows and duplicate (input_hash, country) rows per (country, source).

    One part per country, and the grain key contains country, so a duplicate
    can only sit inside one part: streaming part by part never misses one.
    """
    from prices.enrich import config
    from prices.enrich.stages import decisions_store
    from prices.enrich.stages.extraction import _QTY_BASES

    frames = []
    for part in sorted(decisions_store.parts_root(config.EXTRACTION_PARQUET).glob("*.parquet")):
        df = pq.read_table(
            part, columns=["input_hash", "country", "source", "pricing_basis"]
        ).to_pandas()
        df["qty"] = df["pricing_basis"].isin(_QTY_BASES)
        df["dup"] = df.duplicated(["input_hash", "country"], keep="first")
        frames.append(
            df.groupby(["country", "source"], dropna=False)
            .agg(n_rows=("qty", "size"), qty=("qty", "sum"), dup_keys=("dup", "sum"))
            .reset_index()
        )
    return pd.concat(frames, ignore_index=True)


def _price_drops() -> dict[str, tuple[int, int]]:
    """source key tail 'country/source' -> (n_in, n_dropped), newest run wins."""
    out: dict[str, tuple[int, int]] = {}
    if not lineage.LINEAGE_DIR.is_dir():
        return out
    for run in sorted(p for p in lineage.LINEAGE_DIR.iterdir() if p.is_dir()):
        for path in sorted(run.glob("counters-*.jsonl")):
            with path.open() as fh:
                for line in fh:
                    if "_finalise_shard" not in line:
                        continue
                    row = json.loads(line)
                    if row.get("site") == "concatenate.py:_finalise_shard" and row.get("n_in"):
                        out[row["scope"]] = (int(row["n_in"]), int(row["n_dropped"] or 0))
    return out


def _uv_shares() -> pd.DataFrame:
    t = pq.read_table(BUILD_PARQUET, columns=["country", "source", "qa_status"])
    flagged = pc.is_in(t["qa_status"], value_set=pa.array(UV_REVIEW))
    t = t.append_column("uv", flagged)
    g = t.group_by(["country", "source"]).aggregate([("uv", "sum"), ("uv", "count")])
    df = g.to_pandas().rename(columns={"uv_sum": "uv_rows", "uv_count": "build_rows"})
    df["uv_flag_share"] = df["uv_rows"] / df["build_rows"]
    return df


def extraction_metrics() -> pd.DataFrame:
    """One row per source: the four floor metrics plus n_rows and healthy."""
    from prices.source_sanity import judge

    df = _extraction_counts()
    keys = _source_keys()
    df["key"] = [
        keys.get((c, s), f"?/?/{c}/{s}") for c, s in zip(df["country"], df["source"])
    ]
    df["qty_coverage"] = df["qty"] / df["n_rows"]

    drops = _price_drops()
    rates = []
    for c, s in zip(df["country"], df["source"]):
        n_in, n_dropped = drops.get(f"{c}/{s}", (0, 0))
        rates.append(1.0 - n_dropped / n_in if n_in else 1.0)
    df["price_parse_rate"] = rates

    df = df.merge(_uv_shares()[["country", "source", "build_rows", "uv_flag_share"]],
                  on=["country", "source"], how="left")

    tier1 = {v.key for v in judge() if v.flagged}
    df["tier1_flagged"] = df["key"].isin(tier1)
    df["healthy"] = ~df["tier1_flagged"] & (df["n_rows"] >= HEALTHY_MIN_ROWS)
    return df.sort_values("key").reset_index(drop=True)


METRICS = {"extraction": extraction_metrics}


# ── verdicts ───────────────────────────────────────────────────────


def judge_row(stage: str, row: pd.Series) -> list[str]:
    """Names of the floors this source fails. A missing metric is not a failure:
    a source absent from the build has no uv share to judge yet."""
    failed = []
    for metric, floor in FLOORS[stage].items():
        value = row.get(metric)
        if value is None or pd.isna(value):
            continue
        if DIRECTION[stage][metric] == "min" and value < floor:
            failed.append(f"{metric}={value:.4g} < {floor}")
        elif DIRECTION[stage][metric] == "max" and value > floor:
            failed.append(f"{metric}={value:.4g} > {floor}")
    return failed


def read_verdicts() -> pd.DataFrame:
    """Every gate event ever recorded, oldest first."""
    rows = []
    if lineage.LINEAGE_DIR.is_dir():
        for path in sorted(lineage.LINEAGE_DIR.glob("*/counters-*.jsonl")):
            with path.open() as fh:
                for line in fh:
                    if '"stage": "gate"' not in line:
                        continue
                    rows.append(json.loads(line))
    if not rows:
        return pd.DataFrame(
            columns=["ts", "scope", "gate_stage", "verdict", "escalated", "code_fingerprint", "reason"]
        )
    return pd.DataFrame(rows).sort_values("ts", kind="stable").reset_index(drop=True)


def status_view(events: pd.DataFrame, fingerprints: dict[str, str]) -> pd.DataFrame:
    """Current state per (source, stage), folded from the verdict events.

    An episode runs until the source passes or parks. It reopens -- `pending`,
    attempts back to 0 -- when the stage's code fingerprint moves past the one
    the closing verdict was recorded under. That reopening is the fix for the
    CC `_PARKED_REASONS` defect: a parked source is retried once the code
    changes, not never.
    """
    out = []
    for (scope, stage), g in events.groupby(["scope", "gate_stage"], sort=True):
        status, attempts, escalated, reason, last, fp = "pending", 0, False, None, None, None
        for ev in g.itertuples(index=False):
            if status in ("passed", "parked") and ev.code_fingerprint != fp:
                status, attempts, escalated = "pending", 0, False
            if status in ("passed", "parked"):
                continue  # a re-run under the same code does not reopen it
            attempts += 1
            escalated = escalated or bool(ev.escalated)
            last, fp = ev.reason, ev.code_fingerprint
            if ev.verdict == "pass":
                status, reason = "passed", None
            elif escalated:
                status, reason = "parked", ev.reason
            else:
                reason = ev.reason
        if status in ("passed", "parked") and fp != fingerprints.get(stage):
            status, attempts, escalated = "pending", 0, False
        out.append(
            {
                "source": scope,
                "stage": stage,
                "status": status,
                "attempts": attempts,
                "escalated": escalated,
                "reason": reason,
                "last_gate_output": last,
                "code_fingerprint": fp,
            }
        )
    return pd.DataFrame(out)


def write_status() -> pd.DataFrame:
    events = read_verdicts()
    fps = {stage: code_fingerprint(stage) for stage in FLOORS}
    view = status_view(events, fps)
    STATUS_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    view.to_parquet(STATUS_PARQUET, index=False)
    return view


# ── CLI ────────────────────────────────────────────────────────────


@click.group("gate")
def gate_group() -> None:
    """Per-source quality gates (floors, verdicts, status)."""


@gate_group.command("floors")
@click.option("--stage", default="extraction", show_default=True)
@click.option("--out", type=click.Path(path_type=Path), default=None,
              help="Also write every source's metrics to this parquet.")
def floors_command(stage: str, out: Optional[Path]) -> None:
    """Print each metric's distribution over healthy sources and a proposed floor."""
    df = METRICS[stage]()
    healthy = df[df["healthy"]]
    click.echo(
        f"{len(df)} sources, {len(healthy)} healthy "
        f"(Tier 1 clean, >= {HEALTHY_MIN_ROWS:,} rows)"
    )
    click.echo(f"{'metric':18s} {'dir':4s} {'p05':>8s} {'p10':>8s} {'p25':>8s} "
               f"{'p50':>8s} {'p90':>8s} {'p95':>8s}  proposed  fail_all  fail_healthy")
    for metric, direction in DIRECTION[stage].items():
        vals = healthy[metric].dropna()
        q = vals.quantile([0.05, 0.10, 0.25, 0.50, 0.90, 0.95]).to_numpy()
        proposed = float(q[1] if direction == "min" else q[4])
        col_all, col_h = df[metric], healthy[metric]
        if direction == "min":
            f_all, f_h = int((col_all < proposed).sum()), int((col_h < proposed).sum())
        else:
            f_all, f_h = int((col_all > proposed).sum()), int((col_h > proposed).sum())
        click.echo(f"{metric:18s} {direction:4s} " + " ".join(f"{v:8.4f}" for v in q)
                   + f"  {proposed:8.4f}  {f_all:8d}  {f_h:12d}")
    if out:
        df.to_parquet(out, index=False)
        click.echo(f"wrote {out}")


@gate_group.command("run")
@click.option("--stage", default="extraction", show_default=True)
@click.option("--only", multiple=True, metavar="SELECTOR",
              help="Judge only sources matching this glob over region/subregion/country/source.")
@click.option("--escalated", is_flag=True,
              help="This attempt used the one escalation to a stronger model.")
def run_command(stage: str, only: tuple[str, ...], escalated: bool) -> None:
    """Judge sources against the approved floors; exit 1 if any fails."""
    if not FLOORS.get(stage):
        raise click.ClickException(
            f"no approved floors for {stage!r}; run `prices gate floors` and "
            f"have a human approve the cutoffs into gate.FLOORS"
        )
    df = METRICS[stage]()
    if only:
        patterns = [compile_selector(s) for s in only]
        df = df[[any(p.match(k) for p in patterns) for k in df["key"]]]
    if df.empty:
        raise click.ClickException("no source matched")
    fp = code_fingerprint(stage)
    results = []
    # Every verdict reaches the ledger before anything is printed, for the
    # reason source_sanity gives: a closed stdout must not cost a record.
    for _, row in df.iterrows():
        failed = judge_row(stage, row)
        verdict = "fail" if failed else "pass"
        reason = "; ".join(failed) if failed else "all floors met"
        metrics = {m: (None if pd.isna(row.get(m)) else float(row[m])) for m in DIRECTION[stage]}
        lineage.record(
            "gate",
            f"gate.{stage}",
            reason,
            scope=row["key"],
            gate_stage=stage,
            verdict=verdict,
            escalated=escalated,
            code_fingerprint=fp,
            metrics=metrics,
        )
        results.append((row["key"], verdict, reason))
    write_status()
    n_fail = sum(v == "fail" for _, v, _ in results)
    click.echo(f"{len(results)} sources judged, {n_fail} failed  (fingerprint {fp})")
    for key, verdict, reason in results:
        if verdict == "fail":
            click.echo(f"  FAIL {key:60s} {reason}")
    if n_fail:
        raise SystemExit(1)


@gate_group.command("status")
def status_command() -> None:
    """Rebuild the status table from the ledger and print its counts."""
    view = write_status()
    click.echo(f"wrote {STATUS_PARQUET}")
    if view.empty:
        click.echo("no gate verdicts recorded yet")
        return
    click.echo(view.groupby(["stage", "status"]).size().to_string())
    due = view[(view["status"] == "pending") & (view["attempts"] >= MAX_ATTEMPTS)
               & ~view["escalated"]]
    if len(due):
        click.echo(f"{len(due)} sources due their one escalation:")
        for key in due["source"]:
            click.echo(f"  {key}")
