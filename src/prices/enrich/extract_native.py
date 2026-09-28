"""The row language's own pack patterns, as a fallback behind English.

`extract_pack` is first-match-wins and the native count patterns (LOC_VI,
SET_JA, COUNT_UNIT_*) sit ahead of VALUE_UNIT, so a declared-lang pass run in
vi/ja read "Lốc 4 ... Hộp 180Ml" as count 4 and lost the size. The declared-lang
pass therefore runs English; the native pass only fills the `pack_none` slot
that Pass 1b/1b2 fall back to, so it adds a count but never shadows a size.

Measured 2026-09-28 (vault prices-refactor/2026-09-28-weekly-run.md, step 8a):
native lang lost the size on 1,039 Vietnam and 3,448 Japan products; this
reading recovers them and changes 0 of 60k English names.
"""

from __future__ import annotations

from prices.enrich.normalize import extract_pack
from prices.enrich.regex_patterns._registry import ALWAYS_LANG


def with_native(item_name, stripped, lang, has_non_ascii, effective_lang, ps):
    """`enumerate_candidates` with the declared-lang pass in English, and the
    row language's pack match as the `pack_none` fallback when a pattern tagged
    with that language wins and is more than a bare count of 1."""
    from prices.enrich.extract import enumerate_candidates

    if lang in (None, "any", ALWAYS_LANG):
        return enumerate_candidates(
            item_name, stripped, lang, has_non_ascii, effective_lang, ps
        )
    candidates = enumerate_candidates(
        item_name, stripped, ALWAYS_LANG, has_non_ascii, effective_lang, ps
    )
    cleaned, count, value, unit, rid = extract_pack(
        stripped, lang, with_id=True, patterns=ps.pack
    )
    tagged = {p["id"]: p["lang"] for p in ps.pack}
    if not rid or tagged.get(rid) != lang:
        return candidates
    if value is None and unit is None and (count is None or count <= 1):
        return candidates
    from prices.enrich.extract_decide import Candidate

    groups = {
        "count": count,
        "value": value,
        "unit": unit,
        "regex_id": rid,
        "cleaned": cleaned,
    }
    native = Candidate("pack_none", None, "stripped", groups)
    rest = [c for c in candidates if c.source != "pack_none"]
    return rest[:1] + [native] + rest[1:]
