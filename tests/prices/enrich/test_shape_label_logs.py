"""Held-out, non-circular bucket-invariant property test for the row-morphology
shape labeler (Phase 1.65, Wave 0).

This rides the armed §9 recorder over a read-only sample of real product names
from the deduped enrich cache, flushes the three logs to `tmp_path`, and asserts
**bucket invariants against the recorder's own RAW fields** (candidate_unit,
candidate_multiplier, accepted_source) — NOT against the labeler's emitted shape.
A row that fails an invariant is therefore a genuine defect, not a tautology
(VALIDATION "Property check over armed §9 logs").

Data safety (CLAUDE.md): the deduped cache is read READ-ONLY for input names;
every write target is `tmp_path`. Nothing under `data/` or `outputs/` is touched.

Wave-0 state: the labeler is still the stub and Plan 03 has not yet persisted the
`shape` column on residual_log, so the test SKIPS cleanly. It also skips when the
cache is unavailable. It never errors on collection.
"""

from __future__ import annotations

import pytest

from prices.enrich import match_record
from prices.enrich.extract import extract
from prices.enrich.shape_label import SHAPES
from prices.enrich.tier_b import cache as cache_module

pytestmark = [pytest.mark.integration, pytest.mark.slow]

_SAMPLE_SIZE = 500
_NAME_COLUMN = "product_name_original"


def _sample_names():
    """Up to `_SAMPLE_SIZE` non-empty product names from the deduped cache, or
    None when the cache is absent/empty (caller skips)."""
    df = cache_module.read_cache()
    if df is None or df.empty or _NAME_COLUMN not in df.columns:
        return None
    names = [n for n in df[_NAME_COLUMN].dropna().astype(str).tolist() if n.strip()]
    return names[:_SAMPLE_SIZE] if names else None


def test_shape_buckets_are_clean_over_armed_logs(tmp_path):
    names = _sample_names()
    if names is None:
        pytest.skip("Deduped enrich cache unavailable — cannot sample held-out names")

    import pandas as pd

    match_record.enable(out_dir=tmp_path)
    try:
        for row_id, name in enumerate(names):
            match_record.begin_row(row_id, name, name, None, "")
            tier_a = extract(item_name=name, category=None, country=None, lang=None)
            match_record.end_row(tier_a)
        match_record.flush(out_dir=tmp_path)
    finally:
        match_record.disable()

    residual = pd.read_parquet(tmp_path / "residual_log.parquet")
    match_df = pd.read_parquet(tmp_path / "match_log_long.parquet")

    if "shape" not in residual.columns:
        pytest.skip("shape column not yet persisted on residual_log (pre-Plan-03)")

    # Invariant 5 (membership): exactly one primary shape per row, all in SHAPES.
    assert residual["shape"].notna().all()
    assert set(residual["shape"]).issubset(SHAPES)

    has_modifiers = "modifiers" in residual.columns

    for rec in residual.to_dict("records"):
        rid = rec["row_id"]
        shape = rec["shape"]
        events = match_df[match_df["row_id"] == rid]
        accepted = events[events["accepted"].fillna(False)]

        if shape == "single_measure":
            # Invariant 1: exactly one distinct (amount, unit) group among the
            # unit-bearing events — the labeler's A1 dedup collapses the
            # pack_lang/pack_none/secondary_vu double-fire on the same measure.
            unit_events = events[events["candidate_unit"].notna()]
            groups = set(
                zip(unit_events["candidate_amount"], unit_events["candidate_unit"])
            )
            assert len(groups) == 1, f"row {rid}: single_measure unit groups"

        elif shape == "multipack_measure":
            # Invariant 2: candidate_multiplier > 1 on the accepted/pack candidate.
            mult = accepted["candidate_multiplier"].dropna()
            assert (mult > 1).any(), f"row {rid}: multipack_measure multiplier"

        elif shape == "bare_item":
            # Invariant 3: no measure surfaced to the labeler — either the item
            # fallback won the rung, or no unit-bearing candidate exposed a
            # distinct (amount, unit) group (e.g. a vi_lit_volume accept whose
            # recorder candidate_unit is None still reads as zero unit groups).
            unit_events = events[events["candidate_unit"].notna()]
            unit_groups = set(
                zip(unit_events["candidate_amount"], unit_events["candidate_unit"])
            )
            assert (
                rec["accepted_source"] == "item" or len(unit_groups) == 0
            ), f"row {rid}: bare_item source"

        elif shape == "count_pack":
            # Invariant 4: a count candidate (count basis / multiplier>1) OR an
            # intercepted dose (dosage_strength modifier).
            count_candidate = bool(
                (events["candidate_basis"] == "count").any()
                or (events["candidate_multiplier"].dropna() > 1).any()
            )
            dose = False
            if has_modifiers:
                mods = rec["modifiers"]
                dose = mods is not None and "dosage_strength" in str(mods)
            assert count_candidate or dose, f"row {rid}: count_pack count/dose"
