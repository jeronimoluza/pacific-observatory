"""Composition-diff harness: post-reorg composition == pre-reorg baseline (mapped).

Phase 01.66 / Plan 01, SC2/SC4. This is the instrument that catches a silent
reorder during the file move. It keys ONLY on composed id sequences (never on
module paths), so it is directory-agnostic and survives the reorg.

Two modes, selected by the ``MAPPED`` env var:

  * MAPPED (default, post Plan 03): the live composer emits SCREAMING_SNAKE ids, so
    the live composition must equal the frozen baseline mapped through RENAME. This
    is the SC2/SC4 proof that the reorg changed nothing but the names. The default
    is MAPPED because the reorg has landed.

  * OLD-id self-check (``MAPPED=0``): asserts the live composition equals the frozen
    baseline VERBATIM. Only meaningful on the pre-reorg tree (what Plan 01 asserted);
    retained so the harness can still be run against an un-renamed checkout.

The same assertion body serves both modes — only the expected side is mapped.
"""

from __future__ import annotations

import os

import pytest

import _composition_baseline as baseline
from rename_map import RENAME

pytestmark = pytest.mark.unit

_MAPPED = os.environ.get("MAPPED", "1") not in ("0", "", "false", "False")


def _expected(seq: tuple[str, ...]) -> tuple[str, ...]:
    """Map a frozen-baseline id sequence into the space the live composer emits.

    OLD mode: identity (live ids are still old). MAPPED mode: through RENAME.
    """
    if not _MAPPED:
        return seq
    return tuple(RENAME[i] for i in seq)


def _live_kind(kind: str) -> tuple[str, ...]:
    from prices.enrich.regex_patterns.dict_view import _ids_for_kind

    return _ids_for_kind(kind)


def _live_load_for(country: str | None, lang: str | None) -> tuple[str, ...]:
    from prices.enrich.regex_patterns._registry import load_for

    return tuple(p.id for p in load_for(country, lang))


@pytest.mark.parametrize("kind", sorted(baseline.KIND_BASELINE.keys()))
def test_per_kind_composition_matches_baseline(kind: str) -> None:
    """Each live per-kind id sequence equals the (optionally mapped) baseline."""
    assert _live_kind(kind) == _expected(baseline.KIND_BASELINE[kind])


@pytest.mark.parametrize(
    "key",
    sorted(baseline.LOAD_FOR_BASELINE.keys(), key=lambda k: (str(k[0]), str(k[1]))),
)
def test_load_for_sweep_matches_baseline(key: tuple[str | None, str | None]) -> None:
    """Each live load_for(country, lang) sequence equals the (mapped) baseline."""
    country, lang = key
    assert _live_load_for(country, lang) == _expected(baseline.LOAD_FOR_BASELINE[key])


def test_harness_wiring_self_check() -> None:
    """In OLD mode the live canon must equal the verbatim baseline canon.

    Guards against the harness silently no-op'ing (e.g. empty baseline). In MAPPED
    mode this still holds via RENAME, so the check is mode-agnostic.
    """
    assert len(baseline.CANON) == 11
    assert _live_kind("canon") == _expected(baseline.CANON)
