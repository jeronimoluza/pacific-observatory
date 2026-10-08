"""Shared non-food piece patterns (every country and source).

Drafted 2026-10-06 from a scan of 205k non-food names (9 leaves, a8
`~/scratch/nonfood_cluster_20261005/rx/examples.txt`). Each regex is one
alternation over the languages seen there; names are NFKC-normalised first,
so fullwidth digits are ASCII by the time these run.
"""

from __future__ import annotations

import re

from prices.enrich.regex_patterns_nonfood import NFPattern

_F = re.IGNORECASE | re.UNICODE
_NUM = r"(?P<n>\d{1,4})(?!\d)"
# A pack number: not glued to a preceding Latin/Cyrillic letter, digit,
# decimal, code or size. A CJK character may precede it ("內褲5入").
_N = r"(?<![a-zà-ỹа-яё0-9.,/:#-])" + _NUM
# CJK counters also follow a hyphen ("餐椅原木色-4張").
_N_CJK = r"(?<![a-zà-ỹа-яё0-9.,/:#])" + _NUM
_PIECE_WORD = r"(?:pieces?|pcs?|piezas?|pzs?|pièces?|pezz[io]|peças?|tlg|teilig|предмет)"
# What may not follow a pack number read after a pack word: a measure, a
# size, a seat or drawer count, or a hyphenated word ("Kit 3-Stripes").
_NOT_MEASURE = (
    r"(?!\s*(?:[.,]\d|-\s*[^\W\d_]|mm\b|cm\b|m\b|kg\b|g\b|gr\b|l\b|ml\b|lt\b|gb\b|tb\b|mb\b|w\b|v\b|k\b|ram\b"
    r"|mah\b|inch|in\b|\"|”|%|cl\b|oz\b|lbs?\b|ft\b|pulg|plazas|seater|puestos|cuerpos|drawers?"
    r"|cajones|tiers?|niveles|levels?|años|years?|meses|months?|lit(?:re|er|ro)s?\b|lít"
    # "Set 5 PC", "Juego 4 piezas": the piece word decides (set or weak count).
    r"|" + _PIECE_WORD + r"))"
)
_PACK_WORD = (
    r"(?:pack|packs|set|box|lot|bundle|paquete|paquet|pacote|juego|lote|caja|kit|combo|bộ|набор"
    r"|комплект|упаковка|confezione|embalagem|paket|isi|lốc|zestaw|แพ็ค)"
)
# A Latin or Cyrillic word may not run on; CJK may ("2入組", "3枚セット").
_LAT_END = r"(?![a-zà-ỹа-яё])"


def _p(id_, role, rx, leaves=None):
    return NFPattern(id=id_, role=role, regex=re.compile(rx, _F), leaves=leaves)


