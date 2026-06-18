import pytest

from .conftest import GOLD_COLUMNS, PRODUCTS_INPUT_COLUMNS

pytestmark = pytest.mark.unit


def _dominant_script(s: str) -> str:
    for c in s:
        cp = ord(c)
        if 0x3040 <= cp <= 0x309F or 0x30A0 <= cp <= 0x30FF:
            return "kana"
        if 0xAC00 <= cp <= 0xD7AF:
            return "hangul"
        if 0x0E00 <= cp <= 0x0E7F:
            return "thai"
    for c in s:
        cp = ord(c)
        if 0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF:
            return "han"
    return "latin"


def test_tiny_corpus_columns(tiny_corpus):
    assert list(tiny_corpus.columns) == PRODUCTS_INPUT_COLUMNS


def test_tiny_corpus_row_count(tiny_corpus):
    assert len(tiny_corpus) >= 28


def test_tiny_corpus_covers_five_script_families(tiny_corpus):
    scripts = {_dominant_script(name) for name in tiny_corpus["product_name_original"]}
    assert {"latin", "han", "kana", "thai", "hangul"} <= scripts


def test_tiny_corpus_has_han_only_and_kana_pair(tiny_corpus):
    scripts = [_dominant_script(n) for n in tiny_corpus["product_name_original"]]
    assert "han" in scripts  # zh, pure-Han -> jieba
    assert "kana" in scripts  # ja, kana present -> fugashi


def test_tiny_corpus_has_structural_and_plain_rows(tiny_corpus):
    import re

    has_span = tiny_corpus["product_name_original"].apply(
        lambda s: bool(re.search(r"\d", s))
    )
    assert has_span.any()  # several carry mass/volume/count spans
    assert (~has_span).any()  # several carry none


def test_tiny_gold_columns(tiny_gold):
    assert list(tiny_gold.columns) == GOLD_COLUMNS


def test_tiny_gold_spans_at_least_three_leaves(tiny_gold):
    assert tiny_gold["coicop_code_gold"].nunique() >= 3


def test_tiny_gold_row_count(tiny_gold):
    assert len(tiny_gold) >= 10


def test_fixtures_are_deterministic(tiny_corpus, tiny_gold):
    # No NaN in key identity columns -> in-memory, no file/network gaps.
    assert tiny_corpus["product_name_original"].notna().all()
    assert tiny_gold["coicop_code_gold"].notna().all()
