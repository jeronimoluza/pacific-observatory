"""The parity harness has to partition the delta, not merely describe it."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from prices.build import parity

SNAP = "global_prices_snapshot"

BASE = {
    "input_hash": ["a", "b", "c", "d", "e"],
    "product_name_original": ["milk", "beans pack of 6", "rice", "oil", "tea"],
    "country": ["slovakia", "ghana", "ghana", "ghana", "ghana"],
    "source": ["s1", "s1", "mangusa_cw", "s1", "s1"],
    "declared_coicop_codes": ["", "", "", "01.1.1", ""],
    "observation_date": pd.to_datetime(
        ["2026-01-01", "2026-01-01", "2026-01-01", "2026-01-01", "1970-01-01"],
        utc=True,
    ),
    "price_local": [1.0, 2.0, 3.0, 4.0, 5.0],
    "price_usd": [1.0, 2.0, 3.0, 4.0, 5.0],
    "count": [1, 1, 1, 1, 1],
    "multiplier": [1, 1, 1, 1, 1],
    "is_multipack": [False, False, False, False, False],
    "is_bundle": [False, False, False, False, False],
    "coicop_code": ["01.1.1.1.1"] * 5,
    "unit_value_local": [1.0, 1.0, 1.0, 1.0, 1.0],
    "trust_uv": [True, True, True, True, True],
}


def _write(tmp_path, sub, frame):
    d = tmp_path / sub
    d.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(frame).to_parquet(d / f"{SNAP}.parquet", index=False)
    return d


def test_identical_builds_report_no_change(tmp_path):
    ref = _write(tmp_path, "ref", BASE)
    new = _write(tmp_path, "new", BASE)
    r = parity.compare_keyed(ref / f"{SNAP}.parquet", new / f"{SNAP}.parquet", ("input_hash",))
    assert r["changed"] == 0
    assert r["by_column"] == {}


def test_each_population_claims_its_own_row(tmp_path):
    ref = _write(tmp_path, "ref", BASE)
    after = {k: list(v) for k, v in BASE.items()}
    after["price_local"][0] = 9.0  # slovakia -> price re-parse
    after["count"][1] = 6  # "pack of 6" -> multipack adjacency
    after["count"][2] = 12  # mangusa_cw -> case size
    after["coicop_code"][3] = "01.1.2.2.2"  # declared non-leaf -> reclassified
    after["observation_date"] = list(BASE["observation_date"])
    after["observation_date"][4] = pd.Timestamp("2026-02-02", tz="UTC")  # 1970 stamp
    new = _write(tmp_path, "new", after)

    r = parity.compare_keyed(
        ref / f"{SNAP}.parquet", new / f"{SNAP}.parquet", ("input_hash",)
    )
    assert r["changed"] == 5
    assert r["populations"]["slovak_slovenian_price"] == 1
    assert r["populations"]["pack_of_n_multipack"] == 1
    assert r["populations"]["mangusa_case_size"] == 1
    assert r["populations"]["non_leaf_declared_coicop"] == 1
    assert r["populations"]["cc_1970_date"] == 1
    assert r["unexplained"] == 0


def test_populations_partition_the_changed_rows(tmp_path):
    # 'c' is BOTH mangusa_cw and a count change reachable by two rules; it must
    # be booked once, or "explained" could exceed the delta and hide a regression.
    ref = _write(tmp_path, "ref", BASE)
    after = {k: list(v) for k, v in BASE.items()}
    after["product_name_original"][2] = "rice pack of 12"
    after["count"][2] = 12
    new = _write(tmp_path, "new", after)

    r = parity.compare_keyed(
        ref / f"{SNAP}.parquet", new / f"{SNAP}.parquet", ("input_hash",)
    )
    assert sum(r["populations"].values()) + r["unexplained"] == r["changed"]


def test_a_change_nobody_named_is_unexplained(tmp_path):
    ref = _write(tmp_path, "ref", BASE)
    after = {k: list(v) for k, v in BASE.items()}
    after["price_local"][1] = 99.0  # ghana, no population covers it
    new = _write(tmp_path, "new", after)

    r = parity.compare_keyed(
        ref / f"{SNAP}.parquet", new / f"{SNAP}.parquet", ("input_hash",)
    )
    assert r["changed"] == 1
    assert r["unexplained"] == 1


def test_uv_only_change_does_not_swallow_a_price_change(tmp_path):
    # absolute_uv_gate is last and requires the change to be uv-ONLY, so a row
    # that also moved price stays with the sharper population.
    ref = _write(tmp_path, "ref", BASE)
    after = {k: list(v) for k, v in BASE.items()}
    after["unit_value_local"][0] = 7.0
    after["price_local"][0] = 7.0
    new = _write(tmp_path, "new", after)

    r = parity.compare_keyed(
        ref / f"{SNAP}.parquet", new / f"{SNAP}.parquet", ("input_hash",)
    )
    assert r["populations"]["slovak_slovenian_price"] == 1
    assert r["populations"]["absolute_uv_gate"] == 0


def test_null_equals_null_is_not_a_delta(tmp_path):
    frame = {k: list(v) for k, v in BASE.items()}
    frame["price_local"] = [np.nan] * 5
    ref = _write(tmp_path, "ref", frame)
    new = _write(tmp_path, "new", frame)
    r = parity.compare_keyed(
        ref / f"{SNAP}.parquet", new / f"{SNAP}.parquet", ("input_hash",)
    )
    assert r["changed"] == 0


def test_added_and_dropped_rows_are_not_counted_as_changed(tmp_path):
    ref = _write(tmp_path, "ref", BASE)
    after = {k: list(v)[:4] + [list(v)[4]] for k, v in BASE.items()}
    after["input_hash"][4] = "zz"
    new = _write(tmp_path, "new", after)
    r = parity.compare_keyed(
        ref / f"{SNAP}.parquet", new / f"{SNAP}.parquet", ("input_hash",)
    )
    assert r["dropped"] == 1
    assert r["added"] == 1
    assert r["changed"] == 0


def test_a_non_unique_key_is_refused(tmp_path):
    frame = {k: list(v) for k, v in BASE.items()}
    frame["input_hash"][1] = "a"
    ref = _write(tmp_path, "ref", frame)
    new = _write(tmp_path, "new", frame)
    with pytest.raises(ValueError, match="not unique"):
        parity.compare_keyed(
            ref / f"{SNAP}.parquet", new / f"{SNAP}.parquet", ("input_hash",)
        )


def test_the_same_name_in_two_countries_is_two_rows_not_a_duplicate(tmp_path):
    """A generic aggregator listing ("Eggs, x12") carries one name-hash but is
    reported by many countries at different prices. Under the declared grain
    those are distinct rows; under input_hash alone the build is undiffable."""
    frame = {k: list(v) for k, v in BASE.items()}
    frame["input_hash"][1] = "a"  # same name-hash as row 0...
    frame["country"][1] = "fiji"  # ...but a different country
    frame["price_local"][1] = 9.0
    ref = _write(tmp_path, "ref", frame)
    new = _write(tmp_path, "new", frame)

    key = parity.KEYS[SNAP]
    assert key == ("input_hash", "country")
    r = parity.compare_keyed(ref / f"{SNAP}.parquet", new / f"{SNAP}.parquet", key)

    assert r["common"] == 5
    assert r["dropped"] == 0 and r["added"] == 0 and r["changed"] == 0
