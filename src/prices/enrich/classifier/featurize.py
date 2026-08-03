"""Feature extraction for the local classifier.

Char word-boundary n-gram TF-IDF over normalized product-name keys — the
representation the PoC validated (99.6% leaf-among-leaves on held-out names).
``detect_script`` mirrors the PoC's Unicode-range router so eval can report
per-script accuracy (the known CJK *data* gap: route, don't guess).
"""

from __future__ import annotations

from sklearn.feature_extraction.text import TfidfVectorizer

NGRAM_LO, NGRAM_HI = 3, 5
MIN_DF = 2


def build_vectorizer() -> TfidfVectorizer:
    return TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(NGRAM_LO, NGRAM_HI),
        min_df=MIN_DF,
        lowercase=False,
        sublinear_tf=True,
    )


def detect_script(s: str) -> str:
    for ch in str(s):
        o = ord(ch)
        if 0x4E00 <= o <= 0x9FFF or 0x3400 <= o <= 0x4DBF:
            return "cjk_han"
        if 0x3040 <= o <= 0x30FF:
            return "japanese_kana"
        if 0xAC00 <= o <= 0xD7AF:
            return "korean"
        if 0x0E00 <= o <= 0x0E7F:
            return "thai"
        if 0x0400 <= o <= 0x04FF:
            return "cyrillic"
        if 0x0600 <= o <= 0x06FF:
            return "arabic"
    return "latin_other"
