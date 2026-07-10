"""Consensus CLI (W4.4).

  prices classify-corpus   LOOP A — witnesses+gate over every canonical name;
                           memoize accepts into label_store, rank conflicts.
  prices classify-delta    LOOP B — same, restricted to names not yet in
                           label_store (the incremental path).
  prices queue export      emit an agent-ready CSV slice of the ranked queue.

By default classify-corpus/-delta run only the FAST witnesses (memo, lexicon,
model, source) so a whole-corpus pass scores in minutes. Add --with-knn /
--with-cascade to fold in the heavy retrieval + spaCy witnesses.
"""

from __future__ import annotations

import click
import pandas as pd

from prices.enrich import config, label_store
from prices.enrich.consensus import CONFLICTS_PARQUET, queue
from prices.enrich.consensus.run import classify_frame
from prices.enrich.keys import norm_key

NAME_COL = "first_name"
_STORE_COLS = [
    "canonical_key",
    "leaf",
    "decision",
    "tier",
    "confidence",
    "witness_votes",
    "provenance",
]


def _load_corpus(limit: int | None) -> pd.DataFrame:
    df = pd.read_parquet(config.PRODUCTS_PARQUET)
    if limit:
        df = df.head(limit)
    return df


def _tier_table(accepts: pd.DataFrame, n_conflict: int, n_total: int) -> str:
    lines = ["  tier                 accepts"]
    if not accepts.empty:
        for tier, n in accepts["tier"].value_counts().items():
            lines.append(f"  {tier:<18} {n:>8}")
    n_acc = len(accepts)
    cov = (n_acc / n_total) if n_total else 0.0
    conf = (n_conflict / n_total) if n_total else 0.0
    lines.append(f"  {'ACCEPTED':<18} {n_acc:>8}  ({cov:.1%} of {n_total})")
    lines.append(f"  {'CONFLICT':<18} {n_conflict:>8}  ({conf:.1%})")
    return "\n".join(lines)


def _run(
    corpus: pd.DataFrame, with_knn: bool, with_cascade: bool, dry_run: bool
) -> None:
    n_total = corpus[NAME_COL].map(norm_key).nunique()
    accepts, conflicts = classify_frame(
        corpus, NAME_COL, use_knn=with_knn, use_cascade=with_cascade
    )
    # memo accepts are already authoritative in the store — do not re-append.
    fresh = accepts[accepts["tier"] != "T0_memo"] if not accepts.empty else accepts

    click.echo(_tier_table(accepts, len(conflicts), n_total))

    if dry_run:
        click.echo("(dry-run — nothing written)")
        return

    if not fresh.empty:
        label_store.append(fresh[_STORE_COLS])
        click.echo(f"  wrote {len(fresh)} new labels -> {label_store.LABEL_STORE_PATH}")
    q = queue.build_queue(conflicts, corpus, NAME_COL)
    click.echo(f"  queue: {len(q)} conflicts -> {CONFLICTS_PARQUET}")


@click.command("classify-corpus")
@click.option("--limit", type=int, default=None, help="Cap names (scoped test run).")
@click.option(
    "--with-knn/--no-knn", default=False, help="Include the tier-b KNN witness."
)
@click.option(
    "--with-cascade/--no-cascade",
    default=False,
    help="Include the base-item cascade witness.",
)
@click.option("--dry-run", is_flag=True, help="Score + report only; write nothing.")
def classify_corpus_command(limit, with_knn, with_cascade, dry_run):
    """LOOP A: witnesses + consensus gate over all canonical names."""
    corpus = _load_corpus(limit)
    click.echo(
        f"classify-corpus: {len(corpus)} rows (knn={with_knn} cascade={with_cascade})"
    )
    _run(corpus, with_knn, with_cascade, dry_run)


