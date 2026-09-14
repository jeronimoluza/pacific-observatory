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
    # Full-word sale units observed in the WFP VAM feed's `unit` column
    # (src/prices/fetchers/_shared/*/wfp_food_prices.py, 68 countries). The
    # pound family also covers wb_rtdi_hti's "6 lbs" and gy_moa's "lb".
    "pound": "lb",  # wfp_nic/wfp_bol/wfp_hti/wfp_gtm; as_aspa_utility_rates
    "pounds": "lb",  # "100 Pounds" (wfp_gtm/wfp_ecu/wb_rtdi_gtm), "36 Pounds"
    "lbs": "lb",  # "6 lbs" (wb_rtdi_hti), "20 lbs" (as_doc_cpi_avg_prices)
    # es-LatAm spelling: wfp_bol writes "Libra" and "Pound" on the SAME
    # country+item+date at the SAME price, which is what fixes it to the
    # avoirdupois pound rather than the 460 g colonial libra.
    "libra": "lb",
    "gallon": "gal",  # wfp_gtm/lbr/hti/col, wb_rtdi_lbr/hti, pr_daco_fuel
    "gal": "gal",  # as_aspa_utility_rates, as_doc_cpi_avg_prices, fews_lbr
    "imperial_gallon": "gal_imp",  # ky_ofreg_fuel spells the imperial one out
    "cubic meter": "m3",  # wfp_pse / pcbs_avg_prices_ps drinking water
    "m3": "m3",  # stp_emae / th_pwa / sr_swm water tariffs
}

# Deliberately NOT mapped, though they are frequent in the same columns:
#   * countable sale units ("Unit", "Head", "10 pcs", "Dozen", "Loaf") --
#     they are NOT a mass/volume declaration and must never reach
#     `amount_value`, because merge.compute_unit_value divides a count-basis
#     row by `count`, never by `amount_value`. A "Dozen" folded in here would
#     be priced per piece at the price of twelve. `parse_declared_count` below
#     reads them into the `count` slot instead, which is the denominator that
#     actually applies to them.
#   * non-goods sale units ("USD/LCU" is an FX rate, "Day"/"Month" are wages,
#     "Course" is a transport fare, "1 GB" is a data bundle, "LCU/3.5kg" is a
#     milling tariff). They already fall through the whitelist; they must keep
#     falling through.
#   * container units whose size is commodity-dependent ("Marmite", "Sack",
#     "Box", "Packet", "Heap", "Pile", "Cuartilla", "Godet", "Tin (20 L)").
#   * "1,000 gals" (as_aspa_utility_rates): "gals" is absent on purpose --
#     _NUM_UNIT_RE reads "1,000" as the decimal 1.0, so a plural surface here
#     would under-report the volume by 1000x.

_UNIT_WORD_CI: dict[str, str] = {k.lower(): v for k, v in UNIT_NORM.items()}
for _tok, _canon in _EXTRA_UNIT_WORDS.items():
    _UNIT_WORD_CI.setdefault(_tok.lower(), _canon)

# A leading approximation/tolerance marker ("~500 g", "+-450g") is stripped
# before parsing; it does not change which unit fires.
_LEADING_STRIP_RE = re.compile(r"^[\s+\-±~]+")
# "<number><optional separator><word>" anchored at the start. The word half is
# whatever non-digit/non-space run follows -- deliberately unconstrained, so
# a rejected token (a currency code, a bare "X" multiplier marker) still
# falls through the whitelist lookup below rather than being pattern-matched
# away in the regex itself.
#
# The separator admits `_` as well as whitespace: FEWS NET writes its sale
# units as "5_kg" / "750_ml", and with a space-only separator the word half
# came out as "_kg", missed the whitelist, and dropped the row to `item`
# basis -- which the build then quarantines as `review_missing_qty`. No key
# in any unit table contains an underscore, so nothing else changes meaning.
# A number is still not allowed to follow the separator, so an underscore
# used as a THOUSANDS mark ("1_000 kg") fails the match and falls through
# rather than being read as 1, the same way "1,000" is refused above.
_NUM_UNIT_RE = re.compile(r"^([0-9]+(?:[.,][0-9]+)?)[\s_]*([^\s0-9_][^\s0-9]*)")
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


