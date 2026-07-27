"""`prices label` — the gold-growth labeling workflow as a discoverable verb.

Stages of one labeling round:

    pass-a      independent first pass — GPT via `codex exec` (gpt-5.x)
    pass-b      independent second pass — Gemini (config.LLM_MODEL_ESCALATE)
    merge       align A/B per row -> gold_v5_merged.parquet + the non-agree
                disagreements worklist (package-native, see label_merge)
    gate1-build blind the disagreements into adjudication batches
    (adjudicate) a 3rd model family (Claude/opus) writes adjud_out_*.json —
                this is an out-of-band agent step, not a script
    gate1-verify recompute matches + validate the adjudications
    assemble    consensus + adjudications -> gold_v5_roundN_final.parquet
    consolidate union all gold_v5_* rounds -> gold_labels.parquet (training gold)

`merge` runs in-process; the model-driven / pandas stages shell out to the
`scripts/` implementations so their resumable CLIs stay the single source of
truth. `pull` (candidate selection) is not wired here — the candidate builders
(`build_gold_roundN_candidates.py`, `pull_label_candidates.py`) run ad-hoc.
"""

from __future__ import annotations

import os
import subprocess
import sys

import click

from prices.enrich import config, label_merge

SCRIPTS_DIR = config.REPO_ROOT / "scripts"


def _run_script(name: str, args: list[str]) -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(config.REPO_ROOT / "src"), env.get("PYTHONPATH", "")]
    )
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / name), *args],
        cwd=str(config.REPO_ROOT),
        env=env,
    )
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


@click.group(name="label")
def label_group():
    """Gold-growth labeling: dual-label (codex + gemini) → merge → gate-1
    adjudication (opus) → assemble a gold_v5 round."""


@label_group.command("pass-a")
@click.option("--batch", type=int, default=None, help="Only label this batch index.")
@click.option("--limit-rows", type=int, default=None, help="Smoke: first N rows.")
def pass_a_cmd(batch, limit_rows):
    """Pass A — GPT (codex exec) first labeling pass."""
    args = []
    if batch is not None:
        args += ["--batch", str(batch)]
    if limit_rows is not None:
        args += ["--limit-rows", str(limit_rows)]
    _run_script("gold_v5_label_pass_a.py", args)


@label_group.command("pass-b")
@click.option("--batch", type=int, default=None, help="Only label this batch index.")
@click.option("--limit-rows", type=int, default=None, help="Smoke: first N rows.")
@click.option("--model", default=None, help="Gemini model id (default escalate).")
def pass_b_cmd(batch, limit_rows, model):
    """Pass B — Gemini second labeling pass."""
    args = []
    if batch is not None:
        args += ["--batch", str(batch)]
    if limit_rows is not None:
        args += ["--limit-rows", str(limit_rows)]
    if model:
        args += ["--model", model]
    _run_script("gold_v5_label_pass_b.py", args)


@label_group.command("merge")
def merge_cmd():
    """Merge Pass A + Pass B → gold_v5_merged.parquet + disagreements worklist."""
    summary = label_merge.run()
    click.echo(
        f"merge: {summary['n_rows']} rows "
        f"({summary['n_agree']} agree, {summary['n_disagree']} to adjudicate)"
    )
    click.echo(f"  {summary['merged']}")
    click.echo(f"  {summary['disagreements']}")


@label_group.command("gate1-build")
@click.option("--batch-size", type=int, default=59, help="Rows per adjudication batch.")
@click.option("--tag", default="", help="Suffix for the batch/decode set.")
@click.option("--only-new", is_flag=True, help="Restrict to the newest rows.")
def gate1_build_cmd(batch_size, tag, only_new):
    """Blind the disagreements into gate-1 adjudication batches."""
    args = ["--batch-size", str(batch_size)]
    if tag:
        args += ["--tag", tag]
    if only_new:
        args += ["--only-new"]
    _run_script("build_gate1_adjudication_batches.py", args)


@label_group.command("gate1-verify")
def gate1_verify_cmd():
    """Verify the gate-1 adjudication outputs (coverage + valid codes)."""
    _run_script("verify_gate1_adjudications.py", [])


@label_group.command("assemble")
@click.option("--merged", default="gold_v5_merged.parquet", help="Merged parquet name.")
@click.option("--out", default="gold_v5_final.parquet", help="Output gold name.")
def assemble_cmd(merged, out):
    """Assemble consensus + adjudications → gold_v5_final.parquet."""
    _run_script("build_gold_v5_final.py", ["--merged", merged, "--out", out])


@label_group.command("consolidate")
def consolidate_cmd():
    """Union the gold_v5_* rounds → the canonical gold_labels.parquet (training gold)."""
    from prices.enrich.classifier import dataset

    summary = dataset.consolidate_gold()
    click.echo(f"consolidate: {summary['n_rows']} rows → {summary['out']}")
    click.echo(f"  sources: {', '.join(summary['sources'])}")
