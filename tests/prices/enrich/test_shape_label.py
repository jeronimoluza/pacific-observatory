"""SC1 taxonomy/precedence + SC2 worked-case fixtures for the row-morphology
shape labeler (Phase 1.65, Wave 0 — RED baseline).

The four SC2 worked cases are literal expected tuples drawn straight from the
spec (CONTEXT "Worked cases" / VALIDATION "Exact unit fixtures") — they are the
spec, so they cannot be circular. Under the Wave-0 stub (`classify` returns
`("bare_item", [])`) the `worked_cases` asserts FAIL RED at full magnitude (4/4);
Plan 02 turns them GREEN.

The `taxonomy` invariants (shape ∈ SHAPES, modifiers ⊆ MODIFIERS, no duplicate
modifiers, exactly one primary shape as a single string) hold for ANY valid
`classify` output and so pass even under the stub — they pin the SC1 contract
shape. The A1 assertion (`Stage 2 900g` → `single_measure` + `spec_number`, the
unit-bearing-groups reading flagged for user veto at Plan 04) is the one
taxonomy assert that is RED under the stub.

All recorder output is buffered in-memory only (no `flush`), so nothing is
written under `data/`.
"""

from __future__ import annotations

import pytest

from prices.enrich import match_record
from prices.enrich.extract import extract
from prices.enrich.shape_label import MODIFIERS, SHAPES, classify

pytestmark = pytest.mark.unit


def _label(name):
    """Arm the §9 recorder, run the live cascade on `name`, then classify the
    populated `_CURRENT` buffer + the returned StructuralFields BEFORE `end_row`
    clears the buffer. Returns `(shape, modifiers_set)`. Recorder is always
    disabled again, even on assertion failure."""
    match_record.enable(sample_rate=1.0)
    try:
        match_record.begin_row(0, name, name, None, "")
        tier_a = extract(item_name=name, category=None, country=None, lang=None)
        shape, modifiers = classify(match_record._CURRENT, tier_a)
    finally:
        match_record.disable()
    return shape, modifiers


_WORKED_CASES = [
    ("Vitamin C 1000mg 60 tablets", "count_pack", {"dosage_strength"}),
    ("Vitamin C 1000mg 60'S", "count_pack", {"dosage_strength"}),
    ("SPF 50 sunscreen", "bare_item", {"spec_number"}),
    ("250x5g", "multipack_measure", set()),
]


@pytest.mark.parametrize(
    "name, expected_shape, expected_modifiers",
    _WORKED_CASES,
    ids=[c[0] for c in _WORKED_CASES],
)
def test_worked_cases(name, expected_shape, expected_modifiers):
    """SC2 — the four worked cases label exactly as specified. RED under the
    Wave-0 stub (all four resolve to bare_item); GREEN after Plan 02."""
    shape, modifiers = _label(name)
    assert shape == expected_shape
    assert set(modifiers) == expected_modifiers


_TAXONOMY_NAMES = [c[0] for c in _WORKED_CASES] + ["Stage 2 900g"]


@pytest.mark.parametrize("name", _TAXONOMY_NAMES)
def test_taxonomy_invariants(name):
    """SC1 — structural invariants independent of the worked-case labels: a
    single primary shape from the 6-set, modifiers ⊆ the 6-token set, no
    duplicate modifiers. True for any valid classify output (passes under stub)."""
    shape, modifiers = _label(name)
    assert isinstance(shape, str)
    assert shape in SHAPES
    assert all(m in MODIFIERS for m in modifiers)
    assert len(list(modifiers)) == len(set(modifiers))


def test_taxonomy_a1_stage_2_900g():
    """SC1/A1 — `Stage 2 900g` has ONE unit-bearing group (`900g`); under the
    unit-bearing-groups reading it is `single_measure` + `spec_number(2)`, NOT
    `multi_measure` (the design note's example is loose). Flagged assumption A1:
    if the user vetoes at Plan 04, this widens with Plan 02's predicate. RED
    under the Wave-0 stub."""
    shape, modifiers = _label("Stage 2 900g")
    assert shape == "single_measure"
    assert "spec_number" in set(modifiers)
