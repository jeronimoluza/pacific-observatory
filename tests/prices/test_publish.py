import pandas as pd
import pytest

from prices import publish


def _obs() -> pd.DataFrame:
    """Observations as the live build emits them — coicop_code is the finest
    grain, there is NO sub_label_id column (the classifier never produces one)."""
    now = pd.Timestamp.now().normalize()
    return pd.DataFrame(
        {
            "coicop_code": ["01.1.1.1", "01.1.1.1", "01.1.2.1"],
            "country": ["fiji", "tonga", "fiji"],
            "unit_value_usd": [2.0, 3.0, 5.0],
            "observation_date": [now - pd.Timedelta(days=5)] * 3,
            "standard_unit": ["kg", "kg", "lt"],
        }
    )


@pytest.mark.unit
def test_current_snapshot_groups_by_coicop_leaf():
    snap = publish._current_snapshot(_obs())
    assert "sub_label_id" not in snap.columns
    assert set(snap["coicop_code"]) == {"01.1.1.1", "01.1.2.1"}
    assert len(snap) == 3  # (01.1.1.1, fiji), (01.1.1.1, tonga), (01.1.2.1, fiji)


@pytest.mark.unit
def test_payload_keyed_on_coicop_leaf():
    snap = publish._current_snapshot(_obs())
    monthly = publish._monthly_series(_obs())
    payload = publish._payload(snap, monthly)
    # region median is a single float per coicop leaf, not a per-sub-label dict
    assert isinstance(payload["region_medians"]["01.1.1.1"], float)
    # no retired sub_label_id key leaks into the emitted records
    assert all("sub_label_id" not in r for r in payload["current"])
    assert all("sub_label_id" not in r for r in payload["monthly"])
