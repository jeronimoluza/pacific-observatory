import pandas as pd

from prices.enrich.text_mining import failures, mi


def test_coicop_class_4digit_truncation():
    assert failures.coicop_class("01.2.2.0.1") == "01.2.2"
    assert failures.coicop_class("13.1.2.0") == "13.1.2"
    assert failures.coicop_division("01.2.2.0.1") == "01"
    assert failures.coicop_division("13.1.2.0") == "13"


def test_component_leaf_mi_table_non_negative_bits(tiny_gold):
    rows = failures.component_leaf_mi(tiny_gold)
    assert rows, "expected at least one component MI row"
    for r in rows:
        assert r["mi_leaf_bits"] >= 0.0
        assert r["mi_class_bits"] >= 0.0
        # continuous magnitude has no normalized info-gain (kNN estimator)
        if r["component"] != "magnitude":
            assert 0.0 <= r["norm_info_gain_leaf"] <= 1.0


def test_component_leaf_mi_matches_mi_bits(tiny_gold):
    # dimension is computed from the name via components.decompose; recompute
    # the same component column here and assert the table value == mi.mi_bits.
    from prices.enrich.text_mining import components

    comps = [
        components.decompose(n, lang, None)["dimension"]
        for n, lang in zip(
            tiny_gold["product_name"], tiny_gold["language"], strict=False
        )
    ]
    leaves = list(tiny_gold["coicop_code_gold"])
    expected = mi.mi_bits(
        ["" if c is None else c for c in comps],
        leaves,
    )
    rows = failures.component_leaf_mi(tiny_gold)
    dim_row = next(r for r in rows if r["component"] == "dimension")
    # table reports MI rounded for display; assert it tracks mi.mi_bits exactly
    assert dim_row["mi_leaf_bits"] == round(expected, 4)
    assert expected > 0.0


def test_reports_both_leaf_and_4digit_class(tiny_gold):
    rows = failures.component_leaf_mi(tiny_gold)
    sample = rows[0]
    assert "mi_leaf_bits" in sample
    assert "mi_class_bits" in sample


def test_f4_breadcrumb_and_dimension_info_gain(tiny_gold):
    f4 = failures.f4_category(tiny_gold)
    assert "breadcrumb" in f4
    assert "dimension" in f4
    for key in ("breadcrumb", "dimension"):
        assert 0.0 <= f4[key]["norm_info_gain_leaf"] <= 1.0


def test_slice_by_language_division_channel_with_low_n_flag(tiny_gold):
    sliced = failures.slice_by_lang_division_channel(tiny_gold)
    assert sliced, "expected at least one slice cell"
    # every cell carries an indicative flag (n far below the floor on tiny gold)
    assert any(cell["indicative"] for cell in sliced)
    for cell in sliced:
        assert {"language", "division", "channel", "n", "indicative"} <= set(cell)


def test_build_report_markdown_has_bias_caveat_and_sections(tiny_gold):
    md = failures.build_report(tiny_gold)
    assert "# F1" in md or "## F1" in md
    for f in ("F1", "F2", "F3", "F4", "F5", "F6"):
        assert f in md
    lower = md.lower()
    assert "bias" in lower
    assert "permutation" in lower
    assert "normalized info-gain" in lower or "normalized info gain" in lower


def test_build_report_writes_markdown_to_report_dir(tiny_gold, tmp_path, monkeypatch):
    from prices.enrich.text_mining import io

    monkeypatch.setattr(io, "REPORT_DIR", tmp_path)
    path = failures.write_report(tiny_gold)
    assert path.exists()
    assert path.suffix == ".md"
    assert path.read_text(encoding="utf-8").strip()


def test_component_component_mi_label_free(tiny_gold):
    # dimension -> breadcrumb MI over a corpus-shaped frame, label-free.
    corpus = pd.DataFrame(
        {
            "product_name_original": list(tiny_gold["product_name"]),
            "lang": list(tiny_gold["language"]),
            "category": ["food > x"] * len(tiny_gold),
            "channel": ["supermarket"] * len(tiny_gold),
        }
    )
    rows = failures.component_component_mi(corpus)
    assert rows
    for r in rows:
        assert r["mi_bits"] >= 0.0
