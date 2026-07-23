"""Trap-word vetoes for the (embedding -> head) COICOP classifier.

A head prediction into a target food/bev leaf is REJECTED (demoted to no-decision)
when the raw product name matches that leaf's trap regex -- a processed or adjacent
form the embedding confuses for the fresh/base leaf (canned, juiced, dried,
flavoured, paste, oil, ...). Layered on a single global confidence gate, these
vetoes lift precision from ~95% to 98-99% at flat coverage on wild data.

A row may also REROUTE instead of reject: when `reroute_leaf` is set, a matching
prediction is reassigned to that leaf and accepted. Reroute asserts a positive
(it injects a value into the unit-value calc), so it is held to a higher bar than
reject -- `gold_positive_collisions=0` on the source leaf AND corpus-verified
target precision (e.g. cola+sour is deterministically confectionery, not soda).

The veto database lives in `config.VETO_LEXICON_PARQUET` -- a mix of frozen
config-E regex vetoes (`match_type=regex`) and phrase vetoes mined from wild
LLM-labeled negatives (`match_type=phrase`), all with `gold_positive_collisions=0`
(safe vs gold TPs). This module is a thin loader; edit the parquet, not this file.
"""

from __future__ import annotations

import re
from functools import lru_cache

import pandas as pd

from prices.enrich import config

REJECT = "__reject__"


@lru_cache(maxsize=1)
def _veto_map() -> dict[str, list[tuple[re.Pattern, str | None]]]:
    df = pd.read_parquet(config.VETO_LEXICON_PARQUET)
    reroute = df["reroute_leaf"] if "reroute_leaf" in df.columns else [None] * len(df)
    out: dict[str, list[tuple[re.Pattern, str | None]]] = {}
    for leaf, pattern, match_type, rr in zip(
        df["coicop_leaf"], df["pattern"], df["match_type"], reroute
    ):
        if match_type == "phrase":
            rx = re.compile(rf"\b{re.escape(pattern)}\b", re.IGNORECASE)
        else:
            rx = re.compile(pattern, re.IGNORECASE)
        target = None if pd.isna(rr) else str(rr)
        out.setdefault(leaf, []).append((rx, target))
    return out


def veto_action(leaf: str, name: str) -> str | None:
    """Action for predicting `leaf` on `name`: None, `REJECT`, or a reroute leaf.

    Reroute wins over reject when both match the same predicted leaf.
    """
    entries = _veto_map().get(leaf)
    if not entries:
        return None
    text = str(name).lower()
    hit_reject = False
    for rx, target in entries:
        if rx.search(text):
            if target is not None:
                return target
            hit_reject = True
    return REJECT if hit_reject else None


def is_vetoed(leaf: str, name: str) -> bool:
    """True if predicting `leaf` for `name` hits a trap word and must be rejected."""
    return veto_action(leaf, name) == REJECT
