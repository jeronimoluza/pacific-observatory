"""Entity-agnostic constants for the base-item cascade.

Faithful port of the shared substrate from the locked experiments
(base_item_config.json "shared" + the LEAK/CONTAM/CONTAINER/strip regexes from
fresh_flip_general.py / apple_fresh_flip_v3.py / ao_rice_cascade.py). These are
NOT per base_item — they belong to every entity the cascade runs.
"""

from __future__ import annotations

import re

# --- shared benign / block vocab (base_item_config.json "shared") --------------
QUALITY = {
    "red",
    "green",
    "yellow",
    "golden",
    "big",
    "small",
    "large",
    "whole",
    "fresh",
    "sweet",
    "sour",
    "mini",
    "jumbo",
    "crisp",
    "juicy",
    "ripe",
    "loose",
    "medium",
    "extra",
}
ORIGIN = {
    "china",
    "washington",
    "imported",
    "import",
    "local",
    "usa",
    "nz",
    "american",
    "australian",
    "aussie",
    "egyptian",
    "spanish",
}
BOILER_BLOCK = {
    "bubble",
    "gel",
    "balm",
    "serum",
    "lotion",
    "soap",
    "wash",
    "scrub",
    "shampoo",
    "conditioner",
    "perfume",
    "cologne",
    "candle",
    "mask",
    "foam",
    "cushion",
    "wax",
    "spray",
    "stick",
    "lip",
    "bath",
    "cream",
    "bomb",
    "toy",
    "cover",
    "sunscreen",
    "powder",
    "polish",
    "gloss",
    "tint",
    "mascara",
    "lipstick",
    "deodorant",
    "sanitizer",
    "diffuser",
    "mist",
    "cleanser",
}

# --- regex signals (fresh_flip_general.py) -------------------------------------
LEAK = re.compile(
    r"\b(body ?wash|shampoo|sanit\w*|freshener|deodor\w*|lip ?"
    r"(tint|gloss|balm|stick)|lipstick|perfume|cologne|candle|incense|soap|"
    r"lotion|serum|toner|detergent|cleaner|air ?fresh|toothpaste|mouthwash|"
    r"diffuser|iphone|ipad|watch|macbook|scent|mask)\b"
)
CONTAM = re.compile(
    r"baby|infant|month|fromage|puff|rusk|\bfood\b|muesli|cereal|\boat|beef|"
    r"vegetable|sweetcorn|pumpkin|carrot|juice|drink|soda|cola|lozenge|"
    r"sugar\s?free|balm|tint|scrub|mousse|sherbet|cornflake|sparkl|toilette|"
    r"\btea\b|candy|chocolate|\bjam\b|marmalade|syrup|vinegar|cider|beer|soju|"
    r"wine|handwash|effervescent|tablet|capsule|vitamin|jelly|gummy|biscuit|"
    r"cookie|wafer|nectar|squash|cordial|smoothie|liqueur|hazelnut|chestnut",
    re.I,
)
# fruit + "flavour"/"flavoured" tastes LIKE the item, is not the item.
POISON = re.compile(r"\bflavou?r(?:ed|ing|s)?\b", re.I)
DIGIT = re.compile(r"\d")

# neutral produce containers only. tin/can/jar/bottle/tub/pouch/sachet are
# EXCLUDED on purpose (they mark canned/bottled = processed).
CONTAINER = re.compile(
    r"\b(?:packs?|packets?|pkts?|bags?|boxe?s?|cartons?|ctn|punnets?|trays?|"
    r"nets?|sacks?|cases?|pcs?|pieces?)\b",
    re.I,
)

# tier-a strip rungs that belong in extract_pack eventually (ao_rice_cascade.py).
TOL = re.compile(r"±\s*\d+\s*(?:gm|gms|g|kg|kgs|gram|grams)\b", re.I)
STRAY = re.compile(r"\s*±\s*")
FORMAT = re.compile(r"\b(loose|unpacked|bulk|per ?kg|by weight)\b\s*$", re.I)

# spaCy dependency labels (tier-0 role extraction).
HEAD_POS = {"NOUN", "PROPN"}
MOD_DEPS = {"compound", "amod", "nmod", "poss"}
MOD_CHILD_DEPS = {"amod", "compound", "nmod", "poss", "npadvmod"}

# Fresh produce is priced by weight, count, or per whole item — never by volume.
# A base_item may override with its own allowed_basis; None falls back to this.
# extract().pricing_basis is one of {mass, volume, count, item, None}, so the
# default admits everything but volume.
DEFAULT_ALLOWED_BASIS = {"mass", "count", "item", None}

# --- cascade buckets (promotable = CANDIDATE; GREEN is earned later) -----------
CANDIDATE = "CANDIDATE"
OTHER_FORM = "OTHER_FORM"
REVIEW = "REVIEW"
EXCLUDE = "EXCLUDE"

# promotion status assigned by promote.py (NOT a cascade bucket)
GREEN = "green"
CANDIDATE_OUTLIER = "candidate_outlier"
CANDIDATE_SMALL_GROUP = "candidate_small_group"
BASIS_CONFLICT = "basis_conflict"
