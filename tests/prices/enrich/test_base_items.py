"""Unit tests for the base-item classification cascade."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from prices.enrich.base_items import cascade, mine, store, taxonomy, validate, verdicts
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
        cfg = json.loads(CONFIG.read_text())["base_items"]
        pine = cfg["pineapple"]
        taxonomy.seed_from_config(CONFIG)
        # config allowed_basis + plausible override propagate to the record
        rec = store.load_record("pineapple")
        assert rec["allowed_basis"] == set(pine["allowed_basis"])
        assert rec["plausible_basis"] == set(
            pine.get("plausible_basis") or pine["allowed_basis"]
        )
        # regression: an item with no config allowed_basis stays None
        no_basis = [k for k, v in cfg.items() if not v.get("allowed_basis")]
        if no_basis:
            assert store.load_record(no_basis[0])["allowed_basis"] is None
    finally:
        store.set_data_dir(store.REPO_ROOT / "data" / "prices")


def test_reseed_overrides_stale_on_disk_basis(tmp_path):
    store.set_data_dir(tmp_path)
    try:
        expected = set(
            json.loads(CONFIG.read_text())["base_items"]["pineapple"]["allowed_basis"]
        )
        taxonomy.seed_from_config(CONFIG)
        # simulate a stale on-disk seed with the wrong (empty) basis
        df = store.load_base_items()
        df.loc[df["base_item"] == "pineapple", "allowed_basis"] = ""
        store.write_base_items(df)
        assert store.load_record("pineapple")["allowed_basis"] is None
        # re-seeding must make config authoritative again, not keep the stale row
        taxonomy.seed_from_config(CONFIG)
        assert store.load_record("pineapple")["allowed_basis"] == expected
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


# --- apply-verdicts (judgment -> gazetteer flywheel) ---------------------------
def test_parse_verdicts_maps_roles_and_encodes_form_leaf():
    payload = {
        "item": "pineapple",
        "verdicts": [
            {"token": "SunnyPhil", "role": "variety"},
            {"token": "juice", "role": "form", "leaf": "01.2.1.1.1"},
            {"token": "shampoo", "role": "nonfood"},
        ],
    }
    vmap = verdicts.parse_verdicts(payload, "pineapple")
    assert vmap["sunnyphil"] == ("variety", "apply-verdicts")  # lowercased token
    assert vmap["juice"] == ("form:01.2.1.1.1", "apply-verdicts")  # leaf encoded
    assert vmap["shampoo"][0] == "nonfood"


def test_parse_verdicts_rejects_bad_schema():
    with pytest.raises(ValueError, match="does not match target"):
        verdicts.parse_verdicts({"item": "orange", "verdicts": [{}]}, "pineapple")
    with pytest.raises(ValueError, match="non-empty list"):
        verdicts.parse_verdicts({"item": "pineapple", "verdicts": []}, "pineapple")
    with pytest.raises(ValueError, match="role"):
        verdicts.parse_verdicts(
            {"item": "pineapple", "verdicts": [{"token": "x", "role": "bogus"}]},
            "pineapple",
        )
    with pytest.raises(ValueError, match="requires a 'leaf'"):
        verdicts.parse_verdicts(
            {"item": "pineapple", "verdicts": [{"token": "juice", "role": "form"}]},
            "pineapple",
        )


def test_apply_verdicts_feeds_gazetteer_flywheel(tmp_path):
    store.set_data_dir(tmp_path)
    try:
        taxonomy.seed_from_config(CONFIG)
        vmap = verdicts.parse_verdicts(
            {
                "item": "pineapple",
                "verdicts": [
                    {"token": "sunnyphil", "role": "variety"},
                    {"token": "juice", "role": "form", "leaf": "01.2.1.1.1"},
                ],
            },
            "pineapple",
        )
        store.append_gazetteer("pineapple", vmap)
        rec = store.load_record("pineapple")
        # the confirmed variety is now benign; the form leaf is decoded back
        assert "sunnyphil" in rec["benign"]
        assert rec["form"].get("juice") == "01.2.1.1.1"
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
                "input_hash": "abc123",
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
    assert row["input_hash"] == "abc123"  # join key for the time-series build


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


def test_build_timeseries_traces_green_to_dated_observations():
    from prices.enrich.base_items import timeseries
    from prices.enrich.stages.prepare import _row_input_dict
    from prices.enrich.versioning import input_hash as _input_hash

    name, url = "Basmati Rice 5kg", "https://shop.example/p/rice-5kg"
    ih = _input_hash(
        _row_input_dict(pd.Series({"product_name_original": name, "product_url": url}))
    )
    green = pd.DataFrame(
        [
            {
                "input_hash": ih,
                "product_name_original": name,
                "amount_value": 5.0,
                "count": 1,
                "multiplier": 1,
                "pricing_basis": "mass",
                "coicop_deep_leaf_code": "01.1.1.1.2",
                "base_item": "rice",
                "form": "",
                "variety": "basmati",
            }
        ]
    )
    raw = pd.DataFrame(
        [
            {
                "product_name": name,
                "product_url": url,
                "source": "s1",
                "region": "eap",
                "country": "australia",
                "currency": "USD",
                "price": 10.0,
                "date": "2024-06-01",
            },
            {
                "product_name": name,
                "product_url": url,
                "source": "s1",
                "region": "eap",
                "country": "australia",
                "currency": "USD",
                "price": 12.0,
                "date": "2024-07-01",
            },
            {
                "product_name": "Wild Rice 1kg",
                "product_url": "https://x/y",
                "region": "eap",
                "source": "s2",
                "country": "australia",
                "currency": "USD",
                "price": 9.0,
                "date": "2024-06-01",
            },
        ]
    )
    long_df, snapshot = timeseries.build_timeseries(green, raw)

    assert list(long_df.columns) == timeseries._OUT_COLS
    assert len(long_df) == 2  # only the two GREEN-matched dated observations
    assert set(long_df["input_hash"]) == {ih}
    by_date = long_df.set_index("date")
    assert abs(by_date.loc["2024-06-01", "unit_value_local"] - 2.0) < 1e-6  # 10 / 5kg
    assert abs(by_date.loc["2024-07-01", "unit_value_local"] - 2.4) < 1e-6  # 12 / 5kg
    assert abs(by_date.loc["2024-06-01", "unit_value_usd"] - 2.0) < 1e-6  # USD fx == 1
    assert (long_df["product_url"] == url).all()  # provenance recovered
    assert (long_df["region"] == "eap").all()  # region derived from country
    # snapshot = latest date per input_hash
    assert len(snapshot) == 1
    assert snapshot.iloc[0]["date"] == "2024-07-01"


def test_build_timeseries_drops_undated_products_without_crashing():
    # A GREEN product whose raw observations ALL have unparseable dates must not
    # crash the snapshot idxmax and must be excluded from the dated series.
    from prices.enrich.base_items import timeseries
    from prices.enrich.stages.prepare import _row_input_dict
    from prices.enrich.versioning import input_hash as _input_hash

    def _h(name, url):
        return _input_hash(
            _row_input_dict(
                pd.Series({"product_name_original": name, "product_url": url})
            )
        )

    dated_name, dated_url = "Fuji Apple 1kg", "https://s/p/apple"
    undated_name, undated_url = "Navel Orange 1kg", "https://s/p/orange"
    green = pd.DataFrame(
        [
            {
                "input_hash": _h(dated_name, dated_url),
                "product_name_original": dated_name,
                "amount_value": 1.0,
                "count": 1,
                "multiplier": 1,
                "pricing_basis": "mass",
                "coicop_deep_leaf_code": "01.1.6.1.1",
                "base_item": "apple",
                "form": "",
                "variety": "fuji",
            },
            {
                "input_hash": _h(undated_name, undated_url),
                "product_name_original": undated_name,
                "amount_value": 1.0,
                "count": 1,
                "multiplier": 1,
                "pricing_basis": "mass",
                "coicop_deep_leaf_code": "01.1.6.2.1",
                "base_item": "orange",
                "form": "",
                "variety": "navel",
            },
        ]
    )
    raw = pd.DataFrame(
        [
            {
                "product_name": dated_name,
                "product_url": dated_url,
                "source": "s1",
                "region": "eap",
                "country": "australia",
                "currency": "USD",
                "price": 3.0,
                "date": "2024-06-01",
            },
            {
                "product_name": undated_name,
                "product_url": undated_url,
                "source": "s2",
                "region": "eap",
                "country": "australia",
                "currency": "USD",
                "price": 5.0,
                "date": "not-a-date",
            },
        ]
    )
    long_df, snapshot = timeseries.build_timeseries(green, raw)
    assert set(long_df["input_hash"]) == {_h(dated_name, dated_url)}  # undated dropped
    assert long_df["date"].notna().all()
    assert len(snapshot) == 1  # snapshot did not crash on the all-NaN-date group


def test_load_accumulated_green_concats_latest(tmp_path, monkeypatch):
    from prices.enrich.base_items import timeseries

    # load_accumulated_green reads validate.VALIDATION_RUNS_DIR at call time.
    monkeypatch.setattr(validate, "VALIDATION_RUNS_DIR", tmp_path / "runs")
    cols = validate.ARTIFACT_COLS + ["promotion_status"]
    for item, ih in (("apple", "h1"), ("orange", "h2")):
        art = pd.DataFrame([{c: None for c in cols}])
        art["input_hash"] = ih
        art["promotion_status"] = "green"
        validate.write_run(
            art,
            pd.DataFrame(columns=["product_name_original", "decision"]),
            item,
            datetime.now(timezone.utc),
        )
    acc = timeseries.load_accumulated_green()
    assert set(acc["input_hash"]) == {"h1", "h2"}  # both items' latest greens


def test_build_timeseries_empty_green_returns_empty():
    from prices.enrich.base_items import timeseries

    green = pd.DataFrame(columns=["input_hash", "product_name_original"])
    raw = pd.DataFrame(columns=timeseries._RAW_COLS)
    long_df, snapshot = timeseries.build_timeseries(green, raw)
    assert long_df.empty and snapshot.empty


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
    # New layout: validation_runs/{item}/{stamp}/
    assert run_dir.parent.name == "rice"
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
    # latest pointer resolves to this run
    latest = run_dir.parent / "latest"
    assert latest.resolve() == run_dir.resolve()
    assert (latest / "green.csv").exists()
    # manifest records the run
    manifest = json.loads((run_dir.parent / "manifest.json").read_text())
    assert manifest["base_item"] == "rice"
    assert manifest["runs"][-1]["stamp"] == run_dir.name


def test_write_run_prunes_to_last_n(tmp_path, monkeypatch):
    monkeypatch.setattr(validate, "VALIDATION_RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(validate, "KEEP_RUNS", 3)
    art = pd.DataFrame(columns=validate.ARTIFACT_COLS + ["promotion_status"])
    classified = pd.DataFrame(columns=["product_name_original", "decision"])
    stamps = []
    for i in range(5):
        ts = datetime(2026, 1, 1, 12, i, tzinfo=timezone.utc)
        rd = Path(validate.write_run(art, classified, "rice", ts))
        stamps.append(rd.name)
    item_dir = tmp_path / "runs" / "rice"
    kept = sorted(
        p.name for p in item_dir.iterdir() if p.is_dir() and p.name != "latest"
    )
    assert kept == sorted(stamps[-3:])  # only the last 3 run dirs survive
    assert (item_dir / "latest").resolve().name == stamps[-1]
    # manifest keeps only the surviving runs
    manifest = json.loads((item_dir / "manifest.json").read_text())
    assert [r["stamp"] for r in manifest["runs"]] == stamps[-3:]


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


def test_skip_mine_env_gates_boilerplate(tmp_path, monkeypatch):
    """BASE_ITEMS_SKIP_MINE=1 skips the shared source_boilerplate write so parallel
    classify runs never race on it; unset, boilerplate is mined as before."""
    from prices.enrich.base_items import pipeline

    calls = []
    monkeypatch.setattr(
        pipeline.mine, "mine_source_boilerplate", lambda *a, **k: calls.append(1)
    )
    monkeypatch.setattr(
        pipeline.store,
        "load_record",
        lambda bi: {
            "name": bi,
            "tokens": {bi},
            "fresh_leaf": "01.1.6.1.7",
            "fresh_prefix": "01.1.6",
            "variety": set(),
            "benign": set(),
            "form": {},
            "nonfood": set(),
            "species_veto": set(),
            "allowed_basis": None,
            "plausible_basis": None,
            "coicop2digit_title": "Food",
        },
    )
    sl = pd.DataFrame(
        {
            "product_name_original": ["Foo Bar"],
            "source": ["s1"],
            "lang": ["en"],
            "country": ["ph"],
            "currency": ["PHP"],
            "price": [10.0],
        }
    )
    monkeypatch.setattr(pipeline, "_grep_slice", lambda rec, region: sl.copy())
    monkeypatch.setattr(
        pipeline.pd,
        "read_parquet",
        lambda *a, **k: pd.DataFrame(
            {"product_name_original": ["Foo Bar"], "source": ["s1"], "lang": ["en"]}
        ),
    )
    monkeypatch.setattr(
        pipeline,
        "classify_names",
        lambda *a, **k: [("REVIEW", "brand-residue:foo", None)],
    )
    monkeypatch.setattr(
        pipeline.validate,
        "validate_green",
        lambda green, rec, bi, ts: (
            pd.DataFrame(columns=validate.ARTIFACT_COLS),
            pd.DataFrame(),
        ),
    )
    monkeypatch.setattr(pipeline.validate, "write_run", lambda *a, **k: str(tmp_path))
    monkeypatch.setattr(
        pipeline.mine,
        "review_residue",
        lambda s: (
            pd.DataFrame(columns=["token", "n"]),
            pd.DataFrame(columns=["token", "n"]),
        ),
    )
    monkeypatch.setattr(pipeline, "food_phrase_index", lambda: {})
    monkeypatch.setattr(pipeline.store, "load_boilerplate", lambda s: set())
    monkeypatch.setattr(pipeline.store, "load_form_lexicon", lambda: {})
    monkeypatch.setattr(pipeline.store, "load_neg_lexicon", lambda: {})

    monkeypatch.delenv("BASE_ITEMS_SKIP_MINE", raising=False)
    pipeline.run_iteration("pineapple", None, nlp=object())
    assert calls == [1]  # mined once when the guard is unset

    calls.clear()
    monkeypatch.setenv("BASE_ITEMS_SKIP_MINE", "1")
    pipeline.run_iteration("pineapple", None, nlp=object())
    assert calls == []  # mine skipped when the guard is set
