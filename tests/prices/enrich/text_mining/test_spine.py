import pandas as pd

from prices.enrich.extract import extract
from prices.enrich.text_mining.spine import split_spans, structural_span_density


def _assert_matches_tier_a(name: str, lang: str | None) -> None:
    spans = split_spans(name, lang)
    sf = extract(name, None, None, lang)
    assert spans["pricing_basis"] == sf.pricing_basis
    assert spans["amount_value"] == sf.amount_value
    assert spans["standard_unit"] == sf.standard_unit
    assert spans["count"] == sf.count
    assert spans["multiplier"] == sf.multiplier
    assert spans["is_promotion"] == sf.is_promotion
    assert spans["is_multipack"] == sf.is_multipack


def test_split_spans_matches_tier_a_volume_multipack():
    _assert_matches_tier_a("Coca-Cola 1.5L x6", "en")


def test_split_spans_matches_tier_a_mass():
    _assert_matches_tier_a("Tide Detergent 2kg", "en")


def test_split_spans_matches_tier_a_plain_item():
    _assert_matches_tier_a("Fresh Lettuce", "en")


def test_split_spans_matches_tier_a_zh_mass_pack():
    _assert_matches_tier_a("可口可乐 500g 6入", "zh")


def test_identity_span_has_pack_removed():
    spans = split_spans("Coca-Cola 1.5L x6", "en")
    low = spans["identity_span"].lower()
    assert "1.5l" not in low
    assert "x6" not in low
    assert spans["pricing_basis"] == "volume"
    assert spans["amount_value"] == 1.5


def test_has_structural_span_true_for_packed_item():
    spans = split_spans("Coca-Cola 1.5L x6", "en")
    assert spans["has_structural_span"] is True


def test_has_structural_span_false_for_plain_item():
    spans = split_spans("Plain Bread", "en")
    assert spans["has_structural_span"] is False
    assert spans["pricing_basis"] == "item"


def test_empty_input_no_crash():
    spans = split_spans("   ", None)
    assert spans["has_structural_span"] is False
    assert spans["amount_value"] is None


def test_structural_span_density_bounded(tiny_corpus):
    density = structural_span_density(tiny_corpus)
    assert 0.0 <= density <= 1.0


def test_structural_span_density_sliced(tiny_corpus):
    sliced = structural_span_density(tiny_corpus, by="lang")
    assert isinstance(sliced, pd.Series)
    assert ((sliced >= 0.0) & (sliced <= 1.0)).all()


def test_structural_span_density_empty_frame():
    empty = pd.DataFrame({"product_name_original": [], "lang": []})
    assert structural_span_density(empty) == 0.0
