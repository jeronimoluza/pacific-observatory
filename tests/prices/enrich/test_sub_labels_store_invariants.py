"""Invariant gate for the rebuilt 538-leaf short-item sub-label store (Plan 02).

Locks the digit invariant (538 = 269 food-5-digit + 269 non-food-4-digit + 0
food-4-digit), in-xlsx grounding of food leaf keys, English-only keywords,
prose-free labels, the food numeric_id == 5-digit-key rule, and that every
class 01..15 still loads through the registry without raising (proves the
class-tree reconciliation holds).
"""

from __future__ import annotations

import json
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
