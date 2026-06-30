"""Bijection guard for the authoritative RENAME map (Phase 01.66 / Plan 01, SC1).

A wrong or incomplete RENAME would silently corrupt Plan 03's golden regen and
literal renames. These tests make the map fail loudly BEFORE Plan 03 consumes it
(threat T-01.66-01): the map must be a bijection over the live registry index.
"""

from __future__ import annotations

import re

import pytest

from rename_map import RENAME

pytestmark = pytest.mark.unit

_SCREAMING_SNAKE = re.compile(r"^[A-Z0-9_]+$")


def _index_ids() -> set[str]:
    from prices.enrich.regex_patterns._registry import _INDEX

    return set(_INDEX.keys())


def test_images_cover_every_registry_id() -> None:
    """Post Plan-03 reorg, the live registry holds the RENAMED (image) ids, so
    every `_INDEX` id is a RENAME VALUE — no image missed, no extra image. (Plan 01
    pinned this against the domain; the reorg flipped the registry to the images.)"""
    index_ids = _index_ids()
    rename_images = set(RENAME.values())

    missing = index_ids - rename_images
    extra = rename_images - index_ids
    assert not missing, f"registry ids missing from RENAME images: {sorted(missing)}"
    assert not extra, f"RENAME images absent from registry: {sorted(extra)}"


def test_registry_has_47_ids() -> None:
    """The registry index is the expected 47-id surface."""
    assert len(_index_ids()) == 47


def test_images_are_screaming_snake() -> None:
    bad = {v for v in RENAME.values() if not _SCREAMING_SNAKE.match(v)}
    assert not bad, f"non-SCREAMING_SNAKE images: {sorted(bad)}"


def test_images_are_globally_unique() -> None:
    seen: dict[str, str] = {}
    collisions: list[tuple[str, str, str]] = []
    for old, new in RENAME.items():
        if new in seen:
            collisions.append((new, seen[new], old))
        else:
            seen[new] = old
    assert (
        not collisions
    ), f"colliding images (image, first_old, second_old): {collisions}"


def test_rename_is_a_bijection() -> None:
    """len(set(values)) == len(RENAME) == len(_INDEX) == 47."""
    assert len(set(RENAME.values())) == len(RENAME) == len(_index_ids()) == 47
