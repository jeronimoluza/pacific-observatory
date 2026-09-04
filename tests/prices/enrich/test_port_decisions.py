"""The port must inherit the existing decisions exactly, or refuse."""

import pandas as pd
import pytest

from prices.enrich import port_decisions
from prices.enrich.stages import classify, decisions_store


def decisions_frame(rows):
    """A decisions table as it exists BEFORE the port: no `country` column."""
    cols = [c for c in classify.DECISION_COLS if c != "country"]
    out = pd.DataFrame(
        [{c: None for c in cols} for _ in rows],
        columns=cols,
    )
    for i, (h, code, state) in enumerate(rows):
        out.loc[i, "input_hash"] = h
        out.loc[i, "coicop_code"] = code
        out.loc[i, "state"] = state
        out.loc[i, "trust_level"] = "high"
        out.loc[i, "pricing_basis"] = "item"
    for c in ("amount_value", "count", "multiplier", "confidence", "gate_score"):
        out[c] = out[c].astype("float64")
    for c in (
        "is_promotion",
        "is_bundle",
        "is_multipack",
        "uv_trusted",
        "unit_declared",
    ):
        out[c] = False
    return out


def products_frame(rows):
    return pd.DataFrame(
        [{"input_hash": h, "country": c} for h, c in rows],
    )


def setup_files(tmp_path, dec_rows, prod_rows):
    dec = tmp_path / "decisions.parquet"
    prod = tmp_path / "products_input.parquet"
    decisions_frame(dec_rows).to_parquet(dec, index=False)
    products_frame(prod_rows).to_parquet(prod, index=False)
    return dec, prod


def test_port_attaches_country_by_position_and_preserves_every_row(tmp_path):
    dec, prod = setup_files(
        tmp_path,
        [("h1", "01.1.1.1", "classified"), ("h2", "02.1.1.1", "rejected")],
        [("h1", "fiji"), ("h2", "samoa")],
    )
    summary = port_decisions.port(dec, prod)

    assert summary["rows"] == 2
    assert summary["countries"] == 2
    out = decisions_store.read(dec).set_index("input_hash")
    assert out.loc["h1", "country"] == "fiji"
    assert out.loc["h2", "country"] == "samoa"
    assert out.loc["h1", "coicop_code"] == "01.1.1.1"


def test_port_refuses_when_the_row_counts_disagree(tmp_path):
    dec, prod = setup_files(
        tmp_path,
        [("h1", "01.1.1.1", "classified")],
        [("h1", "fiji"), ("h2", "samoa")],
    )
    with pytest.raises(port_decisions.AlignmentError, match="rows but"):
        port_decisions.port(dec, prod)


def test_port_refuses_when_the_hashes_do_not_line_up(tmp_path):
    """Same length, wrong order — the case that would silently mislabel."""
    dec, prod = setup_files(
        tmp_path,
        [("h1", "01.1.1.1", "classified"), ("h2", "02.1.1.1", "rejected")],
        [("h2", "samoa"), ("h1", "fiji")],
    )
    with pytest.raises(port_decisions.AlignmentError, match="input_hash mismatch"):
        port_decisions.port(dec, prod)


def test_a_refused_port_publishes_nothing(tmp_path):
    dec, prod = setup_files(
        tmp_path,
        [("h1", "01.1.1.1", "classified"), ("h2", "02.1.1.1", "rejected")],
        [("h2", "samoa"), ("h1", "fiji")],
    )
    with pytest.raises(port_decisions.AlignmentError):
        port_decisions.port(dec, prod)
    root = decisions_store.parts_root(dec)
    assert not list(root.glob("*.parquet"))


def test_port_survives_a_batch_boundary(tmp_path):
    """Alignment is checked per batch; the cursor must carry across them."""
    rows = [(f"h{i}", "01.1.1.1", "classified") for i in range(50)]
    prod = [(f"h{i}", "fiji" if i % 2 else "samoa") for i in range(50)]
    dec_path, prod_path = setup_files(tmp_path, rows, prod)

    port_decisions.port(dec_path, prod_path, batch_rows=7)
    out = decisions_store.read(dec_path)
    assert len(out) == 50
    assert set(out["country"]) == {"fiji", "samoa"}
    assert out[out["country"] == "fiji"]["input_hash"].tolist() == [
        f"h{i}" for i in range(50) if i % 2
    ]


def test_ported_decisions_reread_through_the_store_match_the_original(tmp_path):
    rows = [(f"h{i}", "01.1.1.1", "classified") for i in range(10)]
    dec_path, prod_path = setup_files(
        tmp_path, rows, [(f"h{i}", "fiji") for i in range(10)]
    )
    before = pd.read_parquet(dec_path).sort_values("input_hash")
    port_decisions.port(dec_path, prod_path)
    after = decisions_store.read(dec_path).sort_values("input_hash")

    assert len(before) == len(after)
    pd.testing.assert_series_equal(
        before["coicop_code"].reset_index(drop=True),
        after["coicop_code"].reset_index(drop=True),
    )


def test_port_classified_derives_the_view_from_the_ported_parts(tmp_path):
    dec, prod = setup_files(
        tmp_path,
        [
            ("h1", "01.1.1.1", "classified"),
            ("h2", "02.1.1.1", "classified"),
            ("h3", "01.2.2.2", "classified"),
        ],
        [("h1", "fiji"), ("h2", "fiji"), ("h3", "samoa")],
    )
    port_decisions.port(dec, prod)
    view_root = tmp_path / "classified"
    summary = port_decisions.port_classified(
        decisions_store.parts_root(dec), view_root, ("01",)
    )

    # Division 02 is out of scope for the view, so h2 is dropped.
    assert summary["rows"] == 2
    view = decisions_store.read(view_root)
    assert sorted(view["input_hash"]) == ["h1", "h3"]
    # The view keeps its contract: no country column.
    assert "country" not in view.columns
    assert decisions_store.existing_countries(view_root) == {"fiji", "samoa"}
