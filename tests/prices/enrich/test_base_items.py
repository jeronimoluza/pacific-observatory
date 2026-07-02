"""Unit tests for the base-item classification cascade."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from prices.enrich.base_items import cascade, mine, store, taxonomy, validate
from prices.enrich.base_items.static import CANDIDATE, EXCLUDE, OTHER_FORM, REVIEW

CONFIG = Path(".planning/experiments/base_item_config.json")


def _rice_rec():
    return {
        "name": "rice",
        "tokens": {"rice", "rices"},
        "fresh_leaf": "01.1.1.1.2",
        "fresh_prefix": "01.1.1",
        "variety": {"basmati", "jasmine"},
        "benign": {"basmati", "jasmine", "white", "brown"},
        "form": {"flour": "01.1.1.2.2", "noodle": "01.1.1.5.0"},
        "nonfood": {"cooker", "spoon"},
        "species_veto": {"wild"},
        "allowed_basis": None,
        "coicop2digit_title": "Food and non-alcoholic beverages",
    }


# --- pure helpers (no spaCy) ---------------------------------------------------
def test_whole_name_guard():
    assert cascade.whole_name_guard("Apple Shampoo 200ml")[0] == EXCLUDE
    assert cascade.whole_name_guard("Orange Flavoured Water")[0] == OTHER_FORM
    assert cascade.whole_name_guard("Apple Juice 1L")[0] == OTHER_FORM
    assert cascade.whole_name_guard("Fuji Apple 1kg")[0] is None


def test_whole_item_scan():
    rec = _rice_rec()
    assert cascade.whole_item_scan("Rice Cooker 1.8L", rec) == (
        EXCLUDE,
        "nonfood:cooker",
    )
    assert cascade.whole_item_scan("Wild Rice 500g", rec)[0] == REVIEW
    assert cascade.whole_item_scan("Rice Flour 1kg", rec)[0] == OTHER_FORM
    assert cascade.whole_item_scan("Basmati Rice 5kg", rec) == (None, None)


def test_only_in_parens():
    assert cascade.only_in_parens("Lozenges (Orange)", {"orange", "oranges"})
    assert not cascade.only_in_parens("Orange Juice (500ml)", {"orange", "oranges"})


def test_derived_fallback():
    rec = _rice_rec()
    form_lex = {"cracker": "01.1.1.3.1"}
    neg_lex = {"detergent": "05.6.0.0.0"}
    assert cascade.derived_fallback(["wild"], rec, form_lex, neg_lex)[0] == REVIEW
    assert cascade.derived_fallback(["noodle"], rec, form_lex, neg_lex)[0] == OTHER_FORM
    assert (
        cascade.derived_fallback(["cracker"], rec, form_lex, neg_lex)[0] == OTHER_FORM
    )
    assert cascade.derived_fallback(["detergent"], rec, form_lex, neg_lex)[0] == EXCLUDE
    assert cascade.derived_fallback(["sunrice"], rec, form_lex, neg_lex) == (
        REVIEW,
        "brand-residue:sunrice",
    )


def test_calc_str_and_variety():
    from types import SimpleNamespace

    sf = SimpleNamespace(
        pricing_basis="mass",
        amount_value=5.0,
        standard_unit="kg",
        count=1,
        multiplier=1,
    )
    s = validate._calc_str(14.99, "AUD", sf, 2.998)
    assert "5.0kg" in s and "2.9980 AUD/kg" in s
    assert validate._variety_in("Basmati Rice 5kg", {"basmati", "jasmine"}) == "basmati"


# --- prepare re-plumb ((name, url) grain) --------------------------------------
def test_prepare_dedup_by_name_url():
    from prices.enrich.stages.prepare import prepare_input

    raw = pd.DataFrame(
        [
            {
                "product_name": "Apple 1kg",
                "country": "jp",
                "currency": "JPY",
                "price": 500,
                "product_url": "u/a",
                "date": "2024-01-01",
            },
            {
                "product_name": "Apple 1kg",
                "country": "jp",
                "currency": "JPY",
                "price": 600,
                "product_url": "u/a",
                "date": "2024-02-01",
            },
            {
                "product_name": "Apple 1kg",
                "country": "jp",
                "currency": "JPY",
                "price": 700,
                "product_url": "u/b",
                "date": "2024-01-01",
            },
            {
                "product_name": "Rice 5kg",
                "country": "jp",
                "currency": "JPY",
                "price": 900,
                "product_url": None,
                "date": "2024-01-05",
            },
            {
                "product_name": "Rice 5kg",
                "country": "jp",
                "currency": "JPY",
                "price": 950,
                "product_url": "",
                "date": "2024-01-06",
            },
        ]
    )
    out = prepare_input(raw)
    assert len(out) == 3  # 2 apple listings (distinct urls) + 1 rice (url fallback)
    apple = out[out["product_url"] == "u/a"].iloc[0]
    assert apple["price"] == 550.0 and apple["n_rows"] == 2
    rice = out[out["product_name_original"] == "Rice 5kg"].iloc[0]
    assert rice["n_rows"] == 2 and rice["product_url"] == ""


# --- store round-trip ----------------------------------------------------------
def test_store_seed_and_load_record(tmp_path):
    store.set_data_dir(tmp_path)
    try:
        seeded = taxonomy.seed_from_config(CONFIG)
        assert len(seeded) > 0
        rec = store.load_record("rice")
        assert rec["tokens"] == {"rice", "rices"}
        assert rec["fresh_leaf"] == "01.1.1.1.2"
        assert "flour" in rec["form"] and "wild" in rec["species_veto"]

        # flywheel: a confirmed variety enters benign on the next load
        mine.confirm_varieties("rice", ["sunrice"])
        rec2 = store.load_record("rice")
        assert "sunrice" in rec2["benign"]
    finally:
        store.set_data_dir(store.REPO_ROOT / "data" / "prices")


def test_mine_source_boilerplate(tmp_path):
    store.set_data_dir(tmp_path)
    try:
        rows = pd.DataFrame(
            {
                "product_name_original": [
                    f"ShopX Fresh Apple item {i}" for i in range(60)
                ],
                "source": ["shopx"] * 60,
                "lang": ["en"] * 60,
            }
        )
        boiler = mine.mine_source_boilerplate(rows, min_products=50)
        toks = set(boiler["text"])
        assert "shopx" in toks and "fresh" in toks
    finally:
        store.set_data_dir(store.REPO_ROOT / "data" / "prices")


def test_review_residue_splits_cross_base_items(tmp_path):
    store.set_data_dir(tmp_path)
    try:
        taxonomy.seed_from_config(CONFIG)
        result = pd.DataFrame(
            {
                "decision": [REVIEW, REVIEW, REVIEW, CANDIDATE],
                "reason": [
                    "brand-residue:sunrice",
                    "brand-residue:noodle",
                    "no-cue:apple",
                    "earned:bare-item",
                ],
            }
        )
        candidates, cross = mine.review_residue(result)
        assert "sunrice" in set(candidates["token"])
        # 'apple' is a known base_item -> reported back, not a brand candidate
        assert "apple" in set(cross["token"])
    finally:
        store.set_data_dir(store.REPO_ROOT / "data" / "prices")


# --- validate GREEN ------------------------------------------------------------
def test_validate_green_unit_value_and_demote():
    rec = _rice_rec()
    green = pd.DataFrame(
        [
            {
                "product_name_original": "Basmati Rice 5kg",
                "country": "au",
                "currency": "USD",
                "price": 10.0,
                "observation_date": "2024-06-01",
                "lang": "en",
            },
        ]
    )
    art, demoted = validate.validate_green(
        green, rec, "rice", datetime.now(timezone.utc)
    )
    assert len(art) == 1
    row = art.iloc[0]
    assert row["coicop_deep_leaf_code"] == "01.1.1.1.2"
    assert abs(row["unit_value_local"] - 2.0) < 1e-6  # 10 / 5kg
    assert abs(row["unit_value_usd"] - 2.0) < 1e-6  # USD fx_rate == 1
    assert list(art.columns) == validate.ARTIFACT_COLS
    assert "source" in art.columns


def test_write_run_bucket_files(tmp_path, monkeypatch):
    monkeypatch.setattr(validate, "VALIDATION_RUNS_DIR", tmp_path / "runs")
    art = pd.DataFrame(columns=validate.ARTIFACT_COLS)
    classified = pd.DataFrame(
        {
            "product_name_original": ["Rice Wine 750ml", "Rice Cooker", "Sunrice 5kg"],
            "country": ["jp", "jp", "au"],
            "source": ["s1", "s1", "s2"],
            "currency": ["JPY", "JPY", "AUD"],
            "price": [900, 3000, 12],
            "decision": [OTHER_FORM, EXCLUDE, REVIEW],
            "reason": ["form:wine", "nonfood:cooker", "brand-residue:sunrice"],
            "pricing_basis": ["volume", "item", "mass"],
        }
    )
    run_dir = Path(
        validate.write_run(art, classified, "rice", datetime.now(timezone.utc))
    )
    assert run_dir.name.startswith("rice_")
    for fname in ("green.csv", "other_form.csv", "review.csv", "exclude.csv"):
        assert (run_dir / fname).exists()
    rev = pd.read_csv(run_dir / "review.csv")
    assert "source" in rev.columns and rev.iloc[0]["reason"] == "brand-residue:sunrice"


# --- spaCy-backed end-to-end (skipped if model absent) -------------------------
def _nlp_or_skip():
    try:
        import spacy

        return spacy.load("en_core_web_sm", disable=["ner"])
    except Exception:
        pytest.skip("en_core_web_sm not installed")


def test_classify_names_buckets():
    nlp = _nlp_or_skip()
    from prices.enrich.base_items.phrase_index import food_phrase_index

    rec = _rice_rec()
    names = [
        "Basmati Rice 5kg",
        "Rice Cooker 1.8L",
        "Rice Flour 1kg",
        "Rice Wine 750ml",
    ]
    got = cascade.classify_names(
        names, ["en"] * 4, rec, nlp, set(), food_phrase_index(), {}, {}
    )
    buckets = [g[0] for g in got]
    assert buckets[0] == CANDIDATE
    assert buckets[1] == EXCLUDE
    assert buckets[2] == OTHER_FORM
