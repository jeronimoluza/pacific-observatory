"""Currency-code normalisation for prices rows.

Scraped price rows carry whatever the retailer printed, which is often a
symbol or a local abbreviation rather than an ISO 4217 code. This module is
the single place those get mapped.

Consolidated from two previously divergent sources:
  * ``cpi.analysis.core.forex.CURRENCY_TO_ISO`` (committed, EAP-era)
  * ``prices.build.fx._PRICES_CURRENCY_ALIASES`` (uncommitted in template-repo,
    added when the build widened past EAP)
"""

from __future__ import annotations

# Data currency code (as scraped) -> ISO 4217.
CURRENCY_TO_ISO: dict[str, str] = {
    # EAP-era map, from cpi.analysis.core.forex.
    "AUD": "AUD",
    "FJ": "FJD",
    "IDR": "IDR",
    "JPY": "JPY",
    "K": "PGK",  # kina, written as the bare symbol
    "KHR": "KHR",
    "KRW": "KRW",
    "NZD": "NZD",
    "PHP": "PHP",
    "T": "TOP",  # pa'anga, written as the bare symbol
    "USD": "USD",
    "VND": "VND",
    "VNT": "VUV",
    # Added once the build widened past EAP. Both targets are already in the
    # FX cache, so these are alias fixes, not a reason to refetch rates.
    "KM": "BAM",  # Bosnia-Herzegovina convertible mark, written as the symbol
    "CFPF": "XPF",  # CFP franc, written with the "F" suffix spelled out
}


def normalize_currency(code: str) -> str:
    """Map a scraped currency code to ISO 4217.

    Raises ``KeyError`` for codes not in the map, mirroring the historical
    ``cpi.analysis.core.forex.normalize_currency`` contract.
    """
    stripped = code.strip()
    if stripped in CURRENCY_TO_ISO:
        return CURRENCY_TO_ISO[stripped]
    upper = stripped.upper()
    if upper in CURRENCY_TO_ISO:
        return CURRENCY_TO_ISO[upper]
    raise KeyError(
        f"Unknown currency code: '{stripped}'. "
        f"Known codes: {sorted(CURRENCY_TO_ISO.keys())}"
    )


def normalize_currency_safe(code):
    """Normalise where known; otherwise upper-case and pass through.

    Non-strings and empty strings are returned untouched so a malformed row
    stays diagnosable rather than becoming a plausible-looking code.
    """
    if not isinstance(code, str):
        return code
    stripped = code.strip()
    if not stripped:
        return code
    try:
        return normalize_currency(stripped)
    except KeyError:
        return stripped.upper()
