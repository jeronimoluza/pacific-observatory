import click

from prices.enrich import config
from prices.enrich.stages import concatenate as concatenate_stage
from prices.enrich.stages import dedupe as dedupe_stage
from prices.enrich.stages import enrich as enrich_stage
from prices.enrich.stages import merge as merge_stage
from prices.enrich.stages import prepare as prepare_stage
from prices.enrich.stages import taxonomy as taxonomy_stage

STAGES = {
    "concatenate": concatenate_stage.run,
    "prepare": prepare_stage.run,
    "dedupe": dedupe_stage.run,
    "taxonomy": taxonomy_stage.run,
    "match": enrich_stage.run,
    "enrich": enrich_stage.run,  # deprecated alias — kept one release; remove in Phase 8
    "merge": merge_stage.run,
}


def _invalidate_for(stage: str | None) -> None:
    if stage == "concatenate" and concatenate_stage.STATE_FILE.exists():
        concatenate_stage.STATE_FILE.unlink()
    if stage == "prepare" and config.PRODUCTS_INPUT_PARQUET.exists():
        config.PRODUCTS_INPUT_PARQUET.unlink()
    if stage == "dedupe" and config.PRODUCTS_PARQUET.exists():
        config.PRODUCTS_PARQUET.unlink()
    if stage == "taxonomy" and config.COICOP_SUBCATS_JSON.exists():
        config.COICOP_SUBCATS_JSON.unlink()
    if stage in ("match", "enrich"):
        for p in (
            config.ENRICHMENTS_PARQUET,
            config.FAILED_PARQUET,
            config.MATCH_LOG_PARQUET,
        ):
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
    help="Ignore caches for the chosen stage (DANGEROUS on enrich — re-matches every deduped product, no cache reuse).",
)
@click.option(
    "--no-reindex",
    is_flag=True,
    help=(
        "Skip the tier-(b) KNN reindex tail step. Tail runs after match/merge "
        "(or a full pipeline run) and rebuilds per-country HNSW indices from "
        "the post-cascade cache; countries below KNN_BOOTSTRAP_CLUSTER_FLOOR "
        "are skipped silently."
    ),
)
@click.option("-r", "--region", "region", default=None, hidden=True)
@click.option("-S", "--subregion", "subregion", default=None, hidden=True)
@click.option("-c", "--country", "country", default=None, hidden=True)
def process_command(stage, rebuild, no_reindex, region, subregion, country):
    """AI enrichment pipeline (concatenate → prepare → dedupe → taxonomy → match → merge).

    `match` runs the 3-tier cascade: tier (a) regex structural extraction
    overlays, tier (b) channel-aware KNN over per-country cluster-resolved
    cache (cluster_key = (canonical_strict, country, channel); same-channel
    neighbors preferred, cross-channel fallback when fewer than
    MIN_SAME_CHANNEL_KNN same-channel candidates clear threshold; gated by
    cluster_agreement_coicop ≥ KNN_CLUSTER_AGREEMENT_MIN AND tier-a
    pricing_basis agreement), tier (c) KNN-aware LLM reranker for residuals
    with channel-conditional COICOP top-level priors (out-of-prior accepts
    logged to _channel_outliers.parquet).

    Tail step (skipped via --no-reindex): rebuilds the tier-(b) HNSW index
    per country from the post-cascade cache. Runs after match/merge or a
    full pipeline run; other single-stage runs leave indices untouched.
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
        for name in ["concatenate", "prepare", "dedupe", "taxonomy", "match", "merge"]:
            click.echo(f"\n=== {name} ===")
            STAGES[name]()
    if not no_reindex and stage in (None, "match", "enrich", "merge"):
        click.echo("\n=== reindex (tier-b) ===")
        from prices.enrich import index as tier_b_index

        built = tier_b_index.reindex_all()
        click.echo(f"tier-b indices built: {len(built)} country/ies")
        for country, n in sorted(built.items()):
            click.echo(f"  {country}: {n} clusters")
