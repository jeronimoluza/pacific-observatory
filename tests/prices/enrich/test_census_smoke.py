"""Read-only SC5 smoke test for the shape × regex_id census.

Runs `run_census` over a tiny synthetic fixture (never the real
products.parquet) into a pytest `tmp_path`, and proves the three census
contracts: aggregator-channel rows are excluded, a non-empty
`census_shape_regex.parquet` with the expected columns is emitted to `tmp_path`,
and the returned Counter is non-empty. A hard read-only guard snapshots the
`data/` and `outputs/` subtrees before and after the run and asserts nothing
under either was created or modified (CLAUDE.md data-safety hard constraint).
"""

from __future__ import annotations

import os

import pandas as pd
import pytest

from prices.enrich import census, config

pytestmark = [pytest.mark.unit]


def _snapshot(root):
    """Map every file under `root` to (mtime_ns, size). Empty when absent."""
    snap = {}
    if not root.exists():
        return snap
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            path = os.path.join(dirpath, name)
            try:
                st = os.stat(path)
            except FileNotFoundError:
                continue
            snap[path] = (st.st_mtime_ns, st.st_size)
    return snap


def _fixture_df():
    return pd.DataFrame(
        {
            "product_name_original": [
                "Milk 1L",  # value-unit (volume)
                "Eggs 12 PCS",  # count-pack
                "Rice per kg",  # per-kg
                "Plain Notebook",  # bare item
                "Soda 500ml x 6",  # multipack measure
                "Aggregator Combo 2kg",  # excluded (aggregator channel)
            ],
            "channel": [
                "supermarket",
                "supermarket",
                "supermarket",
                "supermarket",
                "hypermarket",
                "aggregator",
            ],
        }
    )


def test_census_excludes_aggregators_and_is_read_only(tmp_path):
    df = _fixture_df()

    # (a) aggregator row excluded at the population-filter boundary.
    names = census._unique_names(df)
    assert "Aggregator Combo 2kg" not in names
    assert "Milk 1L" in names

    data_root = config.REPO_ROOT / "data"
    outputs_root = config.REPO_ROOT / "outputs"
    before_data = _snapshot(data_root)
    before_outputs = _snapshot(outputs_root)

    counter = census.run_census(df, out_dir=tmp_path)

    # (c) returned Counter has at least one (shape, regex_id) entry.
    assert len(counter) >= 1

    # (b) a non-empty census parquet under tmp_path with the expected columns.
    out_path = tmp_path / census.CENSUS_PARQUET_NAME
    assert out_path.exists()
    out_df = pd.read_parquet(out_path)
    assert set(out_df.columns) == {"shape", "regex_id", "fire_count"}
    assert not out_df.empty

    # (d) nothing under data/ or outputs/ was created or modified.
    assert _snapshot(data_root) == before_data
    assert _snapshot(outputs_root) == before_outputs
