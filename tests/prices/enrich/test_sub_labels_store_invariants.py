"""Invariant gate for the rebuilt 538-leaf short-item sub-label store (Plan 02).

Locks the digit invariant (538 = 269 food-5-digit + 269 non-food-4-digit + 0
food-4-digit), in-xlsx grounding of food leaf keys, English-only keywords,
prose-free labels, the food numeric_id == 5-digit-key rule, and that every
class 01..15 still loads through the registry without raising (proves the
class-tree reconciliation holds).
"""

from __future__ import annotations

import json
import re
import warnings
from collections import defaultdict
from pathlib import Path

import pandas as pd
import pytest

from prices.enrich import config
from prices.enrich.keywords import _registry as registry

_STORE_PATH = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "prices"
    / "enrich"
    / "keywords"
    / "coicop"
    / "_sub_labels_store.json"
)

_PROSE_SUBSTRINGS = ("n.e.c.", "including", "in the form of")


def _clear_caches() -> None:
    registry._class_store.cache_clear()
    registry._sub_labels_store.cache_clear()


@pytest.fixture(autouse=True)
def _reset_caches():
    _clear_caches()
    yield
    _clear_caches()


def _load_store() -> dict:
    return json.loads(_STORE_PATH.read_text())


def _all_records(store: dict):
    for cc in store:
        for leaf_code, records in store[cc].items():
            for rec in records:
                yield cc, leaf_code, rec


def _leaf_keys(store: dict) -> list[str]:
    return [lc for cc in store for lc in store[cc]]


def test_leaf_count_invariant():
    store = _load_store()
    leaves = _leaf_keys(store)
    food5 = [c for c in leaves if c.startswith("01") and c.count(".") == 4]
    nf4 = [c for c in leaves if not c.startswith("01") and c.count(".") == 3]
    food4 = [c for c in leaves if c.startswith("01") and c.count(".") == 3]
    assert len(leaves) == 538, len(leaves)
    assert len(food5) == 269, len(food5)
    assert len(nf4) == 269, len(nf4)
    assert len(food4) == 0, food4


@pytest.mark.integration
def test_food_leaf_keys_grounded_in_xlsx():
    store = _load_store()
    df = pd.read_excel(config.COICOP_XLSX)
    df = df[df["code"].notna()].copy()
    df["code"] = df["code"].astype(str)
    xlsx_codes = set(df["code"])
    for lc in store.get("01", {}):
        assert lc.count(".") == 4, lc
        assert lc in xlsx_codes, lc


def test_english_only_keywords():
    store = _load_store()
    for _cc, _lc, rec in _all_records(store):
        assert set(rec["keywords_by_lang"]) == {"en"}, rec


def test_no_prose_labels():
    store = _load_store()
    for _cc, _lc, rec in _all_records(store):
        label = rec["label"]
        assert not label.startswith("Other "), label
        for bad in _PROSE_SUBSTRINGS:
            assert bad not in label, label


def test_numeric_id_rule():
    store = _load_store()
    for lc, records in store.get("01", {}).items():
        for rec in records:
            assert rec["numeric_id"] == lc, (lc, rec["numeric_id"])
    for cc in store:
        if cc == "01":
            continue
        for _lc, records in store[cc].items():
            for rec in records:
                assert rec["numeric_id"] is None, (cc, rec["numeric_id"])


@pytest.mark.integration
def test_registry_loads_all_classes():
    _clear_caches()
    for i in range(1, 16):
        cc = f"{i:02d}"
        klass = registry.load(cc)
        assert klass is not None, cc


# --- Phase 0.9 atomization acceptance gates (SC-2/SC-3/SC-4) ---------------
#
# These validators are RED against the CURRENT (un-atomized) store on purpose:
# they lock the acceptance gate before Wave 1 touches the data. They go GREEN
# only once the atomization pass fills the 48 thin leaves and rewrites the
# labels into atomic/clean/case-deduped forms.

# Standalone parenthetical durability tokens (UN COICOP nd/s/sd/d markers).
_DURABILITY_TOKENS = frozenset({"nd", "s", "sd", "d"})
_DURABILITY_RE = re.compile(
    r"\((" + "|".join(sorted(_DURABILITY_TOKENS, key=len, reverse=True)) + r")\)",
    re.IGNORECASE,
)
# Conjunctions joining two items (surrounded by spaces so we never trip on a
# substring like "sand" / "for").
_CONJUNCTION_RE = re.compile(r"\s+(and|or)\s+", re.IGNORECASE)
_SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_LONG_SLUG_MAX = 15
_LONG_SLUG_AUDIT = config.ENRICH_DIR / "_audit" / "long_slug_ids.json"

# The 5 ROADMAP-SC-4 named worked-example transforms. Single source of truth —
# Plan 03's spot-review harness and SPOT-REVIEW.md reference this constant.
# Each entry: (leaf_code, present_ids, absent_ids).
_WORKED_EXAMPLES = [
    ("01.1.1.2.1", ("wheat-flour",), ("flour-of-wheat",)),
    ("01.1.6.3.1", ("fresh-apples",), ("apples-fresh",)),
    (
        "01.1.2.1.3",
        ("live-goat", "live-lamb", "live-sheep"),
        ("goats-lambs-and-sheep-live",),
    ),
    (
        "01.1.2.2.1",
        (
            "fresh-buffalo-meat",
            "chilled-buffalo-meat",
            "frozen-buffalo-meat",
            "fresh-cattle-meat",
            "chilled-cattle-meat",
            "frozen-cattle-meat",
        ),
        ("fresh-chilled-or-frozen-meat-of", "buffaloes", "cattle"),
    ),
    (
        "01.1.4.1.2",
        ("raw-buffalo-milk", "whole-buffalo-milk"),
        ("raw-and-whole-milk-of-buffaloes",),
    ),
]