SHARED: tuple[NFPattern, ...] = (
    # --- blank: spans that look like counts but are not the quantity sold ---
    _p("NF_N_IN_1", "blank", r"(?<!\d)\d+\s*-?\s*(?:in|en|em|в|σε)\s*-?\s*1(?!\d)"),
    _p("NF_MULTIBUY", "blank",
       r"\d+\s*件\s*\d+(?:\.\d+)?\s*折|第\s*\d+\s*件|\bbuy\s+\d+(?:\s*get\s*\d+(?:\s*free)?)?"
       r"|\b\d+\s*[x×]\s*1\b|\b\d+\s*por\s*\d+\b|\bll[eé]v[ae]\w*\s+\d+|\bmua\s+\d+\s+(?:tặng|giảm)"
       r"|\d+\s*(?:点|個|개|件|本|枚|セット)\s*以上|\d+\s*개\s*이상|\d+\s*セット\s*\d+\s*円|(?<![\d.])\d\s*\+\s*1(?![\d.])"),
    _p("NF_CAPACITY", "blank",
       r"\b(?:for|para|pour|на|до|up\s+to|holds?(?:\s+up\s+to)?|hasta|jusqu'?à|capacity(?:\s+of)?"
       r"|capacidad(?:\s+de|\s+para)?|fits?)\s+\d+\s*(?:pairs?|pares|paires|пар\w*|people|personas"
       r"|persons?|pax|bottles?|botellas|cups?|tazas)"),
    _p("NF_WARRANTY", "blank",
       r"\+\s*\d+\s*(?:years?|yrs?|mois|months?|años|meses|anos|năm|года?|лет)\s*(?:of\s+|de\s+)?"
       r"(?:warranty|guarantee|garant\w*|гарант\w*|bảo\s+hành|保修|保固)"),
    _p("NF_OPTION_LIST", "blank",
       r"\b\d+(?:\s*(?:[-/,]|\bи\b|\bor\b|\bo\b|\by\b|\bou\b)\s*\d+)+"
       r"(?=\s*(?:pcs?|pairs?|pares|paires|пар|шт|units?|unidades|pack|pk))"),
    _p("NF_FREE_SHIPPING", "blank",
       r"\b(?:env[ií]o|shipping|delivery|livraison|frete|despacho|entrega)\s+(?:\w+\s+)?"
       r"(?:gratis|gratuit\w*|free|grátis)\b|\bfree\s+(?:shipping|delivery)\b"
       r"|miễn\s+phí\s+vận\s+chuyển|送料無料"),
    _p("NF_PLUS_SPEC", "blank",
       r"\+\s*\d+(?:[.,]\d+)?\s*%|\b\d+\s*(?:gb|tb|mb)\s*\+\s*\d+\s*(?:gb|tb|mb)\b"),
    # "(Copper + Walnut)": a colour or material pair, not two products.
    _p("NF_PLUS_PAREN", "blank", r"\([^()\d]*\+[^()\d]*\)"),
    # --- bundle: different products under one price ---
    _p("NF_PLUS_JOIN", "bundle", r"\s\+(?:\s+|\s*\d)"),
    _p("NF_FREEBIE", "bundle",
       r"\b(?:\d+\s+)?[^\W\d_]+\s+(?:gratis|gratuit[es]?|offert[es]?)\b|\bde\s+regalo\b|\ben\s+cadeau\b"
       r"|\bwith\s+free\b|\bfree\s+gift\b|\btặng\s+(?:kèm\s+|thêm\s+)?\d|(?:赠|贈|送)\s*\d|증정|в\s+подарок"),
    # --- strong: a homogeneous pack, N is the divisor ---
    # "2 x 36pcs": two packs of 36; the divisor is a x n.
    _p("NF_A_X_N_PIECES", "strong",
       r"(?<![\w.,])(?P<a>\d{1,2})\s*[x×]\s*(?P<n>\d{1,4})\s*(?:pcs?|pzs?|piezas?|pieces?|units?|шт|pack)" + _LAT_END),
    _p("NF_N_PACK", "strong",
       _N + r"\s*-?\s*(?:er[- ]?)?(?:pack|packs|pk|pks|pak|pck)\b|(?<![\w.,/:#-])(?P<n2>\d{1,2})(?!\d)\s*-?\s*(?:er[- ]?)?set\b"),
    _p("NF_PACK_OF_N", "strong",
       r"\b" + _PACK_WORD + r"\b\s*(?:(?:of|de|da|di|из|com|x|×|:)\s*)?" + _NUM + _NOT_MEASURE),
    # "Drypantz Large 36s", "Mask 50s": a piece count on these leaves only;
    # elsewhere "Ns" is a model or a decade ("Run 70s").
    _p("NF_N_S", "strong", _N + r"\s*'?s\b", leaves=("13.2.9.1", "06.1.2")),
    # Weak: a stated count wins ("Twin Pack Large | 44s" is 44).
    _p("NF_WORD_PACK", "weak", r"\b(?P<n>twin|double|triple)\s*-?\s*packs?\b"),
    # Diapers: the size letter is glued to the count ("L48PCS", "S46 Sheets").
    _p("NF_SIZE_N_PIECES", "strong",
       r"(?<![a-z0-9])(?:x{0,3}l|nb|s|m)(?P<n>\d{1,3})\s*(?:pcs|pieces|'?s|sheets?)\b",
       leaves=("13.2.9.1",)),
    # "Plasters 40": a dressing's count at the end of the name.
    _p("NF_DRESSING_N_END", "strong",
       r"\b(?:plasters?|strips?|bandages?|dressings?|pads?)\s+(?P<n>\d{1,3})\s*$",
       leaves=("06.1.2",)),
    _p("NF_N_PAIRS", "strong",
       _N + r"\s*(?:pairs?|pares|paires|paia|пар(?:а|ы)?(?![а-яё])|đôi|双|雙|足|켤레|pasang|คู่)" + _LAT_END,
       leaves=("03",)),
    _p("NF_N_UNITS", "strong",
       _N + r"\s*(?:units?|unidades|unidad|unid\.?|unds?\.?|uds?\.?|unités?|stück|stk\.?|шт\.?|штук[аи]?"
       r"|cái|chiếc|sheets?|hojas|feuilles|листов|tờ)" + _LAT_END),
    _p("NF_N_CJK_UNITS", "strong",
       _N_CJK + r"\s*(?:入り?|個入り?|枚入り?|本入り?|[枚個本足]組|[個枚本足]セット|張|张|팩|입|켤레)"),
    _p("NF_X_N_PIECES", "strong",
       r"[x×]\s*(?P<n>\d{1,4})\s*(?:pcs?|pzs?|piezas?|pieces?|unid\w*|units?|uds?|шт)" + _LAT_END),
    # --- set: N counts a set's components; the set is one item ---
    _p("NF_N_PIECE_SET", "set", _N + r"\s*-?\s*(?:piece|pc|pieza|pièce|pezzo|peça)" + _LAT_END),
    _p("NF_N_PART_SET", "set",
       _N + r"\s*-?\s*(?:tlg\.?|teilig\w*|点(?:セット|組)|件套|件组|件組|món|предмет\w*)"),
    # --- weak: a piece count, a divisor only outside a set ---
    _p("NF_N_PIECES", "weak",
       _N + r"\s*-?\s*(?:pcs|pieces|piezas|pzs|pz|pièces|pezzi|peças|pçs|ชิ้น|buah|個|个|개|件|枚|本)" + _LAT_END),
    _p("NF_SET_NOUN", "setnoun",
       r"\b(?:set|sets|kit|juego|conjunto|ensemble|набор|комплект|batería|bateria|service|sala|living"
       r"|comedor|dining|bedroom|dormitorio|suite)\b|セット|套装|套組|套组|세트"),
)
