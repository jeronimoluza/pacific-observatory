import click

from prices.enrich.eval import runner


@click.command(name="eval")
@click.option(
    "--tier-c",
    is_flag=True,
    help="Invoke tier-c (Gemini) on residuals. Costs API calls; off by default.",
)
@click.option(
    "--no-write",
    is_flag=True,
    help="Print the scorecard without writing report.md/summary.json/misses.csv.",
)
@click.option(
    "--gold",
    "gold_path",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help="Override gold parquet path (default: data/prices/enrich/gold/gold_labels.parquet).",
)
def eval_command(tier_c, no_write, gold_path):
    """Score the enrichment cascade against the working gold set.

    Reports per-field accuracy, composed unit_value accuracy (1% tolerance),
    and attributes each miss to a causal bucket: A_coicop (wrong leaf),
    B_basis (wrong pricing_basis), C_magnitude (wrong unit_value). Writes to
    outputs/prices/reports/eval/. Tier-c is off unless --tier-c is passed.
    """
    runner.run(
        gold_path=gold_path,
        run_tier_c=tier_c,
        write=not no_write,
        print_report=True,
    )
