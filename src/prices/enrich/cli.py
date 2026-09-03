import shutil

import click

from prices import partition
from prices.enrich import config, prepare_shards
from prices.enrich.classifier import backends, batch_embed
from prices.enrich.stages import classify as classify_stage
from prices.enrich.stages import concatenate as concatenate_stage
from prices.enrich.stages import embed as embed_stage
from prices.enrich.stages import merge as merge_stage
from prices.enrich.stages import prepare as prepare_stage

STAGES = {
    "concatenate": concatenate_stage.run,
    "prepare": prepare_stage.run,
    "classify": classify_stage.run,
    "merge": merge_stage.run,
}

STAGE_ORDER = ["concatenate", "prepare", "classify", "merge"]

# Stages that understand a partition selector. classify and merge still read the
# whole corpus, so a scoped run says so rather than quietly ignoring the scope.
SCOPED_STAGES = ("concatenate", "prepare")


def _invalidate_for(stage: str | None, backend: str | None = None) -> None:
    if stage == "concatenate" and concatenate_stage.STATE_FILE.exists():
        concatenate_stage.STATE_FILE.unlink()
    if stage == "prepare" and config.PRODUCTS_INPUT_PARQUET.exists():
        config.PRODUCTS_INPUT_PARQUET.unlink()
    if stage == "classify":
        # Only the chosen backend's output. Dropping both would make --rebuild
        # on one model quietly destroy the other model's run.
        out = backends.get(backend).classified_path
        if out.exists():
            out.unlink()
        # Prediction shards cache head scores per name-bucket; a shard is reused
        # whenever its cached names cover the request, so a bucket untouched by a
        # new batch keeps scores from before a veto-lexicon change and silently
        # reverts the veto. Drop them on --rebuild: re-scoring reruns from the
        # banked embeddings (cheap), it does NOT re-embed.
        if batch_embed.PRED_DIR.exists():
            shutil.rmtree(batch_embed.PRED_DIR)


def _selectors(only, region, subregion, country) -> list[str] | None:
    """Everything the user asked to scope to, as one list of selectors."""
    out = list(only or [])
    from_flags = partition.selector_from_flags(region, subregion, country)
    if from_flags:
        out.append(from_flags)
    return out or None


def _explain(selectors) -> None:
    """What a run would touch, before it starts. Without this the reflex on any
    doubt is --rebuild, which throws away the cache the scoping exists to keep."""
    selected = partition.select(selectors, concatenate_stage.PER_SOURCE_DIR)
    if not selected:
        click.echo(f"no shards match {selectors or 'the whole corpus'}")
        return
    countries = partition.group_by(selected, "country")
    click.echo(f"{len(selected)} shards in {len(countries)} countries")
    for key, group in sorted(countries.items()):
        size = sum(s.size for s in group) / 1e6
        click.echo(f"  {'/'.join(key):<48} {len(group):>4} shards  {size:8.1f} MB")


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
@click.option(
    "--only",
    multiple=True,
    metavar="SELECTOR",
    help=(
        "Restrict to part of the corpus. A selector is a glob over "
        "region/subregion/country/source, so 'ssa', 'ssa/southern/ghana' and "
        "'**/agmarknet' are all valid. Repeatable."
    ),
)
@click.option(
    "--workers",
    type=int,
    default=1,
    show_default=True,
    help="Parallel workers for the stages that shard.",
)
@click.option(
    "--explain",
    is_flag=True,
    help="Print what the selector matches and exit without running anything.",
)
@click.option(
    "--backend",
    type=click.Choice(sorted(backends.BACKENDS)),
    default=None,
    help=(
        "Which model classify scores with. Default comes from "
        "PRICES_CLASSIFIER_BACKEND (currently "
        f"{config.CLASSIFIER_BACKEND!r}). Each writes its own output file."
    ),
)
@click.option("-r", "--region", "region", default=None)
@click.option("-S", "--subregion", "subregion", default=None)
@click.option("-c", "--country", "country", default=None)
def process_command(
    stage, rebuild, only, workers, explain, backend, region, subregion, country
):
    """AI enrichment pipeline (concatenate → prepare → classify → merge).

    `classify` runs the two independent enrich jobs per product: deterministic
    structural regex extraction (pricing_basis / amount / count / promo flags)
    plus COICOP classification by the chosen backend. It is predict-only —
    nothing here fits a model. `hierlex` (default) scores a frozen bundle at
    (name, country) grain into classified_hierlex.parquet; `head` scores the
    in-house trained model at name grain into classified.parquet.
    """
    selectors = _selectors(only, region, subregion, country)
    if explain:
        _explain(selectors)
        return
    if selectors:
        unscoped = [
            name
            for name in ([stage] if stage else STAGE_ORDER)
            if name not in SCOPED_STAGES
        ]
        if unscoped:
            click.echo(
                f"warning: {', '.join(unscoped)} read the whole corpus; "
                "the selector applies to " + ", ".join(SCOPED_STAGES),
                err=True,
            )
    if rebuild:
        _invalidate_for(stage, backend)

    def run_stage(name: str) -> None:
        if name == "concatenate":
            concatenate_stage.run(force=rebuild, selectors=selectors)
        elif name == "prepare":
            prepare_shards.run(selectors=selectors, workers=workers)
        elif name == "classify":
            classify_stage.run(backend=backend, workers=workers)
        else:
            STAGES[name]()

    if stage:
        run_stage(stage)
    else:
        for name in STAGE_ORDER:
            click.echo(f"\n=== {name} ===")
            run_stage(name)


@click.command(name="embed")
@click.option(
    "--backend",
    type=click.Choice(["local", "runpod"]),
    default="local",
    show_default=True,
    help="local encodes here; runpod stages a fleet run and prints how to start it.",
)
@click.option(
    "--only",
    multiple=True,
    metavar="SELECTOR",
    help="Embed only the names under part of the corpus. Repeatable.",
)
@click.option(
    "--pods",
    type=int,
    default=1,
    show_default=True,
    help="runpod only: how many pods to partition the universe across.",
)
@click.option("-r", "--region", "region", default=None)
@click.option("-S", "--subregion", "subregion", default=None)
@click.option("-c", "--country", "country", default=None)
def embed_command(backend, only, pods, region, subregion, country):
    """Put a vector in the embed store for every name that lacks one.

    Classify reads the store and never fills it, so this is the step that costs
    real time and, on runpod, real money. `--backend runpod` writes the universe
    and the per-pod plan and then stops: renting GPUs stays a decision a person
    makes.
    """
    embed_stage.run(
        backend=backend,
        selectors=_selectors(only, region, subregion, country),
        pods=pods,
    )
