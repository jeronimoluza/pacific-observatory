import pytest

from prices.enrich.uv_gate import (
    BASIS_NOT_GATED,
    LEAF_NOT_ALLOWED,
    NO_COICOP_CODE,
    OK,
    gate,
    is_allowed_leaf,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "code",
    [
        "01.1.4.6.0",  # yoghurt
        "01.2.5.0.0",  # water
        "02.1.3.0",  # beer
        "04.5.3.1",  # liquid fuels
        "07.2.2.4",  # motor fuels and lubricants
        "05.6.1.1",  # cleaning products
        "13.1.2.0",  # personal-care products
    ],
)
def test_allowed_leaves(code):
    assert is_allowed_leaf(code)


@pytest.mark.parametrize(
    "code",
    [
        "06.1.1.1",  # pharma -- the 1,412-row dose-as-net-weight family
        "08.2.0.0",  # comms -- the "5G" / "4G" as grams family
        "05.3.1.0",  # major appliances -- capacity read as content
        "13.2.9.1",  # nappies sized by wearer weight -- sibling of allowed 13.1.2
        "05.6.1.9",  # bin bags sized by capacity -- sibling of allowed 05.6.1.1
        "02.3.0.0",  # tobacco: sold per stick, deliberately excluded
        "04.5.1.0",  # electricity: kWh, not mass or volume
    ],
)
def test_denied_leaves(code):
    assert not is_allowed_leaf(code)


def test_prefix_match_is_segment_aware():
    """ "02.1" must not admit a hypothetical two-digit sibling."""
    assert is_allowed_leaf("02.1.3.0")
    assert not is_allowed_leaf("02.10.1")


@pytest.mark.parametrize("code", [None, "", float("nan"), 12])
def test_non_string_codes_are_not_allowed(code):
    assert not is_allowed_leaf(code)


def test_measured_basis_on_allowed_leaf_is_adopted():
    assert gate("01.1.4.6.0", "mass") == (True, OK)


def test_allowed_and_denied_siblings_are_split_at_the_leaf():
    """The two widened classes each sit beside a sibling that must stay out:
    05.6.1.9 sacks and 13.2.9 nappies both carry a size that is not the quantity
    sold, so the allow-list is authored at leaf depth, not class depth."""
    assert gate("05.6.1.1", "volume") == (True, OK)
    assert gate("05.6.1.9", "volume") == (False, LEAF_NOT_ALLOWED)
    assert gate("13.1.2.0", "mass") == (True, OK)
    assert gate("13.2.9.1", "mass") == (False, LEAF_NOT_ALLOWED)


def test_measured_basis_on_denied_leaf_is_refused():
    assert gate("06.1.1.1", "mass") == (False, LEAF_NOT_ALLOWED)


def test_measured_basis_without_a_leaf_is_refused():
    """A rejected/unembedded row has no category evidence to gate on."""
    assert gate(None, "volume") == (False, NO_COICOP_CODE)
    assert gate("", "volume") == (False, NO_COICOP_CODE)


@pytest.mark.parametrize("basis", ["item", "count", None])
def test_ungated_bases_pass_through_on_any_leaf(basis):
    """Layer 1 has no opinion on count/item -- the reason names them as ungated
    so a pass is never mistaken for a check."""
    for code in ("01.1.4.6.0", "06.1.1.1", None):
        assert gate(code, basis) == (True, BASIS_NOT_GATED)


def _products(names, countries, codes=None):
    import pandas as pd

    n = len(names)
    return pd.DataFrame(
        {
            "input_hash": [f"h{i}" for i in range(n)],
            "product_name_original": names,
            "category": [None] * n,
            "country": countries,
            "lang": ["en"] * n,
            "details": [None] * n,
            "declared_coicop_codes": codes or [None] * n,
        }
    )


NAME_KEY = ("product_name_original",)


def _scored(leaf_by, conf=0.99, accepted=True, gate=0.97):
    """name -> (leaf, conf, accepted, leaf_top1, gate_score) on the name key."""
    return {(n,): (leaf, conf, accepted, leaf, gate) for n, leaf in leaf_by.items()}


