"""Tier (a) decide-step — candidate selection over the enumerated matcher fires.

Split out of `extract.py` (which broke the 500-LoC project cap) so the cascade
can be inverted from first-match-wins short-circuit to enumerate-then-decide.

`enumerate_candidates()` (in `extract.py`) records every matcher fire as a
`Candidate`; `decide()` here ports the Pass 1b-1e adoption guards and the 9-rung
precedence ladder verbatim, expressing the ladder as an explicit ordered data
table rather than nested control flow. Arithmetic is copied character-identical
so `amount_value` stays bit-identical to the pre-refactor cascade.

The helper predicates / regexes / maps live in `extract.py` (imported below) and
must stay byte-unchanged. `extract_pack` (in `normalize.py`, shared with
`canonicalize`) is a black box consumed here only for the Pass-1c substring
re-scan, exactly as the original cascade called it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from types import SimpleNamespace

from prices.enrich.extract import (
    _BASIS_TO_SU,
    _BUNDLE_MARKERS,
    _MARKETING_LIMIT_RE,
    _PROMO_MARKERS,
    _SERVINGS_SUFFIX_RE,
    _SU_NORM,
    _UNIT_MAP,
    _VU_RE,
    StructuralFields,
    _is_total_breakdown,
    _markers_fire,
    _value_unit_suppressed,
)
from prices.enrich.normalize import extract_pack


# Loose single-suffix count matchers (bare `\d+s` / `\d+'s`) are eligible to
# promote INTO a co-occurring measure (rung 3's noun_count_raw): the
# bare-adjacency shape (no `X`/`×` operator — that form is a distinct earlier
# candidate, "apos", handled by rung 1) IS the mass->count convention this
# promotion exists for ("Mission Quinoa Wraps 8s 360g" -> count=8). The
# no-measure brand-token case ("333'S OLIVES") never reaches this promotion —
# it requires `st.pack_unit is not None` — so loosening here does not reopen
# that risk. Kept as an explicit hook for any future id that DOES need
# excluding.
_LOOSE_PROMOTE_IDS = frozenset()
_PROMOTE_COUNT_CAP = 144  # a co-occurring measure + count>144 is a size/model artifact
_RANGE_LOW_RE = re.compile(r"\d\s*[-–]\s*$")
# "buy N get M free" bonus-pack idiom ("18+2s"): the suffixed number is a
# promo bonus count, not the pack's piece count — reject it like a range low
# bound (Pass 1b's marketing-limit guard doesn't cover this shape).
_BONUS_PLUS_RE = re.compile(r"\d\s*\+\s*$")
# A bare NS count-suffix PRECEDING the measure ("10s 106g") that is
# IMPLAUSIBLY large for a per-piece pack (e.g. decorative sugar sprinkles
# "100s and 1000s") is a size-descriptor, not a pack quantity. Deliberately a
# NARROW magnitude-only guard, not a general count-before-measure
# suppression: the latter conflicts with the canonical NS gold slice the
# scoreboard gate is built from — e.g. "Laughing Cow Sliced Cheddar Cheese
# 10s 200g" (gold count=10) is the same shape as "Mini Babybel Tasty Cheddar
# Cheese 5s 100g" (corpus holdout, count=1) with opposite truth; no textual
# signal separates them within [8, 30]. 30 is the highest count-before-measure
# value in the gold slice, so gating strictly above it is gate-safe.
_ORDER_GUARDED_IDS = frozenset({"EN_SACHETS", "EN_APOS_S"})
_COUNT_BEFORE_MEASURE_CAP = 30
# A retail pack count above this is not a count: it is an EAN/SKU that trailed a
# pack noun, or a mass/volume figure that lost its unit token. Both fabricate a
# per-piece price by dividing by a huge denominator. Failing the guard drops the
# rung, so the row falls through to `item` -- "no quantity found" -- which the
# SOLD_BY_ITEM_LEAVES gate then quarantines unless the leaf vets it. Guessing
# wrong toward "no quantity" is recoverable; guessing wrong toward a fabricated
# count is not.
_COUNT_PLAUSIBLE_MAX = 1000

# Explicit multiplication operator immediately preceding a promoted count-noun
# match ("1.5g × 20개", "90g*3개입") is the unambiguous "per-unit measure ×
# counter" multipack shape: the counter multiplies the measure, so it belongs
# in `multiplier`, not the UV-inert `count` (Convention A, merge.py:
# compute_unit_value). "x"/"X" additionally require a non-letter neighbor on
# both sides so a brand token ending in the letter x ("Kleenex 20개") never
# misreads as an operator; "×"/"✕"/"*" are unambiguous symbols (never a word's
# trailing letter, e.g. the unit-letter-adjacent "90g*3") so no such guard
# applies to them.
_MULTIPLY_OP_ADJ_RE = re.compile(r"(?:(?<![A-Za-z0-9])[xX](?![A-Za-z])|[×✕*])\s*$")


def _clean_promote_count(ec_cand, stripped: str):
    """The count-noun integer eligible to compose into a measure's count, or None.

    Precision guards (never promote a doubtful token over an explicit measure):
    loose single-suffix ids excluded, pack-size sanity cap, numeric-range low
    bound rejected, bonus-pack "N+Ms" rejected, and (for the bare NS ids only)
    an implausibly large count preceding the measure rejected."""
    if ec_cand is None:
        return None
    n = ec_cand.groups.get("count")
    if not n or n <= 1 or n > _PROMOTE_COUNT_CAP:
        return None
    regex_id = ec_cand.groups.get("regex_id")
    if regex_id in _LOOSE_PROMOTE_IDS:
        return None
    span = ec_cand.span
    if span:
        if _RANGE_LOW_RE.search(
            stripped[max(0, span[0] - 4) : span[0]]
        ) or _BONUS_PLUS_RE.search(stripped[max(0, span[0] - 4) : span[0]]):
            return None
        # servings / marketing-limit clause near the match: a portions count
        # ("50杯分") or a purchase limit, not a pack quantity — mirror Pass 1b2.
        win = stripped[max(0, span[0] - 12) : min(len(stripped), span[1] + 12)]
        if _SERVINGS_SUFFIX_RE.search(win) or _MARKETING_LIMIT_RE.search(win):
            return None
        if (
            regex_id in _ORDER_GUARDED_IDS
            and n > _COUNT_BEFORE_MEASURE_CAP
            and _VU_RE.search(stripped, span[1])
        ):
            return None
    return n


@dataclass(frozen=True)
class Candidate:
    """One recorded matcher fire from the enumerate step.

    `source` tags the matcher origin (pack_lang | pack_none | pack_substr |
    secondary_vu | apos | pharma | extra_unit | extra_count | basis_marker |
    multi_pack); `source_string` tags WHICH string it read (item_name | stripped
    | substring marker) so a ported predicate never reads the wrong string.
    `span` is captured for the Phase 1.6 residual recorder but stays UNWIRED here.
    `groups` carries the raw matcher output the decide step consumes; the optional
    emitted fields mirror StructuralFields slots for forward-compat.
    """

    source: str
    span: tuple[int, int] | None
    source_string: str
    groups: dict
    pricing_basis: str | None = None
    amount_value: float | None = None
    standard_unit: str | None = None
    count: int | None = None
    multiplier: int | None = None


def _resolve_pack(by: dict, *, item_name: str, has_non_ascii: bool):
    """Port of Pass 1b-1e: settle pack_count/pack_value/pack_unit from the
    pack_lang / pack_none candidates, the Pass-1c substring re-scan, the
    secondary value+unit promotion (1d) and the appliance/apparel suppression
    (1e). Guards are byte-identical to the current cascade's if-conditions."""
    from prices.enrich import match_record

    pl = by["pack_lang"].groups
    pack_count, pack_value, pack_unit = pl["count"], pl["value"], pl["unit"]
    pn = by.get("pack_none")

    # Pass 1b: declared-lang matched nothing; retry lang=None result.
    if pack_count is None and pack_value is None and has_non_ascii:
        g = pn.groups
        pack_count, pack_value, pack_unit = g["count"], g["value"], g["unit"]

    # Pass 1b2: value+unit but no outer count; recover a bare lang=None count.
    if pack_value is not None and pack_count is None and has_non_ascii:
        g = pn.groups
        alt_count, alt_value, alt_unit = g["count"], g["value"], g["unit"]
        adopt_alt = alt_count is not None and alt_value is None and alt_unit is None
        if adopt_alt and not _is_total_breakdown(
            item_name, pack_value, pack_unit, alt_count
        ):
            alt_m = re.search(rf"(?<!\d){alt_count}", item_name)
            if alt_m is None:
                pack_count = alt_count
            else:
                a = max(0, alt_m.start() - 12)
                b = min(len(item_name), alt_m.end() + 12)
                window = item_name[a:b]
                if not _MARKETING_LIMIT_RE.search(
                    window
                ) and not _SERVINGS_SUFFIX_RE.search(window):
                    pack_count = alt_count
                elif match_record.is_recording():
                    mkt = _MARKETING_LIMIT_RE.search(window)
                    match_record.record_suppression(
                        suppressed_text=str(alt_count),
                        span=(alt_m.start(), alt_m.end()),
                        suppression_type="match",
                        reason="marketing_limit" if mkt else "servings_portion",
                        regex_id="pack_none",
                    )
        elif adopt_alt and match_record.is_recording():
            match_record.record_suppression(
                suppressed_text=str(alt_count),
                span=None,
                suppression_type="match",
                reason="total_breakdown",
                regex_id="pack_none",
            )

    # Pass 1c: marketing-limit suppression of a count-only match + substring re-scan.
    if pack_count is not None and pack_value is None and pack_unit is None:
        pack_count_m = re.search(rf"(?<!\d){pack_count}", item_name)
        if pack_count_m:
            a = max(0, pack_count_m.start() - 12)
            b = min(len(item_name), pack_count_m.end() + 12)
            if _MARKETING_LIMIT_RE.search(item_name[a:b]):
                if match_record.is_recording():
                    match_record.record_suppression(
                        suppressed_text=str(pack_count),
                        span=(pack_count_m.start(), pack_count_m.end()),
                        suppression_type="match",
                        reason="marketing_limit",
                        regex_id="pack_lang",
                    )
                pack_count = None
                _cleaned, alt_count, alt_value, alt_unit = extract_pack(
                    item_name[pack_count_m.end() :], None
                )
                if alt_value is not None or alt_count is not None:
                    pack_count, pack_value, pack_unit = alt_count, alt_value, alt_unit

    # Pass 1d: promote an embedded value+unit that a count-only match shadowed.
    if pack_count is not None and pack_unit is None and pack_value is None:
        sec = by["secondary_vu"].groups
        if sec["value"] is not None and sec["unit"] is not None:
            pack_value, pack_unit = sec["value"], sec["unit"]

    # Pass 1e: appliance-capacity / apparel-fabric-weight suppression (BUG 3/4).
    if (
        pack_unit is not None
        and _UNIT_MAP.get(pack_unit, {}).get("basis") in ("mass", "volume")
        and _value_unit_suppressed(item_name)
    ):
        if match_record.is_recording():
            vu_m = _VU_RE.search(item_name)
            match_record.record_suppression(
                suppressed_text=item_name[vu_m.start() : vu_m.end()] if vu_m else None,
                span=(vu_m.start(), vu_m.end()) if vu_m else None,
                suppression_type="match",
                reason="appliance_capacity",
                regex_id="VALUE_UNIT",
            )
        pack_value = None
        pack_unit = None

    return pack_count, pack_value, pack_unit