@click.command("classify-delta")
@click.option("--limit", type=int, default=None, help="Cap names (scoped test run).")
@click.option(
    "--with-knn/--no-knn", default=False, help="Include the tier-b KNN witness."
)
@click.option(
    "--with-cascade/--no-cascade",
    default=False,
    help="Include the base-item cascade witness.",
)
@click.option("--dry-run", is_flag=True, help="Score + report only; write nothing.")
def classify_delta_command(limit, with_knn, with_cascade, dry_run):
    """LOOP B: consensus only over names absent from label_store."""
    corpus = _load_corpus(None)
    known = (
        set(label_store.active()["canonical_key"])
        if not label_store.active().empty
        else set()
    )
    corpus = corpus[~corpus[NAME_COL].map(norm_key).isin(known)]
    if limit:
        corpus = corpus.head(limit)
    click.echo(
        f"classify-delta: {len(corpus)} unseen rows (of store={len(known)}; "
        f"knn={with_knn} cascade={with_cascade})"
    )
    if corpus.empty:
        click.echo("  nothing to do")
        return
    _run(corpus, with_knn, with_cascade, dry_run)


@click.command("auto-verdicts")
@click.option(
    "--top", type=int, default=200, help="Ranked queue rows to draft (highest first)."
)
@click.option("--batch-size", type=int, default=50, help="Names per LLM call.")
@click.option(
    "--out", "out_path", type=click.Path(), default=None, help="Staging JSON path."
)
def auto_verdicts_command(top, batch_size, out_path):
    """LLM-draft resolutions over the top conflict-queue slice (HUMAN-GATED).

    Writes a staging JSON in the resolutions shape — nothing reaches the
    label_store until you review it and run `prices queue apply`.
    """
    from prices.enrich.consensus import auto_verdicts

    q = queue.load_queue().head(top)
    if q.empty:
        click.echo("queue is empty — run classify-corpus first")
        return
    click.echo(f"auto-verdicts: drafting {len(q)} conflicts (batch={batch_size})")
    doc = auto_verdicts.draft_verdicts(q, batch_size=batch_size)
    path = auto_verdicts.write_staging(doc, out_path)
    res = doc["resolutions"]
    breakdown = (
        pd.Series([r["decision"] for r in res]).value_counts().to_dict() if res else {}
    )
    click.echo(f"  drafted {len(res)}/{len(q)} verdicts {breakdown}")
    click.echo(f"  staged -> {path}")
    click.echo("  REVIEW then apply:  prices queue apply " + str(path))


@click.group("queue")
def queue_group():
    """Inspect / export the consensus conflict queue."""


@queue_group.command("export")
@click.option(
    "--top", type=int, default=500, help="Rows to export (highest-ranked first)."
)
@click.option(
    "--out", "out_path", type=click.Path(), required=True, help="Destination CSV."
)
def queue_export_command(top, out_path):
    """Emit an agent-ready CSV slice of the ranked conflict queue."""
    q = queue.export_slice(top, out_path)
    click.echo(f"exported {len(q)} conflicts -> {out_path}")


@queue_group.command("apply")
@click.argument("files", nargs=-1, required=True, type=click.Path(exists=True))
@click.option(
    "--no-lexicon", is_flag=True, help="Skip the lexicon regen after writing."
)
def queue_apply_command(files, no_lexicon):
    """Apply resolution FILES to the label_store (T3) + lexicon + gazetteer.

    Accepts several files at once; a canonical_key the files resolve
    differently is escalated to an adjudication file instead of applied.
    """
    from prices.enrich.consensus.apply import apply_resolution_files

    summary = apply_resolution_files(files, regen_lexicon=not no_lexicon)
    click.echo(
        f"queue apply: wrote {summary['written']} T3 labels, "
        f"{summary['escalated']} escalated, {summary['gazetteer_new']} gazetteer rows"
        + (", lexicon rebuilt" if summary["lexicon_rebuilt"] else "")
    )
    if summary["escalated_path"]:
        click.echo(f"  escalated -> {summary['escalated_path']}")
