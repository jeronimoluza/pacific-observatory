import pytest

from prices.enrich.stages.classify import _structural_fields

pytestmark = pytest.mark.unit


def _sf(name, source=None, country="curacao"):
    return _structural_fields(name, None, country, "en", None, None, source)


def test_case_size_promotes_to_multiplier_on_mass():
    """The defect. "400gr (24 pieces)" is one 400g tin, 24 to the case, so the
    denominator is 9.6kg. Left inert it priced the whole case as one tin."""
    sf = _sf("Nutrilon Omneo 400gr (24 pieces)", "mangusa_cw")
    assert sf["pricing_basis"] == "mass"
    assert sf["amount_value"] == pytest.approx(0.4)
    assert sf["count"] == 1
    assert sf["multiplier"] == 24
    assert sf["is_multipack"] is True


def test_the_same_name_is_untouched_for_any_other_source():
    """The correction is a claim about one retailer's SKU convention, not about
    the words. Identical text from anywhere else must be unaffected."""
    for source in (None, "spinneys_eg", "aeon_online"):
        sf = _sf("Nutrilon Omneo 400gr (24 pieces)", source)
        assert sf["count"] == 24
        assert sf["multiplier"] == 1
        assert sf["is_multipack"] is False


def test_volume_was_already_correct_and_stays_correct():
    """Volume always multiplies, so this path never had the bug; assert the
    override does not double-apply on top of it."""
    sf = _sf("Unoli Canola oil 2ltr (6 pieces)", "mangusa_cw")
    assert sf["pricing_basis"] == "volume"
    assert sf["amount_value"] == pytest.approx(2.0)
    assert sf["multiplier"] == 6
    assert sf["count"] == 1


def test_count_basis_rows_are_not_promoted():
    """A count-basis row has no parsed measure: its count IS the denominator and
    already scales it, so promoting would divide by the case size twice."""
    sf = _sf("Assorted Sponges 12 pieces", "mangusa_cw")
    if sf["pricing_basis"] == "count":
        assert sf["multiplier"] == 1
        assert sf["count"] == 12


def test_a_row_with_no_piece_count_is_untouched():
    sf = _sf("Nutrilon Omneo 400gr", "mangusa_cw")
    assert sf["count"] == 1
    assert sf["multiplier"] == 1
    assert sf["is_multipack"] is False