def _apos_um(apos):
    if apos is None:
        return None
    unit_norm = _SU_NORM.get(apos.group("unit"))
    return _UNIT_MAP.get(unit_norm) if unit_norm else None


def _finish(st, pricing_basis, standard_unit, amount_value, count, multiplier):
    """Shared flag block for rungs 3-9 (the non-short-circuit ladder)."""
    is_multipack = (multiplier is not None and multiplier > 1) or (
        pricing_basis == "count" and count is not None and count > 1
    )
    return StructuralFields(
        pricing_basis=pricing_basis,
        amount_value=amount_value,
        standard_unit=standard_unit,
        count=count,
        multiplier=multiplier,
        is_promotion=_markers_fire(st.item_name, st.lang, _PROMO_MARKERS),
        is_bundle=_markers_fire(st.item_name, st.lang, _BUNDLE_MARKERS),
        is_multipack=is_multipack,
        promo_reason=None,
    )


# --- the 9 precedence rungs as data: (rank, predicate, emitter), first wins ----


def _rung_apos_pred(st):
    return _apos_um(st.apos) is not None


def _rung_apos_emit(st):
    um = _apos_um(st.apos)
    value = float(st.apos.group("value").replace(",", "."))
    mult = int(st.apos.group("count"))
    return StructuralFields(
        pricing_basis=um["basis"],
        amount_value=value * float(um["mul"]),
        standard_unit=um["su"],
        count=1,
        multiplier=mult,
        is_promotion=_markers_fire(st.item_name, st.lang, _PROMO_MARKERS),
        is_bundle=_markers_fire(st.item_name, st.lang, _BUNDLE_MARKERS),
        is_multipack=mult > 1,
        promo_reason=None,
    )


