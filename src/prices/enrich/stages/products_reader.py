"""Reading `products_input` for the decide loop, whole or scoped to countries.

Split out of `stages/classify.py`, which is at its size limit. The boundary is a
real one: everything here is about getting rows off disk cheaply, and nothing
here knows what a decision is.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

# Only what the decision loop actually reads. products_input carries pricing and
# provenance columns too; at corpus scale projecting is worth several GB.
#
# `source` is in this list because `_structural_fields` reads it for the
# case-size rule. It was absent, so `p.get("source")` was None for every row of
# a real run and `_PIECE_IS_CASE_SOURCES` could only ever fire in a test that
# passed its own frame. Anything this list omits fails silently, as a default,
# rather than as a KeyError.
PRODUCT_COLS = [
    "input_hash",
    "product_name_original",
    "category",
    "country",
    "lang",
    "details",
    "unit",
    "source",
    "declared_coicop_codes",
]


def _country_filter(countries):
    """`countries` as an arrow predicate, or None for the whole corpus.

    Pushed into the scan rather than applied to the frame afterwards. The
    difference is not cosmetic: products_input is 6.4 GB and a mask still pays
    to materialise every row it is about to discard, which is the shape of bug
    that OOM-killed `build_snapshot`.
    """
    import pyarrow.dataset as pads  # noqa: PLC0415

    if countries is None:
        return None
    return pads.field("country").isin(sorted({str(c) for c in countries}))


def _projection(dataset):
    """Columns to ask for, and columns to fill in afterwards.

    `unit` and `source` postdate parquet files that are still on disk, and
    asking pyarrow for a column a file does not have raises rather than
    returning nulls.
    """
    have = set(dataset.schema.names)
    present = [c for c in PRODUCT_COLS if c in have]
    absent = [c for c in PRODUCT_COLS if c not in have]
    return present, absent


def _warn_absent(in_path: Path, absent) -> None:
    if not absent:
        return
    print(
        f"[classify] {Path(in_path).name} has no {', '.join(absent)} column"
        f"{'s' if len(absent) > 1 else ''} — treated as empty for every row. "
        "Re-run `prices process --stage prepare` to populate it.",
        flush=True,
    )


def read_products(in_path: Path, countries=None) -> pd.DataFrame:
    """`products_input` projected to PRODUCT_COLS, tolerating older files.

    Filling missing columns here keeps a stale products_input readable, and —
    more to the point — makes the degradation VISIBLE: `_structural_fields`
    treats a missing `unit` as "no declared unit", which is indistinguishable
    from a file that genuinely has none unless someone says so out loud.
    """
    import pyarrow.dataset as pads  # noqa: PLC0415

    dataset = pads.dataset(in_path, format="parquet")
    present, absent = _projection(dataset)
    products = dataset.to_table(
        columns=present, filter=_country_filter(countries)
    ).to_pandas()
    for c in absent:
        products[c] = None
    _warn_absent(in_path, absent)
    return products[PRODUCT_COLS]


def iter_products(in_path: Path, chunk_rows: int, countries=None):
    """`read_products` in batches, with the same projection and the same
    missing-column fill.

    The decide loop used to slice a resident frame with `.iloc`, which meant the
    whole corpus stayed in memory for the length of the loop to serve reads that
    parquet can serve directly. At 37.4M rows that frame is ~20 GB, on top of a
    `scored` dict holding 29.4M entries -- the run reached 26 GB on a 26 GB box
    and began swapping a third of the way through. The rows are on disk; read
    them from there.
    """
    import pyarrow.dataset as pads  # noqa: PLC0415

    dataset = pads.dataset(in_path, format="parquet")
    present, absent = _projection(dataset)
    scanner = dataset.scanner(
        columns=present, filter=_country_filter(countries), batch_size=chunk_rows
    )
    for batch in scanner.to_batches():
        # A filtered scan yields empty batches for row groups the predicate
        # eliminated; they would otherwise reach `decide_rows` as no-op work and
        # print a progress line each.
        if batch.num_rows == 0:
            continue
        chunk = batch.to_pandas()
        for c in absent:
            chunk[c] = None
        yield chunk[PRODUCT_COLS]
