import click

from prices.enrich import config
from prices.enrich.stages import concatenate as concatenate_stage
from prices.enrich.stages import enrich as enrich_stage
from prices.enrich.stages import merge as merge_stage
from prices.enrich.stages import prepare as prepare_stage
from prices.enrich.stages import taxonomy as taxonomy_stage

STAGES = {
    "concatenate": concatenate_stage.run,
    "prepare": prepare_stage.run,
    "taxonomy": taxonomy_stage.run,
    "enrich": enrich_stage.run,
    "merge": merge_stage.run,
}


def _invalidate_for(stage: str | None) -> None:
    if stage == "concatenate" and concatenate_stage.STATE_FILE.exists():
        concatenate_stage.STATE_FILE.unlink()
    if stage == "prepare" and config.PRODUCTS_INPUT_PARQUET.exists():
        config.PRODUCTS_INPUT_PARQUET.unlink()
    if stage == "taxonomy" and config.COICOP_SUBCATS_JSON.exists():
        config.COICOP_SUBCATS_JSON.unlink()
    if stage == "enrich":
        for p in (config.ENRICHMENTS_PARQUET, config.FAILED_PARQUET):
            if p.exists():
                p.unlink()


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
    help="Ignore caches for the chosen stage (DANGEROUS on enrich — full 430k pass).",
)
@click.option("-r", "--region", "region", default=None, hidden=True)
@click.option("-S", "--subregion", "subregion", default=None, hidden=True)
@click.option("-c", "--country", "country", default=None, hidden=True)
def process_command(stage, rebuild, region, subregion, country):
    """AI enrichment pipeline (concatenate → prepare → taxonomy → enrich → merge)."""
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
        for name in ["concatenate", "prepare", "taxonomy", "enrich", "merge"]:
            click.echo(f"\n=== {name} ===")
            STAGES[name]()