def _rung_pharma_pred(st):
    return st.pharma_per_unit


def _rung_pharma_emit(st):
    return StructuralFields(
        pricing_basis="count",
        amount_value=None,
        standard_unit="unit",
        count=1,
        multiplier=1,
        is_promotion=_markers_fire(st.item_name, st.lang, _PROMO_MARKERS),
        is_bundle=_markers_fire(st.item_name, st.lang, _BUNDLE_MARKERS),
        is_multipack=False,
        promo_reason=None,
    )


def _rung_pack_unit_pred(st):
    return st.pack_unit is not None


def _rung_pack_unit_emit(st):
    um = _UNIT_MAP.get(st.pack_unit)
    if um:
        amount_value = (
            st.pack_value * float(um["mul"]) if st.pack_value is not None else None
        )
        multiplier = st.pack_count if st.pack_count and st.pack_count > 0 else 1
        count = 1
        # Faithfully capture a real count-noun integer the measure would else drop
        # (extract() records both a mass/volume AND its piece count; the unit-value
        # calc decides what to do with them). Convention: volume -> multiplier,
        # mass/count -> count. Skip a total-breakdown count ("10kg (5kg×2)"): there
        # the integer is the breakdown of the stated total, not an extra quantity.
        # unit=mg is NOT special-cased here: a milligram figure beside a piece
        # count ("160mg Softgel 100s") is the per-piece drug DOSE, and the
        # trailing count is the genuine pack quantity — the corpus holdout
        # (20260715 NS slice) shows 100/100 mg rows want the count promoted
        # (0 counterexamples); a blanket `pack_unit != "mg"` block was pure
        # recall loss. `_clean_promote_count`'s magnitude cap (above) is the
        # real precision gate now.
        n = st.noun_count_raw
        if (
            n
            and n > 1
            and multiplier == 1
            and not _is_total_breakdown(st.item_name, st.pack_value, st.pack_unit, n)
        ):
            # "<per-unit measure>. Pack N" (e.g. "17.5g. Pack 60sachets") is a
            # MULTIPACK: the measure is per-unit and N multiplies it, whatever the
            # basis. "Pack of N" reads identically and is accepted too -- without
            # the optional `of` the adjacency test silently missed it and the
            # count stayed inert, pricing "41.5g (Pack of 48Pcs)" as a single
            # 41.5g bar. "N Pack <total>" ("Thin Sausages 24 Pack 1.8kg") still
            # does NOT match, because N precedes "Pack" there rather than
            # following it, so its count stays inert as before. Likewise an
            # explicit multiply operator joining the measure and N ("1.5g × 20개")
            # is an unambiguous multipack signal on mass basis too.
            if (
                um["basis"] == "volume"
                or st.noun_count_via_operator
                or re.search(rf"[Pp]ack\s*(?:of\s*)?0*{n}(?!\d)", st.item_name)
            ):
                multiplier = n
            else:
                count = n
        return _finish(st, um["basis"], um["su"], amount_value, count, multiplier)
    return _finish(st, "item", "item", None, 1, 1)


