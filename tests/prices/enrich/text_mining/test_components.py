from prices.enrich import normalize
from prices.enrich.text_mining import components, spine


def test_decompose_returns_six_components():
    out = components.decompose("Coca-Cola 1.5L x6", "en", "beverages > soda")
    for key in (
        "brand",
        "identity_noun",
        "dimension",
        "magnitude",
        "pack",
        "breadcrumb",
    ):
        assert key in out


def test_decompose_volume_dimension_and_magnitude_match_spine():
    name = "Coca-Cola 1.5L x6"
    out = components.decompose(name, "en", "beverages")
    spans = spine.split_spans(name, "en")
    assert out["dimension"] == "volume"
    assert out["dimension"] == spans["pricing_basis"]
    assert out["magnitude"] is not None
    assert out["magnitude"] == spans["amount_value"]


def test_decompose_breadcrumb_matches_normalize_breadcrumb():
    category = "Beverages > Soft Drinks > Cola"
    out = components.decompose("Coca-Cola 1.5L x6", "en", category)
    assert out["breadcrumb"] == normalize.normalize_breadcrumb(category)


def test_decompose_pack_present_for_multipack():
    out = components.decompose("Coca-Cola 1.5L x6", "en", "beverages")
    assert out["pack"] is not None


def test_decompose_identity_noun_nonempty_for_named_item():
    out = components.decompose("White Rice 5kg", "en", "food > grains")
    assert out["identity_noun"]
    assert "rice" in out["identity_noun"].lower()


def test_decompose_empty_name_all_none_no_crash():
    out = components.decompose("", "en", None)
    assert out["brand"] is None
    assert out["identity_noun"] is None
    assert out["dimension"] is None
    assert out["magnitude"] is None
    assert out["pack"] is None
    assert out["breadcrumb"] == ""


def test_decompose_no_category_breadcrumb_empty():
    out = components.decompose("Hand Soap", "en", None)
    assert out["breadcrumb"] == ""


def test_decompose_cjk_routes_without_crash():
    out = components.decompose("白米 五公斤", "zh", "food")
    assert "dimension" in out
    assert out["identity_noun"] is not None
