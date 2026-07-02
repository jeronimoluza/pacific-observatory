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
    click.echo(f"promotion: {summary.get('promotion')}  GREEN={summary.get('n_green')}")
    ls = summary.get("loop_status") or {}
    click.echo(
        f"loop-status: {'STOP' if ls.get('stop') else 'CONTINUE'} ({ls.get('reason')})"
    )
    if summary.get("basis_conflict"):
        click.echo("basis_conflict:\n" + summary["basis_conflict"])
    click.echo(
        f"GREEN validated={summary['green_validated']}  "
        f"demoted(basis)={summary['green_demoted']}"
    )
    click.echo(
        f"run dir: {summary['run_dir']}  (candidates.csv / green.csv / "
        f"other_form.csv / review.csv / exclude.csv)"
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


@click.command("build-timeseries")
@click.argument(
    "green_csv", required=False, type=click.Path(exists=True, path_type=Path)
)
def build_timeseries_command(green_csv):
    """Trace GREEN products back to their dated scrapes.

    With no argument, concatenates every validation_runs/{item}/latest/green.csv
    (the accumulated GREEN across all classified base_items); pass a single
    GREEN_CSV to scope to one run. Joins the GREEN keys (input_hash) to
    raw_prices.csv, reapplies each product's unit-value transform per dated price,
    attaches date-accurate FX, and writes the long parquet
    outputs/prices/eap_prices.parquet + latest-snapshot CSV eap_prices_latest.csv.
    """
    from . import timeseries

    summary = timeseries.run(green_csv)
    click.echo(
        f"green products: {summary['green_products']}  "
        f"matched: {summary['matched_products']}  "
        f"observations: {summary['observations']}"
    )
    click.echo(f"long parquet: {summary['parquet']}")
    click.echo(f"latest snapshot: {summary['snapshot']}")


@click.command("apply-verdicts")
@click.argument("base_item")
@click.argument("verdicts_json", type=click.Path(exists=True, path_type=Path))
def apply_verdicts_command(base_item, verdicts_json):
    """Apply a judgment agent's verdicts JSON to the gazetteer flywheel.

    VERDICTS_JSON is a {"item", "verdicts":[{token, role, leaf?}]} document (a
    Sonnet agent reads a run folder's review.csv and emits it — see the
    classify-base-item-prices skill). Validates it against BASE_ITEM, then
    appends the (token -> role) rows to gazetteer.parquet so the next
    `prices classify BASE_ITEM` earns them. The cascade is NOT re-run here.
    """
    from . import store
    from . import verdicts as V

    payload = json.loads(Path(verdicts_json).read_text())
    try:
        vmap = V.parse_verdicts(payload, base_item)
    except ValueError as e:
        raise click.ClickException(str(e)) from e

    before = len(store.load_gazetteer())
    store.append_gazetteer(base_item, vmap)
    after = len(store.load_gazetteer())
    click.echo(
        f"apply-verdicts {base_item}: {len(vmap)} verdicts parsed, "
        f"{after - before} new gazetteer rows (was {before}, now {after})."
    )


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
