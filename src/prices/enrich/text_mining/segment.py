import logging
from collections import Counter
from functools import lru_cache

import jieba
from fugashi import Tagger
from kiwipiepy import Kiwi
from pythainlp.tokenize import word_tokenize as _th_tok

from prices.enrich.text_mining.script_detect import dominant_script

jieba.setLogLevel(logging.ERROR)

_KANA = ("hiragana", "katakana")
_HAN = ("han", "han_ext_a")


@lru_cache(maxsize=1)
def _ja_tagger() -> Tagger:
    return Tagger()


@lru_cache(maxsize=1)
def _ko_tagger() -> Kiwi:
    return Kiwi()


def _segment_japanese(s: str) -> list[str]:
    return [w.surface for w in _ja_tagger()(s) if w.surface.strip()]


def _segment_chinese(s: str) -> list[str]:
    return [t for t in jieba.lcut(s) if t.strip()]


def _segment_thai(s: str) -> list[str]:
    return [t for t in _th_tok(s, engine="newmm") if t.strip()]


def _segment_korean(s: str) -> list[str]:
    return [t.form for t in _ko_tagger().tokenize(s) if t.form.strip()]


def segment(s: str, script: str) -> list[str]:
    if script in _KANA:
        return _segment_japanese(s)
    if script in _HAN:
        return _segment_chinese(s)
    if script == "thai":
        return _segment_thai(s)
    if script == "hangul":
        return _segment_korean(s)
    return s.split()


def segment_auto(s: str) -> list[str]:
    return segment(s, dominant_script(s))


def ngrams(tokens: list[str], n: int) -> list[tuple[str, ...]]:
    if n < 1 or len(tokens) < n:
        return []
    return [tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]


def collocations(tokens: list[str], n: int = 2) -> Counter:
    return Counter(ngrams(tokens, n))
