import re

import pandas as pd
import pytest

from prices.enrich import config, label_store
from prices.enrich.coicop_taxonomy import load_taxonomy_index

# Pre-existing curated defect: `wipes` and 267 GREEN rows are stamped 05.6.1.0,
# a code absent from COICOP (xlsx has 05.6.1.1 "Household cleaning products").
# Correct leaf is almost certainly 05.6.1.1; the remap touches published-series
# identity so it is a deliberate, human-gated change, not part of W1 plumbing.
# This allowlist keeps CI a ratchet: any *new* invalid code still fails.
KNOWN_NON_LEAF_LEGACY = {"05.6.1.0"}

_CODE_RE = re.compile(r"^\d{2}(\.\d+)+$")

BASE_ITEMS_PATH = config.REPO_ROOT / "data" / "prices" / "base_items.parquet"


def _leaves():
    leaves, _ = load_taxonomy_index()
    return leaves


def _coicop_codes(series):
    vals = {str(v) for v in series.dropna().unique()}
    return {v for v in vals if _CODE_RE.match(v)}


@pytest.mark.unit
def test_base_items_codes_are_leaves():
    if not BASE_ITEMS_PATH.exists():
        pytest.skip("base_items.parquet absent")
    leaves = _leaves()
    codes = _coicop_codes(pd.read_parquet(BASE_ITEMS_PATH)["coicop_code"])
    invalid = codes - leaves - KNOWN_NON_LEAF_LEGACY
    assert (
        not invalid
    ), f"non-leaf COICOP codes in base_items.parquet: {sorted(invalid)}"


@pytest.mark.unit
def test_label_store_codes_are_leaves():
    df = label_store.load()
    if df.empty:
        pytest.skip("label_store.parquet empty/absent")
    leaves = _leaves()
    codes = _coicop_codes(df[df["decision"] == "leaf"]["leaf"])
    invalid = codes - leaves - KNOWN_NON_LEAF_LEGACY
    assert (
        not invalid
    ), f"non-leaf COICOP codes in label_store.parquet: {sorted(invalid)}"
