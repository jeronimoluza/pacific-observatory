from functools import lru_cache

from lingua import Language, LanguageDetectorBuilder

# Restricted to the languages actually present in the EAP corpus
# (src/configs/countries.yaml). Restricting the set is both a speed and a
# short-text-accuracy lever (RESEARCH Pattern 3 / Pitfall 5).
EAP_LANGUAGES = [
    Language.ENGLISH,
    Language.CHINESE,
    Language.JAPANESE,
    Language.KOREAN,
    Language.THAI,
    Language.INDONESIAN,
    Language.MALAY,
    Language.VIETNAMESE,
    Language.TAGALOG,
]

# Sentinel for empty / whitespace / undetectable input.
UNKNOWN = "und"


@lru_cache(maxsize=1)
def get_detector():
    return (
        LanguageDetectorBuilder.from_languages(*EAP_LANGUAGES)
        .with_preloaded_language_models()
        .build()
    )


def _iso(language) -> str:
    if language is None:
        return UNKNOWN
    return language.iso_code_639_1.name.lower()


def detect_languages(strings):
    strings = list(strings)
    # lingua's parallel batch API can choke on blank strings; route them to the
    # sentinel up front and only ask the detector about non-blank inputs.
    blank = [not s or not s.strip() for s in strings]
    payload = ["" if b else s for b, s in zip(blank, strings, strict=True)]
    detector = get_detector()
    detected = list(detector.detect_languages_in_parallel_of(payload))
    return [
        UNKNOWN if b else _iso(lang) for b, lang in zip(blank, detected, strict=True)
    ]


def confidence_values(string: str):
    if not string or not string.strip():
        return []
    return get_detector().compute_language_confidence_values(string)
