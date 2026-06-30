"""Deterministic product-name normalization.

Pure functions, no I/O at call time. YAML / JSON static tables are loaded
once at import. Output identity keys are stable across runs and machines
provided the static tables don't change.

Tier (a) structural extraction (`extract`, `StructuralFields`) lives in
`prices.enrich.extract` — split out in Phase 3 to keep this file under the
500-LoC cap.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from prices.enrich.regex_patterns.dict_view import (
    pack_patterns_for_normalize,
    unit_norm as _typed_unit_norm,
)

_STATIC = Path(__file__).resolve().parent / "static"
_BRAND_JSON = _STATIC / "brand_aliases.json"
_STOP_JSON = _STATIC / "stop_words.json"


def _load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_")}


_PACK_PATTERNS = pack_patterns_for_normalize()
_UNIT_NORM = _typed_unit_norm()
_BRAND_ALIASES = _load_json(_BRAND_JSON)
_STOP_WORDS_RAW = _load_json(_STOP_JSON)
_STOP_BY_LANG: dict[str, set[str]] = {k: set(v) for k, v in _STOP_WORDS_RAW.items()}

# Brand aliases are matched longest-key-first so multi-word brands win
# (e.g. "the north face" before "the").
_BRAND_ALIAS_KEYS = sorted(_BRAND_ALIASES.keys(), key=len, reverse=True)

# CJK-only brand keys (no word boundaries in CJK script) — applied as raw
# substring replacement before clean_text, since CJK has no tokenization.
_CJK_BRAND_KEYS = [k for k in _BRAND_ALIAS_KEYS if any(ord(c) >= 0x3000 for c in k)]

# English "Pack/Bundle of N" OUTER multiplier. Only consulted when the winning
# pack match was a per-unit value+unit with no count (e.g. "150ml Pack of 2");
# the N then becomes the outer pack multiplier. The negative lookahead rejects a
# digit glued to a measure unit ("Pack of 500g" = one 500 g pack, not 500 packs).
_OUTER_PACK_OF_RE = re.compile(
    r"\b(?:pack|bundle)\s*of\s*(\d+)\b(?!\s*(?:k?gs?|m?ls?|ltrs?|lt|oz|lb|mg|l)\b)",
    re.IGNORECASE,
)

# Count markers whose N is an INTERNAL piece-count, not an outer pack: English
# "N Pack/PCS/pieces" and Vietnamese "N miếng/viên". When one of these co-occurs
# with a single total mass/volume, the spec treats the measure as the pack TOTAL
# (e.g. "24 Pack 1.8kg" = 24 items totalling 1.8 kg, multiplier 1), so the count
# must not be promoted to a multiplier. Excludes "Combo/Lốc N" (real outer pack).
_TOTAL_INTERNAL_COUNT_IDS = {"NUM_PCS", "COUNT_UNIT_VI"}
_VALUE_UNIT_PAT = next(p for p in _PACK_PATTERNS if p["id"] == "VALUE_UNIT")
# A counter joined to the measure by x/×/* IS an explicit multiplier ("12PACK x
# 86g", "6 PCS X 100ml") — NOT a total, so the total-internal redirect is skipped.
_COUNTER_X_MEASURE_RE = re.compile(
    r"(?:pack|pcs|pieces?|ct|miếng|viên)\s*[x×*]\s*\d", re.IGNORECASE
)

# CJK stop-words and ZH/JA promo markers are substring-stripped because
# CJK script has no word boundaries.
_CJK_LANGS = {"zh", "ja"}


@dataclass(frozen=True)
class CanonicalProduct:
    canonical_strict: str
    canonical_loose: str
    brand: str | None
    count: int | None
    value: float | None
    unit: str | None
    country: str
    lang: str


def _strip_to_ascii_safe(s: str) -> str:
    """NFKD + drop Latin diacritics, but PRESERVE CJK/Kana combining marks
    (Japanese dakuten ダ→タ+゙ would otherwise break voicing). A combining
    mark is kept iff the immediately preceding base char is in the CJK/Kana
    range (U+3000+)."""
    s = unicodedata.normalize("NFKD", s)
    out: list[str] = []
    base = ""
    for c in s:
        if unicodedata.combining(c):
            if base and ord(base) >= 0x3000:
                out.append(c)
            # else: drop (Latin/Cyrillic/Greek diacritic)
        else:
            out.append(c)
            base = c
    return "".join(out)


def clean_text(s: str, lang: str | None = None) -> str:
    if not s:
        return ""
    s = _strip_to_ascii_safe(s)
    s = s.lower()
    # replace any punctuation/symbol char with a single space
    s = re.sub(r"[^\w\s一-鿿぀-ゟ゠-ヿ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def extract_pack(
    s: str, lang: str | None = None, with_id: bool = False
) -> tuple[str, int | None, float | None, str | None]:
    """Return (text_with_pack_removed, count, value, unit). First match wins.

    When `with_id` is True, append the winning pattern id (or None) as a 5th
    element — an additive, display-only channel for the §9 recorder. The first
    four elements are identical to the default (4-tuple) return for every input.
    """
    if not s:
        return (s, None, None, None, None) if with_id else (s, None, None, None)
    for pat in _PACK_PATTERNS:
        if pat["lang"] != "any" and lang and pat["lang"] != lang:
            continue
        m = pat["regex"].search(s)
        if not m:
            continue
        gd = m.groupdict()
        count = int(gd["count"]) if gd.get("count") else None
        value = float(gd["value"].replace(",", ".")) if gd.get("value") else None
        unit = None
        if gd.get("unit"):
            raw_unit = gd["unit"]
            unit = _UNIT_NORM.get(
                raw_unit, _UNIT_NORM.get(raw_unit.lower(), raw_unit.lower())
            )
        if count is None and value is not None and unit is not None:
            om = _OUTER_PACK_OF_RE.search(s)
            if om:
                count = int(om.group(1))
        if (
            value is None
            and count is not None
            and pat["id"] in _TOTAL_INTERNAL_COUNT_IDS
            and not _COUNTER_X_MEASURE_RE.search(s)
        ):
            vm = _VALUE_UNIT_PAT["regex"].search(s)
            if vm:
                raw = vm.group("unit")
                unit = _UNIT_NORM.get(raw, _UNIT_NORM.get(raw.lower(), raw.lower()))
                value = float(vm.group("value").replace(",", "."))
                count = None
                cleaned = (s[: vm.start()] + " " + s[vm.end() :]).strip()
                cleaned = re.sub(r"\s+", " ", cleaned)
                if with_id:
                    return cleaned, count, value, unit, pat["id"]
                return cleaned, count, value, unit
        cleaned = (s[: m.start()] + " " + s[m.end() :]).strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        if with_id:
            return cleaned, count, value, unit, pat["id"]
        return cleaned, count, value, unit
    return (s, None, None, None, None) if with_id else (s, None, None, None)


def _strip_promo_substrings(s: str, lang: str | None) -> str:
    if not lang or lang not in _CJK_LANGS:
        return s
    for marker in _STOP_BY_LANG.get(lang, ()):
        if marker and marker in s:
            s = s.replace(marker, " ")
    return re.sub(r"\s+", " ", s).strip()


_MAX_BRAND_NGRAM = max((len(k.split()) for k in _BRAND_ALIAS_KEYS), default=1)


def _apply_brand_aliases(s: str) -> tuple[str, str | None]:
    """Token-aware n-gram replacement: try longest phrase first at each cursor.
    Avoids substring false positives (e.g. \"lay\" inside \"lays\")."""
    tokens = s.split()
    out: list[str] = []
    found_brand: str | None = None
    i = 0
    while i < len(tokens):
        matched = False
        for n in range(min(_MAX_BRAND_NGRAM, len(tokens) - i), 0, -1):
            phrase = " ".join(tokens[i : i + n])
            if phrase in _BRAND_ALIASES:
                canonical = _BRAND_ALIASES[phrase]
                if found_brand is None:
                    found_brand = canonical
                out.append(canonical)
                i += n
                matched = True
                break
        if not matched:
            out.append(tokens[i])
            i += 1
    return " ".join(out), found_brand


def _strip_stop_tokens(s: str, lang: str | None) -> str:
    stops = _STOP_BY_LANG.get(lang or "en", set())
    if not stops:
        return s
    tokens = [t for t in s.split() if t and t not in stops]
    return " ".join(tokens)


def canonicalize(
    item_name: str,
    category: str | None,
    country: str,
    lang: str | None = None,
) -> CanonicalProduct:
    if not item_name:
        return CanonicalProduct(
            canonical_strict="",
            canonical_loose="",
            brand=None,
            count=None,
            value=None,
            unit=None,
            country=country or "",
            lang=lang or "",
        )

    text = item_name
    cjk_brand: str | None = None
    # Pass 1: strip CJK promo substrings BEFORE NFKD lower-casing
    # (markers are exact byte sequences and full-width-fold-safe).
    text = _strip_promo_substrings(text, lang)
    # Pass 1b: CJK brand substring replace (no tokenization possible).
    for key in _CJK_BRAND_KEYS:
        if key in text:
            canonical = _BRAND_ALIASES[key]
            if cjk_brand is None:
                cjk_brand = canonical
            text = text.replace(key, f" {canonical} ")
    # Pass 2: pack extraction on raw-ish text (regex covers casing variants).
    text, count, value, unit = extract_pack(text, lang)
    # Pass 3: character cleanup, lowercase, punctuation→space.
    text = clean_text(text, lang)
    # Pass 4: brand alias replacement (longest first, token-aware).
    text, brand = _apply_brand_aliases(text)
    if brand is None:
        brand = cjk_brand
    # Pass 5: stop-word strip (Latin scripts) — CJK stops were handled in Pass 1.
    text = _strip_stop_tokens(text, lang)

    tokens = sorted(t for t in text.split() if t)
    base = " ".join(tokens)

    pack_part: list[str] = []
    if count is not None:
        pack_part.append(f"x{count}")
    if value is not None and unit:
        v = int(value) if value.is_integer() else value
        pack_part.append(f"{v}{unit}")
    pack_str = " ".join(pack_part)

    strict = " ".join(p for p in (base, pack_str) if p)
    loose = base

    return CanonicalProduct(
        canonical_strict=strict,
        canonical_loose=loose,
        brand=brand,
        count=count,
        value=value,
        unit=unit,
        country=country or "",
        lang=lang or "",
    )


# --- Category breadcrumb normalization (tier-b passage augmentation) -------

_BREADCRUMB_SPLIT_RE = re.compile(r"\s*(?:>>|>|→|\||/|:|\s-\s)\s*")

_GENERIC_BREADCRUMB_LEADERS = {
    "shop",
    "products",
    "home",
    "store",
    "all",
    "all-categories",
    "browse",
    "catalog",
}

MIN_CATEGORY_AGREEMENT = 0.5


def normalize_breadcrumb(raw: str | None) -> str:
    """Normalize a category breadcrumb to a 2-segment leaf>parent string.

    Lowercases ASCII segments, leaves non-ASCII (CJK/Thai/Khmer/Cyrillic)
    as-is, drops generic leader segments, returns the last 2 segments joined
    by " > "."""
    if not raw:
        return ""
    parts = _BREADCRUMB_SPLIT_RE.split(str(raw).strip())
    parts = [p.strip() for p in parts if p.strip()]
    parts = [p.lower() if p.isascii() else p for p in parts]
    parts = [p for p in parts if p.lower() not in _GENERIC_BREADCRUMB_LEADERS]
    if not parts:
        return ""
    parts = parts[-2:]
    return " > ".join(parts)


def resolve_cluster_category(group_categories: list[str | None]) -> str:
    """Modal-vote a cluster's representative category from member rows.

    Singleton (1 non-empty row): return its normalized category directly —
    the entire cluster IS that row, there is nothing to disagree with.
    Multi-row: take modal vote with threshold MIN_CATEGORY_AGREEMENT,
    longest-string tiebreak (mirrors _pick_rep). Returns "" when no row
    carries a normalizable category, or when the modal share is below
    threshold."""
    if not group_categories:
        return ""
    norm = [normalize_breadcrumb(c) for c in group_categories]
    norm = [c for c in norm if c]
    if not norm:
        return ""
    if len(norm) == 1:
        return norm[0]
    counter = Counter(norm)
    top, count = counter.most_common(1)[0]
    if count / len(norm) < MIN_CATEGORY_AGREEMENT:
        return ""
    winners = [c for c, k in counter.items() if k == count]
    return max(winners, key=len)


# --- Tier (a) regex extractor moved to prices.enrich.extract ---------------
