"""SC1 structural test — decide() precedence is DATA, not pure control flow.

Phase 1.5 inverted the tier-(a) cascade from a first-match-wins nested if/elif
chain to enumerate-then-decide: ``enumerate_candidates`` records every matcher
fire as a ``Candidate``, and ``decide`` selects among them by walking an explicit
ordered precedence table. This test asserts that contract structurally:

  1. ``decide`` consumes a ranked candidate list (its first parameter is the
     candidate sequence) and ``Candidate`` is the public record type.
  2. The 9-rung precedence ladder is exposed as an ordered data structure
     (``_RUNGS``) the test can introspect — confirming the ranks are sequential
     1..9 and appear in the load-bearing order
     apos > pharma > pack_unit > extra_entry > basis_marker > multi_pack >
     pack_count>1 > extra_count>1 > item.

If the ladder regressed back into a hidden nested if/elif chain, ``_RUNGS`` would
not exist (or would not be an ordered, introspectable sequence) and this fails.
"""

from __future__ import annotations

import inspect

from prices.enrich import extract_decide
from prices.enrich.extract_decide import Candidate, _RUNGS, decide

# The faithful port's load-bearing order (RESEARCH Q1 precedence ladder).
_EXPECTED_RUNG_ORDER = [
    "_rung_apos_pred",
    "_rung_pharma_pred",
    "_rung_pack_unit_pred",
    "_rung_extra_entry_pred",
    "_rung_basis_marker_pred",
    "_rung_multi_pack_pred",
    "_rung_pack_count_pred",
    "_rung_extra_count_pred",
    "_rung_item_pred",
]


def test_decide_consumes_a_candidate_list():
    """decide()'s first parameter is the enumerated candidate sequence, and
    Candidate is a public dataclass carrying the matcher-fire record."""
    params = list(inspect.signature(decide).parameters.values())
    assert params, "decide() must take at least one parameter"
    assert params[0].name == "candidates"
    # Candidate is the record type the enumerate step produces.
    assert hasattr(Candidate, "__dataclass_fields__")
    for field in ("source", "groups", "source_string"):
        assert field in Candidate.__dataclass_fields__


def test_precedence_is_an_ordered_data_table():
    """The 9-rung ladder is exposed as an ordered, introspectable structure."""
    assert isinstance(_RUNGS, (list, tuple)), "_RUNGS must be an ordered sequence"
    assert len(_RUNGS) == 9, "expected exactly 9 precedence rungs"
    # Each rung is (rank, predicate, emitter); ranks are sequential 1..9.
    ranks = [rung[0] for rung in _RUNGS]
    assert ranks == list(range(1, 10)), f"ranks not sequential 1..9: {ranks}"
    for rung in _RUNGS:
        assert len(rung) == 3
        _rank, predicate, emitter = rung
        assert callable(predicate)
        assert callable(emitter)


def test_rungs_appear_in_load_bearing_precedence_order():
    """The predicates appear in the apos > pharma > … > item order; this order
    is the spec and must not silently reshuffle."""
    order = [rung[1].__name__ for rung in _RUNGS]
    assert order == _EXPECTED_RUNG_ORDER


def test_decide_is_data_driven_not_a_hidden_if_chain():
    """decide() walks _RUNGS (the data table) rather than encoding the ladder as
    its own nested if/elif chain. Proxy: the rung predicates/emitters are module
    -level objects referenced by _RUNGS, and decide's source iterates them."""
    src = inspect.getsource(decide)
    assert "_RUNGS" in src, "decide() must consult the _RUNGS data table"
    # The rung emitters live as named module objects (data), not inline branches.
    for name in _EXPECTED_RUNG_ORDER:
        assert hasattr(extract_decide, name)
