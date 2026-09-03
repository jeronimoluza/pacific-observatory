"""Parse a fetcher-declared `unit` string into structural quantity fields.

Some fetchers populate `price_observations.csv` with a `unit` column that
states the price's sale unit directly -- e.g. agmarknet's
`"quintal (100 kg)"` for a Rs/100kg mandi price. `extract.py`'s structural
regex reads only the product NAME, so a commodity name that carries no
quantity token (`Bread`, `Ajwan`) loses this signal entirely once `unit` is
discarded at ingestion (the historical bug this module fixes).

The `unit` column is dirty across fetchers -- currency codes (`SLE`, `SDG`,
`USD/LCU`), bare numbers (`5000.0`), and count/item markers (`each`, `Unit`,
`un`) all show up in it. `parse_declared_unit` is deliberately narrow: it
recognises only an explicit, human-reviewed set of mass/volume tokens (plus
`quintal`) and a `<number> <unit>` shape built on top of them. Anything else
returns `(None, None, None)` so the caller falls through to today's
behaviour instead of guessing.
"""

from __future__ import annotations

import re

from prices.enrich.regex_patterns.unit_tables import UNIT_MAP, UNIT_NORM

# Tokens `UNIT_NORM` doesn't carry -- literal, non-Latin, or full-word
# spellings observed in fetcher `unit` columns. Keyed exactly as they appear
# (case folded at lookup time); values are canonical `UNIT_MAP` keys.
_EXTRA_UNIT_WORDS: dict[str, str] = {
    "kilogram": "kg",
    "kilograms": "kg",
    "के.जी.": "kg",  # Nepali "kg" (kalimati_market)
    'ק"ג': "kg",  # Hebrew "kg" abbreviation
    "קילוגרם": "kg",  # Hebrew "kilogram"
    "גרם": "g",  # Hebrew "gram"
    "ליטר": "l",  # Hebrew "liter"
    "מיליליטר": "ml",  # Hebrew "milliliter"
    'מ"ל': "ml",  # Hebrew "ml" abbreviation
}

_UNIT_WORD_CI: dict[str, str] = {k.lower(): v for k, v in UNIT_NORM.items()}
for _tok, _canon in _EXTRA_UNIT_WORDS.items():
    _UNIT_WORD_CI.setdefault(_tok.lower(), _canon)

# A leading approximation/tolerance marker ("~500 g", "+-450g") is stripped
# before parsing; it does not change which unit fires.
_LEADING_STRIP_RE = re.compile(r"^[\s+\-±~]+")
# "<number><optional space><word>" anchored at the start. The word half is
# whatever non-digit/non-space run follows -- deliberately unconstrained, so
# a rejected token (a currency code, a bare "X" multiplier marker) still
# falls through the whitelist lookup below rather than being pattern-matched
# away in the regex itself.
_NUM_UNIT_RE = re.compile(r"^([0-9]+(?:[.,][0-9]+)?)\s*([^\s0-9]+)")
_TRAILING_PUNCT_RE = re.compile(r"[.,;:\"']+$")

_QUINTAL_RE = re.compile(r"^quintal\b", re.IGNORECASE)
_QUINTAL_KG = 100.0


def _lookup(token: str) -> str | None:
    # Exact match first: some literal tokens (के.जी.) carry punctuation as
    # part of the spelling itself, so it must not be stripped before this
    # lookup. Only a token that fails verbatim gets its trailing punctuation
    # trimmed and re-tried (e.g. "Kg." from "1 Kg. Granel").
    key = token.lower()
    canon = _UNIT_WORD_CI.get(key)
    if canon is not None:
        return canon
    return _UNIT_WORD_CI.get(_TRAILING_PUNCT_RE.sub("", token).lower())


def parse_declared_unit(raw) -> tuple[str | None, float | None, str | None]:
    """Return `(pricing_basis, amount_value, standard_unit)` for a declared
    `unit` string, or `(None, None, None)` when it isn't confidently a
    mass/volume declaration.

    `amount_value` is already in canonical units (kg/lt), matching what
    `extract.py` would have produced had the name itself carried the token.
    """
    if raw is None:
        return None, None, None
    text = str(raw).strip()
    if not text:
        return None, None, None

    if _QUINTAL_RE.match(text):
        return "mass", _QUINTAL_KG, "kg"

    stripped = _LEADING_STRIP_RE.sub("", text)
    if not stripped:
        return None, None, None

    m = _NUM_UNIT_RE.match(stripped)
    if m:
        canon = _lookup(m.group(2))
        if canon is None:
            return None, None, None
        emit = UNIT_MAP.get(canon)
        if emit is None:
            return None, None, None
        try:
            value = float(m.group(1).replace(",", "."))
        except ValueError:
            return None, None, None
        return emit.basis, value * emit.mul, emit.su

    canon = _lookup(stripped)
    if canon is None:
        return None, None, None
    emit = UNIT_MAP.get(canon)
    if emit is None:
        return None, None, None
    return emit.basis, emit.mul, emit.su
