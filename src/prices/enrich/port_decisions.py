"""One-time port of the single-file decisions table to per-country parts.

The existing `decisions_*.parquet` is a complete, correct decision for every
`input_hash` in the corpus — 37.4M rows that cost 72 minutes to produce. Nothing
about it is stale; it simply predates the per-country layout and carries no
`country` column. This attaches one and splits the file, so the work is
inherited rather than recomputed.

**Country comes from position, and every row is checked.** The decisions table
was written by streaming `products_input` once, in file order, appending each
chunk's decisions in the order they were decided — so row *i* of one file is row
*i* of the other. That is an implementation detail, not a guarantee, so this
verifies `input_hash` on every single row rather than trusting it. A mismatch
aborts before anything is published; it never guesses.

Once ported, `classified` is derived from the new parts rather than joined
again: it has always been exactly `classified_view(decisions, divisions)`, so
recomputing it from the ported decisions is both cheaper and self-consistent.

This module is removable once every checkout has been ported.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import click
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from prices.enrich import config
from prices.enrich.classifier import backends
from prices.enrich.stages import decisions_store
from prices.enrich.stages.classify import (
    DECISION_SCHEMA,
    classified_mask,
    classified_view,
)


class AlignmentError(RuntimeError):
    """The two files do not line up row for row, so position cannot be trusted."""


def _country_lookup(products_path: Path) -> tuple[pa.ChunkedArray, pa.ChunkedArray]:
    """`(input_hash, country)` for the whole corpus, as arrow columns.

    Two columns of 37.4M rows, not the 17-column 6.4 GB frame — the hash is
    needed to verify alignment and the country is the thing being attached.
    """
    table = pq.read_table(products_path, columns=["input_hash", "country"])
    return table.column("input_hash"), table.column("country")


def port(
    decisions_path: Optional[Path] = None,
    products_path: Optional[Path] = None,
    out_root: Optional[Path] = None,
    batch_rows: int = 500_000,
) -> dict:
    """Split the decisions file into one part per country. Returns a summary."""
    decisions_path = Path(decisions_path or config.DECISIONS_HIERLEX_PARQUET)
    products_path = Path(products_path or config.PRODUCTS_INPUT_PARQUET)
    out_root = Path(out_root or decisions_store.parts_root(decisions_path))

    pf = pq.ParquetFile(decisions_path)
    n_dec = pf.metadata.num_rows
    hashes, countries = _country_lookup(products_path)
    if len(hashes) != n_dec:
        raise AlignmentError(
            f"{decisions_path.name} has {n_dec:,} rows but "
            f"{products_path.name} has {len(hashes):,}. The decisions table was "
            "not produced from this products_input; re-run classify instead of "
            "porting."
        )

    cursor = 0
    with decisions_store.PartitionedWriter(out_root, DECISION_SCHEMA) as writer:
        for batch in pf.iter_batches(batch_size=batch_rows):
            n = batch.num_rows
            want = hashes.slice(cursor, n)
            got = batch.column(batch.schema.get_field_index("input_hash"))
            # Element-wise on the whole batch, so an off-by-one anywhere in
            # 37.4M rows surfaces here rather than as a country silently
            # attached to the wrong product.
            if not want.equals(pa.chunked_array([got])):
                raise AlignmentError(
                    f"input_hash mismatch at row {cursor:,}: the decisions table "
                    "is not row-aligned with products_input, so country cannot be "
                    "attached by position. Re-run classify instead of porting."
                )
            frame = batch.to_pandas()
            frame["country"] = countries.slice(cursor, n).to_pandas().values
            writer.write(frame)
            cursor += n
            print(f"[port] {cursor:,}/{n_dec:,} rows", flush=True)
        parts = dict(writer.rows_by_country)

    return {
        "source": str(decisions_path),
        "parts_root": str(out_root),
        "rows": cursor,
        "countries": len(parts),
    }


def port_classified(
    dec_root: Path,
    view_root: Path,
    divisions,
) -> dict:
    """Rebuild `classified` from the ported decision parts, part by part.

    Not a second join: `classified` has always been exactly
    `classified_view(decisions, divisions)`, so deriving it here keeps the two
    tables consistent by construction and costs one pass over the parts.
    """
    dec_root = Path(dec_root)
    view_root = Path(view_root)
    view_root.mkdir(parents=True, exist_ok=True)
    n_view = 0
    written = []
    for part in sorted(dec_root.glob("*.parquet")):
        dec = pd.read_parquet(part)
        view = classified_view(dec, divisions)
        keep = classified_mask(dec, divisions)
        for country, sub in decisions_store.split_by_country(
            view, dec.loc[keep, "country"]
        ):
            out = view_root / f"{country}.parquet"
            tmp = out.with_suffix(".parquet.tmp")
            sub.to_parquet(tmp, index=False)
            tmp.replace(out)
            written.append(out)
        n_view += len(view)
        print(f"[port] {part.stem}: {len(view):,} classified rows", flush=True)
    return {"parts_root": str(view_root), "rows": n_view, "parts": len(written)}


@click.command(name="port-decisions")
@click.option("--backend", default=None, help="Which backend's tables to port.")
@click.option("--decisions", type=click.Path(), default=None)
@click.option("--products", type=click.Path(), default=None)
@click.option(
    "--batch-rows", type=int, default=500_000, show_default=True, help="Rows per pass."
)
def port_command(backend, decisions, products, batch_rows):
    """Split the single-file decisions and classified tables into country parts."""
    be = backends.get(backend)
    dec_path = Path(decisions) if decisions else be.decisions_path
    summary = port(
        decisions_path=dec_path,
        products_path=Path(products) if products else None,
        batch_rows=batch_rows,
    )
    click.echo(
        f"ported {summary['rows']:,} decisions into {summary['countries']} "
        f"country parts under {summary['parts_root']}"
    )
    view = port_classified(
        decisions_store.parts_root(dec_path),
        decisions_store.parts_root(be.classified_path),
        be.divisions,
    )
    click.echo(f"rebuilt {view['rows']:,} classified rows in {view['parts']} parts")
