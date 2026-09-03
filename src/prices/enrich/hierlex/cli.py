"""`prices hierlex` — verify, score and decide with a frozen HierLex bundle.

Three commands rather than one, because the expensive middle step is resumable
and the cheap outer ones are not worth re-running with it: `verify` is a seconds-
long integrity gate, `score` is the multi-hour full-corpus pass that lands
shards, and `decide` re-reads those shards under whichever acceptance policy is
being evaluated. Switching policy costs a `decide`, never a `score`.
"""

from __future__ import annotations

import json
from pathlib import Path

import click

from prices.enrich.hierlex import driver, package, scorer


@click.group("hierlex")
def hierlex_group() -> None:
    """Score the corpus with William Seitz's frozen HierLex-Select model."""


@hierlex_group.command("verify")
@click.option("--version", default=None, help="Bundle version (default: newest).")
def verify_cmd(version: str | None) -> None:
    """Check every frozen artifact against the bundle's own sha256 manifest."""
    installed = package.available()
    if not installed:
        raise click.ClickException(
            f"no bundle installed under {package.PACKAGE_ROOT}; unzip the "
            "implementation package into a directory there"
        )
    click.echo(f"installed: {', '.join(installed)}")
    pkg = package.resolve(version)
    meta = package.manifest(pkg)
    problems = package.verify(pkg)
    click.echo(f"bundle:    {pkg.name}")
    click.echo(f"version:   {meta['method_version']}")
    click.echo(
        f"classes:   {meta['classes']}  trained on {meta['training_rows']:,} rows"
    )
    click.echo(f"recipe:    {meta['embedding_recipe']}")
    for name, thr in sorted(meta["thresholds"]["thresholds"].items()):
        click.echo(f"  tau {name} = {thr:.6f}")
    if problems:
        raise click.ClickException("integrity FAILED:\n  " + "\n  ".join(problems))
    click.echo(f"integrity: OK ({len(meta['artifacts'])} artifacts)")


@hierlex_group.command("score")
@click.option("--version", default=None, help="Bundle version (default: newest).")
@click.option(
    "--chunk-rows",
    default=20_000,
    show_default=True,
    help="Pairs scored per forward pass.",
)
@click.option(
    "--max-buckets",
    default=None,
    type=int,
    help="Stop after N store buckets — an ETA probe that leaves resumable shards.",
)
@click.option(
    "--products",
    "products_path",
    default=None,
    type=click.Path(path_type=Path),
    help="Override products_input.parquet.",
)
def score_cmd(version, chunk_rows, max_buckets, products_path) -> None:
    """Score every (name, country) pair into resumable per-bucket shards."""
    summary = driver.run(
        version=version,
        chunk_rows=chunk_rows,
        max_buckets=max_buckets,
        products_path=products_path,
    )
    click.echo(json.dumps(summary, indent=2))


@hierlex_group.command("decide")
@click.option("--version", default=None, help="Bundle version (default: newest).")
@click.option(
    "--policy",
    default="conservative_risk",
    type=click.Choice(scorer.POLICIES),
    show_default=True,
    help="Acceptance threshold; conservative_risk is the package default.",
)
@click.option(
    "--out",
    "out_path",
    default=None,
    type=click.Path(path_type=Path),
    help="Override classified.parquet.",
)
@click.option(
    "--decisions",
    "full_out_path",
    default=None,
    type=click.Path(path_type=Path),
    help="Override decisions.parquet.",
)
@click.option(
    "--products",
    "in_path",
    default=None,
    type=click.Path(path_type=Path),
    help="Override products_input.parquet.",
)
def decide_cmd(version, policy, out_path, full_out_path, in_path) -> None:
    """Build the decisions table from existing shards under an acceptance policy."""
    from prices.enrich.hierlex import decide

    summary = decide.run(
        version=version,
        policy=policy,
        in_path=in_path,
        out_path=out_path,
        full_out_path=full_out_path,
    )
    click.echo(json.dumps(summary, indent=2))


@hierlex_group.command("report")
@click.option("--version", default=None, help="Bundle version (default: newest).")
@click.option(
    "--policy",
    default="conservative_risk",
    type=click.Choice(scorer.POLICIES),
    show_default=True,
)
def report_cmd(version, policy) -> None:
    """Acceptance rates over the scored shards, overall and by country."""
    import pandas as pd

    pkg = package.resolve(version)
    meta = package.manifest(pkg)
    tau = float(meta["thresholds"]["thresholds"][f"lexical_correctness_gate_{policy}"])
    df = driver.load_shards(meta["method_version"])
    df["ok"] = (df["calibrated_correctness_score"] >= tau) & df["is_leaf"]
    click.echo(f"{meta['method_version']}  policy={policy}  tau={tau:.6f}")
    click.echo(f"pairs scored : {len(df):,}")
    click.echo(f"accepted     : {int(df['ok'].sum()):,} ({df['ok'].mean():.2%})")
    click.echo(
        f"fallback     : {int(df['is_fallback'].sum()):,} ({df['is_fallback'].mean():.2%})"
    )
    by = (
        df.groupby("country")["ok"]
        .agg(["size", "mean"])
        .sort_values("size", ascending=False)
        .head(20)
    )
    click.echo("\ntop countries by volume:")
    with pd.option_context("display.float_format", "{:.2%}".format):
        click.echo(by.rename(columns={"size": "pairs", "mean": "accept"}).to_string())
