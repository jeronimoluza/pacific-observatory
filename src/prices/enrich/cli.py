import click

from prices.enrich import config
from prices.enrich.stages import classify as classify_stage
from prices.enrich.stages import concatenate as concatenate_stage
from prices.enrich.stages import merge as merge_stage
from prices.enrich.stages import prepare as prepare_stage

STAGES = {
    "concatenate": concatenate_stage.run,
    "prepare": prepare_stage.run,
    "classify": classify_stage.run,
    "merge": merge_stage.run,
}

STAGE_ORDER = ["concatenate", "prepare", "classify", "merge"]


def _invalidate_for(stage: str | None) -> None:
    if stage == "concatenate" and concatenate_stage.STATE_FILE.exists():
        concatenate_stage.STATE_FILE.unlink()
    if stage == "prepare" and config.PRODUCTS_INPUT_PARQUET.exists():
        config.PRODUCTS_INPUT_PARQUET.unlink()
    if stage == "classify" and config.CLASSIFIED_PARQUET.exists():
        config.CLASSIFIED_PARQUET.unlink()


@click.command(name="process")
@click.option(
    "--stage",
    type=click.Choice(list(STAGES.keys())),
    default=None,
    help="Run a single stage; omit to run all in order.",
)
@click.option(
    "--rebuild",
    is_flag=True,
    help="Ignore caches for the chosen stage (re-classifies every product).",
)
@click.option("-r", "--region", "region", default=None, hidden=True)
@click.option("-S", "--subregion", "subregion", default=None, hidden=True)
@click.option("-c", "--country", "country", default=None, hidden=True)
def process_command(stage, rebuild, region, subregion, country):
    """AI enrichment pipeline (concatenate → prepare → classify → merge).

    `classify` runs the two independent enrich jobs per product: deterministic
    structural regex extraction (pricing_basis / amount / count / promo flags)
    plus (embedding → head) COICOP classification — a Qwen3-Embedding of the raw
    name feeding a logistic-regression head, accepted only where the global
    confidence gate clears and no trap veto fires. Output is filtered to the
    configured COICOP division (default 01 — the EAP F&B PoC).
    """
    if any([region, subregion, country]):
        click.echo(
            "warning: -r/-S/-c are accepted but ignored by prices process (global pipeline).",
            err=True,
        )
    if rebuild:
        _invalidate_for(stage)
    if stage:
        STAGES[stage]()
    else:
        for name in STAGE_ORDER:
            click.echo(f"\n=== {name} ===")
            STAGES[name]()
