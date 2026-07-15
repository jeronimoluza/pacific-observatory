"""SC1 bucket-layout invariants for the tier-a regex reorg (Phase 01.66 / Plan 03).

Asserts the morphology-bucket carving the reorg introduced:
  * every registry pattern carries a non-null ``bucket`` in the five-bucket set;
  * every id is SCREAMING_SNAKE;
  * the bucket cardinalities are exactly 4 / 4 / 11 / 27 / 1;
  * VERSION_CJK is parked (kind="unrouted") and absent from every composed bucket;
  * the ``script`` field is set iff the pattern lived under script/<family>/.

Plus the rename-grep gate (threat T-01.66-05): no live cascade module may still
contain an OLD id string from the RENAME domain — a missed literal rename would
break behavior silently.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from rename_map import RENAME

pytestmark = pytest.mark.unit

_BUCKETS = {"per_unit_marker", "single_measure", "multipack", "count_pack", "_unrouted"}
_SCREAMING_SNAKE = re.compile(r"^[A-Z0-9_]+$")

_EXPECTED_CARDINALITY = {
    "per_unit_marker": 4,
    "single_measure": 4,
    "multipack": 11,
    "count_pack": 31,
    "_unrouted": 1,
}

# Patterns that lived under script/<family>/ pre-reorg — the ONLY ones that carry
# a non-null script field. Everything under shared/* and lang/<lang>/* is
# script=None even when it contains CJK/Latin characters (the FIELD MAPPING).
_SCRIPT_CJK = {
    "CJK_MAI",
    "CJK_PAIR",
    "CJK_GRAIN",
    "CJK_STRIP",
    "CJK_SHEET",
    "CJK_SET",
    "VERSION_CJK",
    "CJK_NUMERAL_SET",
    "CJK_KO_PCS",
    "CJK_N_X_COUNT",
    "CJK_DOUBLE_PACK",
    "INNER_X_OUTER_STAR",
    "INNER_X_OUTER",
}
_SCRIPT_LATIN = {
    "EN_CAPS",
    "EN_TABLETS",
    "EN_SACHETS",
    "EN_SHEETS",
    "EN_PACK_OF",
    "EN_N_PACK",
    "EN_N_INDIVIDUAL_PACK",
    "EN_HALF_DOZEN",
    "EN_DOZEN",
    "EN_TWIN_PACK",
    "EN_TRIPLE_PACK",
    "EN_DOUBLE_PACK",
    "EN_COUNT_NUM_NOUN",
    "EN_COUNT_NOUN_TRAIL",
}


def _index() -> dict:
    from prices.enrich.regex_patterns._registry import _INDEX

    return _INDEX


def test_every_pattern_has_a_valid_bucket() -> None:
    bad = {
        pid: p.bucket for pid, (p, _) in _index().items() if p.bucket not in _BUCKETS
    }
    assert not bad, f"patterns with missing/invalid bucket: {bad}"


def test_every_id_is_screaming_snake() -> None:
    bad = sorted(pid for pid in _index() if not _SCREAMING_SNAKE.match(pid))
    assert not bad, f"non-SCREAMING_SNAKE ids: {bad}"


def test_bucket_cardinalities() -> None:
    from collections import Counter

    counts = Counter(p.bucket for p, _ in _index().values())
    assert dict(counts) == _EXPECTED_CARDINALITY


def test_version_cjk_is_parked_and_unrouted() -> None:
    from prices.enrich.regex_patterns.dict_view import (
        pack_patterns_for_normalize,
        regex_units_for_extract,
    )

    idx = _index()
    pat, _ = idx["VERSION_CJK"]
    assert pat.kind == "unrouted"
    assert pat.bucket == "_unrouted"

    _um, eu, ec, mp, _promo, _bundle, pbm = regex_units_for_extract()
    composed = (
        {p["id"] for p in pack_patterns_for_normalize()}
        | {e["id"] for e in eu}
        | {e["id"] for e in ec}
        | {e["id"] for e in mp}
        | {e["id"] for e in pbm}
    )
    assert "VERSION_CJK" not in composed


def test_script_field_set_iff_under_script_family() -> None:
    idx = _index()
    script_set = {pid for pid, (p, _) in idx.items() if p.script is not None}
    assert script_set == (_SCRIPT_CJK | _SCRIPT_LATIN)
    for pid in _SCRIPT_CJK:
        assert idx[pid][0].script == "cjk", pid
    for pid in _SCRIPT_LATIN:
        assert idx[pid][0].script == "latin", pid


# --------------------------------------------------------------------------- #
# Rename-grep gate (T-01.66-05): no OLD id may survive in a live cascade module.
# Scoped to the live path only — tools/ and static/*.yaml are documented-stale.
# --------------------------------------------------------------------------- #
_SRC = Path(__file__).resolve().parents[3] / "src" / "prices" / "enrich"
_LIVE_CASCADE_MODULES = (
    _SRC / "normalize.py",
    _SRC / "extract.py",
    _SRC / "extract_patterns.py",
    _SRC / "extract_decide.py",
    _SRC / "regex_patterns" / "dict_view.py",
)


@pytest.mark.parametrize("module", _LIVE_CASCADE_MODULES, ids=lambda p: p.name)
def test_no_old_id_survives_in_live_module(module: Path) -> None:
    text = module.read_text(encoding="utf-8")
    survivors = sorted(
        old for old in RENAME if re.search(rf"\b{re.escape(old)}\b", text)
    )
    assert not survivors, f"{module.name} still references old ids: {survivors}"
