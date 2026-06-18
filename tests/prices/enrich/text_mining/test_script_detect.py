from prices.enrich.text_mining.script_detect import (
    char_script,
    dominant_script,
    script_histogram,
)


def test_char_script_one_per_family():
    assert char_script("A") == "latin"
    assert char_script("5") == "digit"
    assert char_script("好") == "han"
    assert char_script("あ") == "hiragana"
    assert char_script("ア") == "katakana"
    assert char_script("한") == "hangul"
    assert char_script("ก") == "thai"
    assert char_script(",") == "punct"
    assert char_script(" ") == "space"


def test_dominant_script_ignores_digit_punct_space():
    # only latin letters survive the digit/punct/space filter
    assert dominant_script("A1, B2 C3") == "latin"


def test_dominant_script_kana_present_routes_japanese():
    # Han + kana mix: kana presence overrides pure-Han -> a kana script
    assert dominant_script("コカ・コーラ 500ml 6本") in ("katakana", "hiragana")
    assert dominant_script("醤油 1リットル") in ("katakana", "hiragana")
    assert dominant_script("おにぎり 鮭") in ("katakana", "hiragana")


def test_dominant_script_pure_han_routes_chinese():
    assert dominant_script("白米 五公斤") == "han"
    assert dominant_script("洗发水") == "han"


def test_dominant_script_latin_string():
    assert dominant_script("Minyak Goreng 1L") == "latin"
    assert dominant_script("Nuoc Mam 500ml") == "latin"


def test_dominant_script_thai_and_hangul():
    assert dominant_script("น้ำมันพืช 1 ลิตร") == "thai"
    assert dominant_script("쌀 10kg") == "hangul"


def test_dominant_script_empty_defaults_latin():
    assert dominant_script("") == "latin"
    assert dominant_script("123 !!!") == "latin"


def test_script_histogram_sums_to_classified_chars():
    s = "Abc あア 5,"
    hist = script_histogram(s)
    # histogram counts every classified char (incl digit/punct/space)
    assert sum(hist.values()) == len(s)
    assert hist["latin"] == 3
    assert hist["hiragana"] == 1
    assert hist["katakana"] == 1
    assert hist["digit"] == 1
    assert hist["punct"] == 1
    assert hist["space"] == 2


def test_script_histogram_over_tiny_corpus(tiny_corpus):
    for name in tiny_corpus["product_name_original"]:
        hist = script_histogram(name)
        assert sum(hist.values()) == len(name)


def test_dominant_script_routes_every_corpus_row(tiny_corpus):
    by_lang = dict(
        zip(tiny_corpus["lang"], tiny_corpus["product_name_original"], strict=True)
    )
    # ja rows must route to a kana script (not han) so they reach fugashi
    assert dominant_script(by_lang["ja"]) in ("katakana", "hiragana")
    # zh rows must route to han so they reach jieba
    assert dominant_script(by_lang["zh"]) == "han"
    assert dominant_script(by_lang["ko"]) == "hangul"
    assert dominant_script(by_lang["th"]) == "thai"
    for lang in ("en", "id", "ms", "vi", "tl"):
        assert dominant_script(by_lang[lang]) == "latin"
