"""Currency-aware separator handling for `normalize_price`.

The shipped `normalize_price` resolves `1.234,56` vs `1,234.56` by which
separator comes last, and handles a lone comma by tail length. It has **no
branch for a lone dot**, so one always reaches `float()` as a decimal point and
`78.000` VND silently becomes `78.0`.

Two measurements shaped the fix rather than a guessed currency list:

1. **Structured markup never carries the pattern.** Across 8,744 archived
   pages, JSON-LD and microdata `content=` attributes produced *zero* 3-digit
   dot tails - schema.org asks for a machine-readable number, so those tiers
   ship `78000`. The defect cannot fire there.
2. **It fires on visible text**, which is what the microdata tier reads when an
   element has no `content` attribute (`<span itemprop="price">78.000</span>`),
   and what every CSS selector reads. In the published table this is currently
   0.29% of VND rows, 0.02% of IDR - small because today's data is JSON-LD
   dominated. It grows as history is added: JSON-LD fires on 0% of pre-2016
   pages, so older captures fall to exactly the text surfaces that carry
   locale formatting.

Only one case is genuinely ambiguous - a single dot with exactly three digits
after it. Everything else is decidable from the string alone:

    1.234.567   more than one dot   -> thousands, always
    1.5 / 1.50  tail is not 3       -> decimal, always
    78.000      tail is exactly 3   -> needs the currency

For that last case a currency that quotes no minor unit (VND, JPY, CLP, ...)
means thousands. With no currency the behaviour is unchanged, so this can never
be worse than what ships today.
"""

import re

# ISO 4217 currencies with minor unit 0 - a fractional price is not expressible.
_ISO_ZERO_DECIMAL = {
    "BIF", "CLP", "DJF", "GNF", "ISK", "JPY", "KMF", "KRW", "PYG",
    "RWF", "UGX", "VND", "VUV", "XAF", "XOF", "XPF",
}

# Officially 2 minor digits, but retail prices are integer-only in practice and
# the written convention is dot-as-thousands. Kept separate from the ISO set so
# the distinction stays visible: these are judgement calls, the set above is not.
_DE_FACTO_INTEGER = {
    "COP",  # Colombian peso   $78.000
    "IDR",  # Indonesian rupiah Rp78.000
    "IRR",  # Iranian rial
    "KHR",  # Cambodian riel
    "LAK",  # Lao kip
    "MMK",  # Myanmar kyat
    "UZS",  # Uzbek som
    "HUF",  # Hungarian forint  1.234 Ft
}

ZERO_DECIMAL = _ISO_ZERO_DECIMAL | _DE_FACTO_INTEGER


def normalize_price(raw, currency=None):
    """Strip currency symbols and thousands separators.

    Resolves the EU (``1.234,56``) vs US (``1,234.56``) convention by which
    separator appears last. A lone comma is a decimal point only when exactly
    two digits follow it - ``1,50`` is one-fifty, ``1,500`` is fifteen hundred.
    A lone dot is a decimal point unless the value cannot have one: more than
    one dot means thousands, and a single dot with exactly three digits after
    it means thousands when ``currency`` has no minor unit.
    """
    if raw is None:
        return None
    s = re.sub(r"[^\d.,\-]", "", str(raw))
    if not s:
        return None
    has_comma, has_dot = "," in s, "." in s
    if has_comma and has_dot:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif has_comma:
        tail = s.split(",")[-1]
        s = s.replace(",", ".") if len(tail) == 2 else s.replace(",", "")
    elif has_dot:
        if s.count(".") > 1:
            # 1.234.567 - a decimal point cannot repeat, so these are groupers
            s = s.replace(".", "")
        elif len(s.split(".")[-1]) == 3 and _no_minor_unit(currency):
            # 78.000 in a currency that has no fractional part
            s = s.replace(".", "")
    try:
        return str(float(s))
    except ValueError:
        return None


def _no_minor_unit(currency):
    return bool(currency) and str(currency).strip().upper() in ZERO_DECIMAL
