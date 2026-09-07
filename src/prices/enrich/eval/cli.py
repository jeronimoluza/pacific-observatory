import click

from prices.enrich import config
from prices.enrich.eval import head_eval


@click.command(name="eval")
@click.option(
    "--scope",
    default=None,
    help="Rows to score: 'all' (default — every COICOP division), 'food' "
    "(division 01), 'nonfood', or a single division code like '05'. Scoping to "
    "one division COSTS coverage; the head scores ~4pt higher across all "
    "divisions because it can spend confidence where the taxonomy is easy.",
)
@click.option(
    "--target-precision",
    type=float,
    default=head_eval.TARGET_PRECISION,
    help="Precision the gate targets when deriving tau (default 0.98).",
)
@click.option(
    "--embed-preset",
    type=click.Choice(sorted(config.CLASSIFIER_EMBED_PRESETS)),
    default=None,
    help="Embedding preset to score (default: production gpu_bf16). "
    "Experimental presets let an alternative encoder be benchmarked on the "
    "same gold CV harness; it does NOT retrain the production bundle.",
)
def eval_command(scope, target_precision, embed_preset):
    """Score the (embedding -> head -> meta-gate) classifier against gold.

    Reports coverage at the target precision floor for BOTH gates — the head's
    raw softmax confidence and the meta-gate — plus a per-leaf breakdown, using
    out-of-fold predictions so no row is scored by a model that trained on it.

    The three OOF tables are cached per (block layout, weights, scope, row set);
    the first run at a new configuration takes about an hour, repeats are fast.
    """
    if embed_preset:
        config.CLASSIFIER_EMBED_ENSEMBLE = config.CLASSIFIER_EMBED_PRESETS[embed_preset]
        click.echo(f"embed preset: {embed_preset}")
    head_eval.run(scope=scope, target_precision=target_precision)
