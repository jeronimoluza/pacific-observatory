"""Apply the currency-aware normalize_price to template-repo.

This session is worktree-isolated and cannot write to template-repo, so the fix
ships as an applier rather than a diff. Idempotent: re-running after a
successful apply reports `already applied` and changes nothing.

    python infra/price-normalize/apply_patch.py [--check]

Four edits: the function itself, then the three call sites that have a currency
in hand but currently compute it *after* the price and so cannot pass it.
"""
import argparse
import os
import sys

REPO = "/Users/jeronimoluza/wb/pacificobservatory/repo/template-repo"
ARCHIVED = REPO + "/src/prices/price_scraping/archived.py"
EMBEDDED = REPO + "/src/prices/price_scraping/archived_embedded.py"

OLD_FN = '''def normalize_price(raw: Any) -> str | None:
    """Strip currency symbols and thousands separators.

    Resolves the EU (``1.234,56``) vs US (``1,234.56``) decimal convention by
    which separator appears last. A lone comma is a decimal point only when
    exactly two digits follow it — ``1,50`` is one-fifty, ``1,500`` is fifteen
    hundred.
    """
    if raw is None:
        return None
    s = re.sub(r"[^\\d.,\\-]", "", str(raw))
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
    try:
        return str(float(s))
    except ValueError:
        return None'''

NEW_FN = '''# ISO 4217 currencies with minor unit 0 — a fractional price is not expressible.
_ISO_ZERO_DECIMAL = {
    "BIF", "CLP", "DJF", "GNF", "ISK", "JPY", "KMF", "KRW", "PYG",
    "RWF", "UGX", "VND", "VUV", "XAF", "XOF", "XPF",
}

# Officially 2 minor digits, but retail prices are integer-only in practice and
# the written convention is dot-as-thousands. Kept separate from the ISO set so
# the distinction stays visible: these are judgement calls, the set above is not.
_DE_FACTO_INTEGER = {
    "COP", "IDR", "IRR", "KHR", "LAK", "MMK", "UZS", "HUF",
}

ZERO_DECIMAL_CURRENCIES = _ISO_ZERO_DECIMAL | _DE_FACTO_INTEGER


def _no_minor_unit(currency: str | None) -> bool:
    return bool(currency) and str(currency).strip().upper() in ZERO_DECIMAL_CURRENCIES


def normalize_price(raw: Any, currency: str | None = None) -> str | None:
    """Strip currency symbols and thousands separators.

    Resolves the EU (``1.234,56``) vs US (``1,234.56``) decimal convention by
    which separator appears last. A lone comma is a decimal point only when
    exactly two digits follow it — ``1,50`` is one-fifty, ``1,500`` is fifteen
    hundred.

    A lone dot is a decimal point unless the value cannot have one. Structured
    markup never needs this — schema.org asks for a machine-readable number, and
    across 8,744 archived pages JSON-LD and ``content=`` attributes produced
    zero 3-digit dot tails — but the microdata tier falls back to element text
    (``<span itemprop="price">78.000</span>``) and every CSS selector reads
    rendered text, where the grouping dot is normal. Only one shape is
    ambiguous, so only that one consults ``currency``:

        1.234.567   more than one dot   -> thousands, always
        1.5 / 1.50  tail is not 3       -> decimal, always
        78.000      tail is exactly 3   -> thousands iff no minor unit

    Passing no ``currency`` leaves the ambiguous case exactly as it shipped.
    """
    if raw is None:
        return None
    s = re.sub(r"[^\\d.,\\-]", "", str(raw))
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
            # a decimal point cannot repeat, so these are grouping separators
            s = s.replace(".", "")
        elif len(s.split(".")[-1]) == 3 and _no_minor_unit(currency):
            s = s.replace(".", "")
    try:
        return str(float(s))
    except ValueError:
        return None'''

