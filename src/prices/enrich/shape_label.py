"""Tier (a) row-morphology shape labeler (Phase 1.65).

A pure, side-channel classifier that rides beside the enumerate-then-decide
ladder: given the §9 recorder's per-row buffer (`match_record._CURRENT`) plus the
tier-a `StructuralFields`, it returns exactly one primary `shape` from `SHAPES`
and zero-or-more `modifiers` from `MODIFIERS`. It never mutates its inputs and is
never wired into `extract()`'s active path, so the OFF-equivalence guarantee
(SC4) holds for free.

This module imports only stdlib `re` at top — NOT `match_record`, `extract`, or
`extract_decide` — so the labeler stays isolated and `end_row` can lazy-import it
without an import cycle (Plan 03).
"""

from __future__ import annotations

import re  # noqa: F401  (used by the dose/spec detectors authored in Plan 02)

# The six primary shape labels (top-down precedence; exactly one per row).
SHAPES = frozenset(
    {
        "per_unit_priced",
        "multi_measure",
        "multipack_measure",
        "single_measure",
        "count_pack",
        "bare_item",
    }
)

# The six modifier tokens (zero-or-more per row): the four §9 suppression reasons
# emitted by decide() plus the two the labeler computes fresh (dosage_strength,
# spec_number).
MODIFIERS = frozenset(
    {
        "dosage_strength",
        "spec_number",
        "marketing_limit",
        "appliance_capacity",
        "servings_portion",
        "total_breakdown",
    }
)


def classify(current, structural_fields):
    # Wave-0 stub: returns the fallthrough shape. Plan 02 fills the interceptor
    # precedence (dose/spec detectors + candidate-set + StructuralFields reads).
    return ("bare_item", [])
