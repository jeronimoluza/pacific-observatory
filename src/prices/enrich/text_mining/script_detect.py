import unicodedata
from collections import Counter

_RANGES = [
    ("hiragana", 0x3040, 0x309F),
    ("katakana", 0x30A0, 0x30FF),
    ("han", 0x4E00, 0x9FFF),
    ("han_ext_a", 0x3400, 0x4DBF),
    ("hangul", 0xAC00, 0xD7AF),
    ("thai", 0x0E00, 0x0E7F),
    ("cyrillic", 0x0400, 0x04FF),
    ("arabic", 0x0600, 0x06FF),
]

_NON_LETTER = ("digit", "punct", "space")

_KANA = ("hiragana", "katakana")

# Scripts that own a dedicated segmenter. When any of these letters appear, the
# string routes to that segmenter even if embedded Latin unit tokens (kg/ml)
# happen to outnumber them. Latin is the catch-all fallback (str.split).
_SEGMENTER_SCRIPTS = (
    "hiragana",
    "katakana",
    "han",
    "han_ext_a",
    "hangul",
    "thai",
    "cyrillic",
    "arabic",
)


def char_script(c: str) -> str:
    if c.isdigit():
        return "digit"
    cp = ord(c)
    for name, lo, hi in _RANGES:
        if lo <= cp <= hi:
            return name
    cat = unicodedata.category(c)
    if cat[0] in ("P", "S"):
        return "punct"
    if cat[0] == "Z":
        return "space"
    if "LATIN" in unicodedata.name(c, ""):
        return "latin"
    return "other"


def script_histogram(s: str) -> Counter:
    return Counter(char_script(c) for c in s)


def dominant_script(s: str) -> str:
    counts = Counter(
        script for script in (char_script(c) for c in s) if script not in _NON_LETTER
    )
    if not counts:
        return "latin"
    if any(counts.get(k, 0) for k in _KANA):
        kana = {k: counts[k] for k in _KANA if counts.get(k, 0)}
        return max(kana, key=kana.get)
    seg = {s: counts[s] for s in _SEGMENTER_SCRIPTS if counts.get(s, 0)}
    if seg:
        return max(seg, key=seg.get)
    return counts.most_common(1)[0][0]