# --- call site 1: rows_from_jsonld. currency is read ~10 lines below the price,
# so it is hoisted above the price rather than duplicated.
OLD_JSONLD = '''        for offer in _offer_list(node):
            price = normalize_price(_price_of(offer))
            if not price or float(price) <= 0:
                continue'''
NEW_JSONLD = '''        for offer in _offer_list(node):
            currency = _valid_currency(
                offer.get("priceCurrency") or node.get("priceCurrency")
            )
            price = normalize_price(_price_of(offer), currency)
            if not price or float(price) <= 0:
                continue'''

OLD_JSONLD_CUR = '''            currency = _valid_currency(
                offer.get("priceCurrency") or node.get("priceCurrency")
            )
            if currency:
                row["currency"] = currency'''
NEW_JSONLD_CUR = '''            if currency:
                row["currency"] = currency'''

# --- call site 2: row_from_meta
OLD_META = '''    meta = meta_tags(html_text)
    price = None
    for key in ("product:price:amount", "og:price:amount", "price"):
        candidate = normalize_price(meta.get(key))'''
NEW_META = '''    meta = meta_tags(html_text)
    currency = _valid_currency(
        meta.get("product:price:currency") or meta.get("og:price:currency")
    )
    price = None
    for key in ("product:price:amount", "og:price:amount", "price"):
        candidate = normalize_price(meta.get(key), currency)'''

OLD_META_CUR = '''    currency = _valid_currency(
        meta.get("product:price:currency") or meta.get("og:price:currency")
    )
'''

# --- call site 3: archived_embedded
OLD_EMB = '''        price = normalize_price(_find_price(obj))
        if not price or float(price) <= 0:
            continue
        row = {"product_name": name[:500], "price": price}
        pid = _find_id(obj)
        if pid:
            row["product_id"] = pid
        currency = _valid_currency(obj.get("currency") or obj.get("priceCurrency"))'''
NEW_EMB = '''        currency = _valid_currency(obj.get("currency") or obj.get("priceCurrency"))
        price = normalize_price(_find_price(obj), currency)
        if not price or float(price) <= 0:
            continue
        row = {"product_name": name[:500], "price": price}
        pid = _find_id(obj)
        if pid:
            row["product_id"] = pid'''


def patch(path, pairs, label):
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    if all(new in src for _o, new in pairs):
        print("  %-24s already applied" % label)
        return src, False
    out = src
    for old, new in pairs:
        if new in out and old not in out:
            continue
        if old not in out:
            print("  %-24s ANCHOR NOT FOUND — file has drifted, not patching"
                  % label)
            print("    missing: %s..." % old.splitlines()[0].strip()[:70])
            return src, None
        out = out.replace(old, new, 1)
    print("  %-24s patched" % label)
    return out, True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="report what would change, write nothing")
    args = ap.parse_args()

    for p in (ARCHIVED, EMBEDDED):
        if not os.path.exists(p):
            print("missing: %s" % p)
            return 1

    print("archived.py")
    a_src, a_ok = patch(ARCHIVED, [
        (OLD_FN, NEW_FN),
        (OLD_JSONLD, NEW_JSONLD),
        (OLD_JSONLD_CUR, NEW_JSONLD_CUR),
        (OLD_META, NEW_META),
        # the hoisted copy in row_from_meta leaves the original behind; drop it
        (OLD_META_CUR, ""),
    ], "normalize_price + sites")
    print("archived_embedded.py")
    e_src, e_ok = patch(EMBEDDED, [(OLD_EMB, NEW_EMB)], "flight-data call site")

    if a_ok is None or e_ok is None:
        return 2
    if args.check:
        print("\n--check: nothing written")
        return 0
    if a_ok:
        with open(ARCHIVED, "w", encoding="utf-8") as fh:
            fh.write(a_src)
    if e_ok:
        with open(EMBEDDED, "w", encoding="utf-8") as fh:
            fh.write(e_src)
    print("\ndone. verify with:")
    print("  python infra/price-normalize/test_pricenorm.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
