"""Golden-snapshot regression gate for tier-a extraction.

freeze(): snapshot extract() fields over a corpus.
diff():   re-extract over the same corpus, return rows that changed vs the
          snapshot (must be empty except intentionally-targeted rows).
bless():  overwrite the snapshot after a human confirms the intended diff.
"""

from __future__ import annotations

import pandas as pd

from prices.enrich.config import REPO_ROOT
from prices.enrich.extract import extract

SNAPSHOT = (
    REPO_ROOT
    / "data"
    / "prices"
    / "_enrich"
    / "_regex_snapshots"
    / "extraction_snapshot.parquet"
)
FIELDS = ["pricing_basis", "amount_value", "count", "multiplier", "standard_unit"]


def _extract_frame(corpus: pd.DataFrame) -> pd.DataFrame:
    names = corpus["product_name_original"].astype(str)
    langs = corpus["lang"] if "lang" in corpus.columns else [None] * len(names)
    recs = []
    for n, lg in zip(names, langs):
        sf = extract(item_name=n, category=None, country=None, lang=lg)
        recs.append({"name": n, "lang": lg, **{f: getattr(sf, f) for f in FIELDS}})
    return pd.DataFrame(recs)


def freeze(corpus: pd.DataFrame) -> str:
    out = _extract_frame(corpus)
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(SNAPSHOT, index=False)
    return str(SNAPSHOT)


def diff(corpus: pd.DataFrame) -> pd.DataFrame:
    if not SNAPSHOT.exists():
        raise FileNotFoundError(f"no snapshot at {SNAPSHOT}; run freeze first")
    old = pd.read_parquet(SNAPSHOT).set_index(["name", "lang"])
    new = _extract_frame(corpus).set_index(["name", "lang"])
    joined = old.join(new, lsuffix="_old", rsuffix="_new", how="outer")
    changed = pd.Series(False, index=joined.index)
    for f in FIELDS:
        changed |= joined[f"{f}_old"].astype(str) != joined[f"{f}_new"].astype(str)
    return joined[changed].reset_index()


def bless(corpus: pd.DataFrame) -> str:
    return freeze(corpus)
