"""``prices train-classifier [--division D] [--bless]``.

Trains the next (embedding -> head) classifier version end-to-end (dataset ->
fit -> cross-validated eval) and prints the config-E scorecard. ``--bless``
promotes the ``latest`` pointer only when precision does not regress against the
current latest.
"""

from __future__ import annotations

import json

import click

from prices.enrich import config
from prices.enrich.classifier import (
    EVAL_METRICS_FILE,
    next_version,
    read_latest,
    version_dir,
    write_latest,
)
from prices.enrich.classifier import train
from prices.enrich.eval import head_eval

REGRESS_EPS = 0.02


def _latest_precision() -> float | None:
    latest = read_latest()
    if latest is None:
        return None
    path = version_dir(latest) / EVAL_METRICS_FILE
    if not path.exists():
        return None
    return json.loads(path.read_text()).get("precision")


@click.command("train-classifier")
@click.option(
    "--scope",
    default=None,
    help="Rows to train on: 'all' (default — every COICOP division), 'food', "
    "'nonfood', or a single division code. Restricting the scope COSTS coverage.",
)
@click.option(
    "--bless",
    is_flag=True,
    help="Promote `latest` if precision is non-regressing.",
)
def train_classifier_command(scope, bless):
    """Train classifier vN+1, cross-validate against gold, optionally bless."""
    scope = scope or config.CLASSIFIER_DEFAULT_SCOPE
    version = next_version()
    click.echo(f"training {version} (scope={scope}) ...")

    tr = train.fit(version, scope=scope)
    click.echo(
        f"  fit: {tr['n_train']} rows, {tr['n_classes']} classes, "
        f"head accuracy {tr['head_accuracy']:.1%}, tau={tr['tau']} "
        f"(raw tau {tr['tau_raw']}), {tr['n_iter']} iters "
        f"(converged={tr['converged']}), oof={tr['oof_secs']}s fit={tr['fit_secs']}s"
    )
    metrics = head_eval.run(scope=scope)
    (version_dir(version) / EVAL_METRICS_FILE).write_text(
        json.dumps({k: v for k, v in metrics.items() if k != "per_leaf"}, indent=2),
        encoding="utf-8",
    )

    if not bless:
        click.echo(f"(not blessed — `latest` still {read_latest() or 'unset'})")
        return

    prev = _latest_precision()
    if prev is not None and metrics["precision"] < prev - REGRESS_EPS:
        click.echo(
            f"\nNOT blessing — precision regressed {prev} -> {metrics['precision']}"
        )
        raise SystemExit(1)
    write_latest(version)
    click.echo(f"\nblessed: latest -> {version}")
