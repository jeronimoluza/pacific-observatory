"""Hand-authored regex / constant block for tier (a) extraction.

Relocated verbatim out of `extract.py` (which sat at 498/500 LoC) so the
span-threading work in the match-event recorder has line budget. Pure data —
no logic. Re-imported into `extract.py` so every existing
`from prices.enrich.extract import _SU_NORM` (etc.) keeps resolving unchanged.
"""

from __future__ import annotations

import re

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


# Net-weight TOLERANCE clause (butcher/produce "actual weight may vary"
# idiom): "± 25 gm" / "(± 50 gm)" / "(Net Weight ± 50 gm)". The number here is
# a variance allowance, not the sale quantity — the real measure is always the
# OTHER value+unit elsewhere in the name (e.g. "Green Capsicum ± 15 gm 300 gm"
# -> 300 gm). Stripped from item_name before any pattern runs so no candidate
# ever reads the tolerance value as the quantity.
_TOLERANCE_CLAUSE_RE = re.compile(
    r"\(?\s*(?:Net\s+Weight\s+)?±\s*\d+(?:[.,]\d+)?\s*"
    r"(?:gm?|kg|mg|ml|l|oz|lb)\b\s*\)?",
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
# pack_patterns' VALUE_UNIT regex but lives here so we can call it
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
