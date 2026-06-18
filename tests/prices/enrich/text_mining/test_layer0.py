import pandas as pd

from prices.enrich.text_mining.layer0_probe import (
    REQUIRED_SECTIONS,
    build_layer0_report,
    render,
)


def test_script_distribution_shares_sum_to_one(tiny_corpus):
    report = build_layer0_report(tiny_corpus)
    shares = report["script_distribution"]["overall"]
    total = sum(row["share"] for row in shares)
    assert abs(total - 1.0) < 1e-6


def test_structural_span_density_bounded(tiny_corpus):
    report = build_layer0_report(tiny_corpus)
    density = report["structural_span_density"]["overall"]
    assert 0.0 <= density <= 1.0


def test_language_distribution_keys_are_iso(tiny_corpus):
    report = build_layer0_report(tiny_corpus)
    block = report["language_distribution"]
    assert "overall" in block
    langs = [row["language"] for row in block["overall"]]
    assert langs
    assert all(isinstance(code, str) and 2 <= len(code) <= 3 for code in langs)


def test_per_script_char_frequency_present(tiny_corpus):
    report = build_layer0_report(tiny_corpus)
    block = report["per_script_char_frequency"]["overall"]
    assert block
    assert all("script" in row and "char" in row for row in block)


def test_length_distributions_present(tiny_corpus):
    report = build_layer0_report(tiny_corpus)
    token_block = report["token_length_dist"]["overall"]
    char_block = report["char_length_dist"]["overall"]
    assert token_block["mean"] >= 0.0
    assert char_block["mean"] >= 0.0


def test_word_ngram_collocation_top_lists(tiny_corpus):
    report = build_layer0_report(tiny_corpus)
    assert report["word_top"]["overall"]
    assert "ngram_top" in report
    assert "collocation_top" in report


def test_blocks_sliced_by_country_channel(tiny_corpus):
    report = build_layer0_report(tiny_corpus)
    sliced = report["script_distribution"]["by_country_channel"]
    assert sliced
    a_key = next(iter(sliced))
    assert isinstance(a_key, tuple)
    assert len(a_key) == 2


def test_rendered_markdown_has_required_headers(tiny_corpus):
    report = build_layer0_report(tiny_corpus)
    md = render(report)
    for header in REQUIRED_SECTIONS:
        assert header in md


def test_default_is_unweighted(tiny_corpus):
    unweighted = build_layer0_report(tiny_corpus)
    weighted = build_layer0_report(tiny_corpus, weighted=True)
    # n_rows varies per row, so weighting must change at least the char-length mean.
    assert (
        unweighted["char_length_dist"]["overall"]["mean"]
        != weighted["char_length_dist"]["overall"]["mean"]
    )


def test_empty_frame_no_crash():
    empty = pd.DataFrame(
        {
            "product_name_original": [],
            "country": [],
            "channel": [],
            "lang": [],
            "n_rows": [],
        }
    )
    report = build_layer0_report(empty)
    md = render(report)
    assert isinstance(md, str)
    assert report["structural_span_density"]["overall"] == 0.0
