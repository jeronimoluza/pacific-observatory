"""Regression: cross_check.lookup_allowed_bases is depth-aware after the
sub-label store moved division-01 (food) leaves from 4-digit to 5-digit.

- Non-food codes still resolve at 4-digit (byte-equivalent to old behavior).
- Food codes resolve at 5-digit: the 5-digit class-tree leaf is found where the
  OLD unconditional 4-digit truncation returned "unknown_leaf".
- SILENT_OVERRIDE arbitration stays alive for food: proven with a SYNTHETIC
  food leaf carrying a singleton allowed_bases (the curated food allowed_bases
  were intentionally purged in Plan 02 Task 1 and deferred to a later phase;
  this synthetic leaf exercises the food arbitration path for when they return).
"""

from __future__ import annotations

import pytest

from prices.enrich.keywords import _registry as registry
from prices.enrich.keywords.types import (
    COICOPClass,
    Group,
    Leaf,
    SubLabel,
    Subgroup,
)
from prices.enrich import cross_check


def _clear_caches() -> None:
    registry._class_store.cache_clear()
    registry._sub_labels_store.cache_clear()
    cross_check._class_cache.clear()


@pytest.fixture(autouse=True)
def _reset_caches():
    _clear_caches()
    yield
    _clear_caches()


def _a_non_food_leaf() -> str:
    """Return a real 4-digit non-food (division != 01) leaf code from the
    on-disk class tree, so the test does not hardcode a guessed code."""
    klass = registry.load("02")
    assert klass is not None
    for grp in klass.groups:
        for sg in grp.subgroups:
            for leaf in sg.leaves:
                if leaf.code.count(".") == 3:
                    return leaf.code
    raise AssertionError("no 4-digit leaf found in class 02")


@pytest.mark.integration
def test_non_food_resolves_at_four_digit():
    """A non-food code resolves its 4-digit leaf against the on-disk tree."""
    code = _a_non_food_leaf()
    cross_check._class_cache.clear()
    _, level = cross_check.lookup_allowed_bases(code, None)
    assert level != "unknown_class"
    assert level != "unknown_leaf"


@pytest.mark.integration
def test_non_food_truncates_extra_segments_to_four_digit():
    """A non-food code with extra segments still truncates to 4-digit (old
    behavior): resolution byte-equivalent to passing the bare 4-digit code."""
    code = _a_non_food_leaf()
    cross_check._class_cache.clear()
    a = cross_check.lookup_allowed_bases(code, None)
    cross_check._class_cache.clear()
    b = cross_check.lookup_allowed_bases(code + ".99", None)
    assert a == b


@pytest.mark.integration
def test_food_resolves_at_five_digit_where_four_digit_would_fail():
    """A real division-01 5-digit code resolves to a non-None class-tree leaf,
    whereas the OLD 4-digit truncation (01.1.1.1) is no longer a leaf and would
    have returned unknown_leaf. Assert both directions (regression closure)."""
    food_code = "01.1.1.1.2"  # Rice (real 5-digit leaf post-Task-1)

    # NEW depth-aware behavior: 5-digit leaf is found.
    _, level_new = cross_check.lookup_allowed_bases(food_code, None)
    assert level_new != "unknown_leaf", level_new
    assert level_new not in ("unknown_class", "no_code")

    # OLD behavior simulation: truncating food to 4-digit no longer resolves.
    cross_check._class_cache.clear()
    truncated = ".".join(food_code.split(".")[:4])  # 01.1.1.1
    _, level_old = cross_check.lookup_allowed_bases(truncated, None)
    assert level_old == "unknown_leaf", level_old


def _synthetic_food_class(food_code: str, allowed_basis: str) -> COICOPClass:
    """A minimal class '01' with one 5-digit food leaf whose sub_label carries
    a singleton allowed_bases — stands in for the deferred curated food bases."""
    sub = SubLabel(
        id="synthetic-anchor",
        label="synthetic",
        keywords_by_lang={"en": ("synthetic",)},
        allowed_bases=frozenset({allowed_basis}),
        role="anchor",
        numeric_id=food_code,
    )
    leaf = Leaf(
        code=food_code,
        label="Synthetic food leaf",
        keywords_by_lang={"en": ("synthetic",)},
        sub_labels=(sub,),
    )
    sg = Subgroup(code="01.1.1", label="sg", leaves=(leaf,))
    grp = Group(code="01.1", label="grp", subgroups=(sg,))
    return COICOPClass(code="01", label="Food", groups=(grp,))


def test_food_silent_override_with_synthetic_singleton_allowed_bases():
    """consolidate(<mismatching basis>, <food code>, None) -> SILENT_OVERRIDE.

    Uses a SYNTHETIC injected food leaf (Option A) because the real on-disk food
    allowed_bases were deliberately purged in Task 1 and deferred. Depth-aware
    resolution still walks the 5-digit food code to the singleton-bases leaf, so
    the live arbitration path is proven alive for food.
    """
    food_code = "01.1.1.1.2"
    allowed_basis = "mass"
    mismatching_basis = "volume"

    cross_check._class_cache["01"] = _synthetic_food_class(food_code, allowed_basis)

    allowed, level = cross_check.lookup_allowed_bases(food_code, None)
    assert allowed == frozenset({allowed_basis}), (allowed, level)

    bucket, override = cross_check.consolidate(mismatching_basis, food_code, None)
    assert bucket == "SILENT_OVERRIDE", bucket
    assert override == allowed_basis


def test_food_pass_through_under_old_truncation_simulation():
    """Documents the regression that was closed: with the OLD 4-digit
    truncation the synthetic 5-digit food leaf is unreachable, so consolidate
    returns PASS_THROUGH. The depth-aware fix is what flips it to
    SILENT_OVERRIDE (see the test above)."""
    food_code = "01.1.1.1.2"
    cross_check._class_cache["01"] = _synthetic_food_class(food_code, "mass")

    # Simulate the OLD behavior by querying the 4-digit truncation directly:
    # the synthetic class has no 4-digit leaf, so it is unreachable.
    truncated = ".".join(food_code.split(".")[:4])
    bucket, override = cross_check.consolidate("volume", truncated, None)
    assert bucket == "PASS_THROUGH", bucket
    assert override is None
