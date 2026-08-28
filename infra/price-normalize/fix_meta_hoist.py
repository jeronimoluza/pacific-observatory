"""Repair the `currency` hoist that apply_patch.py deleted in row_from_meta.

`apply_patch.py` applies its edits in order. Edit 4 inserts a hoisted
`currency = _valid_currency(...)` above the price loop; edit 5 then deletes
"the original copy left behind below" by matching that exact text with
`str.replace(old, "", 1)`. `replace` takes the *first* occurrence, which after
edit 4 is the hoist itself -- so the assignment the loop needs is removed and
the stale copy below survives, leaving `row_from_meta` raising
`UnboundLocalError` on every page that reaches it.

It never showed up in `test_pricenorm.py` because that test exercises
`normalize_price` directly and never calls `row_from_meta`. It surfaced only
when the miss-corpus harness ran the whole ladder: 8,111 of 8,744 pages
errored.

This restores the intended shape -- currency read once, above the loop, used
by both the loop and the row.
"""
import argparse
import os
import sys

REPO = "/Users/jeronimoluza/wb/pacificobservatory/repo/template-repo"
ARCHIVED = REPO + "/src/prices/price_scraping/archived.py"

BROKEN = '''    meta = meta_tags(html_text)
    price = None
    for key in ("product:price:amount", "og:price:amount", "price"):
        candidate = normalize_price(meta.get(key), currency)
        if candidate and float(candidate) > 0:
            price = candidate
            break
    name = meta.get("og:title") or meta.get("twitter:title")
    if not (price and name):
        return None
    row = {
        "product_name": _html.unescape(name).strip()[:500],
        "price": price,
        "url": urljoin(url, meta.get("og:url") or url),
    }
    currency = _valid_currency(
        meta.get("product:price:currency") or meta.get("og:price:currency")
    )
    if currency:'''

FIXED = '''    meta = meta_tags(html_text)
    # Read above the loop: `normalize_price` needs it to tell a grouping dot
    # from a decimal point, and the row needs it below.
    currency = _valid_currency(
        meta.get("product:price:currency") or meta.get("og:price:currency")
    )
    price = None
    for key in ("product:price:amount", "og:price:amount", "price"):
        candidate = normalize_price(meta.get(key), currency)
        if candidate and float(candidate) > 0:
            price = candidate
            break
    name = meta.get("og:title") or meta.get("twitter:title")
    if not (price and name):
        return None
    row = {
        "product_name": _html.unescape(name).strip()[:500],
        "price": price,
        "url": urljoin(url, meta.get("og:url") or url),
    }
    if currency:'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(ARCHIVED):
        print("missing: %s" % ARCHIVED)
        return 1
    with open(ARCHIVED, encoding="utf-8") as fh:
        src = fh.read()

    if FIXED in src:
        print("  row_from_meta hoist    already applied")
        return 0
    if BROKEN not in src:
        print("  row_from_meta hoist    ANCHOR NOT FOUND -- file has drifted")
        return 2
    out = src.replace(BROKEN, FIXED, 1)
    print("  row_from_meta hoist    patched")
    if args.check:
        print("\n--check: nothing written")
        return 0
    with open(ARCHIVED, "w", encoding="utf-8") as fh:
        fh.write(out)
    print("\nwrote %s" % ARCHIVED)
    return 0


if __name__ == "__main__":
    sys.exit(main())