# Worked-example leaf codes, exported for Plan 03's spot-review harness.
_WORKED_EXAMPLE_LEAVES = [lc for lc, _present, _absent in _WORKED_EXAMPLES]


def test_every_leaf_non_empty():
    """SC-2: every one of the 538 leaves carries at least one record.

    RED today (48 empty leaves: 42 div-01, 5 div-14, 1 div-15); GREEN only
    after thin-leaf enrichment fills them all."""
    store = _load_store()
    empty = [
        lc
        for lc, recs in ((lc, recs) for cc in store for lc, recs in store[cc].items())
        if not recs
    ]
    assert (
        not empty
    ), f"{len(empty)} empty leaves (expected 0 post-atomization): {sorted(empty)[:10]}"


def test_labels_atomic_clean():
    """SC-3: every label is atomic & clean — no n.e.c., no leading "Other ",
    no colon, no durability marker, no multi-clause comma/semicolon run, no
    standalone " and "/" or " conjunction joining two items."""
    store = _load_store()
    offenders: list[tuple[str, str, str]] = []
    for _cc, lc, rec in _all_records(store):
        label = rec["label"]
        low = label.lower()
        if (
            "n.e.c." in low
            or low.startswith("other ")
            or ":" in label
            or "," in label
            or ";" in label
            or _DURABILITY_RE.search(label)
            or _CONJUNCTION_RE.search(label)
        ):
            offenders.append((lc, rec["id"], label))
    assert (
        not offenders
    ), f"{len(offenders)} non-atomic/unclean labels (expected 0): {offenders[:10]}"


def test_case_deduped():
    """SC-4a: within each (leaf_code, id) group no two labels are equal after
    .lower(), and no record's en keyword list contains a case-variant pair.

    RED today (426 records carry a [label, label.lower()] keyword pair)."""
    store = _load_store()
    label_groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    kw_offenders: list[tuple[str, str]] = []
    for _cc, lc, rec in _all_records(store):
        label_groups[(lc, rec["id"])].append(rec["label"])
        kws = rec["keywords_by_lang"].get("en", [])
        if len({k.lower() for k in kws}) != len(kws):
            kw_offenders.append((lc, rec["id"]))
    label_offenders = [
        (lc, _id)
        for (lc, _id), labels in label_groups.items()
        if len({lbl.lower() for lbl in labels}) != len(labels)
    ]
    offenders = label_offenders + kw_offenders
    assert (
        not offenders
    ), f"{len(offenders)} case-variant id-groups (expected 0): {offenders[:10]}"


def test_id_slug_format():
    """SC-4b: every id is lowercase, hyphen/alnum-only (modifier-first slug).

    ids > 15 chars are NOT a hard failure (legit compounds like
    `fresh-buffalo-meat` = 17) — they are soft-flagged via warnings.warn and
    routed to the long-slug justification surface for spot-review."""
    store = _load_store()
    bad_format: list[str] = []
    long_ids: list[str] = []
    for _cc, _lc, rec in _all_records(store):
        slug = rec["id"]
        if not _SLUG_RE.match(slug):
            bad_format.append(slug)
        if len(slug) > _LONG_SLUG_MAX:
            long_ids.append(slug)

    long_ids = sorted(set(long_ids))
    _LONG_SLUG_AUDIT.parent.mkdir(parents=True, exist_ok=True)
    _LONG_SLUG_AUDIT.write_text(json.dumps(long_ids, indent=2, ensure_ascii=False))
    if long_ids:
        warnings.warn(
            f"{len(long_ids)} ids exceed {_LONG_SLUG_MAX} chars; routed to "
            f"{_LONG_SLUG_AUDIT} for spot-review justification",
            stacklevel=1,
        )

    assert not bad_format, (
        f"{len(bad_format)} ids violate slug format (lowercase hyphen/alnum): "
        f"{sorted(set(bad_format))[:10]}"
    )


@pytest.mark.parametrize(
    "leaf_code,present_ids,absent_ids",
    _WORKED_EXAMPLES,
    ids=[lc for lc, _p, _a in _WORKED_EXAMPLES],
)
def test_worked_example_atomization(leaf_code, present_ids, absent_ids):
    """ROADMAP-SC-4: the 5 NAMED worked-example transforms ARE the phase goal.

    RED today (the un-atomized store still has the source rows like
    `flour-of-wheat`); GREEN only after Wave 2 atomizes the store. A missing
    leaf code is a HARD failure (not a skip) so the gate can never pass
    vacuously."""
    store = _load_store()
    flat = {lc: recs for cc in store for lc, recs in store[cc].items()}
    assert leaf_code in flat, (
        f"worked-example leaf {leaf_code} not present in store keys — fix the "
        "code against _sub_labels_store.json"
    )
    ids = {rec["id"] for rec in flat[leaf_code]}
    missing_present = [i for i in present_ids if i not in ids]
    leaked_absent = [i for i in absent_ids if i in ids]
    assert not missing_present and not leaked_absent, (
        f"{leaf_code}: missing atomized ids {missing_present}; "
        f"un-atomized ids still present {leaked_absent}; current ids={sorted(ids)}"
    )