def test_decide_rows_emits_uv_trusted():
    """Wiring check: the gate's verdict reaches the decision table, and the two
    families it exists to stop (pharma dose, `5G` as grams) come back False even
    though extraction still reads a mass off both names."""
    from prices.enrich.stages.classify import decide_rows

    names = ["Yoghurt 500g", "Avodart 0.5mg", "iPhone 15 5G 256GB"]
    leaves = ["01.1.4.6.0", "06.1.1.1", "08.1.1.0"]
    products = _products(names, ["peru"] * 3)
    out = decide_rows(
        products, _scored(dict(zip(names, leaves))), NAME_KEY, frozenset()
    )

    assert "uv_trusted" in out.columns
    by_name = {n: bool(v) for n, v in zip(names, out["uv_trusted"])}
    assert by_name["Yoghurt 500g"]
    assert not by_name["Avodart 0.5mg"]
    assert not by_name["iPhone 15 5G 256GB"]
    # The gate withholds adoption; it never edits what extraction read.
    assert out.loc[1, "pricing_basis"] == "mass"
    assert out.loc[2, "pricing_basis"] == "mass"


def test_rejected_row_gets_no_trusted_denominator():
    """No accepted leaf means no category evidence, so a measured denominator is
    not adoptable even when the name plainly states one."""
    from prices.enrich.stages.classify import decide_rows

    products = _products(["Yoghurt 500g"], ["peru"])
    out = decide_rows(
        products,
        _scored({"Yoghurt 500g": "01.1.4.6.0"}, conf=0.10, accepted=False, gate=0.20),
        NAME_KEY,
        frozenset(),
    )
    assert out.loc[0, "state"] == "rejected"
    assert not bool(out.loc[0, "uv_trusted"])


def test_item_basis_is_trusted_regardless_of_leaf():
    """`item` carries a denominator of 1 by construction, so layer 1 passes it
    through on any leaf -- including one the allow-list excludes."""
    from prices.enrich.stages.classify import decide_rows

    products = _products(["Paracetamol Tablets"], ["peru"])
    out = decide_rows(
        products, _scored({"Paracetamol Tablets": "06.1.1.1"}), NAME_KEY, frozenset()
    )
    assert out.loc[0, "pricing_basis"] == "item"
    assert bool(out.loc[0, "uv_trusted"])


def test_hierlex_writers_carry_uv_trusted():
    """Both HierLex outputs must carry the column.

    `decide_rows` sets it, but the column only REACHES disk because
    `decisions_hierlex.parquet` is written against `DECISION_SCHEMA` and
    `classified_hierlex.parquet` through `classified_view`'s ENRICHMENT_COLS
    projection. Either projection could be narrowed without touching the gate,
    so assert the two writer contracts directly.
    """
    import pyarrow as pa

    from prices.enrich.stages.classify import (
        DECISION_COLS,
        DECISION_SCHEMA,
        classified_view,
        decide_rows,
    )
    from prices.enrich.stages.merge import ENRICHMENT_COLS

    assert "uv_trusted" in ENRICHMENT_COLS
    assert "uv_trusted" in DECISION_COLS
    assert DECISION_SCHEMA.field("uv_trusted").type == pa.bool_()

    products = _products(["Yoghurt 500g", "Avodart 0.5mg"], ["peru", "peru"])
    dec = decide_rows(
        products,
        _scored({"Yoghurt 500g": "01.1.4.6.0", "Avodart 0.5mg": "06.1.1.1"}),
        NAME_KEY,
        frozenset(),
    )
    # decisions_hierlex.parquet: the arrow writer must accept the frame as-is.
    table = pa.Table.from_pandas(dec, schema=DECISION_SCHEMA, preserve_index=False)
    assert table.column("uv_trusted").to_pylist() == [True, False]
    # classified_hierlex.parquet: the division view must retain it.
    view = classified_view(dec, ("01",))
    assert "uv_trusted" in view.columns
    assert bool(view.loc[0, "uv_trusted"])


def test_hierlex_parent_fallback_codes_are_gated_by_prefix():
    """HierLex may assign at PARENT grain via a synthetic
    `<parent>.__parent_fallback__` token, which reaches `coicop_code` verbatim.
    Segment-aware prefix matching must still read it as its division: wine
    admits a volume denominator, a partially-allowed parent does not."""
    assert is_allowed_leaf("02.1.2.__parent_fallback__")
    assert is_allowed_leaf("01.1.4.__parent_fallback__")
    assert is_allowed_leaf("07.2.2.__parent_fallback__")
    # `13.1.2` is allowed but its parent `13.1` is not -- the fallback is
    # coarser than the allow-list, so it must NOT inherit the grant.
    assert not is_allowed_leaf("13.1.__parent_fallback__")
    # ditto `05.6.1.1` vs the `05.6.1` parent (bin bags live under 05.6.1.9).
    assert not is_allowed_leaf("05.6.1.__parent_fallback__")
    assert not is_allowed_leaf("06.1.1.__parent_fallback__")
