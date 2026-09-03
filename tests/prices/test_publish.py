import pandas as pd
import pytest

from prices import publish


def _obs() -> pd.DataFrame:
    """Observations as the live build emits them — (coicop_code, standard_unit)
    is the finest grain, there is NO sub_label_id column (the classifier never
    produces one). The last row puts 01.1.1.1 in a second unit so the mixed-unit
    case is covered."""
    now = pd.Timestamp.now().normalize()
    return pd.DataFrame(
        {
            "coicop_code": ["01.1.1.1", "01.1.1.1", "01.1.2.1", "01.1.1.1"],
            "country": ["fiji", "tonga", "fiji", "fiji"],
            "unit_value_usd": [2.0, 3.0, 5.0, 900.0],
            "observation_date": [now - pd.Timedelta(days=5)] * 4,
            "standard_unit": ["kg", "kg", "lt", "lt"],
        }
    )


@pytest.mark.unit
def test_current_snapshot_groups_by_coicop_leaf_and_unit():
    snap = publish._current_snapshot(_obs())
    assert "sub_label_id" not in snap.columns
    assert set(snap["coicop_code"]) == {"01.1.1.1", "01.1.2.1"}
    # (01.1.1.1, fiji, kg) (01.1.1.1, tonga, kg) (01.1.2.1, fiji, lt)
    # (01.1.1.1, fiji, lt) — the lt row does NOT fold into fiji's kg median
    assert len(snap) == 4
    fiji_kg = snap[
        snap["coicop_code"].eq("01.1.1.1")
        & snap["country"].eq("fiji")
        & snap["standard_unit"].eq("kg")
    ]
    assert fiji_kg["median_usd"].iloc[0] == 2.0


@pytest.mark.unit
def test_payload_keyed_on_coicop_leaf():
    snap = publish._current_snapshot(_obs())
    monthly = publish._monthly_series(_obs())
    payload = publish._payload(snap, monthly)
    # keyed on (coicop leaf, unit), then on region — not on a retired sub-label
    medians = payload["region_medians"]["01.1.1.1|kg"]
    assert set(medians) <= {c["key"] for c in payload["region_cols"]}
    assert all(isinstance(v, float) for v in medians.values())
    # fiji and tonga are both EAP, so the region and world medians agree here
    assert medians["world"] == medians["eap"] == 2.5
    # the 900.0 lt observation lands in its own row and never moves the kg one
    assert payload["region_medians"]["01.1.1.1|lt"]["world"] == 900.0
    # no retired sub_label_id key leaks into the emitted records
    assert all("sub_label_id" not in r for r in payload["current"])
    assert all("sub_label_id" not in r for r in payload["monthly"])


@pytest.mark.unit
def test_piece_units_fold_only_on_allowlisted_leaves():
    """item and unit are one quantity on a sold-by-item leaf, two elsewhere."""
    now = pd.Timestamp.now().normalize()
    leaf = sorted(publish.SOLD_BY_ITEM_LEAVES)[0]
    df = pd.DataFrame(
        {
            "coicop_code": [leaf, leaf, "01.1.1.1", "01.1.1.1"],
            "country": ["fiji"] * 4,
            "unit_value_usd": [2.0, 1.0, 2.0, 1.0],
            "observation_date": [now - pd.Timedelta(days=5)] * 4,
            "standard_unit": ["item", "unit", "item", "unit"],
        }
    )
    snap = publish._current_snapshot(df)
    on = snap[snap["coicop_code"].eq(leaf)]
    off = snap[snap["coicop_code"].eq("01.1.1.1")]
    # allowlisted leaf: one folded row carrying both observations
    assert list(on["standard_unit"]) == [publish.MERGED_PIECE_UNIT]
    assert on["n_obs"].iloc[0] == 2
    assert on["median_usd"].iloc[0] == 1.5
    # off-allowlist: untouched, still two rows -- item there means "no quantity"
    assert set(off["standard_unit"]) == {"item", "unit"}
