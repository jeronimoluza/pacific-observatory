"""Tier (a) — deterministic structural-field extractor.

Pure functions. Owns: pricing_basis, amount_value, standard_unit, count,
multiplier, is_promotion, is_bundle, is_multipack, promo_reason.

Split out of `normalize.py` in Phase 3 to keep both files under the
500-LoC project cap. Depends on `extract_pack` from normalize for the
first-pass regex sweep.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from prices.enrich.normalize import extract_pack
from prices.enrich.regex_patterns.dict_view import regex_units_for_extract


@dataclass(frozen=True)
class StructuralFields:
    """Tier (a) output. Every field is independently optional; None means
    "regex didn't fire — caller should leave the slot empty and let downstream
    tiers fill it (or not)."""

    pricing_basis: str | None
    amount_value: float | None
    standard_unit: str | None
    count: int | None
    multiplier: int | None
    is_promotion: bool | None
    is_bundle: bool | None
    is_multipack: bool | None
    promo_reason: str | None


(
    _UNIT_MAP,
    _EXTRA_UNITS,
    _EXTRA_COUNT,
    _MULTI_PACK,
    _PROMO_MARKERS,
    _BUNDLE_MARKERS,
    _PRICING_BASIS_MARKERS,
) = regex_units_for_extract()


_MARKETING_LIMIT_RE = re.compile(
    r"(?:限り|限定|まで|お一人|お1人|まとめ買い|名様限定|名様まで|お一人様|突破|累計|売れ|名様"
    r"|工作天|工作日|営業日|個口|円OFF|円引き|円分|送料|配送)"
)

# Patterns that LOOK like pack/count markers but are calendar/time/role context.
# Stripped from item_name before extract_pack/extra_count runs.
_PHRASE_STRIP_PATTERNS = [
    re.compile(r"\d+\s*個\s*(?:工作天|工作日|営業日|月|年|歳|口)"),
    re.compile(r"\d+\s*名様\s*(?:限定|まで)?"),
    re.compile(r"\d+\s*枚\s*(?:限り|限定)"),
    re.compile(r"\d+\s*(?:年|月|日|歳|時|分|秒)"),
    re.compile(r"\d+\s*(?:円|¥)\s*(?:OFF|引き|引|分)?"),
    re.compile(r"\d+\s*[%％]"),
    re.compile(r"\d+\s*W\b"),  # wattage
]

# CJK count markers inside parens often signal item-multipack (multiplier), not
# count-basis. e.g. "(3入)" on outlet adapters → item, mul=3, not count=3.
_PAREN_CJK_MULTIPACK_RE = re.compile(
    r"[（(][^）)]*?(?P<count>\d+)\s*(?:入|包|盒|組|箱)\s*[）)]"
)

_APOS_S_X_UNIT_RE = re.compile(
    r"(?P<count>\d+)['’]?\s*[sS]\s*[xX×]\s*"
    r"(?P<value>\d+(?:[.,]\d+)?)\s*"
    r"(?P<unit>g|G|kg|KG|mg|MG|gm|GM|gr|GR|oz|OZ|lb|LB|ml|mL|ML|l|L)\b"
)

# Secondary value+unit scan (used when pack_patterns returns count-only). Mirrors
# pack_patterns' value_unit_volume_mass regex but lives here so we can call it
# AFTER an initial count-only match — pack_patterns is first-match-wins.
_SECONDARY_VU_RE = re.compile(
    r"(?<![A-Za-z0-9.])(?P<value>\d+(?:[.,]\d+)?)\s*"
    r"(?P<unit>ml|mL|ML|l|L|kg|KG|g|G|mg|MG|gm|GM|gr|GR|oz|OZ|lb|LB|Oz|cl|CL|cL|Cl)\b"
)
_SU_NORM = {
    "ml": "ml",
    "mL": "ml",
    "ML": "ml",
    "l": "l",
    "L": "l",
    "kg": "kg",
    "KG": "kg",
    "g": "g",
    "G": "g",
    "mg": "mg",
    "MG": "mg",
    "gm": "g",
    "GM": "g",
    "gr": "g",
    "GR": "g",
    "oz": "oz",
    "OZ": "oz",
    "Oz": "oz",
    "lb": "lb",
    "LB": "lb",
    "cl": "cl",
    "CL": "cl",
    "cL": "cl",
    "Cl": "cl",
}


def _find_value_unit_anywhere(item_name: str):
    """Returns (count_unused, value, unit) — second scan for embedded value+unit
    when a first-pass count-only match shadowed the real mass/volume signal."""
    m = _SECONDARY_VU_RE.search(item_name)
    if not m:
        return None, None, None
    try:
        value = float(m.group("value").replace(",", "."))
    except ValueError:
        return None, None, None
    unit = _SU_NORM.get(m.group("unit"))
    return None, value, unit


def _match_extra_unit(item_name: str, lang: str | None):
    for entry in _EXTRA_UNITS:
        if entry["lang"] != "any" and lang and entry["lang"] != lang:
            continue
        m = entry["regex"].search(item_name)
        if m:
            value = float(m.group("value").replace(",", "."))
            return entry, value
    return None, None


_BASIS_TO_SU = {"mass": "kg", "volume": "lt"}


def _match_pricing_basis_marker(item_name: str, lang: str | None) -> str | None:
    """Return pricing_basis when a bare per-unit marker fires (no amount_value)."""
    for entry in _PRICING_BASIS_MARKERS:
        if entry["lang"] != "any" and lang and entry["lang"] != lang:
            continue
        if entry["regex"].search(item_name):
            return entry["pricing_basis_emit"]
    return None


_CJK_NUM = {
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}


def _cjk_numeral_to_int(s: str) -> int | None:
    if not s:
        return None
    if s == "十":
        return 10
    if "十" in s:
        parts = s.split("十", 1)
        tens = _CJK_NUM.get(parts[0], 1) if parts[0] else 1
        ones = _CJK_NUM.get(parts[1], 0) if parts[1] else 0
        return tens * 10 + ones
    n = 0
    for ch in s:
        v = _CJK_NUM.get(ch)
        if v is None:
            return None
        n = n * 10 + v
    return n if n else None


def _match_extra_count(item_name: str, lang: str | None) -> int | None:
    for entry in _EXTRA_COUNT:
        if entry["lang"] != "any" and lang and entry["lang"] != lang:
            continue
        for m in entry["regex"].finditer(item_name):
            # Local marketing-clause check: suppress count when a limit clause
            # (限り / 限定 / 突破 / お一人様 / まとめ買い …) sits within ~12 chars
            # of the match. Global presence is too aggressive (long descriptive
            # Japanese product titles often contain these terms incidentally).
            a = max(0, m.start() - 12)
            b = min(len(item_name), m.end() + 12)
            if _MARKETING_LIMIT_RE.search(item_name[a:b]):
                continue
            fc = entry.get("fixed_count")
            if fc is not None:
                return int(fc)
            try:
                if "count_cjk" in m.groupdict():
                    n = _cjk_numeral_to_int(m.group("count_cjk"))
                    if n is not None and n > 0:
                        return n
                    continue
                return int(m.group("count"))
            except (IndexError, ValueError):
                continue
    return None


def _match_multi_pack(item_name: str, lang: str | None):
    for entry in _MULTI_PACK:
        if entry["lang"] != "any" and lang and entry["lang"] != lang:
            continue
        m = entry["regex"].search(item_name)
        if m:
            try:
                inner = int(m.group("count"))
                outer = int(m.group("multiplier"))
                return inner, outer
            except (IndexError, ValueError):
                continue
    return None


def _markers_fire(item_name: str, lang: str | None, markers) -> bool:
    for grp in markers:
        if grp["lang"] != "any" and lang and grp["lang"] != lang:
            continue
        for pat in grp["patterns"]:
            if pat.search(item_name):
                return True
    return False


def extract(
    item_name: str,
    category: str | None,
    country: str | None,
    lang: str | None,
) -> StructuralFields:
    """Tier (a) — deterministic structural-field extraction.

    Owns: pricing_basis, amount_value, standard_unit, count, multiplier,
          is_promotion, is_bundle, is_multipack, promo_reason.

    Empty / whitespace input → all fields None. Otherwise:
    - mass/volume marker (g/kg/mg/oz/lb/ml/l/cl) → basis=mass|volume, su=kg|lt,
      amount_value in canonical units, count=1, multiplier=pack_count or 1.
    - Count-only marker (12 PCS, セット, 入, etc.) → basis=count, su=unit,
      count=N, multiplier=1.
    - No marker → basis=item, su=item, amount_value=None, count=1, multiplier=1.
    """
    if not item_name or not item_name.strip():
        return StructuralFields(None, None, None, None, None, None, None, None, None)

    has_non_ascii = any(ord(ch) > 127 for ch in item_name)

    # Pass 0: detect "20'S X 2g" style (count'S × value+unit) — DILMAH/tea-bag
    # idiom. Routes straight to mass/volume + multiplier=count.
    apos = _APOS_S_X_UNIT_RE.search(item_name)

    # Strip calendar/time/role/marketing phrases that look like pack/count
    # markers so pack_patterns and extra_count_markers don't lock onto them.
    stripped = item_name
    for pat in _PHRASE_STRIP_PATTERNS:
        stripped = pat.sub(" ", stripped)

    # Pass 1: try pack_patterns on the stripped name with declared language.
    _cleaned, pack_count, pack_value, pack_unit = extract_pack(stripped, lang)
    # Pass 1b: if nothing matched and the name has any non-ASCII char (CJK / vi
    # diacritic / etc.), retry lang=None so script-specific patterns can fire.
    # Most country `languages` lists are `[en, <other>]`; lang=None scans all.
    if pack_count is None and pack_value is None and has_non_ascii:
        _cleaned, pack_count, pack_value, pack_unit = extract_pack(stripped, None)

    # Pass 1c: local marketing-clause suppression for count-only matches.
    # Pack_patterns is first-match-wins, so the count could be e.g. "953枚突破"
    # (marketing) instead of the real "4枚セット". Re-find the count match in
    # the name and check the surrounding window for a limit clause.
    if pack_count is not None and pack_value is None and pack_unit is None:
        pack_count_m = re.search(rf"(?<!\d){pack_count}", item_name)
        if pack_count_m:
            a = max(0, pack_count_m.start() - 12)
            b = min(len(item_name), pack_count_m.end() + 12)
            if _MARKETING_LIMIT_RE.search(item_name[a:b]):
                pack_count = None
                _cleaned, alt_count, alt_value, alt_unit = extract_pack(
                    item_name[pack_count_m.end() :], None
                )
                if alt_value is not None or alt_count is not None:
                    pack_count, pack_value, pack_unit = alt_count, alt_value, alt_unit

    # Pass 1d: a count-only marker from pack_patterns ("5 Pack", "4入") can mask
    # a real mass/volume signal elsewhere in the name. If pack returned a count
    # but no value/unit, search the rest of the name for a value+unit pair and
    # prefer mass/volume when found — schema requires basis=mass|volume when
    # an explicit weight/volume marker is present.
    if pack_count is not None and pack_unit is None and pack_value is None:
        sec_count, sec_value, sec_unit = _find_value_unit_anywhere(item_name)
        if sec_value is not None and sec_unit is not None:
            # promote: keep pack_count as multiplier, attach value+unit
            pack_value, pack_unit = sec_value, sec_unit

    extra_entry, extra_value = (None, None)
    if pack_unit is None:
        extra_entry, extra_value = _match_extra_unit(item_name, lang)

    # Broaden lang for marker tries when the name contains non-ASCII chars —
    # otherwise vi/ko/zh-tagged patterns never fire for countries whose primary
    # language is English (e.g. vietnam → "en" in countries.yaml).
    effective_lang = None if has_non_ascii else lang

    extra_count = (
        _match_extra_count(item_name, effective_lang)
        if pack_unit is None and extra_entry is None and pack_count is None
        else None
    )

    basis_marker = (
        _match_pricing_basis_marker(item_name, lang)
        if pack_unit is None and extra_entry is None
        else None
    )

    multi_pack = _match_multi_pack(item_name, effective_lang)

    # Apos pattern wins outright when it matched — it's very specific.
    if apos is not None:
        unit_norm = _SU_NORM.get(apos.group("unit"))
        um = _UNIT_MAP.get(unit_norm) if unit_norm else None
        if um is not None:
            value = float(apos.group("value").replace(",", "."))
            mult = int(apos.group("count"))
            return StructuralFields(
                pricing_basis=um["basis"],
                amount_value=value * float(um["mul"]),
                standard_unit=um["su"],
                count=1,
                multiplier=mult,
                is_promotion=_markers_fire(item_name, lang, _PROMO_MARKERS),
                is_bundle=_markers_fire(item_name, lang, _BUNDLE_MARKERS),
                is_multipack=mult > 1,
                promo_reason=None,
            )

    pricing_basis: str | None = None
    standard_unit: str | None = None
    amount_value: float | None = None
    count: int | None = None
    multiplier: int | None = None

    if pack_unit is not None:
        um = _UNIT_MAP.get(pack_unit)
        if um:
            pricing_basis = um["basis"]
            standard_unit = um["su"]
            if pack_value is not None:
                amount_value = pack_value * float(um["mul"])
            count = 1
            multiplier = pack_count if pack_count and pack_count > 0 else 1
        else:
            pricing_basis = "item"
            standard_unit = "item"
            count = 1
            multiplier = 1
    elif extra_entry is not None:
        pricing_basis = extra_entry["basis"]
        standard_unit = extra_entry["su"]
        amount_value = extra_value * extra_entry["mul"]
        count = 1
        multiplier = 1
    elif basis_marker is not None:
        pricing_basis = basis_marker
        standard_unit = _BASIS_TO_SU.get(basis_marker, "item")
        amount_value = None
        count = 1
        multiplier = 1
    elif multi_pack is not None:
        inner, outer = multi_pack
        pricing_basis = "count"
        standard_unit = "unit"
        count = inner
        multiplier = outer
    elif pack_count is not None and pack_count > 1:
        pricing_basis = "count"
        standard_unit = "unit"
        count = pack_count
        multiplier = 1
    elif extra_count is not None and extra_count > 1:
        pricing_basis = "count"
        standard_unit = "unit"
        count = extra_count
        multiplier = 1
    else:
        # No structural signal OR pack_count == 1: a single item.
        # (Hard-coded "1pcs" / "1 Tablet" markers are still single items.)
        pricing_basis = "item"
        standard_unit = "item"
        count = 1
        multiplier = 1

    is_multipack = (multiplier is not None and multiplier > 1) or (
        pricing_basis == "count" and count is not None and count > 1
    )
    is_promotion = _markers_fire(item_name, lang, _PROMO_MARKERS)
    is_bundle = _markers_fire(item_name, lang, _BUNDLE_MARKERS)

    return StructuralFields(
        pricing_basis=pricing_basis,
        amount_value=amount_value,
        standard_unit=standard_unit,
        count=count,
        multiplier=multiplier,
        is_promotion=is_promotion,
        is_bundle=is_bundle,
        is_multipack=is_multipack,
        promo_reason=None,
    )