def _rung_extra_entry_pred(st):
    return st.extra_entry is not None


def _rung_extra_entry_emit(st):
    return _finish(
        st,
        st.extra_entry["basis"],
        st.extra_entry["su"],
        st.extra_value * st.extra_entry["mul"],
        1,
        1,
    )


def _rung_basis_marker_pred(st):
    return st.basis_marker is not None


def _rung_basis_marker_emit(st):
    # A bare "Per KG"/"Per L" marker means the price IS already stated per
    # standard unit, i.e. amount_value=1.0 (one kg / one litre) so
    # compute_unit_value's denominator (amount_value * multiplier) collapses to
    # 1 and unit_value == price. amount_value=None (the old behavior) instead
    # made Convention A's mass/volume branch return None outright, silently
    # dropping the unit value for every bare-marker name.
    return _finish(
        st, st.basis_marker, _BASIS_TO_SU.get(st.basis_marker, "item"), 1.0, 1, 1
    )


def _count_is_plausible(n) -> bool:
    return n is None or n <= _COUNT_PLAUSIBLE_MAX


def _rung_multi_pack_pred(st):
    if st.multi_pack is None:
        return False
    inner, outer = st.multi_pack
    return _count_is_plausible(inner) and _count_is_plausible(outer)


def _rung_multi_pack_emit(st):
    inner, outer = st.multi_pack
    return _finish(st, "count", "unit", None, inner, outer)


def _rung_pack_count_pred(st):
    return (
        st.pack_count is not None
        and st.pack_count > 1
        and _count_is_plausible(st.pack_count)
    )


def _rung_pack_count_emit(st):
    return _finish(st, "count", "unit", None, st.pack_count, 1)


def _rung_extra_count_pred(st):
    return (
        st.extra_count is not None
        and st.extra_count > 1
        and _count_is_plausible(st.extra_count)
    )


def _rung_extra_count_emit(st):
    return _finish(st, "count", "unit", None, st.extra_count, 1)


