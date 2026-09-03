"""Unit tests for the narrow-source short-circuit rule (ADR-0002).

`is_narrow` must return False whenever the resolved code is not an actual
taxonomy leaf, even when every declared code shares a single 3-digit class
prefix (the old, sole condition). Synthetic leaf sets are used throughout so
no xlsx I/O is needed here.
"""

from __future__ import annotations

import pytest

from prices.enrich import coicop_codes

pytestmark = [pytest.mark.unit]

LEAVES = {"04.1.1", "04.1.2", "01.1.1.1.0", "01.1.2.0.0"}


def test_single_leaf_code_short_circuits():
    assert coicop_codes.is_narrow(["04.1.1"], LEAVES) is True
    assert coicop_codes.resolved_code(["04.1.1"]) == "04.1.1"


def test_single_non_leaf_code_does_not_short_circuit():
    # "01.1" has children (01.1.1.1.0, 01.1.2.0.0) so it is a parent, not a leaf.
    assert coicop_codes.is_narrow(["01.1"], LEAVES) is False


def test_multi_code_same_parent_does_not_short_circuit():
    # Both codes share the "04.1" class prefix (old rule alone would pass),
    # but the truncated 4-char prefix "04.1" is not itself in the leaf set.
    assert coicop_codes.shares_single_class(["04.1.1", "04.1.2"]) is True
    assert coicop_codes.is_narrow(["04.1.1", "04.1.2"], LEAVES) is False


def test_cpi_publisher_multi_division_list_unchanged_classifier_runs():
    # A CPI publisher declaring coverage scope across many divisions, e.g.
    # sib_cpi / statssa_cpi declaring ["01", "02", ..., "13"]. Never narrow —
    # not by the old rule (no single shared prefix) and not by the new one.
    codes = [f"{i:02d}" for i in range(1, 14)]
    assert coicop_codes.shares_single_class(codes) is False
    assert coicop_codes.is_narrow(codes, LEAVES) is False


def test_unknown_code_does_not_short_circuit():
    # A code entirely absent from the taxonomy fails the leaf-membership
    # check the same way a real parent node does.
    assert coicop_codes.is_narrow(["08.1.0"], LEAVES) is False


def test_is_narrow_empty_or_none_codes():
    assert coicop_codes.is_narrow([], LEAVES) is False
    assert coicop_codes.is_narrow(None, LEAVES) is False


def test_resolved_code_multi_code_still_truncates():
    # resolved_code's multi-code truncation branch is retained: is_narrow is
    # the sole gate on correctness, so a truncated non-leaf code is simply
    # never accepted by is_narrow, never stamped by the caller.
    assert coicop_codes.resolved_code(["04.1.1", "04.1.2"]) == "04.1"
