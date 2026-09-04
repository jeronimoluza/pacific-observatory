"""One row per category, and nothing converted that could not be."""

from __future__ import annotations

import pandas as pd
import pytest

from prices.build import unit_collapse


def _obs(rows):
    return pd.DataFrame(
        rows, columns=["coicop_code", "country", "standard_unit", "unit_value_usd"]
    )


def _mass(rows):
    return pd.DataFrame(
        rows,
        columns=["coicop_code", "unit", "median_amount", "accepted", "rejected_reason"],
    )


BANANAS = "01.1.6.1.2"
OIL = "01.1.5.1.3"
RICE = "01.1.1.2.1"


def test_the_display_unit_is_the_leaf_majority_unit():
    df = _obs(
        [(BANANAS, "fiji", "kg", 2.0)] * 3 + [(BANANAS, "tonga", "each", 0.5)],
    )
    assert unit_collapse.canonical_units(df) == {BANANAS: "kg"}


def test_a_tie_breaks_toward_mass_not_toward_whichever_sorted_first():
    df = _obs([(BANANAS, "fiji", "each", 0.5), (BANANAS, "tonga", "kg", 2.0)])
    assert unit_collapse.canonical_units(df)[BANANAS] == "kg"


def test_piece_rows_join_the_mass_row_instead_of_forming_a_second_one():
    """The reported defect: "Bananas, fresh /kg" and "/each" as two table rows."""
    df = _obs(
        [(BANANAS, "fiji", "kg", 2.0)] * 3 + [(BANANAS, "tonga", "each", 0.4)],
    )
    mass = _mass([(BANANAS, "kg", 0.2, True, None)])

    out, dropped = unit_collapse.collapse(df, mass, value_cols=("unit_value_usd",))

    assert dropped.empty
    assert out["standard_unit"].unique().tolist() == ["kg"]
    assert len(out.groupby(["coicop_code", "country"])) == out["country"].nunique()
    # $0.40 for a 0.2 kg banana is $2.00/kg -- it lands on the measured rows.
    assert out.loc[out["country"] == "tonga", "unit_value_usd"].iloc[0] == pytest.approx(
        2.0
    )


def test_a_leaf_the_mass_table_rejected_drops_its_piece_rows_with_that_reason():
    """Rice is rejected for unstable mass; a rice "unit" is a bag of unknown size,
    so converting it would fabricate a per-kilo price rather than reveal one."""
    df = _obs([(RICE, "fiji", "kg", 2.0)] * 3 + [(RICE, "tonga", "each", 9.0)])
    mass = _mass([(RICE, "kg", 1.0, False, "unstable_mass (robust_cv=0.80>0.5)")])

    out, dropped = unit_collapse.collapse(df, mass, value_cols=("unit_value_usd",))

    assert len(out) == 3
    assert len(dropped) == 1
    assert "unstable_mass" in dropped["drop_reason"].iloc[0]
    assert dropped["display_unit"].iloc[0] == "kg"


def test_volume_converts_to_mass_through_the_leaf_density_not_through_water():
    """Oil is 0.92 kg/lt. A litre priced at $9.20 is $10.00 per kilo, and using
    water here would report $9.20 -- an 8% error applied to every oil row."""
    df = _obs([(OIL, "fiji", "kg", 10.0)] * 3 + [(OIL, "tonga", "lt", 9.20)])

    out, _ = unit_collapse.collapse(df, _mass([]), value_cols=("unit_value_usd",))

    assert out["standard_unit"].unique().tolist() == ["kg"]
    assert out.loc[out["country"] == "tonga", "unit_value_usd"].iloc[0] == pytest.approx(
        10.0
    )
    assert out.loc[out["country"] == "tonga", "display_unit_source"].iloc[0] == "density"


def test_a_density_conversion_is_reversible():
    """Whichever unit wins the vote, the leaf's level must be the same."""
    kg_wins = _obs([(OIL, "a", "kg", 10.0)] * 2 + [(OIL, "b", "lt", 9.20)])
    lt_wins = _obs([(OIL, "a", "lt", 9.20)] * 2 + [(OIL, "b", "kg", 10.0)])

    a, _ = unit_collapse.collapse(kg_wins, _mass([]), value_cols=("unit_value_usd",))
    b, _ = unit_collapse.collapse(lt_wins, _mass([]), value_cols=("unit_value_usd",))

    assert a["unit_value_usd"].round(6).nunique() == 1
    assert b["unit_value_usd"].round(6).nunique() == 1


def test_a_leaf_absent_from_the_mass_table_still_drops_rather_than_guesses():
    df = _obs([(BANANAS, "fiji", "kg", 2.0)] * 3 + [(BANANAS, "tonga", "each", 0.4)])
    out, dropped = unit_collapse.collapse(df, _mass([]), value_cols=("unit_value_usd",))
    assert len(out) == 3
    assert dropped["drop_reason"].iloc[0] == "no typical mass for leaf"


def test_a_leaf_already_in_one_unit_is_untouched():
    df = _obs([(RICE, "fiji", "kg", 2.0), (RICE, "tonga", "kg", 3.0)])
    out, dropped = unit_collapse.collapse(df, _mass([]), value_cols=("unit_value_usd",))
    assert dropped.empty
    assert out["unit_value_usd"].tolist() == [2.0, 3.0]
    assert (out["display_unit_source"] == "native").all()


def test_a_piece_mass_measured_in_litres_still_reaches_a_kilo_display():
    """The mass table records some leaves in lt. That is not a reason to drop
    the leaf's piece rows when the display unit came out kg."""
    df = _obs([(BANANAS, "fiji", "kg", 2.0)] * 3 + [(BANANAS, "tonga", "each", 0.4)])
    mass = _mass([(BANANAS, "lt", 0.2, True, None)])
    out, dropped = unit_collapse.collapse(df, mass, value_cols=("unit_value_usd",))
    assert dropped.empty
    assert out["standard_unit"].unique().tolist() == ["kg"]
