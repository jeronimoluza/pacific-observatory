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
from prices.enrich.regex_patterns.dict_view import (
    regex_units_for_extract,
    value_unit_pattern,
)
from prices.enrich.regex_patterns.shared.range_lower import collapse_numeric_ranges


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

_VU_RE, _VU_SUPPRESS_WINDOW = value_unit_pattern()

# Appliance-capacity / apparel-fabric-weight / storage-container context cues
# (BUG 3 / BUG 4). A mass/volume value+unit within `_VU_SUPPRESS_WINDOW` chars of
# one of these is the product's capacity or fabric weight, not a sale quantity.
# High-precision nouns only: bare modifiers that co-occur with consumables
# ("oven" → oven cleaner, "fan", "tank") are deliberately excluded so genuine
# by-volume/by-weight goods are not suppressed.
_VU_SUPPRESS_CTX_RE = re.compile(
    r"refrigerator|freezer|washing\s*machine|tumble\s*dry|\bdryer\b|dishwasher|"
    r"microwave\s*oven|water\s*heater|air\s*fryer|rice\s*cooker|\btumbler\b|\bsteamer\b|"
    r"洗衣機|洗衣机|冰箱|冷凍庫|冷冻柜|冷凍櫃|製氧機|制氧机|冷氣機|冷气机|"
    r"熱水器|热水器|飲水機|饮水机|洗碗機|洗碗机|吸塵器|吸尘器|烘衣機|乾衣機|"
    r"除濕機|除湿机|收納盒|收纳盒|收納箱|收纳箱|炊飯器|タンブラー|水筒|"
    r"t-?shirt|hoodie|sweatshirt|trackpants",
    re.IGNORECASE,
)

# Negative guard: appliance-care CONSUMABLES (washer-drum cleaner, dishwasher
# rinse aid, fridge deodorizer) and perfumes mention an appliance/apparel noun
# but ARE sold by weight/volume. If any consumable-form cue is present anywhere
# in the name, never suppress — the mass/volume is real.
_VU_NEG_RE = re.compile(
    r"清潔|清洗|洗滌|洗劑|除臭|消臭|脫臭|去味|淨味|柔軟|洗衣精|洗衣粉|洗衣球|"
    r"凝珠|潤乾|香氛|防潮|防霉|乾燥劑|活性炭|專用|補充|除濕盒|"
    r"conditioner|shampoo|detergent|cleaner|rinse|softener|deodor|fragrance|"
    r"refill|edt|edp|parfum|perfume|cologne|salt|wart|verruca|descal|nail polish",
    re.IGNORECASE,
)


_MARKETING_LIMIT_RE = re.compile(
    r"(?:限り|限定|まで|お一人|お1人|まとめ買い|名様限定|名様まで|お一人様|突破|累計|売れ|名様"
    r"|工作天|工作日|営業日|個口|円OFF|円引き|円分|送料|配送)"
)

# Inner value+unit tokens, used to detect a "total（per×count）" breakdown idiom
# (e.g. 10kg（5kg×2袋）) so the outer count isn't double-applied to the total.
_INNER_VALUE_UNIT_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(ml|mL|ML|kg|KG|g|G|l|L|cl|CL)")

# Servings counters (N杯分 / N食分 / N回分 / N人前) are "portions worth", never a
# pack multiplier — used to veto a recovered outer-pack count in Pass 1b2.
_SERVINGS_SUFFIX_RE = re.compile(r"杯分|食分|回分|人前")

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
    # Pharma per-tablet strength: `100mg Tablet`, `20mcg Capsule`. The number
    # is the API dose, not the package weight. Stripping it prevents tier-a
    # from emitting basis=mass with a tiny per-pill value (2026-06-16).
    re.compile(
        r"\d+(?:[.,]\d+)?\s*(?:mg|MG|Mg|mcg|MCG|µg|ug)\s+"
        r"(?:Tablet|Tablets|TABLET|TABLETS|tablet|tablets|"
        r"Tab|Tabs|Capsule|Capsules|CAPSULE|CAPSULES|capsule|capsules|"
        r"Cap|Caps|Caplet|Caplets|Pill|Pills|PILL|PILLS|pill|pills)\b"
    ),
]

