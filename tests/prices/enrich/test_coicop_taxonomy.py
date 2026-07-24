"""Unit tests for the COICOP taxonomy helpers used by the gold-labeling workflow.

Cover the pure leaf-derivation and block-rendering logic with synthetic frames
so no xlsx I/O is needed (the real COICOP_XLSX lives under data/).
"""

from __future__ import annotations

import pandas as pd
import pytest

from prices.enrich import coicop_taxonomy

pytestmark = [pytest.mark.unit]


def test_deepest_leaves_drops_parents():
    codes = {"01", "01.1", "01.1.1", "01.1.1.1.0", "01.1.2.0.0"}
    assert coicop_taxonomy.deepest_leaves(codes) == {"01.1.1.1.0", "01.1.2.0.0"}


def test_deepest_leaves_keeps_isolated_code():
    assert coicop_taxonomy.deepest_leaves({"05.6.1.1"}) == {"05.6.1.1"}


def test_render_leaf_blocks_only_leaves_with_optional_bullets():
    df = pd.DataFrame(
        {
            "code": ["01.1", "01.1.1.0.0", "01.1.2.0.0"],
            "title": ["parent (not a leaf)", "Rice", "Bread"],
            "includes": [None, "white rice\n* brown rice", None],
        }
    )
    blocks = coicop_taxonomy.render_leaf_blocks(df)
    # the non-leaf parent 01.1 is dropped
    assert set(blocks) == {"01.1.1.0.0", "01.1.2.0.0"}
    assert blocks["01.1.1.0.0"].startswith("01.1.1.0.0 | Rice")
    assert "includes: white rice; brown rice" in blocks["01.1.1.0.0"]
    # a leaf with no includes value emits no includes line
    assert "includes:" not in blocks["01.1.2.0.0"]
