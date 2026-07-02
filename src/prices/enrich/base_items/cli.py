"""`python run.py prices classify <base_item>` — one loop iteration."""

from __future__ import annotations

import json
from pathlib import Path

import click


@click.command("classify")
@click.argument("base_item")
@click.option("--region", default=None, help="Restrict the grep to one region slug.")
@click.option(
    "--seed-config",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Seed base_items.parquet from a base_item_config.json first.",
)
@click.option(
    "--derive-lexicons",
    is_flag=True,
    help="Re-derive the shared FORM/NEG lexicons from coicop_categories.xlsx first.",
)
@click.option(
    "--append",
    is_flag=True,
    help="Append the validated GREEN artifact to outputs/prices/{region}_prices.csv.",
)
def classify_command(base_item, region, seed_config, derive_lexicons, append):
    """Bucket one base_item (GREEN / OTHER_FORM / REVIEW / EXCLUDE), validate the
    GREEN unit-values, and write logs/prices/validation_runs/{base_item}_*.csv."""
    import spacy

    from . import pipeline, store, taxonomy

    nlp = spacy.load("en_core_web_sm", disable=["ner"])

    if derive_lexicons:
        neg, form = taxonomy.derive_lexicons(nlp)
        click.echo(f"derived lexicons: NEG={neg}  FORM={form}")
    if seed_config:
        seeded = taxonomy.seed_from_config(seed_config)
        click.echo(f"seeded base_items rows: {len(seeded)}")

    known = set(store.load_base_items()["base_item"].astype(str))
    if base_item not in known:
        raise click.ClickException(
            f"'{base_item}' not in base_items.parquet. Seed it first "
            f"(--seed-config) or add candidate rows via taxonomy.extract_candidates."
        )

    summary = pipeline.run_iteration(base_item, region, nlp=nlp)
    click.echo("=" * 66)
    click.echo(f"base_item={base_item}  region={region}  matched={summary['n']}")
    if summary["n"] == 0:
        return
    click.echo(f"distribution: {summary['distribution']}")
    click.echo(
        f"GREEN validated={summary['green_validated']}  "
        f"demoted(basis)={summary['green_demoted']}"
    )
    click.echo(
        f"run dir: {summary['run_dir']}  (green.csv / other_form.csv / "
        f"review.csv / exclude.csv)"
    )
    if summary["review_cross_base_items"]:
        click.echo("REVIEW cross-base_items to report back to base_items.parquet:")
        click.echo("  " + json.dumps(summary["review_cross_base_items"]))
    if summary["review_brand_candidates"]:
        click.echo("REVIEW brand/variety candidates (confirm -> gazetteer):")
        click.echo("  " + json.dumps(summary["review_brand_candidates"][:15]))

    if append:
        if not region:
            raise click.ClickException("--append requires --region")
        out = pipeline.append_region(summary["run_dir"], region)
        click.echo(f"appended validated GREEN -> {out}")


@click.command("regex-check")
@click.option("--bless", is_flag=True, help="Overwrite the snapshot after review.")
def regex_check_command(bless):
    """Freeze/diff the tier-a extraction snapshot over the base_item corpus."""
    from . import pipeline, regex_check, store

    corpus = pipeline.full_corpus(store.load_base_items())
    if not regex_check.SNAPSHOT.exists() or bless:
        path = regex_check.bless(corpus) if bless else regex_check.freeze(corpus)
        click.echo(f"snapshot written: {path}")
        return
    d = regex_check.diff(corpus)
    if d.empty:
        click.echo("regex-check: no diff vs snapshot (regression-free).")
    else:
        out = regex_check.SNAPSHOT.parent / "regex_check_diff.csv"
        d.to_csv(out, index=False)
        click.echo(
            f"regex-check: {len(d)} rows changed -> {out} (review before --bless)"
        )
