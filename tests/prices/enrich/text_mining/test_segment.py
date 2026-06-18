import pytest

from prices.enrich.text_mining.segment import (
    collocations,
    ngrams,
    segment,
    segment_auto,
)


def test_segment_latin_uses_str_split():
    assert segment("Coca Cola Zero", "latin") == ["Coca", "Cola", "Zero"]


@pytest.mark.parametrize("se_lang_str", ["Minyak Goreng 1L", "Beras Premium 5kg"])
def test_segment_se_asian_latin_uses_str_split(se_lang_str):
    # Indonesian/Malay/Vietnamese/Tagalog route through Latin whitespace split.
    assert segment(se_lang_str, "latin") == se_lang_str.split()


def test_segment_han_routes_jieba_multitoken():
    toks = segment("可口可乐橙汁", "han")
    assert toks
    assert len(toks) > 1  # jieba splits the multi-word zh string


def test_segment_katakana_routes_fugashi():
    toks = segment("コカ・コーラ", "katakana")
    assert toks
    # fugashi surfaces are reassemblable; not single-char Han fragments
    assert "".join(toks) == "コカ・コーラ"


def test_segment_thai_routes_newmm():
    toks = segment("น้ำมันพืช", "thai")
    assert toks
    assert all(t.strip() for t in toks)


def test_segment_hangul_routes_kiwipiepy():
    toks = segment("코카콜라 두부", "hangul")
    assert toks
    assert "두부" in toks  # kiwipiepy surfaces the noun form


def test_segment_auto_kana_string_routes_japanese_not_jieba():
    # A Han+kana Japanese string must reach fugashi, never jieba.
    s = "コカ・コーラ 500ml 6本"
    auto = segment_auto(s)
    via_ja = segment(s, "katakana")
    assert auto == via_ja
    assert auto  # non-empty


def test_segment_auto_pure_han_routes_jieba():
    s = "白米 五公斤"
    auto = segment_auto(s)
    via_zh = segment(s, "han")
    assert auto == via_zh
    assert auto


def test_segment_auto_latin():
    assert segment_auto("Fresh Lettuce") == ["Fresh", "Lettuce"]


def test_ngrams_basic():
    assert ngrams(["a", "b", "c"], 2) == [("a", "b"), ("b", "c")]
    assert ngrams(["a", "b", "c"], 3) == [("a", "b", "c")]
    assert ngrams(["a"], 2) == []


def test_collocations_counts_rankable():
    toks = ["a", "b", "a", "b", "c"]
    counts = collocations(toks, n=2)
    # ("a","b") occurs twice; result is a Counter (frequency-rankable)
    assert counts[("a", "b")] == 2
    assert counts.most_common(1)[0][0] == ("a", "b")


def test_segment_auto_over_corpus_rows(tiny_corpus):
    # Every row in the multilingual fixture yields a non-empty token list,
    # and Japanese kana rows never produce only single-char Han fragments.
    for _, row in tiny_corpus.iterrows():
        toks = segment_auto(row["product_name_original"])
        assert toks, f"empty tokens for {row['product_name_original']!r}"