# Pharma per-unit markers — when any of these fire, the product is sold per
# tablet/capsule/pill regardless of what mass extract_pack might have seen.
# Force basis=count (overrides downstream basis decision). See fix 3 in the
# 2026-06-16 tier-a precision-lift batch.
#
# Two trigger shapes:
#   1. Drug strength `<N>mg Tablet/Capsule/...` — the N is API dose, not pkg.
#   2. Explicit `(per Tablet)` / `(per Capsule)` literal marker.
# Either suffices.
_PHARMA_PER_UNIT_RE = re.compile(
    r"\d+(?:[.,]\d+)?\s*(?:mg|MG|Mg|mcg|MCG|µg|ug)\s+"
    r"(?:Tablet|Tablets|TABLET|TABLETS|tablet|tablets|"
    r"Tab|Tabs|Capsule|Capsules|CAPSULE|CAPSULES|capsule|capsules|"
    r"Cap|Caps|Caplet|Caplets|Pill|Pills|PILL|PILLS|pill|pills)\b"
    r"|\((?:per\s+(?:Tablet|Capsule|Cap|Caplet|Pill)|"
    r"per\s+tablet|per\s+capsule|per\s+cap|per\s+caplet|per\s+pill|"
    r"PER\s+TABLET|PER\s+CAPSULE|PER\s+CAP|PER\s+CAPLET|PER\s+PILL)\)"
)

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


def _is_total_breakdown(name, matched_value, matched_unit, count):
    """True when `matched_value`+`matched_unit` is a stated TOTAL whose breakdown
    `(per × count)` also appears in `name` (e.g. 10kg（5kg×2袋）). In that case the
    outer `count` is the breakdown of the total, not an extra multiplier, so it
    must not be re-applied (would double the quantity)."""
    if matched_value is None or matched_unit is None or not count or count <= 1:
        return False
    um = _UNIT_MAP.get(matched_unit)
    if not um:
        return False
    matched_canon = matched_value * float(um["mul"])
    for m in _INNER_VALUE_UNIT_RE.finditer(name):
        inner_um = _UNIT_MAP.get(_SU_NORM.get(m.group(2)))
        if not inner_um:
            continue
        inner_canon = float(m.group(1).replace(",", ".")) * float(inner_um["mul"])
        if (
            inner_canon < matched_canon
            and abs(inner_canon * count - matched_canon) < 1e-9
        ):
            return True
    return False


def _value_unit_suppressed(name: str) -> bool:
    """Wire PackPattern.suppress_window for value_unit_volume_mass: True when the
    first latin value+unit match in `name` sits within the suppress window of an
    appliance / apparel / storage-container cue, i.e. the number is a capacity or
    fabric weight rather than a sale quantity (BUG 3 / BUG 4)."""
    if _VU_SUPPRESS_WINDOW is None:
        return False
    m = _VU_RE.search(name)
    if not m:
        return False
    if _VU_NEG_RE.search(name):
        return False
    a = max(0, m.start() - _VU_SUPPRESS_WINDOW)
    b = min(len(name), m.end() + _VU_SUPPRESS_WINDOW)
    return bool(_VU_SUPPRESS_CTX_RE.search(name[a:b]))


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


