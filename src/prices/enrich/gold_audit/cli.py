"""``prices gold-audit {oof,neighbors,signals,experiment,score,export,ingest}``.

The stages run in that order and chain through the ``latest`` run pointer, so
after ``oof`` starts a run the rest can be invoked without repeating ``--run``.

Ordinary sequence:

    prices gold-audit oof                     # slow: one head per division
    prices gold-audit neighbors               # slow: kNN over the embed store
    prices gold-audit signals
    prices gold-audit experiment              # <- decide here whether to spend
    prices gold-audit score
    prices gold-audit export --subset both-disagree --n 0 --max-pairs 5
    # ... adjudicate the JSONL out of band ...
    prices gold-audit ingest verdicts.jsonl
"""

from __future__ import annotations

import json

import click

from prices.enrich.gold_audit import (
    adjudicate,
    codex_pass,
    experiment,
    neighbors,
    new_run_id,
    oof,
    resolve_run,
    score,
    signals,
    write_latest,
)


def _echo(payload: dict) -> None:
    click.echo(json.dumps(payload, indent=2, default=str))


_run_opt = click.option(
    "--run", "run_id", default=None, help="Audit run id (default: latest)."
)
_division_opt = click.option(
    "--division", default=None, help="Restrict to one COICOP division (default: all)."
)


@click.group("gold-audit")
def gold_audit_group():
    """Find likely-wrong gold labels without relabeling the whole corpus."""


@gold_audit_group.command("oof")
@_division_opt
@click.option("--run", "run_id", default=None, help="Reuse an existing run id.")
def oof_command(division, run_id):
    """Fit a throwaway head per division; persist out-of-fold predictions."""
    rid = run_id or new_run_id()
    result = oof.compute(rid, divisions=[division] if division else None)
    write_latest(rid)
    _echo(result)


@gold_audit_group.command("neighbors")
@_run_opt
@_division_opt
@click.option(
    "-k", default=neighbors.DEFAULT_K, show_default=True, help="Neighbours per row."
)
def neighbors_command(run_id, division, k):
    """Compute local embedding-neighbourhood agreement for every gold row."""
    rid = resolve_run(run_id)
    _echo(neighbors.compute(rid, k=k, divisions=[division] if division else None))


@gold_audit_group.command("signals")
@_run_opt
def signals_command(run_id):
    """Join OOF, neighbourhood, provenance and duplicate signals."""
    _echo(signals.build(resolve_run(run_id)))


@gold_audit_group.command("experiment")
@_run_opt
@click.option(
    "--json", "as_json", is_flag=True, help="Emit raw JSON instead of the table."
)
def experiment_command(run_id, as_json):
    """Test whether neighbourhood disagreement predicts out-of-fold error."""
    result = experiment.run(resolve_run(run_id))
    _echo(result) if as_json else click.echo(experiment.format_report(result))


@gold_audit_group.command("score")
@_run_opt
def score_command(run_id):
    """Rank every gold row by suspicion score."""
    _echo(score.rank(resolve_run(run_id)))


@gold_audit_group.command("export")
@_run_opt
@_division_opt
@click.option(
    "--n", default=1000, show_default=True, help="Suspect cap; 0 means no limit."
)
@click.option(
    "--subset",
    type=click.Choice(sorted(score.SUBSETS)),
    default=None,
    help="Which suspects to draw from (default: any-signal).",
)
@click.option(
    "--max-pairs",
    type=int,
    default=None,
    help="Keep only the N largest dispute pairs — how a calibration slice is cut.",
)
@click.option(
    "--batch-size",
    default=adjudicate.DEFAULT_BATCH_SIZE,
    show_default=True,
    help="Real rows per JSONL batch file, before controls are seeded.",
)
def export_command(run_id, division, n, subset, max_pairs, batch_size):
    """Write blind, pair-grouped, control-seeded adjudication batches as JSONL."""
    _echo(
        adjudicate.export(
            resolve_run(run_id),
            n,
            division=division,
            subset=subset,
            batch_size=batch_size,
            max_pairs=max_pairs,
        )
    )


@gold_audit_group.command("codex")
@_run_opt
@click.option(
    "--only", type=int, default=None, help="Adjudicate a single batch index only."
)
@click.option("--model", default=codex_pass.MODEL, show_default=True)
def codex_command(run_id, only, model):
    """Run the codex CLI over the exported batches (skips ones already done)."""
    _echo(codex_pass.run(resolve_run(run_id), only=only, model=model))


@gold_audit_group.command("check")
@_run_opt
def check_command(run_id):
    """Score the planted controls. Writes nothing — read this before ingesting."""
    _echo(codex_pass.report(resolve_run(run_id)))


@gold_audit_group.command("collect")
@_run_opt
def collect_command(run_id):
    """Flatten the per-batch verdicts into one JSONL for ``ingest``."""
    click.echo(str(codex_pass.collect(resolve_run(run_id))))


@gold_audit_group.command("ingest")
@click.argument("verdicts", type=click.Path(exists=True, dir_okay=False))
@_run_opt
def ingest_command(verdicts, run_id):
    """Turn returned verdicts into a reviewable gold corrections CSV."""
    _echo(adjudicate.ingest(resolve_run(run_id), verdicts))
