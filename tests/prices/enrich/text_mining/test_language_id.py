from prices.enrich.text_mining.language_id import (
    EAP_LANGUAGES,
    UNKNOWN,
    confidence_values,
    detect_languages,
    get_detector,
)


def test_detect_languages_aligned_with_input(tiny_corpus):
    names = list(tiny_corpus["product_name_original"])
    result = detect_languages(names)
    assert isinstance(result, list)
    assert len(result) == len(names)


def test_japanese_and_thai_resolve(tiny_corpus):
    by_lang = dict(
        zip(tiny_corpus["lang"], tiny_corpus["product_name_original"], strict=True)
    )
    out = {
        lang: detect_languages([by_lang[lang]])[0] for lang in ("ja", "th", "ko", "zh")
    }
    assert out["ja"] == "ja"
    assert out["th"] == "th"
    assert out["ko"] == "ko"
    assert out["zh"] == "zh"


def test_detector_set_is_restricted():
    # the configured set is the 9 EAP languages, excluding common non-EAP ones
    iso = {lang.iso_code_639_1.name.lower() for lang in EAP_LANGUAGES}
    assert "de" not in iso  # German excluded
    assert "fr" not in iso  # French excluded
    assert "ja" in iso and "th" in iso and "en" in iso
    assert len(EAP_LANGUAGES) == 9


def test_empty_and_whitespace_return_sentinel():
    assert detect_languages([""]) == [UNKNOWN]
    assert detect_languages(["   "]) == [UNKNOWN]
    assert detect_languages(["123 !!!"]) == [UNKNOWN]


def test_confidence_values_for_single_string():
    conf = confidence_values("Hello world this is English")
    assert isinstance(conf, list)
    assert conf  # non-empty
    top = conf[0]
    assert 0.0 <= top.value <= 1.0


def test_detector_is_singleton():
    assert get_detector() is get_detector()