# Countable sale units. The price is the price of N comparable pieces, so the
# denominator is `count` -- merge.compute_unit_value divides a count-basis row
# by `count * multiplier` and never looks at `amount_value`, which is why these
# must not go through `parse_declared_unit` above.
#
# Values are pieces per declared unit; a numeric prefix multiplies them, so
# "30 pcs" is 30 and "2 Dozen" is 24. Every key was read off a fetcher `unit`
# column in `products_input.parquet` (measured 2026-09-14) -- nothing is added
# on the strength of looking plausible.
#
# The membership test is "one declared unit is one COMPARABLE piece". That is
# what makes a per-piece unit value mean the same thing in two countries, and
# it is why these are still excluded:
#   * "Bunch", "Tray", "Bundle", "Parcel", "Packet", "Marmite", "Sack", "Box",
#     "Heap", "Pile" -- containers whose piece count is commodity-dependent and
#     nowhere in the string. Priced per container they are not comparable to
#     anything; priced as count=1 they would claim to be.
#   * "Pair" (455 obs, pbs_spi/wfp_prices) -- a pair of shoes is ONE sale unit,
#     not two priced pieces, so a count of 2 would halve it and a count of 1
#     would collide with the genuine singles. Ambiguous either way.
#   * "Bar" (127 obs, wfp_prices) -- soap, i.e. division 05, and the build
#     carries divisions 01 and 02 only. Nothing to gain against the ambiguity.
_COUNT_WORDS: dict[str, int] = {
    "each": 1,  # 726,112 obs -- prixnc, monitorul_preturilor, kam_mk
    "ea": 1,  # bahamas_wholesale, fews_net
    "unit": 1,  # 93,491 obs -- wfp_prices, wb_rtdi_prices
    "un": 1,  # 15,585 obs -- precios_claros (es "unidad")
    "item": 1,  # nomin, ulavale_jlent_as
    "piece": 1,
    "pieces": 1,
    "pc": 1,
    "pcs": 1,  # 52,784 obs -- wfp_prices "30 pcs", consumer_price_station
    "biji": 1,  # 87,523 obs -- pricecatcher (ms/id "piece")
    "batang": 1,  # 6,405 obs -- pricecatcher (ms/id "stick", e.g. one cob)
    "fruit": 1,  # 21,209 obs -- harti_daily_prices (lk, priced per fruit)
    "egg": 1,  # harti_daily_prices, afcd_wholesale, moc_agri_prices
    "eggs": 1,  # moet_price_monitor "30 eggs"
    "head": 1,  # wfp_prices -- one head of cattle/cabbage
    "loaf": 1,  # wfp_prices
    "dozen": 12,  # nsia_kabul_prices, pbs_spi, kz_socfood_avg_prices
    "шт": 1,  # rosstat_avg_prices ("10 шт.", "1000 шт.")
    "个": 1,  # 15,283 obs -- xinfadi_wholesale
    "יחידה": 1,  # 23,083 obs -- stop_market_il, super_yuda_il
    "יחידות": 1,  # 38,272 obs -- tiv_taam_il, rami_levy_il, yohananof_il
}

# A count multiplier must be a whole number, and "1,000" is exactly the shape
# `_NUM_UNIT_RE` reads as the decimal 1.0 (see the "1,000 gals" note above). A
# comma in the digits is therefore rejected outright rather than silently
# under-counting by 1000x; "1.00 יחידות", which the Israeli feed writes for a
# single item, is not affected.
_COUNT_NUM_RE = re.compile(r"^[0-9]+(?:\.[0-9]+)?$")


def _count_lookup(token: str) -> int | None:
    key = token.lower()
    n = _COUNT_WORDS.get(key)
    if n is not None:
        return n
    return _COUNT_WORDS.get(_TRAILING_PUNCT_RE.sub("", token).lower())


def parse_declared_count(raw) -> int | None:
    """Return the piece `count` a countable declared `unit` states, else None.

    The counterpart to `parse_declared_unit`: that one owns mass/volume and
    fills `amount_value`, this one owns countable sale units and fills `count`.
    They are disjoint by construction -- a token in `_COUNT_WORDS` is in none
    of the mass/volume tables -- so the caller tries the measured parser first
    and falls through to this one, and the order never changes an answer.
    """
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None

    stripped = _LEADING_STRIP_RE.sub("", text)
    if not stripped:
        return None

    m = _NUM_UNIT_RE.match(stripped)
    if m:
        per = _count_lookup(m.group(2))
        if per is None or not _COUNT_NUM_RE.match(m.group(1)):
            return None
        value = float(m.group(1))
        if value <= 0 or value != int(value):
            return None
        return int(value) * per

    return _count_lookup(stripped)
