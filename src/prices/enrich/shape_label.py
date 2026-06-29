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

import re

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


# Deterministic emit order for the modifier list (stable test + JSON output).
_MODIFIER_ORDER = (
    "dosage_strength",
    "spec_number",
    "marketing_limit",
    "appliance_capacity",
    "servings_portion",
    "total_breakdown",
)

# The four §9 suppression reasons the labeler READS off the recorder's
# `suppressed_ids` (the other two — dosage_strength, spec_number — are computed
# fresh). dosage_strength is in REASON_TOKENS but never recorded, so it is not
# read here.
_READ_MODIFIERS = frozenset(
    {
        "marketing_limit",
        "appliance_capacity",
        "servings_portion",
        "total_breakdown",
    }
)

# Bare-dose detector: the mg/mcg/µg alternation lifted from `_PHARMA_PER_UNIT_RE`
# (extract_patterns.py:85-93), with IU added and the Tablet/Capsule adjacency
# DROPPED — `1000mg 60 tablets` breaks adjacency, so the pharma regex misses it.
# Keys on the dose UNIT, never on magnitude (`7g lip balm` is mass, not a dose).
# Linear: one quantifier per token, no nested quantifier (ReDoS gate T-1.65-01).
_DOSE_RE = re.compile(r"\d+(?:[.,]\d+)?\s*(?:mg|MG|Mg|mcg|MCG|µg|ug|IU)\b")

# High-precision spec detectors (A3, precision-first): SPF, percentage, 4-digit
# year, and a glued model token. Every pattern is linear with a single bounded
# quantifier per token — no `.*`/`.+` nesting (ReDoS gate T-1.65-01).
_SPEC_RES = (
    re.compile(r"SPF\s*\d+", re.IGNORECASE),
    re.compile(r"\d+(?:[.,]\d+)?\s*[%％]"),
    re.compile(r"\b(?:19|20)\d{2}\b"),
    re.compile(r"\b[A-Z]{1,3}\d{3,}\b"),
)

# Plain integer-run locator used to enumerate the numbers present in a name when
# demoting a `numeric_nonquantity` to a spec_number modifier. Single quantifier.
_INT_RE = re.compile(r"\d+")


def _dose_present(text):
    return bool(_DOSE_RE.search(text or ""))


def _spec_present(text):
    t = text or ""
    return any(rx.search(t) for rx in _SPEC_RES)


def _read_modifiers(suppressed_ids):
    present = set((suppressed_ids or {}).values()) & _READ_MODIFIERS
    return [m for m in _MODIFIER_ORDER if m in present]


def classify(current, structural_fields):
    # Wave-0 stub: returns the fallthrough shape. Task 2 fills the interceptor
    # precedence (dose/spec detectors + candidate-set + StructuralFields reads).
    return ("bare_item", [])
