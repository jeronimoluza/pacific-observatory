import pandas as pd
import pytest

from prices.build import aggregate, leaf_typical_mass, sold_by_item

pytestmark = pytest.mark.unit

LEAF = "01.1.7.4.1"  # not in SOLD_BY_ITEM_LEAVES, so it is convertible


def measured_rows(n, amount, leaf=LEAF, country="fiji"):
    return pd.DataFrame(
        {
            "coicop_code": [leaf] * n,
            "country": [country] * n,
            "pricing_basis": ["mass"] * n,
            "amount_value": [amount] * n,
            "standard_unit": ["kg"] * n,
            "count": [float("nan")] * n,
            "multiplier": [float("nan")] * n,
            "price": ["10"] * n,
            "currency": ["FJD"] * n,
        }
    )


def item_row(leaf=LEAF, country="fiji"):
    return pd.DataFrame(
        {
            "coicop_code": [leaf],
            "country": [country],
            "pricing_basis": ["item"],
            "amount_value": [float("nan")],
            "standard_unit": ["item"],
            "count": [float("nan")],
            "multiplier": [float("nan")],
            "price": ["10"],
            "currency": ["FJD"],
        }
    )


@pytest.fixture(autouse=True)
def isolated_table(tmp_path, monkeypatch):
    """Keep the persisted table inside tmp_path — these tests write it."""
    path = tmp_path / "leaf_typical_mass.csv"
    monkeypatch.setattr(leaf_typical_mass, "TYPICAL_MASS_CSV", path)
    monkeypatch.setattr(leaf_typical_mass, "BUILD_DIR", tmp_path)
    monkeypatch.setattr(aggregate, "TYPICAL_MASS_CSV", path)
    return path


def test_full_frame_derives_and_writes_the_table(isolated_table):
    df = pd.concat([measured_rows(40, 1.0), item_row()], ignore_index=True)
    out = sold_by_item.convert_item_rows(df)
    assert isolated_table.exists()
    assert (out["mass_source"] == "derived_typical").sum() == 1
    assert out.loc[out["mass_source"] == "derived_typical", "amount_value"].iloc[0] == 1.0


def test_a_slice_derives_a_different_mass_than_the_corpus(isolated_table):
    """Why the pin exists. The corpus says this leaf typically weighs 1 kg;
    the slice, on its own rows, says 5 kg — and the converted row's unit value
    then differs from the full build for no reason to do with the fix."""
    corpus = pd.concat(
        [measured_rows(40, 1.0), measured_rows(40, 5.0, country="tonga")],
        ignore_index=True,
    )
    corpus_mass = leaf_typical_mass.derive_typical_mass(corpus)
    slice_mass = leaf_typical_mass.derive_typical_mass(
        measured_rows(40, 5.0, country="tonga")
    )
    assert leaf_typical_mass.accepted_lookup(corpus_mass) != leaf_typical_mass.accepted_lookup(
        slice_mass
    )


def test_a_pinned_table_is_used_and_never_rewritten(isolated_table):
    corpus = pd.concat([measured_rows(40, 1.0), item_row()], ignore_index=True)
    sold_by_item.convert_item_rows(corpus)
    pinned = leaf_typical_mass.read_typical_mass()
    stamp = isolated_table.stat().st_mtime_ns

    # A slice whose own rows would say 5 kg, converted against the pin.
    sliced = pd.concat(
        [measured_rows(40, 5.0, country="tonga"), item_row(country="tonga")],
        ignore_index=True,
    )
    out = sold_by_item.convert_item_rows(sliced, table=pinned)
    converted = out[out["mass_source"] == "derived_typical"]
    assert converted["amount_value"].iloc[0] == 1.0
    assert isolated_table.stat().st_mtime_ns == stamp


def test_read_typical_mass_round_trips_the_accepted_flag(isolated_table):
    table = leaf_typical_mass.derive_typical_mass(measured_rows(40, 1.0))
    leaf_typical_mass.write_typical_mass(table)
    back = leaf_typical_mass.read_typical_mass()
    assert back["accepted"].dtype == bool
    assert leaf_typical_mass.accepted_lookup(back) == leaf_typical_mass.accepted_lookup(
        table
    )


def test_read_typical_mass_is_none_when_absent(isolated_table):
    assert leaf_typical_mass.read_typical_mass() is None


def test_a_full_build_recomputes_by_default(isolated_table):
    assert aggregate._pinned_typical_mass(scoped=False, recompute=None) is None


def test_a_scoped_build_pins_by_default(isolated_table):
    leaf_typical_mass.write_typical_mass(
        leaf_typical_mass.derive_typical_mass(measured_rows(40, 1.0))
    )
    table = aggregate._pinned_typical_mass(scoped=True, recompute=None)
    assert table is not None
    assert leaf_typical_mass.accepted_lookup(table)[LEAF][0] == 1.0


def test_a_scoped_build_with_no_pin_raises_rather_than_deriving(isolated_table):
    with pytest.raises(RuntimeError, match="pinned typical-mass table"):
        aggregate._pinned_typical_mass(scoped=True, recompute=None)


def test_recompute_overrides_the_default_in_both_directions(isolated_table):
    leaf_typical_mass.write_typical_mass(
        leaf_typical_mass.derive_typical_mass(measured_rows(40, 1.0))
    )
    assert aggregate._pinned_typical_mass(scoped=True, recompute=True) is None
    assert aggregate._pinned_typical_mass(scoped=False, recompute=False) is not None
