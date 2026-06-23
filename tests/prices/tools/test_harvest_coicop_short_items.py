"""Unit + integration tests for the COICOP short-item harvest module.

Tests 1-3 drive the prose filter / bullet split deterministically against a tiny
in-memory DataFrame (monkeypatched `pandas.read_excel`), so no xlsx read happens.
Tests 4-5 read the real `config.COICOP_XLSX` and are marked integration.
"""

from __future__ import annotations

import pandas as pd
import pytest

from prices.enrich import config
from prices.tools import harvest_coicop_short_items as h


def _patch_xlsx(monkeypatch, rows: list[dict]) -> None:
    """Replace pandas.read_excel (as seen by the module) with an in-memory frame."""
    df = pd.DataFrame(rows)

    def _fake_read_excel(*args, **kwargs):
        return df.copy()

    monkeypatch.setattr(h.pd, "read_excel", _fake_read_excel)


def test_prose_candidates_dropped(monkeypatch):
    """Test 1: Other/n.e.c./multi-clause prose bullets are purged; only 'rice' kept."""
    includes = (
        "* rice_x000D_\n"
        "* Other cereals_x000D_\n"
        "* n.e.c._x000D_\n"
        "* mixed cereal grains, in the form of dried grains, "
        "also including other ingredients"
    )
    _patch_xlsx(
        monkeypatch,
        [
            {
                "code": "99.9",
                "title": "T",
                "intro": None,
                "includes": includes,
                "alsoIncludes": None,
                "excludes": None,
            }
        ],
    )
    items = h.harvest_leaf_items({"99.9"})["99.9"]
    # Title "T" is kept by construction; the bullet set must be exactly {"rice"}.
    bullet_items = [i for i in items if i != "T"]
    assert bullet_items == ["rice"], items


def test_short_comma_phrase_kept(monkeypatch):
    """Test 2: 'farro, broken and pearled' (4 tokens, no clause marker) is kept."""
    _patch_xlsx(
        monkeypatch,
        [
            {
                "code": "99.9",
                "title": "T",
                "intro": None,
                "includes": "* farro, broken and pearled",
                "alsoIncludes": None,
                "excludes": None,
            }
        ],
    )
    items = h.harvest_leaf_items({"99.9"})["99.9"]
    assert "farro, broken and pearled" in items, items


def test_parenthetical_qualifier_kept(monkeypatch):
    """Test 3: 'Maize (corn)' parenthetical qualifier is not prose."""
    _patch_xlsx(
        monkeypatch,
        [
            {
                "code": "99.9",
                "title": "T",
                "intro": None,
                "includes": "* Maize (corn)",
                "alsoIncludes": None,
                "excludes": None,
            }
        ],
    )
    items = h.harvest_leaf_items({"99.9"})["99.9"]
    assert "Maize (corn)" in items, items


@pytest.mark.integration
def test_grounding_in_leaf_only():
    """Test 4: every harvested item for 01.1.1.1.1 appears in that row's own cells."""
    code = "01.1.1.1.1"
    items = h.harvest_leaf_items({code})[code]
    df = pd.read_excel(config.COICOP_XLSX, sheet_name="COICOP_2018")
    df["code"] = df["code"].astype(str)
    row = df[df["code"] == code].iloc[0]
    blob = " ".join(
        str(row[c])
        for c in ("title", "intro", "includes", "alsoIncludes")
        if pd.notna(row[c])
    ).lower()
    for item in items:
        assert item.lower() in blob, (item, blob)
    assert "Wheat" in items, items
    assert "bulgur" in items, items
    assert "farro, broken and pearled" in items, items


@pytest.mark.integration
def test_full_xlsx_smoke_no_prose():
    """Test 5: leaf-shaped harvest yields non-empty lists, zero prose strings.

    The leaf set (D2) is food 5-digit (division 01) + non-food 4-digit. Group /
    division / class rows legitimately carry only prose and are not leaves, so the
    non-empty invariant is asserted over the leaf shape, not every xlsx row.
    """
    df = pd.read_excel(config.COICOP_XLSX, sheet_name="COICOP_2018")
    df["code"] = df["code"].astype(str)
    df = df[df["code"] != "nan"]
    depth = df["code"].str.count(r"\.") + 1
    is_food = df["code"].str.startswith("01.")
    leaf_codes = set(df["code"][(is_food & (depth == 5)) | (~is_food & (depth == 4))])

    d = h.harvest_leaf_items(leaf_codes)
    assert d, "empty harvest"
    union: list[str] = []
    empties: list[str] = []
    for code, items in d.items():
        assert isinstance(items, list), (code, items)
        if not items:
            empties.append(code)
        union.extend(items)
    # Catch-all "Other …"/n.e.c. leaves legitimately harvest empty under the D1
    # purge (their own cells carry only prose). Plan 02 patches thin leaves; here
    # we only require the bulk of leaves to yield items and the union to be
    # prose-free. (~87/538 catch-all leaves are empty by design.)
    assert len(empties) < len(d) // 2, (len(empties), len(d))
    assert union, "no items harvested across all leaves"
    assert all("n.e.c." not in i.lower() for i in union)
    assert not any(i.lower().startswith("other ") for i in union)
    assert all("including" not in i.lower() for i in union)
    assert all("in the form of" not in i.lower() for i in union)
