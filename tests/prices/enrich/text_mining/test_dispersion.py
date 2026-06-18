import json

import numpy as np
import pandas as pd
import pytest

from prices.enrich.text_mining import io
from prices.enrich.text_mining.dispersion import (
    F5_PARQUET_NAME,
    F5_SCHEMA,
    LOW_N_FLOOR,
    build_f5,
)

_EXPECTED_COLUMNS = [
    "coicop_leaf",
    "country",
    "n",
    "unit_value_mean",
    "unit_value_std",
    "cov",
    "dimension_mix",
    "n_suppressed_flag",
]


def test_schema_constant_matches_expected_columns():
    assert F5_SCHEMA == _EXPECTED_COLUMNS


def _gold_with_known_group(floor: int) -> pd.DataFrame:
    # One (leaf x country) group with known unit values 4, 6, 8 (n=3),
    # padded with extra rows so n >= floor for the un-suppressed assertion.
    rows = []
    for v in [4.0, 6.0, 8.0]:
        rows.append(("Rice", "01.1.1.0.1", "philippines", "en", "rice", "mass", v))
    # pad the same group up to the floor
    for _ in range(floor):
        rows.append(("Rice", "01.1.1.0.1", "philippines", "en", "rice", "mass", 6.0))
    # a separate low-n group (n=2 < floor)
    rows.append(("Cola", "01.2.2.0.1", "japan", "ja", "soft_drink", "volume", 0.5))
    rows.append(("Cola", "01.2.2.0.1", "japan", "ja", "soft_drink", "volume", 0.5))
    return pd.DataFrame(
        rows,
        columns=[
            "product_name",
            "coicop_code_gold",
            "country",
            "language",
            "sub_label_gold",
            "basis_gold",
            "val_gold",
        ],
    )


def test_build_f5_returns_frame_and_markdown(tiny_gold):
    frame, md = build_f5(tiny_gold, source="gold")
    assert isinstance(frame, pd.DataFrame)
    assert isinstance(md, str)
    assert len(md) > 0


def test_frame_columns_exactly_locked_schema(tiny_gold):
    frame, _ = build_f5(tiny_gold, source="gold")
    assert list(frame.columns) == _EXPECTED_COLUMNS


def test_cov_equals_std_over_mean_known_group():
    gold = _gold_with_known_group(LOW_N_FLOOR)
    frame, _ = build_f5(gold, source="gold")
    grp = frame[
        (frame["coicop_leaf"] == "01.1.1.0.1") & (frame["country"] == "philippines")
    ].iloc[0]
    assert grp["cov"] == pytest.approx(grp["unit_value_std"] / grp["unit_value_mean"])


def test_n_suppressed_flag_true_below_floor_false_above():
    gold = _gold_with_known_group(LOW_N_FLOOR)
    frame, _ = build_f5(gold, source="gold")
    high = frame[
        (frame["coicop_leaf"] == "01.1.1.0.1") & (frame["country"] == "philippines")
    ].iloc[0]
    low = frame[
        (frame["coicop_leaf"] == "01.2.2.0.1") & (frame["country"] == "japan")
    ].iloc[0]
    assert bool(high["n_suppressed_flag"]) is False
    assert bool(low["n_suppressed_flag"]) is True
    assert int(high["n"]) >= LOW_N_FLOOR
    assert int(low["n"]) < LOW_N_FLOOR


def test_dimension_mix_parses_as_json_basis_share(tiny_gold):
    frame, _ = build_f5(tiny_gold, source="gold")
    for raw in frame["dimension_mix"]:
        mix = json.loads(raw)
        assert isinstance(mix, dict)
        assert all(isinstance(k, str) for k in mix)
        assert all(isinstance(v, (int, float)) for v in mix.values())
        assert mix == {} or pytest.approx(sum(mix.values()), abs=1e-9) == 1.0


def test_parquet_written_under_report_dir(tiny_gold, tmp_path, monkeypatch):
    monkeypatch.setattr(io, "REPORT_DIR", tmp_path)
    written = build_f5(tiny_gold, source="gold", write=True)
    parquet_path = written["parquet_path"]
    assert parquet_path.name == F5_PARQUET_NAME
    assert tmp_path.resolve() in parquet_path.resolve().parents
    reread = pd.read_parquet(parquet_path)
    assert list(reread.columns) == _EXPECTED_COLUMNS


def test_written_parquet_path_resolves_under_text_mining():
    assert io.REPORT_DIR.name == "_text_mining"
    assert "_enrich" in str(io.REPORT_DIR)


def test_corpus_source_uses_price_over_amount_times_multiplier():
    # corpus unit value = price / amount_value / multiplier; basis from pricing_basis.
    corpus = pd.DataFrame(
        [
            ("Rice 1kg", "philippines", "en", 100.0, "01.1.1.0.1"),
            ("Rice 2kg", "philippines", "en", 200.0, "01.1.1.0.1"),
        ],
        columns=[
            "product_name_original",
            "country",
            "lang",
            "price",
            "declared_coicop_codes",
        ],
    )
    frame, _ = build_f5(corpus, source="corpus")
    assert list(frame.columns) == _EXPECTED_COLUMNS
    # both resolve to ~100/kg, so unit_value_mean ~ 100 and cov small
    grp = frame.iloc[0]
    assert grp["unit_value_mean"] == pytest.approx(100.0, rel=1e-6)


def test_empty_input_returns_empty_locked_schema_frame():
    empty = pd.DataFrame(
        columns=[
            "product_name",
            "coicop_code_gold",
            "country",
            "language",
            "sub_label_gold",
            "basis_gold",
            "val_gold",
        ]
    )
    frame, md = build_f5(empty, source="gold")
    assert list(frame.columns) == _EXPECTED_COLUMNS
    assert len(frame) == 0
    assert isinstance(md, str)


def test_single_row_group_std_zero_cov_zero():
    gold = pd.DataFrame(
        [("Solo", "09.9.9.0.1", "fiji", "en", "x", "mass", 3.0)],
        columns=[
            "product_name",
            "coicop_code_gold",
            "country",
            "language",
            "sub_label_gold",
            "basis_gold",
            "val_gold",
        ],
    )
    frame, _ = build_f5(gold, source="gold")
    grp = frame.iloc[0]
    assert grp["unit_value_std"] == pytest.approx(0.0)
    assert grp["cov"] == pytest.approx(0.0)
    assert np.isfinite(grp["cov"])
