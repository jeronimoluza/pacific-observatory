"""SC3 unmask + SC4 non-perturbation for the additive `extract_pack(with_id=True)`
channel (Phase 1.66 Wave 3).

Two INDEPENDENT assertions so a display change can never mask a behavior change:

* Assertion A (SC3 display): with the §9 recorder armed over canon-path names, the
  match log surfaces the real winning bucket id (VALUE_UNIT / VALUE_UNIT_ZH /
  NUM_X_VALUE_UNIT / the early-return NUM_PCS morphology) — the opaque
  `pack_lang` / `pack_none` / `secondary_vu` literals no longer appear as a
  `regex_id` for those rows.
* Assertion B (SC4 non-perturbation): `extract()` returns byte-identical
  `StructuralFields` recorder-OFF vs recorder-ON, and the 5-tuple `with_id` return
  agrees with the 4-tuple default on its first four elements for every name.

Data safety (CLAUDE.md): every write target is `tmp_path`; nothing under `data/`
or `outputs/` is touched.
"""

from __future__ import annotations

import pytest

from prices.enrich import match_record
from prices.enrich.extract import extract
from prices.enrich.normalize import extract_pack

pytestmark = pytest.mark.unit

# (name, lang, expected real winning bucket id surfaced on the canon path)
_CASES = [
    ("Coca-Cola 500ml", "en", "VALUE_UNIT"),
    ("可口可樂 1.5公升", "zh", "VALUE_UNIT_ZH"),
    ("Plain Crackers 4x20g", "en", "NUM_X_VALUE_UNIT"),
    # total-breakdown early-return branch: the count marker fires first and the
    # value+unit is rescanned, so the surfaced morphology is the count id.
    ("Thin Sausages 24 Pack 1.8kg", "en", "NUM_PCS"),
]

_OPAQUE_IDS = {"pack_lang", "pack_none", "secondary_vu"}


def test_canon_path_surfaces_real_ids(tmp_path):
    import pandas as pd

    match_record.enable(out_dir=tmp_path)
    try:
        for row_id, (name, lang, _expected) in enumerate(_CASES):
            match_record.begin_row(row_id, name, name, None, "")
            tier_a = extract(item_name=name, category=None, country=None, lang=lang)
            match_record.end_row(tier_a)
        match_record.flush(out_dir=tmp_path)
    finally:
        match_record.disable()

    match_df = pd.read_parquet(tmp_path / "match_log_long.parquet")

    for row_id, (name, _lang, expected) in enumerate(_CASES):
        ids = set(match_df[match_df["row_id"] == row_id]["regex_id"])
        assert expected in ids, f"{name!r}: expected {expected!r} in {ids!r}"
        assert ids.isdisjoint(_OPAQUE_IDS), f"{name!r}: opaque id surfaced in {ids!r}"


def test_no_match_candidates_read_no_match(tmp_path):
    """A bare item with no structural match surfaces `no_match` on the empty-span
    candidates — never the opaque `pack_lang` / `pack_none` / `VALUE_UNIT`
    fallback literals (SC3 refinement)."""
    import pandas as pd

    name = "Plain Spiral Notebook"
    match_record.enable(out_dir=tmp_path)
    try:
        match_record.begin_row(0, name, name, None, "")
        tier_a = extract(item_name=name, category=None, country=None, lang="en")
        match_record.end_row(tier_a)
        match_record.flush(out_dir=tmp_path)
    finally:
        match_record.disable()

    match_df = pd.read_parquet(tmp_path / "match_log_long.parquet")
    ids = set(match_df[match_df["row_id"] == 0]["regex_id"])

    assert "no_match" in ids, f"expected 'no_match' in {ids!r}"
    assert ids.isdisjoint(
        {"pack_lang", "pack_none", "VALUE_UNIT"}
    ), f"opaque fallback literal surfaced on no-match row: {ids!r}"


def test_off_equals_on_and_with_id_non_perturbation():
    for name, lang, _expected in _CASES:
        off = extract(item_name=name, category=None, country=None, lang=lang)

        match_record.enable()
        try:
            match_record.begin_row(0, name, name, None, "")
            on = extract(item_name=name, category=None, country=None, lang=lang)
            match_record.end_row(on)
        finally:
            match_record.disable()

        assert off == on, f"{name!r}: OFF != ON StructuralFields"
        assert extract_pack(name, lang, with_id=True)[:4] == extract_pack(
            name, lang
        ), f"{name!r}: with_id 5-tuple[:4] != 4-tuple"
