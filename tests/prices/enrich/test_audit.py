import pytest

from prices.enrich.audit import FLAG, NO_STRUCTURAL, PASS, REJECT, audit

pytestmark = pytest.mark.unit


DENYLIST = {
    "01.1.1.1.1": {
        "excluded": frozenset({"volume"}),
        "action": "reject",
        "semantic": "HIGH",
        "evidence_state": "CONFIRMED",
        "profile": "SOLID",
        "label": "Wheat",
    },
    "01.2.1.0.0": {
        "excluded": frozenset({"mass"}),
        "action": "flag",
        "semantic": "HIGH",
        "evidence_state": "UNOBSERVED",
        "profile": "LIQUID",
        "label": "Juice",
    },
}


def test_pass_when_basis_allowed():
    assert audit("01.1.1.1.1", "mass", DENYLIST) == PASS


def test_reject_when_excluded_and_action_reject():
    assert audit("01.1.1.1.1", "volume", DENYLIST) == REJECT


def test_flag_when_excluded_and_action_flag():
    assert audit("01.2.1.0.0", "mass", DENYLIST) == FLAG


def test_no_structural_when_basis_none():
    assert audit("01.1.1.1.1", None, DENYLIST) == NO_STRUCTURAL


def test_no_structural_when_basis_empty_string():
    assert audit("01.1.1.1.1", "", DENYLIST) == NO_STRUCTURAL


def test_leaf_absent_from_denylist_passes():
    assert audit("99.9.9.9.9", "volume", DENYLIST) == PASS


def test_item_and_count_never_excluded():
    assert audit("01.1.1.1.1", "item", DENYLIST) == PASS
    assert audit("01.1.1.1.1", "count", DENYLIST) == PASS


def test_unobserved_cannot_reject_even_with_high_semantic():
    entry = DENYLIST["01.2.1.0.0"]
    assert entry["semantic"] == "HIGH"
    assert entry["evidence_state"] == "UNOBSERVED"
    assert entry["action"] == "flag"
    assert audit("01.2.1.0.0", "mass", DENYLIST) == FLAG
