"""A row that passed every QA gate must not be dropped by the payload builder.

`COMPARABLE_UNITS` omits `item` on the grounds that `item` is the
quantity-parse-failure bucket. That is true of the bucket as a whole and false
of the slice that reaches this module: `qa.py::_row_has_quantity` lets an
`item` row become `trusted` only where `SOLD_BY_ITEM_LEAVES` vets the commodity
as a genuine indivisible piece -- an avocado, a coconut, a head of lettuce.

So the filter was discarding rows the trust gate had already cleared: 92,223 of
them on the 2026-09-10 corpus, and with them 531 (country, leaf) cells across
about a hundred countries. `publish.py` has folded `item` and `unit` into one
label since 2026-09-04; the explorer never grew the equivalent.
"""

from __future__ import annotations

import pandas as pd
import pytest

from prices.build.sold_by_item import SOLD_BY_ITEM_LEAVES
from prices.explorer.aggregate import _fold_piece_units
from prices.explorer.sources import COMPARABLE_UNITS

pytestmark = pytest.mark.unit

PIECE_LEAF = "01.1.6.1.7"  # Pineapples, fresh
WEIGHED_LEAF = "01.1.1.3.9"  # bread n.e.c. -- never on the allowlist


def _obs(rows: list[tuple[str, str]]) -> pd.DataFrame:
    return pd.DataFrame([{"coicop_code": c, "standard_unit": u} for c, u in rows])


def test_the_allowlist_is_not_empty():
    assert PIECE_LEAF in SOLD_BY_ITEM_LEAVES
    assert WEIGHED_LEAF not in SOLD_BY_ITEM_LEAVES


def test_a_genuine_per_piece_row_survives_the_comparable_units_filter():
    out = _fold_piece_units(_obs([(PIECE_LEAF, "item")]))
    assert out.standard_unit.iloc[0] == "unit"
    assert out.standard_unit.isin(
        COMPARABLE_UNITS
    ).all(), "a trusted per-piece row must reach the payload"


def test_an_off_allowlist_item_row_is_left_alone():
    """Off-allowlist `item` really does mean "no quantity found" and must not
    be promoted into a comparable unit by this fold."""
    out = _fold_piece_units(_obs([(WEIGHED_LEAF, "item")]))
    assert out.standard_unit.iloc[0] == "item"
    assert not out.standard_unit.isin(COMPARABLE_UNITS).any()


def test_measured_rows_are_untouched():
    rows = [(WEIGHED_LEAF, "kg"), (PIECE_LEAF, "kg"), (PIECE_LEAF, "unit")]
    out = _fold_piece_units(_obs(rows))
    assert out.standard_unit.tolist() == ["kg", "kg", "unit"]


def test_the_fold_is_a_no_op_when_nothing_matches():
    df = _obs([(WEIGHED_LEAF, "kg")])
    assert _fold_piece_units(df) is df
