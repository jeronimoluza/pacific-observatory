"""Post-classification basis-audit layer.

After a product is classified into a COICOP leaf and its `pricing_basis` is
independently extracted by regex (`extract.py`), this layer inspects the
`(leaf, basis)` pair against a curated DENYLIST of physically-impossible
pairs and withholds trust from contradictions. It may REJECT (drop) or FLAG
(quarantine) a row -- it may never override, reroute, or fabricate a basis.

Author a denylist of impossible (leaf, basis) pairs; everything not excluded
is provisionally allowed. `count` and `item` are never excluded (packaging
dims, not sale basis).

The denylist lives in `config.BASIS_DENYLIST_PARQUET` -- edit the parquet,
not this file. `audit()` reads a single runtime field, `action`, derived at
authoring time from `semantic` (is this basis physically impossible?) and
`evidence_state` (has the corpus backed it?): `action == "reject"` iff
`semantic == "HIGH" AND evidence_state == "CONFIRMED"`, else `action ==
"flag"`. An unseen leaf therefore structurally cannot reject.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd

from prices.enrich import config

PASS = "PASS"
REJECT = "REJECT"
FLAG = "FLAG"
NO_STRUCTURAL = "NO_STRUCTURAL"


@lru_cache(maxsize=1)
def _denylist_map() -> dict[str, dict]:
    return load_denylist(config.BASIS_DENYLIST_PARQUET)


def load_denylist(path: Path) -> dict[str, dict]:
    """leaf -> {excluded, action, semantic, evidence_state, profile, label}.

    Only rows with a non-empty `excluded` set are included.
    """
    df = pd.read_parquet(path)
    out: dict[str, dict] = {}
    for row in df.itertuples(index=False):
        excl = row.excluded or ""
        excl_set = frozenset(x for x in excl.split("|") if x)
        if not excl_set:
            continue
        out[row.code] = {
            "excluded": excl_set,
            "action": row.action,
            "semantic": row.semantic,
            "evidence_state": row.evidence_state,
            "profile": row.profile,
            "label": row.label,
        }
    return out


def audit(leaf: str, basis: str | None, denylist: dict[str, dict]) -> str:
    """PASS | REJECT | FLAG | NO_STRUCTURAL.

    basis in the leaf's excluded set -> REJECT if action=="reject" else FLAG.
    Basis not excluded / leaf absent from denylist -> PASS.
    Missing structural basis -> NO_STRUCTURAL (nothing to audit).
    """
    if basis is None or basis == "":
        return NO_STRUCTURAL
    entry = denylist.get(leaf)
    if entry is None:
        return PASS
    if basis in entry["excluded"]:
        return REJECT if entry["action"] == "reject" else FLAG
    return PASS
