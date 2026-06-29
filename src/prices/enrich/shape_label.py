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


def _accounted_numbers(events, sf):
    accounted = set()
    for ev in events:
        amt = ev.get("candidate_amount")
        if ev.get("candidate_unit") is not None and amt is not None:
            accounted.add(int(amt))
        mult = ev.get("candidate_multiplier")
        if mult is not None:
            accounted.add(int(mult))
    if sf is not None:
        if sf.multiplier is not None:
            accounted.add(int(sf.multiplier))
        if sf.count is not None:
            accounted.add(int(sf.count))
    return accounted


def _orphan_number(name, events, sf):
    # A `numeric_nonquantity`: a digit run in the name that is neither a
    # unit-bearing amount, a multiplier, nor a count candidate — demoted to a
    # spec_number modifier (CONTEXT decision 2 / RESEARCH §3 step 5). Reads the
    # accounted values off the candidate set; never re-detects units or counts.
    present = {int(m) for m in _INT_RE.findall(name)}
    return bool(present - _accounted_numbers(events, sf))


def _unit_group_count(events):
    # Distinct (amount, unit) pairs among unit-bearing candidates. The dedup
    # collapses the pack_lang + secondary_vu double-fire on the same `900g`, so
    # `Stage 2 900g` reads as ONE group (A1: unit-bearing groups only).
    groups = set()
    for ev in events:
        unit = ev.get("candidate_unit")
        if unit is not None:
            groups.add((ev.get("candidate_amount"), unit))
    return len(groups)


def _has_count_candidate(events):
    for ev in events:
        if ev.get("_source") == "extra_count" or ev.get("candidate_basis") == "count":
            mult = ev.get("candidate_multiplier")
            if mult is not None and mult > 1:
                return True
    return False


def classify(current, structural_fields):
    if current is None:
        return ("bare_item", [])

    sf = structural_fields
    src = current.get("accepted_source")
    events = current.get("match", [])
    sup = current.get("suppressed_ids", {})
    name = current.get("working_name") or current.get("raw_name") or ""

    dose = _dose_present(name)
    spec = _spec_present(name) or _orphan_number(name, events, sf)
    count_candidate = _has_count_candidate(events)
    unit_groups = _unit_group_count(events)

    basis = sf.pricing_basis if sf is not None else None
    mult = sf.multiplier if sf is not None else None
    is_multipack = sf.is_multipack if sf is not None else None
    measure_basis = basis in ("mass", "volume")

    # First-match interceptor precedence (CONTEXT taxonomy / RESEARCH Finding A).
    if src == "basis_marker":
        shape = "per_unit_priced"
    elif dose and count_candidate and measure_basis:
        # Finding A: the dose mass won the rung but the count is the sellable
        # quantity — `1000mg 60 tablets` / `60'S`.
        shape = "count_pack"
    elif is_multipack or (mult is not None and mult > 1):
        shape = "multipack_measure"
    elif unit_groups >= 2:
        shape = "multi_measure"
    elif measure_basis and mult in (None, 1) and unit_groups == 1:
        shape = "single_measure"
    elif basis == "count":
        shape = "count_pack"
    else:
        shape = "bare_item"

    modifiers = _read_modifiers(sup)
    if dose and shape not in ("single_measure", "multi_measure"):
        modifiers.append("dosage_strength")
    if spec:
        modifiers.append("spec_number")

    seen = set()
    ordered = []
    for m in _MODIFIER_ORDER:
        if m in modifiers and m not in seen:
            seen.add(m)
            ordered.append(m)
    return (shape, ordered)
