"""Orchestrator for the prices enrichment pipeline.

Runs the full ``load → quantities → classify → merge`` chain, or a single
stage when ``--stage`` is passed. Exposes the ``po prices process`` CLI
verb wired in ``src/cli.py``.

Layout assumed:
    data/prices/{region}/{sub}/{country}/{source}/...   # raw + intermediate
    data/prices/_enrich/                                # this pipeline's working files
    outputs/prices/all_countries_prices.csv             # final published CSV
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import click
import pandas as pd

from .classification import reclassify_missing_classifications
from .classify import run_classify
from .load import run_load
from .merge import run_merge
from .quantities import run_quantities
from .utils import get_project_root

logger = logging.getLogger(__name__)

STAGES = ("load", "quantities", "classify", "merge")


def _print_banner(title: str) -> None:
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def run_pipeline(
    project_root: Optional[Path] = None,
    stage: Optional[str] = None,
    rebuild: bool = False,
    skip_classification: bool = False,
) -> Optional[pd.DataFrame]:
    """Run the enrichment pipeline.

    ``stage`` selects a single step from ``STAGES``. When ``None``, runs the
    whole chain. ``rebuild`` only applies to ``load``. ``skip_classification``
    only applies when the full chain or ``classify`` is being run.
    """
    if project_root is None:
        project_root = get_project_root()

    if stage is not None and stage not in STAGES:
        raise click.BadParameter(
            f"unknown stage '{stage}'. Choose from: {', '.join(STAGES)}"
        )

    run_load_stage       = stage in (None, "load")
    run_quantities_stage = stage in (None, "quantities")
    run_classify_stage   = stage in (None, "classify") and not skip_classification
    run_merge_stage      = stage in (None, "merge")

    if run_load_stage:
        _print_banner("STEP 1: Load and prepare data")
        run_load(project_root, rebuild=rebuild)

    if run_quantities_stage:
        _print_banner("STEP 2: Extract quantities (Standardized Unit Price System)")
        run_quantities(project_root)

    if stage in (None, "classify") and skip_classification:
        _print_banner("STEP 3: SKIPPED — Using existing classifications")
    elif run_classify_stage:
        _print_banner("STEP 3: Classify with COICOP using Gemini AI")
        run_classify(project_root)

    if run_merge_stage:
        _print_banner("STEP 4: Merge & Finalize")
        return run_merge(project_root)

    return None


# ── CLI ─────────────────────────────────────────────────────────────


@click.command("process")
@click.option(
    "--stage",
    type=click.Choice(list(STAGES), case_sensitive=False),
    default=None,
    help="Run a single stage. Omit to run the full load → quantities → classify → merge chain.",
)
@click.option(
    "--rebuild",
    is_flag=True,
    help="Drop prepared_cache.parquet + manifest.json and re-load from scratch.",
)
@click.option(
    "--skip-classification",
    is_flag=True,
    help="Skip the Gemini classification step (reuse existing gemini_classification.csv).",
)
@click.option(
    "--reclassify-missing",
    is_flag=True,
    help=(
        "Only retry NaN coicop_code rows in gemini_classification.csv. "
        "Mutually exclusive with --stage / --rebuild / --skip-classification."
    ),
)
@click.option(
    "--region", "-r", default=None,
    help="(Accepted for symmetry with other pipelines; the cache is global.)",
)
@click.option(
    "--subregion", "-S", default=None,
    help="(Accepted for symmetry with other pipelines; the cache is global.)",
)
@click.option(
    "--country", "-c", default=None,
    help="(Accepted for symmetry with other pipelines; the cache is global.)",
)
def process_command(
    stage: Optional[str],
    rebuild: bool,
    skip_classification: bool,
    reclassify_missing: bool,
    region: Optional[str],
    subregion: Optional[str],
    country: Optional[str],
) -> None:
    """Load → quantities → classify → merge for the prices pipeline."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    if reclassify_missing:
        if stage or rebuild or skip_classification:
            raise click.UsageError(
                "--reclassify-missing cannot be combined with "
                "--stage / --rebuild / --skip-classification."
            )
        reclassify_missing_classifications()
        return

    if any((region, subregion, country)):
        logger.warning(
            "region/subregion/country filters are accepted but not yet "
            "applied — the enrichment cache is global."
        )

    try:
        run_pipeline(
            stage=stage,
            rebuild=rebuild,
            skip_classification=skip_classification,
        )
    except Exception as exc:
        raise click.ClickException(str(exc))


if __name__ == "__main__":
    process_command()
