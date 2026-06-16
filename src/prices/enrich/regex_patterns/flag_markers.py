"""Per-language promotion and bundle marker regex strings.

Translated verbatim from `static/regex_units.yaml::promo_markers` and
`::bundle_markers`. These are bare regex strings used for boolean flag
detection — they have no named groups, no fixed_count, and don't fit the
PackPattern record. They live in a separate module so consumers can scan
them directly.

Each value is the tuple of regex strings for that language. Use
re.compile(..., re.IGNORECASE) at consumption time to match prior behavior.
"""

from __future__ import annotations

from typing import Mapping


PROMO_MARKERS: Mapping[str, tuple[str, ...]] = {
    "any": (
        r"\b\d+\s*%\s*off\b",
        r"\b\d+\s*%\s*OFF\b",
    ),
    "en": (
        r"\b(?:promo|promotion|sale|discount|clearance|markdown|special\s*offer|buy\s+\d+\s+get|on\s+sale)\b",
    ),
    "es": (r"\b(?:oferta|promoci[oó]n|descuento|rebaja|ahorr[oa])\b",),
    "pt": (r"\b(?:oferta|promo[cç][aã]o|desconto|saldo|liquida[cç][aã]o)\b",),
    "fr": (r"\b(?:solde|promotion|promo|remise|offre\s*sp[eé]ciale)\b",),
    "zh": (r"(?:特價|折扣|優惠|特惠|促銷|減價|特賣|降價|限時)",),
    "ja": (r"(?:セール|割引|お買い得|特売|お徳用|値引き)",),
    "ko": (r"(?:할인|세일|특가|특별가|기획전)",),
    "vi": (
        r"(?:giảm\s*giá|khuyến\s*m[ãa]i|ưu\s*đãi)",
        r"\bsale\b",
    ),
    "th": (r"(?:ลดราคา|โปรโมชั่น|ลดพิเศษ|ราคาพิเศษ)",),
    "id": (r"(?:diskon|promosi|jualan|harga\s*spesial)",),
    "ms": (r"(?:diskaun|promosi|jualan|harga\s*istimewa)",),
}


BUNDLE_MARKERS: Mapping[str, tuple[str, ...]] = {
    "any": (
        r"\b(?:gift\s*set|gift\s*pack|starter\s*kit|sample\s*kit|trial\s*kit)\b",
        r"\b(?:variety\s*pack|assorted\s*pack|assortment)\b",
    ),
    "en": (
        r"\b(?:back\s*to\s*school\s*(?:combo|pack)|holiday\s*set|essentials\s*set)\b",
    ),
    "zh": (r"(?:禮盒|禮品套裝|綜合裝|綜合組|福袋)",),
    "ja": (r"(?:ギフトセット|福袋|詰め合わせ)",),
    "ko": (r"(?:선물\s*세트|기획\s*세트)",),
    "es": (r"\b(?:set\s*de\s*regalo|kit\s*de\s*bienvenida)\b",),
    "pt": (r"\b(?:kit\s*presente|kit\s*de\s*boas-vindas)\b",),
}
