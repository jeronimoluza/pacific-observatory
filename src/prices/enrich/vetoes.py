"""Trap-word vetoes for the (embedding -> head) COICOP classifier.

A head prediction into a target food/bev leaf is REJECTED (demoted to no-decision)
when the raw product name matches that leaf's trap regex -- a processed or adjacent
form the embedding confuses for the fresh/base leaf (canned, juiced, dried,
flavoured, paste, oil, ...). Layered on a single global confidence gate, these
vetoes lift precision from ~95% to 98-99% at flat coverage on wild data.

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


@lru_cache(maxsize=1)
def _veto_map() -> dict[str, list[re.Pattern]]:
    df = pd.read_parquet(config.VETO_LEXICON_PARQUET)
    out: dict[str, list[re.Pattern]] = {}
    for leaf, pattern, match_type in zip(
        df["coicop_leaf"], df["pattern"], df["match_type"]
    ):
        if match_type == "phrase":
            rx = re.compile(rf"\b{re.escape(pattern)}\b", re.IGNORECASE)
        else:
            rx = re.compile(pattern, re.IGNORECASE)
        out.setdefault(leaf, []).append(rx)
    return out


def is_vetoed(leaf: str, name: str) -> bool:
    """True if predicting `leaf` for `name` hits a trap word and must be rejected."""
    rxs = _veto_map().get(leaf)
    if not rxs:
        return False
    text = str(name).lower()
    return any(rx.search(text) for rx in rxs)
