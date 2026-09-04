"""The snapshot must read EAP rows, not read everything and drop the rest.

products_input is the global corpus. `build_snapshot` wants one region out of
it, and reading the whole file first cost 27.1 GB of anon-rss and an oom-kill on
a 26 GB box. Pushing the predicate into the reader is only safe if it selects
exactly what the mask selected, so that equality is what these assert.
"""

from __future__ import annotations

import pandas as pd
import pytest

from prices.build import aggregate
from prices.build.basket import EAP_COUNTRIES

pytestmark = pytest.mark.unit


def write_corpus(path):
    """Two EAP countries and two that are not, interleaved so a reader that
    ignores the predicate and takes the first N rows still fails."""
    eap = sorted(EAP_COUNTRIES)[:2]
    rows = []
    for i in range(12):
        country = [eap[0], "france", eap[1], "brazil"][i % 4]
        rows.append({"input_hash": f"h{i}", "country": country, "price": float(i)})
    pd.DataFrame(rows).to_parquet(path, index=False)
    return path, eap


def test_pushdown_selects_exactly_what_the_mask_selected(tmp_path):
    path, eap = write_corpus(tmp_path / "pi.parquet")

    whole = pd.read_parquet(path)
    masked = whole[whole["country"].isin(EAP_COUNTRIES)].reset_index(drop=True)
    pushed = pd.read_parquet(
        path, filters=[("country", "in", sorted(EAP_COUNTRIES))]
    ).reset_index(drop=True)

    pd.testing.assert_frame_equal(masked, pushed)
    assert set(pushed["country"]) == set(eap)
    assert len(pushed) == 6


def test_the_snapshot_reader_is_not_reading_the_whole_corpus(tmp_path, monkeypatch):
    """A guard on the call itself. If someone reverts to an unfiltered read the
    equality test above still passes -- it exercises pandas, not the caller."""
    path, _ = write_corpus(tmp_path / "pi.parquet")
    monkeypatch.setattr(aggregate, "PRODUCTS_INPUT_PARQUET", path)

    seen = {}
    real = pd.read_parquet

    def spy(p, *a, **kw):
        if str(p) == str(path):
            seen["filters"] = kw.get("filters")
        return real(p, *a, **kw)

    monkeypatch.setattr(aggregate.pd, "read_parquet", spy)
    monkeypatch.setattr(
        aggregate,
        "load_filtered_cache",
        lambda: pd.DataFrame({"input_hash": ["h0"], "coicop_code": ["01.1.1.1.0"]}),
    )
    try:
        aggregate.build_snapshot()
    except Exception:
        # The join and _finalize need columns this fixture does not carry. The
        # assertion is about how the corpus was READ, which has already happened.
        pass

    assert seen.get("filters"), "build_snapshot read products_input unfiltered"
    field, op, _ = seen["filters"][0]
    assert (field, op) == ("country", "in")