def _rung_item_pred(st):
    return True


def _rung_item_emit(st):
    return _finish(st, "item", "item", None, 1, 1)


_RUNGS = (
    (1, _rung_apos_pred, _rung_apos_emit),
    (2, _rung_pharma_pred, _rung_pharma_emit),
    (3, _rung_pack_unit_pred, _rung_pack_unit_emit),
    (4, _rung_extra_entry_pred, _rung_extra_entry_emit),
    (5, _rung_basis_marker_pred, _rung_basis_marker_emit),
    (6, _rung_multi_pack_pred, _rung_multi_pack_emit),
    (7, _rung_pack_count_pred, _rung_pack_count_emit),
    (8, _rung_extra_count_pred, _rung_extra_count_emit),
    (9, _rung_item_pred, _rung_item_emit),
)

# Maps each winning rung to the candidate source it represents (the §9 match-log
# accepted source). pack_unit (3) and pack_count (7) both resolve from the
# pack candidate, so both map to 'pack_lang'.
_RUNG_SOURCE = {
    1: "apos",
    2: "pharma",
    3: "pack_lang",
    4: "extra_unit",
    5: "basis_marker",
    6: "multi_pack",
    7: "pack_lang",
    8: "extra_count",
    9: "item",
}


def decide(
    candidates,
    *,
    apos,
    pharma_per_unit,
    item_name,
    stripped,
    lang,
    has_non_ascii,
    effective_lang,
):
    """Select a StructuralFields from the enumerated candidate set.

    Ports the cascade's Pass 1b-1e pack refinement (sequential — their order is
    the spec) and then evaluates the 9-rung precedence as an explicit ordered
    data table (`_RUNGS`), first-satisfied-wins. Adoption guards for
    extra_entry / extra_count / basis_marker are byte-identical to the original
    if-conditions, gating which recorded candidate is actually used.
    """
    from prices.enrich import match_record

    by = {c.source: c for c in candidates}

    pack_count, pack_value, pack_unit = _resolve_pack(
        by, item_name=item_name, has_non_ascii=has_non_ascii
    )

    extra_entry, extra_value = (None, None)
    if pack_unit is None:
        c = by.get("extra_unit")
        if c is not None:
            extra_entry, extra_value = c.groups["entry"], c.groups["value"]

    extra_count = None
    if pack_unit is None and extra_entry is None and pack_count is None:
        c = by.get("extra_count")
        extra_count = c.groups["count"] if c is not None else None

    # Count-noun integer promoted into a co-occurring measure's count/multiplier
    # (rung 8 would otherwise drop it). Precision-first: only promote a CLEAN
    # pack-size token — never the loose single-suffix matchers (bare `\d+s` /
    # `\d+'s`, which fire on brands/sizes), never an implausible size, and never
    # a numeric-range low bound (e.g. "9-11pcs" is a size range, not a pack of 11).
    ec_cand = by.get("extra_count")
    noun_count_raw = _clean_promote_count(ec_cand, stripped)

    # Was the promoted count-noun joined to the measure by an explicit
    # multiplication operator ("1.5g × 20개")? If so rung 3 routes it to
    # `multiplier` instead of `count` — see _MULTIPLY_OP_ADJ_RE above.
    noun_count_via_operator = False
    if noun_count_raw is not None and ec_cand is not None and ec_cand.span:
        span = ec_cand.span
        window = stripped[max(0, span[0] - 6) : span[0]]
        noun_count_via_operator = bool(_MULTIPLY_OP_ADJ_RE.search(window))

    basis_marker = None
    if pack_unit is None and extra_entry is None:
        c = by.get("basis_marker")
        basis_marker = c.groups["basis"] if c is not None else None

    c = by.get("multi_pack")
    multi_pack = (c.groups["inner"], c.groups["outer"]) if c is not None else None

    st = SimpleNamespace(
        apos=apos,
        pharma_per_unit=pharma_per_unit,
        item_name=item_name,
        lang=lang,
        pack_count=pack_count,
        pack_value=pack_value,
        pack_unit=pack_unit,
        extra_entry=extra_entry,
        extra_value=extra_value,
        extra_count=extra_count,
        noun_count_raw=noun_count_raw,
        noun_count_via_operator=noun_count_via_operator,
        basis_marker=basis_marker,
        multi_pack=multi_pack,
    )

    for _rank, predicate, emit in _RUNGS:
        if predicate(st):
            if match_record.is_recording():
                match_record.record_accepted(_rank, _RUNG_SOURCE[_rank])
            return emit(st)
    return _rung_item_emit(st)  # unreachable: rung 9 is a catch-all
