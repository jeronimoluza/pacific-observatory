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


class _DocStub(list):
    pass


def _produce_rec():
    return {
        "tokens": {"apple", "apples"},
        "plausible_basis": {"mass", "count", "item", None},
        "allowed_basis": {"mass"},
        "nonfood": set(),
        "species_veto": set(),
        "form": {},
        "benign": {"fuji"},
    }


def test_two_level_basis_cascade_and_record():
    rec = _produce_rec()
    # volume is IMPLAUSIBLE for produce -> hard-gated to OTHER_FORM
    d, r = cascade.decide("Fuji Apple", _DocStub(), set(), rec, set(), "volume", {}, {})
    assert d == OTHER_FORM
    assert "plausible" in r
    # count is PLAUSIBLE (in plausible_basis) even though not in allowed_basis ->
    # must survive the cascade's hard gate (allowed_basis enforced later).
    d2, r2 = cascade.decide(
        "Fuji Apple", _DocStub(), set(), rec, set(), "count", {}, {}
    )
    assert d2 != OTHER_FORM or "plausible" not in r2


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


def test_seed_propagates_allowed_basis(tmp_path):
    store.set_data_dir(tmp_path)
    try:
        taxonomy.seed_from_config(CONFIG)
        # pineapple carries config allowed_basis=["mass"] + plausible override
        rec = store.load_record("pineapple")
        assert rec["allowed_basis"] == {"mass"}
        assert rec["plausible_basis"] == {"mass", "count", "item"}
        # regression: an item with no config allowed_basis stays None
        assert store.load_record("apple")["allowed_basis"] is None
    finally:
        store.set_data_dir(store.REPO_ROOT / "data" / "prices")


def test_reseed_overrides_stale_on_disk_basis(tmp_path):
    store.set_data_dir(tmp_path)
    try:
        taxonomy.seed_from_config(CONFIG)
        # simulate a stale on-disk seed with the wrong (empty) basis
        df = store.load_base_items()
        df.loc[df["base_item"] == "pineapple", "allowed_basis"] = ""
        store.write_base_items(df)
        assert store.load_record("pineapple")["allowed_basis"] is None
        # re-seeding must make config authoritative again, not keep the stale row
        taxonomy.seed_from_config(CONFIG)
        assert store.load_record("pineapple")["allowed_basis"] == {"mass"}
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


def test_validate_keeps_basis_conflict_row():
    rec = _rice_rec()
    rec["allowed_basis"] = {"mass"}
    rec["plausible_basis"] = {"mass", "count", "item", None}
    green = pd.DataFrame(
        [
            {
                "product_name_original": "Rice 10 pcs",
                "country": "au",
                "currency": "USD",
                "price": 5.0,
                "observation_date": "2024-06-01",
                "lang": "en",
            },
        ]
    )
    art, demoted = validate.validate_green(
        green, rec, "rice", datetime.now(timezone.utc)
    )
    # count row is NOT hard-demoted anymore; it stays in the artifact for promote
    assert len(demoted) == 0
    assert len(art) == 1


def test_validation_runs_dir_under_data():
    assert "data" in str(validate.VALIDATION_RUNS_DIR)
    assert "_enrich" in str(validate.VALIDATION_RUNS_DIR)


def test_write_run_bucket_files(tmp_path, monkeypatch):
    monkeypatch.setattr(validate, "VALIDATION_RUNS_DIR", tmp_path / "runs")
    art = pd.DataFrame(columns=validate.ARTIFACT_COLS + ["promotion_status"])
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
    for fname in (
        "candidates.csv",
        "green.csv",
        "other_form.csv",
        "review.csv",
        "exclude.csv",
    ):
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


def test_loop_status_ratio_and_convergence():
    from prices.enrich.base_items.pipeline import loop_status

    # candidate pile <= 2x green -> stop by ratio
    s = loop_status(n_candidate=10, n_green=6, moved_fraction=0.5)
    assert s["stop"] and s["reason"] == "ratio"
    # flywheel dry -> stop by convergence
    s2 = loop_status(n_candidate=100, n_green=5, moved_fraction=0.01)
    assert s2["stop"] and s2["reason"] == "convergence"
    # neither -> continue
    s3 = loop_status(n_candidate=100, n_green=5, moved_fraction=0.5)
    assert not s3["stop"]


def test_promote_handles_nonunique_index():
    from prices.enrich.base_items import promote as P

    rows = [
        {
            "base_item": "orange",
            "pricing_basis": "mass",
            "country": "fiji",
            "unit_value_usd": uv,
        }
        for uv in [2.0, 2.0, 2.1, 1.9, 2.05]
    ]
    df_in = pd.DataFrame(rows, index=[0, 0, 0, 0, 0])  # pathological non-unique index
    out = P.promote(df_in, allowed_basis={"mass"})
    assert (out["group_n"] == 5).all()
    assert (out["promotion_status"] == "green").all()


def test_promote_bands_and_small_groups():
    from prices.enrich.base_items import promote as P

    rows = []
    # fiji kg: 6 tight rows ~2.0 + 1 outlier 20.0
    for uv in [1.9, 2.0, 2.1, 2.0, 1.95, 2.05, 20.0]:
        rows.append(
            {
                "base_item": "orange",
                "pricing_basis": "mass",
                "country": "fiji",
                "unit_value_usd": uv,
            }
        )
    # australia kg: only 3 rows -> held
    for uv in [3.0, 3.1, 2.9]:
        rows.append(
            {
                "base_item": "orange",
                "pricing_basis": "mass",
                "country": "australia",
                "unit_value_usd": uv,
            }
        )
    # count basis not in allowed -> basis_conflict
    for uv in [0.5, 0.6, 0.55, 0.52, 0.58]:
        rows.append(
            {
                "base_item": "orange",
                "pricing_basis": "count",
                "country": "fiji",
                "unit_value_usd": uv,
            }
        )
    df = P.promote(pd.DataFrame(rows), allowed_basis={"mass"})
    fiji_kg = df[(df.country == "fiji") & (df.pricing_basis == "mass")]
    assert (fiji_kg[fiji_kg.unit_value_usd < 3]["promotion_status"] == "green").all()
    assert (
        fiji_kg[fiji_kg.unit_value_usd == 20.0]["promotion_status"].iloc[0]
        == "candidate_outlier"
    )
    au = df[df.country == "australia"]
    assert (au["promotion_status"] == "candidate_small_group").all()
    cnt = df[df.pricing_basis == "count"]
    assert (cnt["promotion_status"] == "basis_conflict").all()
    assert set(["group_n", "group_median_usd", "band_lo", "band_hi"]).issubset(
        df.columns
    )


def test_regex_check_diff_empty_then_flags(tmp_path, monkeypatch):
    from prices.enrich.base_items import regex_check as R

    monkeypatch.setattr(R, "SNAPSHOT", tmp_path / "extraction_snapshot.parquet")
    corpus = pd.DataFrame(
        {
            "product_name_original": ["Rice 5kg", "Oranges 12 pack"],
            "lang": ["en", "en"],
        }
    )
    R.freeze(corpus)  # write snapshot
    diff = R.diff(corpus)  # same code + corpus -> empty
    assert diff.empty
    # a perturbed extraction surfaces a non-empty diff
    perturbed = corpus.copy()
    perturbed.loc[0, "product_name_original"] = "Rice 500g"
    diff2 = R.diff(perturbed)
    assert not diff2.empty
