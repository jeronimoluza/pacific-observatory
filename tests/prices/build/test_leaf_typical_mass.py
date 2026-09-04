"""The price-ratio gate must see the rows unit_collapse actually converts.

Reproduces the eggs leaf on the production build: piece rows arrive with
`pricing_basis="count"` (an explicit multipack marker, e.g. "Eggs x12", was
divided out upstream), never `pricing_basis="item"`. The gate's `convertible`
mask filtered on `pricing_basis == "item"` only, so on the real corpus (where
every converting leaf's piece rows are `count`-basis, zero are `item`-basis)
it is structurally blind: `leaf_price_ratios` returns empty for every leaf
that actually converts, and `implausible_price_ratio` never fires.

The measured (mass-basis) rows here model a multi-egg carton -- amount_value
is the PACK's mass, not one egg's -- while the count-basis rows already carry
a genuine per-egg price (price / count, computed upstream). Dividing a
per-egg price by a per-carton mass is off by roughly the carton size, which
is exactly the kind of error `implausible_price_ratio` exists to catch.
"""

from __future__ import annotations

import pandas as pd

from prices.build import leaf_typical_mass as ltm

CODE = "01.1.4.8.1"  # eggs, in prod; any code not on the sold_by_item allowlist


def _eggs_frame() -> pd.DataFrame:
    rows = []
    # 40 measured (mass-basis) rows: a carton weighing ~0.66kg, priced at a
    # realistic ~$5/kg for eggs bought by weight.
    for i in range(40):
        rows.append(
            dict(
                coicop_code=CODE,
                country="testland",
                pricing_basis="mass",
                standard_unit="kg",
                amount_value=0.66,
                count=None,
                multiplier=1.0,
                price_local=3.3,  # 3.3 / 0.66 = $5.00/kg
            )
        )
    # 20 count-basis rows: "Eggs x12" style, price already reflects one dozen
    # and count=12 divides it down to a genuine ~$0.20 per single egg.
    for i in range(20):
        rows.append(
            dict(
                coicop_code=CODE,
                country="testland",
                pricing_basis="count",
                standard_unit="unit",
                amount_value=None,
                count=12.0,
                multiplier=1.0,
                price_local=2.40,  # 2.40 / 12 = $0.20 per egg
            )
        )
    return pd.DataFrame(rows)


def test_a_count_basis_piece_mismatch_is_caught_by_the_ratio_gate():
    """Dividing a per-egg price by a per-carton mass understates the derived
    $/kg by roughly the carton size (12x here) -- the ratio gate must catch
    this even though the piece rows are `count`-basis, not `item`-basis."""
    df = _eggs_frame()

    table = ltm.derive_typical_mass(df)
    row = table[table["coicop_code"] == CODE].iloc[0]

    assert not row["accepted"], (
        "a typical mass that produces a ~12x price disagreement between "
        "count-basis piece rows and measured mass rows must not be accepted"
    )
    assert "implausible_price_ratio" in row["rejected_reason"]


def test_the_ratio_gate_still_ignores_sold_by_item_leaves():
    """Leaves on the sold_by_item allowlist keep their piece rows natively --
    unit_collapse never converts them -- so the gate must still leave them out
    of the ratio check regardless of pricing_basis."""
    from prices.build.sold_by_item import SOLD_BY_ITEM_LEAVES

    sbi_code = next(iter(SOLD_BY_ITEM_LEAVES))
    df = _eggs_frame()
    df["coicop_code"] = sbi_code

    table = ltm.derive_typical_mass(df)
    ratios = ltm.leaf_price_ratios(df, table[table["accepted"]])
    assert ratios.empty or sbi_code not in set(ratios["coicop_code"])
