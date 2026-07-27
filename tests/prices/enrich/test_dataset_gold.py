"""Gold consolidation: a single canonical gold_labels.parquet, derived from the
gold_v5_* sources by `consolidate_gold` and read back by `_load_gold`."""

from __future__ import annotations

import pandas as pd
import pytest

from prices.enrich.classifier import dataset

pytestmark = [pytest.mark.unit]


def _gold(rows):
    return pd.DataFrame(rows, columns=["product_name", "code", "verdict"])


def test_consolidate_gold_unions_v5_sources(tmp_path):
    _gold([["Milk 1L", "01.1.4.1.1", "leaf"]]).to_parquet(
        tmp_path / "gold_v5_8k_final.parquet", index=False
    )
    _gold([["Cola 330ml", "01.2.6.0.0", "leaf"]]).to_parquet(
        tmp_path / "gold_v5_fnb_extra.parquet", index=False
    )
    _gold([["Rice 5kg", "01.1.1.3.1", "leaf"]]).to_parquet(
        tmp_path / "gold_v5_round7_final.parquet", index=False
    )

    summary = dataset.consolidate_gold(tmp_path)

    out = tmp_path / "gold_labels.parquet"
    assert out.exists()
    assert summary["n_rows"] == 3
    assert set(summary["sources"]) == {
        "gold_v5_8k_final.parquet",
        "gold_v5_fnb_extra.parquet",
        "gold_v5_round7_final.parquet",
    }
    assert len(pd.read_parquet(out)) == 3


def test_consolidate_gold_is_idempotent(tmp_path):
    _gold([["Milk 1L", "01.1.4.1.1", "leaf"]]).to_parquet(
        tmp_path / "gold_v5_8k_final.parquet", index=False
    )
    dataset.consolidate_gold(tmp_path)
    dataset.consolidate_gold(tmp_path)  # a stale gold_labels must not be re-ingested
    assert len(pd.read_parquet(tmp_path / "gold_labels.parquet")) == 1


def test_load_gold_reads_consolidated_and_derives_division(tmp_path):
    _gold([["Milk 1L", "01.1.4.1.1", "leaf"]]).to_parquet(
        tmp_path / "gold_labels.parquet", index=False
    )
    g = dataset._load_gold(tmp_path)
    assert g.loc[0, "division"] == "01"


def test_load_gold_missing_points_at_consolidate(tmp_path):
    with pytest.raises(FileNotFoundError, match="consolidate"):
        dataset._load_gold(tmp_path)
