"""Extraction under another checkout's code, for `prices rulecheck shared`.

Run as its own interpreter: `python _rulecheck_extract.py SRC_ROOT IN OUT WORKERS`.
`prices` is imported only after SRC_ROOT replaces this script's directory at the
front of sys.path, so the code under SRC_ROOT -- not the running checkout -- is
what extracts. Writes the extraction fields for every row of IN, and for its
upper-cased name (the case-invariance check), in IN's row order.
"""

import sys


def _rows(chunk):
    from prices.enrich.stages.extraction import _structural_fields

    out = []
    for r in chunk:
        out.append(_structural_fields(*r))
        out.append(_structural_fields(str(r[0]).upper(), *r[1:]))
    return out


if __name__ == "__main__":
    src, inp, outp, workers = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
    sys.path[0] = src
    from multiprocessing import get_context

    import pandas as pd

    from prices.enrich.stages.extraction import EXTRACTION_FIELDS

    cols = ["product_name_original", "category", "country", "lang", "details", "unit", "source"]
    rows = list(pd.read_parquet(inp, columns=cols).itertuples(index=False, name=None))
    step = max(1, len(rows) // (workers * 8) + 1)
    chunks = [rows[i : i + step] for i in range(0, len(rows), step)]
    with get_context("fork").Pool(workers) as pool:
        flat = [f for part in pool.map(_rows, chunks) for f in part]
    frame = pd.DataFrame(flat, columns=EXTRACTION_FIELDS)
    frame.iloc[0::2].reset_index(drop=True).to_parquet(outp, index=False)
    frame.iloc[1::2].reset_index(drop=True).to_parquet(outp + ".upper", index=False)
