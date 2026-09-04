"""Latin terms inside non-space-delimited keyword packs need their own boundary.

Thai, Khmer, Burmese, Lao and the CJK packs match as bare substrings, because
those scripts do not put spaces between words. They also carry Latin strings --
IMF, GDP, ASEAN, WHO -- because those languages print them verbatim. Matching
those as bare substrings let `UN` fire inside "fund" and `AI` inside "said":
measured on 57.6 MB of real Thai, Chinese, Japanese, Burmese, Lao and Khmer
articles, 2,741 of `UN`'s 2,874 hits were false, and `FFA`, `MARA`, `MPS`,
`CORN`, `PETROL`, `NFA` and `QE` were false every single time.

A Latin term is therefore bounded by "not an ASCII letter" rather than by
``\\b``. ``\\b`` would be wrong here: Thai and Han text runs flush against
embedded Latin, so ``\\b`` would drop the real hits.

Both matchers are covered. The regex in ``utils`` is used by the older EPU
path; the Aho-Corasick automaton in ``annotate`` is what a build actually runs,
and a fix in one without the other would leave the two disagreeing.
"""

import pytest

from src.text.analysis.annotate import KeywordBundle, build_combined_automaton
from src.text.analysis.annotate import _match_all_categories
from src.text.analysis.utils import match_keywords

# (term, text, language, should_match, why)
CASES = [
    ("un", "the fund announced a plan", "thai", False, "inside 'fund'"),
    ("un", "รายงานของ un ระบุว่า", "thai", True, "standalone, spaced"),
    ("un", "รายงานของunระบุว่า", "thai", True, "flush against Thai"),
    ("ai", "he said that yesterday", "thai", False, "inside 'said'"),
    ("ai", "เทคโนโลยี ai ใหม่", "thai", True, "standalone"),
    ("gdp", "gdp ขยายตัว", "thai", True, "standalone"),
    ("gdp", "ตัวเลขgdpล่าสุด", "thai", True, "flush against Thai"),
    ("war", "afterward the talks resumed", "my", False, "inside 'afterward'"),
    ("ida", "abidance in the law", "km", False, "inside 'abidance'"),
    ("mps", "the camps were cleared", "my", False, "inside 'camps'"),
    ("ocha", "a mocha latte", "km", False, "inside 'mocha'"),
    ("nfa", "brazenfaced denial", "lao", False, "inside 'brazenfaced'"),
    # non-Latin terms keep bare substring matching
    ("经济", "中国经济增长放缓", "chinese_simplified", True, "Han substring"),
    ("เงินเฟ้อ", "ปัญหาเงินเฟ้อรุนแรง", "thai", True, "Thai substring"),
    # space-delimited languages are untouched by any of this
    ("un", "the fund announced a plan", "en", False, "english \\b unchanged"),
    ("trade", "a trade deficit widened", "en", True, "english \\b unchanged"),
    ("trade", "balustrade repairs", "en", False, "english \\b unchanged"),
]


@pytest.mark.parametrize("term,text,language,expected,why", CASES)
def test_regex_matcher_bounds_latin_terms(term, text, language, expected, why):
    found, _ = match_keywords(text, [term], language)
    assert found is expected, f"{language}: '{term}' in '{text}' ({why})"


@pytest.mark.parametrize("term,text,language,expected,why", CASES)
def test_automaton_matcher_agrees_with_regex(term, text, language, expected, why):
    """The build runs the automaton, so it must reach the same verdict."""
    bundle = KeywordBundle(
        language=language,
        epu={"economic": [term], "policy": [], "uncertainty": []},
        topics={},
        actors={},
        script_language=language,
    )
    counts = _match_all_categories(text, build_combined_automaton(bundle))
    assert (counts["econ"] > 0) is expected, f"{language}: '{term}' in '{text}' ({why})"