def enumerate_candidates(
    item_name: str,
    stripped: str,
    lang: str | None,
    has_non_ascii: bool,
    effective_lang: str | None,
):
    """Record every tier-a matcher fire as a Candidate, without deciding.

    Same matcher calls on the same strings the cascade uses today (RESEARCH Q5
    black-box enumeration); each fire is tagged with its source_string so
    decide() never reads the wrong string. The Pass-1c substring re-scan is
    data-dependent on the resolved pack_count, so decide() performs that fire.
    """
    from prices.enrich.extract_decide import Candidate

    candidates: list = []

    _cleaned, pack_count, pack_value, pack_unit = extract_pack(stripped, lang)
    candidates.append(
        Candidate(
            source="pack_lang",
            span=None,
            source_string="stripped",
            groups={"count": pack_count, "value": pack_value, "unit": pack_unit},
        )
    )
    if has_non_ascii:
        _cleaned, nc, nv, nu = extract_pack(stripped, None)
        candidates.append(
            Candidate(
                source="pack_none",
                span=None,
                source_string="stripped",
                groups={"count": nc, "value": nv, "unit": nu},
            )
        )
    sec_count, sec_value, sec_unit = _find_value_unit_anywhere(item_name)
    candidates.append(
        Candidate(
            source="secondary_vu",
            span=None,
            source_string="item_name",
            groups={"count": sec_count, "value": sec_value, "unit": sec_unit},
        )
    )
    extra_entry, extra_value = _match_extra_unit(stripped, lang)
    if extra_entry is not None:
        candidates.append(
            Candidate(
                source="extra_unit",
                span=None,
                source_string="stripped",
                groups={"entry": extra_entry, "value": extra_value},
            )
        )
    extra_count = _match_extra_count(stripped, effective_lang)
    if extra_count is not None:
        candidates.append(
            Candidate(
                source="extra_count",
                span=None,
                source_string="stripped",
                groups={"count": extra_count},
            )
        )
    basis_marker = _match_pricing_basis_marker(stripped, lang)
    if basis_marker is not None:
        candidates.append(
            Candidate(
                source="basis_marker",
                span=None,
                source_string="stripped",
                groups={"basis": basis_marker},
            )
        )
    multi_pack = _match_multi_pack(stripped, effective_lang)
    if multi_pack is not None:
        candidates.append(
            Candidate(
                source="multi_pack",
                span=None,
                source_string="stripped",
                groups={"inner": multi_pack[0], "outer": multi_pack[1]},
            )
        )
    return candidates


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

    # Collapse single-unit mass/volume ranges to their lower bound (spec rule)
    # before any pattern reads the name.
    item_name = collapse_numeric_ranges(item_name)

    has_non_ascii = any(ord(ch) > 127 for ch in item_name)

    # Fix 3 (2026-06-16): pharma "(per Tablet)" / "(per Capsule)" marker forces
    # basis=count regardless of any mass token in the name (e.g. "100mg" is
    # API strength, not package weight). Phrase-strip above already wiped
    # `<N>mg Tablet` from `stripped`; this flag short-circuits the basis tree
    # in decide().
    pharma_per_unit = bool(_PHARMA_PER_UNIT_RE.search(item_name))

    # Pass 0: detect "20'S X 2g" style (count'S × value+unit) — DILMAH/tea-bag
    # idiom. Routes straight to mass/volume + multiplier=count.
    apos = _APOS_S_X_UNIT_RE.search(item_name)

    # Strip calendar/time/role/marketing phrases that look like pack/count
    # markers so pack_patterns and extra_count_markers don't lock onto them.
    stripped = item_name
    for pat in _PHRASE_STRIP_PATTERNS:
        stripped = pat.sub(" ", stripped)

    # Broaden lang for non-ASCII names so vi/ko/zh-tagged patterns fire even when
    # the country's primary language is English (e.g. vietnam → "en").
    effective_lang = None if has_non_ascii else lang

    from prices.enrich.extract_decide import decide

    candidates = enumerate_candidates(
        item_name, stripped, lang, has_non_ascii, effective_lang
    )
    return decide(
        candidates,
        apos=apos,
        pharma_per_unit=pharma_per_unit,
        item_name=item_name,
        stripped=stripped,
        lang=lang,
        has_non_ascii=has_non_ascii,
        effective_lang=effective_lang,
    )
