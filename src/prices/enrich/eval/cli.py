import click

from prices.enrich import config
from prices.enrich.eval import head_eval


@click.command(name="eval")
@click.option(
    "--division",
    default=config.CLASSIFIER_DEFAULT_DIVISION,
    help="COICOP division to score (default 01 — food & non-alcoholic beverages).",
)
@click.option(
    "--target-precision",
    type=float,
    default=head_eval.TARGET_PRECISION,
    help="Precision the global gate targets when deriving tau (default 0.98).",
)
def eval_command(division, target_precision):
    """Score the (embedding -> head) classifier against gold via cross-validation.

    Reports the config-E operating point — global confidence gate at the target
    precision plus per-leaf trap vetoes — as overall precision and coverage plus
    a per-leaf breakdown, using out-of-fold predictions on the gold food/bev
    leaves.
    """
    head_eval.run(division=division, target_precision=target_precision)
